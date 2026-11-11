# WorkBuddy 额度顺序、备用模型与提示

2026-11-11 更新：新团队六个 DSH 角色使用 WorkBuddy 免费及临期积分优先策略。每日恢复与签到时间改为**北京时间 13:00**，取代早期的 08:00。Antigravity 保持独立运行时。

## 调用顺序

1. **已核实免费的 WorkBuddy 通道**：先国际版，再国内版。必须读取账号当前模型目录，并按促销起止时间、时区和有效倍率核对；旧缓存的“0 折”或免费文字不是当前免费证明。
2. **临期积分**：没有可用免费通道后，优先使用未来三天内到期的有效积分。各区域先按插件账号池规则排列候选，再比较国际／国内队首候选的最早到期时间。
3. **其余 WorkBuddy 积分**：国内版优先，再国际版；同区域继续遵循账号池顺序。
4. **已有 DeepSeek API**：前面的已知通道遇到明确额度错误后，才使用用户已授权的 API 配置。价格、目录或余额读取失败属于信息不全，不能当成“额度用完”直接转付费 API。

国内仅包含桌面插件池里已勾选的两个账号，遵循可用状态、临期情况、用户手动排序等原生规则，不做固定 A/B 轮流。国际账号池关闭，仅使用用户选中的账号；没有显式选择时，读取插件原生当前账号，不自动纳入其他账号。

积分按**账号**选择，实际扣除该账号中的哪个积分包由 WorkBuddy 决定。发现账号有临期积分，不等于能指定扣除某个赠送包，也不等于本次调用免费。

## 对默认模型和任务的影响

大管家、Plan 评审、协作编码、通用助手默认使用 DeepSeek V4.1 Flash，支持在国际／国内等价 DeepSeek 通道间按上述成本顺序选择。Plan 负责人的 Kimi、独立审核的 GLM 正常情况下保留原模型，只有明确额度问题才进入 DeepSeek／GLM Flash 备用链；最终候选为已有 DeepSeek API。

用户明确手动选择的模型优先使用。备用机制不修改 Bot 默认设置，不重派用户任务，不重跑此前已完成的工具步骤；它在 DSH `agent/request-error` 与 `agent/request` 边界续接失败的模型请求。同模型换额度通道保留受支持的思考档位；换成其他模型时使用该模型实际支持的配置。

工作台通过【系统·模型状态】说明实际选择的区域、模型、账号短码及免费／临期／普通积分类别。“准备尝试”和“已实际返回”分别记录，顶部菜单仍代表用户选择，不能单凭菜单证明实际调用成功。账号专用内部 provider 不增加到日常模型菜单。

每日北京时间 **13:00 后的新回合**重新检查原模型与额度策略；跨越 13:00 的正在执行回合不被打断。免费促销到期会在下一次模型请求前重新核对，不中断已经开始的响应。用户手动设置模型或思考程度后，旧备用优先权清除，日常恢复不会覆盖新选择。

新成本策略由 `run-acp-agent.sh` 为六个 `wf-*` DSH 角色启用。历史 DSH 角色保留原固定备用链，不通过本轮变更扩张账号使用范围。插件没有写入或升级 DSH／WorkBuddy 安装包。

## 签到与每日检查

每日任务按北京时间 **13:00**执行国内已勾选账号签到，然后检查备用恢复状态。Mac 需在线且执行环境可用，不能承诺睡眠或离线时准点完成。恢复时间判断在本地插件内完成，不依赖定时任务恰好准时运行。

```sh
node integrations/openmausbot/workbuddy/checkin.mjs --daily-checkin
node integrations/openmausbot/model-fallback/status.mjs --daily-check
```

签到先读当天状态，未签才领取，再读回确认；已签显示 `already_verified`，本次领取并确认显示 `claimed_verified`。即使领取请求超时，也必须读回确认才能报成功。若先前领取是否成功仍不明确，保留 `unconfirmed`，后续只核对，不盲目重复领取。只处理国内个人账号，不领取企业、国际或其他活动奖励，不发模型请求。

查看签到本地记录：

```sh
node integrations/openmausbot/workbuddy/checkin.mjs --status
```

