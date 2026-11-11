# Workflour 项目大纲与 Windows 复现顺序

更新：2026-11-11。本文说明当前实现与下一台 Windows 电脑应复现的方法；不是 Windows 已部署声明。事实验收见 [CURRENT-STATUS.zh-CN.md](CURRENT-STATUS.zh-CN.md)。

## 目标与当前有效方案

用户在一个工作台交任务，团队负责建项目、调研、计划、编码、独立审核和实际使用检查；用户查看进度，最后亲自验收。日常使用不要求用户执行终端。模型、角色和任务会话分开：同一 Bot 可换模型，每个新项目使用独立任务会话，共享材料写在项目目录中。

当前流程是 **大管家 → Plan Team → Code Team → Plan 实际体验 → 用户验收**。早期的双 Bot、八 Bot、三方强制讨论和 Code Team 总控方案属于历史；新部署采用以下七角色。旧 Windows 指南中的 `code-team`、七个 DSH profile、八 Bot 和 08:00 应分别更新为 `plan-code`、六个 DSH profile、七 Bot 和北京时间 13:00。

| 角色 | 默认运行时 / 模型 | 思考 | 职责 |
| --- | --- | --- | --- |
| 大管家 | DSH / WorkBuddy DeepSeek V4.1 Flash | Low | 接单、转交、简短汇报；不重复做技术计划 |
| Plan · 项目负责人 | DSH / WorkBuddy Kimi K3.1 Pro | High | 调研、初案、定稿、派单、维护唯一共享状态 |
| Plan · 方案与体验评审 | DSH / WorkBuddy DeepSeek V4.1 Flash | High | 独立评计划，最后实际使用成品；两阶段使用独立记录 |
| Code · 主编码 | Antigravity / Gemini 3.8 Flash | High | 实现、自测、保存代码与测试证据 |
| Code · 独立审核 | DSH / WorkBuddy GLM-5.3-Flash | High | 独立读实际代码、复核测试、提出具体缺陷 |
| Code · 协作编码 | DSH / WorkBuddy DeepSeek V4.1 Flash | High | 按需接清楚、不重叠的子任务；小项目不强制启用 |
| 通用助手 | DSH / WorkBuddy DeepSeek V4.1 Flash | Low | 临时分析、自由讨论、协助调整大管家的模型 |

声明配置见 [roles.json](../integrations/openmausbot/team-v2/roles.json)，职责见 [agents](../agents/)。Mac 的 `team-v2/deployment.json` 是原机器的实时映射，已排除出仓库；Windows 必须在原生创建角色后建立自己的 Bot ID 映射，不能直接复用旧 ID。

## 系统分层与文件入口

| 层 | 当前实现 | Windows 应保留的含义 |
| --- | --- | --- |
| 工作台 | OpenMausBot 0.1.143，原生聊天、委派、任务和模型菜单 | 继续复用原生能力，不另造聊天或派单服务 |
| DSH 执行层 | 一个 Harness 版本、多个独立 `omb-wf-*` profile | profile 分离模型和技能；不是多个软件版本或文件权限沙箱 |
| 模型通道 | `dsh-connect-workbuddy` 5.13.1；既有 DeepSeek API 作最后备用 | WorkBuddy 提供模型与额度通道，不是额外工作 Agent |
| 独立编码运行时 | Antigravity 原生 ACP | 保留独立运行时，不以 Gemini CLI 代替 |
| ACP 兼容 | [ACP-RESUME.md](../integrations/openmausbot/ACP-RESUME.md)、[桥接实现](../integrations/openmausbot/acp-resume-bridge.py) | 把适配后的加载请求恢复到同一持久会话；不伪造历史重放 |
| 阶段与证据 | [PLAN-CODE-WORKFLOW.md](../integrations/openmausbot/PLAN-CODE-WORKFLOW.md)、[coordinator-workflow.py](../scripts/coordinator-workflow.py)、[workflow-check.py](../scripts/workflow-check.py) | 真实回执、唯一派单 token、当前代码快照、用户验收门 |
| 项目初始化 | [new-project.py](../scripts/new-project.py)、[模板](../templates/project/) | 新空目录使用 `--workflow plan-code`，拒绝静默覆盖已有项目 |
| 模型设置 | [MODEL-CONTROLS.md](../integrations/openmausbot/MODEL-CONTROLS.md)、[bot-model.py](../scripts/bot-model.py) | 当前任务与以后默认值明确区分；跨运行时新建会话并读交接 |
| 记录和恢复 | [RECOVERY-AND-RECORDS.md](../integrations/openmausbot/RECOVERY-AND-RECORDS.md)、[workflow-observer.py](../scripts/workflow-observer.py) | 观察器只同步已注册项目，不代派任务、审批或改阶段 |
| 额度与签到 | [备用策略](../integrations/openmausbot/model-fallback/README.md)、[WorkBuddy 接入](../integrations/openmausbot/workbuddy/README.md) | 免费/临期优先、明确错误分类、13:00 边界、幂等签到 |
| 精简界面 | [workbench](../integrations/openmausbot/workbench/README.md)、[prepare-workbench.py](../scripts/prepare-workbench.py) | 固定版本私有副本注入 CSS/JS；高级设置可恢复；不改全局产品包 |
| 后台 | [launchd 说明](../integrations/openmausbot/launchd/README.md) | Mac 实现作为语义依据；Windows 另做后台托管 |

