# Windows 必须完成的适配

状态：依据2026-11-11源码列出，**不是已经在Windows实现/测试的清单**。保留ACP、原生委派、当前Plan/Code账本，不重造整套编排；不能因为文件扩展名是`.mjs`就宣称跨平台。

## P0：运行入口与配置

| 当前机制 | Windows差距 | 完成标准 |
| --- | --- | --- |
| `run-acp-agent.sh` | Bash、Mac dsh路径、`/usr/bin/python3`、`/usr/bin/ruby` | 新Windows入口；保留--version、profile、pool完整patch、title/fallback patch、bridge；stdout仅协议 |
| `run-agy-agent.sh` | Unix路径与信号 | 原生Windows agy acp入口，参数按安装版本help，停止只影响自己的进程树 |
| `acp-resume-bridge.py` | `.cmd`、stdio、进程组、编码 | UTF-8字节无BOM；恢复同一持久session，不用新会话重述冒充；EOF/取消无孤儿进程 |
| `setup.sh`与profiles | Bash、绝对路径、symlink、旧账号来源 | 幂等Windows生成器；六个omb-wf profile＋AGY；不靠旧Doc账号，不覆盖未知配置 |
| `provision-team.py`与roles | Mac路径／原Bot身份 | 生成Windows新ID与路由，原生Soul读回；不执行Mac旧Bot删除清单 |
| customAcp CLI字符串 | 空格、中文、`.cmd`解析 | 阅读安装版驱动，参数数组/包装器真实验证；不用shell拼接解决所有问题 |
| `bot-model.py` | runtime识别依赖入口形式 | 稳定实例映射，所有Bot可选择真实目录；任务/默认隔离，跨runtime保留Ask |

代码、配置、记录统一UTF-8。安装版内置bundles由DSH处理；node_modules和虚拟环境在Windows本机重建。Full只指产品审批，不提升到管理员或SYSTEM。

## P0：新额度与签到的具体平台依赖

| 文件 | 当前实现事实 | Windows工作 |
| --- | --- | --- |
| `workbuddy/client.mjs` | `execFileAsync('ruby',...)`读取desktop YAML；默认`~/.dsh/profiles/desktop`；只支持插件5.13.1 | 选择经过核对的Windows YAML解析方式或显式Ruby路径；参数化真实profile/包目录；保留安全字段白名单、账号/区域核对、版本保护 |
| `checkin.mjs` | 临时Python子进程用`fcntl.flock`、`O_NOFOLLOW`；命令名`python3` | 跨平台互斥与Python定位；并发、异常退出、状态损坏、跨日、未确认领取均实测；不能去掉锁后直接上定时任务 |
| `scripts/workbuddy-pool-sync.rb` | Ruby完整配置层，POSIX uid/chmod、`Process.kill(0)`、原子rename与进程归属清理 | Windows用户/进程身份与ACL检查、有界替换失败；保留每ACP进程独立overlay，不能覆盖desktop配置或删其他进程文件 |
| `model-fallback/budget-router.mjs` | 加载安装版公开Adapter/Store/Client；临时内部provider、原生池快照 | 安装模块解析、后台路径、凭据刷新、账号限定及实际provider回执；不将内部provider塞进菜单 |
| `budget-policy.mjs`/`plugin.mjs` | 免费有效期、原生池顺序＋跨区队首临期比较；13点新回合；用户手动选择保护 | 先离线时间/错误测试，再小额真实ACP；不能把未知额度当耗尽，不伪造免费或指定扣包 |
| 每日任务 | Mac Codex automation不会自动迁移 | Windows自建北京时间13:00签到→恢复检查；同用户、无并发重复；离线/睡眠补跑先查状态 |

国内只用桌面池获授权勾选账号，国际池关闭只用当前账号；不从本机所有凭据中扩大名单。Windows加密凭据按插件官方说明由本机WorkBuddy解析，不能搬Mac token或关闭加密。插件上游main比固定5.13.1新，升级需专门兼容验证。

## P0：状态、文件与恢复不能退化