`--status` 不读取凭据、不联网；它显示当天本地记录，不能替代实时查询。签到日志位于 `~/.workflour/workbuddy/checkin-state.json`；余额和目录快照位于 `~/.dsh/workflour-billing/snapshot.json`，有效期五分钟；会话备用记录位于 `~/.dsh/workflour-fallback/`。这些记录不保存密钥、提示词或推理正文。`status.mjs --daily-check` 会写检查汇总，不切模型或重派任务。详见 [签到与读取接口说明](../workbuddy/README.md)。

## 错误提示与边界

- 迟迟未回复但请求仍开着：表示等待，不自动认定断线或额度耗尽。
- 连接、超时、服务故障：先走宿主有界重试；仍失败就保留任务并提示，不因此消耗付费 API。
- 限流或排队：不等于余额不足。账号故障切换只在允许范围内进行，不能借限流跳到 API。
- 明确额度错误：按已批准的候选顺序尝试，账号和模型共同去重，成功后显示实际通道。
- 目录／余额未知、路由加载失败、状态损坏：明确失败并保留现场，不把缓存名称当成实际成功。
- 用户停止、取消或等待审批：不自动恢复、换运行时或另派任务。
- 认证、内容拒绝、参数错误：不能靠更换提供商绕过。

Antigravity 不加载此 DSH 插件。Gemini 的额度或连接异常由原生委派返回，并向用户说明；本版没有 AGY → DSH 自动跨运行时备用。需要更换时使用新任务＋项目交接，保留旧会话及回执。

不同 Bot 的失败记录仍可能各自出现一次额度错误；不能承诺全局无重复失败。新目录当前尚未核实国际免费通道，旧促销缓存不能算作免费调用验收通过。

## 验证状态与来源

- `tests/test_budget_policy.mjs`、`tests/test_budget_router.mjs`：价格有效期、跨区排序、账号限定、内部通道与候选行为。
- `tests/test_model_fallback.mjs`：备用、停止、错误分类、手动选择与 13:00 回合边界。
- `tests/test_workbuddy_checkin.mjs`：24 项离线测试通过；包括账号隔离、身份核对、每日状态、超时、读回、去重、跨进程锁与目录保留选中模型。
- `tests/evidence/workbuddy-quota-20261111/checkin-live-repeat.json`：两个国内账号均读回 `already_verified`，重复运行没有再次领取。
- `tests/evidence/workbuddy-quota-20261111/live-catalog-and-credit-order.json`：真实目录与余额读取证据；它不是模型调用成功证据。
- **本轮真实 ACP 已验证**：两次最小请求均实际使用国际临期 DeepSeek 并返回 `BILLING-READY`、0 工具调用；第二次显式 Low 与实际来源/档位一致，内部 adapter 注册后仍不进入手动目录。[真实证据](../../../tests/evidence/workbuddy-quota-20261111/budget-acp-live.json)。未人为耗尽账号，本轮未触发付费 API；完整候选顺序用离线测试覆盖。
- 全套 Node 62 通过；Python 165 项（164 通过、1 跳过）。自动化 ACTIVE，每日 13:00，插件使用同一恢复时间；Bot 默认未变。

复用已安装的 [dsh-connect-workbuddy](https://github.com/dingminhua/dsh-connect-workbuddy) 5.13.1（MIT，Copyright © 2026 LaoDing）的 Store、Client、Catalog、Adapter 和 Shim；跨区域成本顺序是 Workflour 的组合策略。账号池内部排序参考其原生实现，未升级或修改插件安装包。

早期检索另看过 [dsh-llm-fallbacks](https://github.com/omdsh-dev/dsh-llm-fallbacks)、[dsh-model-rotator](https://github.com/chimneyQ/dsh-model-rotator) 与 [DSH 原生重试实现](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/llm/llm-retry/src/index.ts)；没有安装上述社区备用插件。早期 `tests/evidence/manager-naiwa-20261110/fallback-live.json` 使用合成 QUOTA 后实际调用已有 API，仅证明旧固定备用链，不能证明 WorkBuddy 当时真的用完或新成本排序已通过。