## 一项任务怎样完成

1. 大管家收原始需求、项目目录和验收条件，交给 Plan 负责人。
2. Plan 负责人先查现成方案和必要资料，明确用户原话、约束、假设，写初案；Plan 评审给独立意见，负责人定稿。方案讨论最多两轮。
3. 通常只派一个主编码。确实需要协作编码时，先写清独立子任务和文件归属。网页可在可运行初版时做一次体验咨询，不能代替最终体验检查。
4. Code 主编码保存实现、自测命令与输出；独立审核者检查当前代码和测试。代码变了，旧审核快照就不能继续代表当前版本。
5. Plan 评审实际使用成品；网页必须有真实浏览器操作、桌面及手机视口截图、逐需求结果，不能只看代码说体验通过。技术与体验返工共用两轮预算。
6. Plan 负责人核对材料一致性并汇总交付；状态停在 `acceptance/pending`，等用户确认。检查器通过不是用户已经接受。

共享文件包括需求、计划、`.workflour/handoff.json`、`.workflour/coordination.json` 和 `HANDOFF.md`；各角色把自己的记录放到 `records/<角色>/`。只有 Plan 负责人更新共享状态。讨论通过原生委派与回传，群公告本身不会唤醒其他 Bot。

## 已有保护与当前缺口

失败、停止或超时后先对账，确认原生回执与副作用，不能直接再发同一任务。停止需要对应停止之后的明确继续来源；一次阶段/角色恢复最多重试一次。原生等待审批、排队、运行、需要输入均不能当作失败重派。

同一个工作会话的运行中补充可能形成串行第二回执。当前已支持显式 `supplement` 登记，必须等主单与所有补充完成才能复审；不能删除补充或重置轮数绕过。含补充的失败恢复尚不能套用普通 retry，需明确检查失败部分后处理。

当前已完成一次有维护介入的真实网页全流程。仍未证明无人值守稳定交付或优于单 Agent；Windows 尚未实测，任意已有仓库一键接管、严格文件沙箱、任意命令无损恢复、AGY 自动跨运行时备用和报告 Agent 都未纳入完成范围。

## Windows 的具体实施顺序

以下是接手 Agent 的工作顺序，不是让用户逐条开终端。旧 [Windows 部署资料](windows-deployment/00-从这里开始.md) 提供安装与适配细节；其中历史分工必须按本文替换。下载地址与安装参数是当时核对的记录，部署当天应再次查官方来源和本机 `--help`，不要假定 `latest` 永远对应固定版本。