`scripts/coordinator-workflow.py`、`workflow-check.py`、`workflow-observer.py`等有`fcntl`及POSIX文件行为；项目checker是复制品，要一起处理。可优先评估[Portalocker](https://portalocker.readthedocs.io/en/latest/)（BSD-3-Clause）或经测试的Windows标准库锁。不能删除锁、全skip并发测试或把`msvcrt`字节锁当作自动等价。

保留原子写与旧文件：Windows文件被编辑器/杀毒占用时有界重试并报错，不无限循环。`chmod(0600)`不等于Windows ACL，实际检查当前用户权限。`O_NOFOLLOW`不存在时处理symlink/junction/路径越界与竞争，不直接去掉保护；本项目仍非严格沙箱。

安全续跑约束：

1. claim先于派单，保存token、assignment ID、thread ID、准确sender/worker；不靠聊天摘要猜状态。
2. 不确定发送结果先对账；queued/running/审批都是活跃。旧回执取消但worker已直接续跑，也不能retry。
3. research/plan由Plan自身record，不伪造回执；共享handoff只由plan-lead维护。
4. 新queued补充逐条登记supplement，保留primary/token；主单＋全部补充完成、最新证据有效后才复审。
5. 补充失败/停止首版不能普通retry整单，明确阻塞并核查副作用；不能删除补充或清token绕过。
6. 失败恢复与业务返工分别有界，停止需对应停止之后的继续来源；不要重做其他成功角色。
7. 代码变化使旧审核、测试、体验快照失效；最终只能待用户验收。

## P1：技能、浏览器、UI与本地记录

| 范围 | 适配与验证 |
| --- | --- |
| 27个技能符号链接 | Git for Windows/ZIP可能变成普通文本或失效；枚举验证，合法链接或受控实际复制，保留源/许可证并回读SKILL；不要让Bot读取一行链接文字当完整技能 |
| 私有工作台runtime | `prepare-workbench.py`依赖服务文件/依赖/assets/skills的symlink并验证manifest；Windows合法链接/复制两种方案要同步校验实现，不改全局npm包 |
| `wf-shared/BROWSER.md`/CAPABILITIES | Mac `.tools/browser/bin/python`不可复制；Windows重建venv和浏览器，隔离context，真实截图读图/手机桌面交互 |
| observer | vault路径参数化；同步和后台安装分离；只注册项目，错误保留有效旧记录并提示 |
| export-agent-record | 只导可见消息，UTF-8可点文件链接；不导隐藏思考、凭据和原始敏感工具输出 |
| session-title/autogroup | Windows盘符、大小写、cwd与desktop模块；ACP排队、桌面唯一分类写入，冷会话刷新真实验证 |
| native_assignments | 只读核对安装版OMB schema与实际数据根；schema不符明确失败，不能直接写DB“修好” |
| templates | 当前新项目是`--workflow plan-code`；隐藏模板完整，旧manual/code-team不删除或冒充新流程；Bash辅助脚本按实际需求移植 |

UI保留模型、思考、新对话、停止、权限、记录和高级入口。Windows需实际截图核验；Mac已部署v4不等于Windows也加载到相同CSS/JS。

## 后台托管

优先[Windows Task Scheduler](https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-start-page)，不是给launchd改后缀。`scripts/omb-public.ps1 up|down|restart|status`是建议目标接口，**目前未实现**。

- 与登录WorkBuddy/DSH/AGY的同一Windows用户，首版登录时启动，不用SYSTEM；无人登录运行另验认证依赖。
- 固定本机可执行程序、cwd、数据根，不在后台临时npx下载新版本。
- 已运行不重复启动；核对端口、进程和数据归属。restart遇活跃Bot拒绝，down禁用当前自动拉起意图。
- 观察器单独一个循环，约20秒同步，不用一堆重叠任务；崩溃有界重启，有日志。
- 每日北京时间13:00换算到实际系统时区；插件按新回合判定，不依赖计划任务准点。
- 停止只限记录归属的进程树，不用`taskkill /IM node.exe /F`；重登/重启先对账再继续。

交付时分别列出已实现、已真实测试、阻塞与未测；Windows安装器、后台入口、七Bot、完整网页、签到和模型切换均需本机证据。公网访问、报告Agent和跨runtime无损迁移不属于首轮前置条件。
