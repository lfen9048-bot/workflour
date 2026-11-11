# WorkBuddy 读取桥接与每日签到

此目录复用本机已安装的 `dsh-connect-workbuddy` **5.13.1**，为额度路由提供模型目录及积分数据，并为国内个人账号执行每日签到。不会升级插件、修改账号选择、请求模型或领取其他活动奖励。

上游：[dingminhua/dsh-connect-workbuddy](https://github.com/dingminhua/dsh-connect-workbuddy)，MIT，Copyright © 2026 LaoDing。代码直接调用安装包已有接口，没有复制凭据解析或计费请求实现；版本变化时会明确拒绝加载，需重新核对兼容性。

## 每天怎样运行

当前日程为**北京时间 13:00**：先签到，再检查备用模型恢复状态。脚本没有常驻后台进程，日程由现有 Codex 自动化触发。Mac 睡眠、离线或执行环境不可用时不能保证准点运行。

```sh
# 实际签到：只处理桌面插件已勾选的国内账号
node integrations/openmausbot/workbuddy/checkin.mjs --daily-checkin

# 只看今天的本地签到记录，不联网、不读凭据
node integrations/openmausbot/workbuddy/checkin.mjs --status
```

日常使用不要求用户执行终端命令；上述命令供维护和诊断。定时恢复在本地备用插件中按 13:00 的新回合生效，不打断正在执行的任务。

| 状态 | 含义 |
| --- | --- |
| `already_verified` | 上游读回显示今天已经签到，本次没有再领取 |
| `claimed_verified` | 本次尝试领取后，上游再次读回确认今天已签到 |
| `unconfirmed` | 可能已经发出领取，但读回尚未确认；不报成功、不盲目重复领取 |
| `failed` | 凭据、活动状态或查询等失败，查看对应错误码 |
| `unsupported` | 企业账号等不支持的对象，没有执行领取 |

每次运行逐账号读取上游状态，不单凭本地“今天已完成”缓存跳过核对。活动已结束但 `todayCheckedIn=true` 时仍正确记为已签。领取超时后若读回成功，可以确认完成；若仍不明，后续执行只查询，保留不确定状态。一个账号失败不阻止另一个账号独立检查。

日志位于 `~/.workflour/workbuddy/checkin-state.json`，以北京时间日期和账号哈希分开记录，权限为 `0600`。跨进程锁防止重复执行；异常退出后内核释放锁，不靠删除过期锁文件抢占。状态文件损坏时停止并保留原文件，不自动清空。记录不包含账号邮箱、密钥、提示词或推理正文。

2026-11-11 实测重复运行：两个国内账号均为 `already_verified`，本次未重复领取。证据：[签到读回](../../../tests/evidence/workbuddy-quota-20261111/checkin-live-repeat.json)。本记录不代表未来每天都已签到。

## 账号范围与读取接口

`client.mjs` 读取可信桌面配置 `~/.dsh/profiles/desktop/cordis.patch.yml` 中的非秘密字段：地区是否启用、选中账号、账号池勾选及排序、各地区已勾选模型。国内限定两个已勾选账号；国际池关闭，仅取用户选中／插件当前的一个账号。不会把其他已登录但未勾选的国内账号加入范围。

每次使用账号前，通过原生 `WorkBuddyCredentialStore.selectAccount()` 和 `resolve()` 处理所需刷新，并核对返回的账号标识及区域。刷新可能更新插件自有凭据副本，不修改桌面登录文件。凭据留在闭包内，不由桥接输出或写入本项目日志。

导出接口：

- `loadPreferences()`：地区、池顺序、已选账号和 `enabledModelIds` 等安全配置。
- `loadPlugin()`：版本保护后的 Store／Client／身份与区域解析器，以及安装包路径。桥接只导入官方 CLI 使用的独立模块，不导入 DSH 宿主入口。
- `createBridge()`：提供 `getPreferences()`、`listAccounts()`、`resolveCredential()` 的安全摘要，以及 `fetchModels()`、`fetchCredits()`、`fetchCheckinStatus()`、`claimDailyCheckin()`。
- `createBridge({includeGlobal:false})`：签到使用，不读取国际账号凭据。

`fetchModels(region, accountId)` 将该区域已勾选模型作为原生 `keepModelIds` 传入：模型即使不在官方 CLI 子目录中，只要上游配置仍提供，就可以保留；不会根据旧缓存拼出已下架模型。返回原始公开促销时段及价格字段，由额度策略检查是否当前有效。

`fetchCredits()` 保留计费包的 `remain`、`monthly`、`refreshAtMs`、`expiresAtMs`，汇总有效余额、未来三天内到期积分及最早到期时间。月度刷新时间不当作一次性积分的失效时间，过期包不纳入可用余额。摘要不能证明某包免费，也不能指定上游实际扣哪个包。

成本路由顺序为：**已核实免费 → 国际／国内临期账号比较最早到期 → 其余 WorkBuddy 积分 → 既有 DeepSeek API**。区内继续尊重插件池规则；详见 [额度策略](../model-fallback/README.md)。当前实时目录未返回国际免费 DeepSeek，旧 0 折缓存不能算当前免费。真实 ACP 已验证国际临期 DeepSeek 调用正常，Low 档位读回一致、0 工具调用；详见 [实际调用](../../../tests/evidence/workbuddy-quota-20261111/budget-acp-live.json)。

## 验证

```sh
node --test tests/test_workbuddy_checkin.mjs
```

24 项离线测试通过，覆盖身份和区域隔离、未勾选账号拒绝、纯独立模块加载、选中模型保留、签到读回、超时不误报、跨日、状态损坏及跨进程互斥。安装版 5.13.1 的独立模块加载及安全配置读取已核验；模型实际回复仍需独立 ACP 证据。