| 步骤 | 要做的工作 | 完成证据与停止条件 |
| --- | --- | --- |
| 1. 固定目标与目录 | 记录 Windows 版本/架构，源码目录、Obsidian vault、数据目录和实际可执行路径；Windows 11 x64 为原指南目标 | 中文和空格路径可读写；不生成 Mac 绝对路径；不复制 Mac 凭据或运行数据库 |
| 2. 装基础工具 | 按 [软件安装指南](windows-deployment/02-软件下载与账号准备.md) 安装 Node、Python、Git、PowerShell、Obsidian | 每个工具记录实际版本与路径；Node 满足 OMB 的要求；UTF-8 正常 |
| 3. 先验证单个 DSH | 从官方源安装 Harness，选定 Desktop 管理的 CLI 或隔离 CLI，避免两个 `dsh` 互相覆盖 | `dsh --version`、实际命令路径与 Host/profile 对应；尚不创建全部角色 |
| 4. 装 WorkBuddy 插件 | 本机安装并由用户登录 WorkBuddy；在目标 DSH profile 安装 `dsh-connect-workbuddy@5.13.1`，完整重启 Host | 插件加载、实时模型目录、DeepSeek/GLM 最小调用分别验证；不把目录存在当作实际可用 |
| 5. 验证 Antigravity | 从官方源安装原生 CLI，由用户完成登录，核对实际 ACP flags | 能创建会话、读写测试目录、停止；不能用另一个 Gemini 工具冒充 |
| 6. 移植启动与 profile 生成 | 为 [DSH 入口](../run-acp-agent.sh)、[AGY 入口](../run-agy-agent.sh)、[setup.sh](../integrations/openmausbot/setup.sh) 提供 Windows 等价入口；生成六个 `omb-wf-*` DSH profile | `.cmd`/`.exe`、带空格参数、UTF-8、EOF、退出码和进程树都实测；ACP stdout 只有 JSON-RPC |
| 7. 修跨平台锁与文件语义 | 适配三个工作流脚本的 `fcntl`、`O_NOFOLLOW`、原子替换、junction/symlink 检查；同时处理 [checkin.mjs](../integrations/openmausbot/workbuddy/checkin.mjs) 内嵌 Python `fcntl` 锁 | 并发领取只有一个成功；进程死后释放；坏状态保留；不能删除锁代码或全量 skip 来宣称支持 |
| 8. 适配账号池与额度 | 适配 [workbuddy-pool-sync.rb](../scripts/workbuddy-pool-sync.rb) 的 Ruby/Mac 入口；保留私有进程内配置覆盖，读取目标机原生登录和勾选账号 | 源凭据文件不被覆写；手动模型优先；未知目录/余额不等于耗尽；内部路由不进模型菜单 |
| 9. 接入原生 OMB 与七角色 | 固定并核对 OMB 0.1.143；先前台完成登录与 ACP 实例验证，再按 roles.json 建新 Bot、原生路由与本机 ID 映射 | 七角色逐个执行实际文件/命令探针；模型与真实思考档位一致；权限不被跨运行时换模偷偷放大 |
| 10. 启用模板、记录与模型卡 | 初始化 `plan-code` 小项目；参数化 vault；接通只读观察器、DSH 原生标题/归组、任务级安全模型卡 | 新会话命名正确，其他项目不动；当前任务和默认值互不混淆；完整隐藏模板被复制 |
| 11. 启用精简 UI 和后台 | Windows 核对上游 hash 与私有 runtime 路径；无 symlink 权限时采用经校验的复制方案。用同一登录用户的 Task Scheduler 实现托管，不能照抄 launchd | 原生登录不受影响；高级可恢复；busy 时拒绝重启；down 后不被拉起；不能误杀其他 Node/DSH 进程 |
| 12. 验证每日 13:00 | 使用 Asia/Shanghai 语义配置签到与恢复；签到先查询、已领取跳过、并发锁生效；插件下一回合才恢复 | 边界测试与状态读回通过；再等待真实定时触发留证。未观察到自然触发时明确未验证 |
| 13. 跑完整新项目 | 从工作台给大管家一项小功能，走完 Plan/Code/体验；受控验证停止后继续、失败提示、重启对账 | 有真实独立审核、命令输出与截图；无重复专业派单；最终 pending，用户验收后才 done |

Windows 首轮优先把本机单 Agent、七角色原生协作和恢复验证做扎实。公网手机入口属于后续独立步骤：重新配置目标机网络和认证，不能复制 Mac 的 SSH 私钥、公网地址或配对状态。

## 仓库应保存什么

保存代码、模板、角色职责、技能来源和许可证、人工搭建/调研/决策/验证摘要、经过审核的截图与证据摘要。私有 GitHub 也不应包含 API key、token、账号登录库、浏览器 profile、OpenMausBot 原始数据库、完整自动聊天或未筛选附件。

原 Mac 的旧聊天导出是本地恢复材料，不是 Windows 初始化输入。Windows 学习的是约束、实现和验证方法；不要把旧 Bot ID、已完成任务或旧验收状态自动导入新机器。
