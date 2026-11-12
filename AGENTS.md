# 项目协作说明

## 项目用途

本目录用于搭建多 Agent 协作写代码、推进项目的工作流。
这是用户与 AI 共同逐步构建的项目。

具体工具、模型、Agent 分工和工作流架构随实际构建确定。
不得把助手建议、设计草案或工作假设当成用户已确认的要求。

## 上下文位置

Obsidian 知识库根目录：
/Users/a1/Documents/Obsidian/多Agent协作开发工作流

以下笔记路径均相对于该知识库根目录。

### 从 GitHub / Windows 接手

若上述 Mac 知识库不存在，改读本仓库 `docs/CURRENT-STATUS.zh-CN.md`、
`docs/PROJECT-OUTLINE.zh-CN.md` 和 `docs/project-records/首页.md`。
`docs/project-records/` 是已整理的手写工作记录快照；新电脑要建立自己的知识库，
不要尝试创建 `/Users/a1/...` 或写回原 Mac 数据。先读
`docs/windows-deployment/00-从这里开始.md` 与 `08-Windows-Agent接手提示词.md`。
新电脑生成自己的 Bot ID、路径和账号状态，不复用历史真实部署标识。
本仓库的 Windows 说明是移植交接；Mac 实测成功不代表 Windows 已验证。

## 接手时如何恢复上下文

1. 阅读 `首页.md`，了解当前状态与会话交接。
2. 阅读 `01-需求/目标与待定事项.md`，区分已明确与待定内容。
3. 阅读 `记录约定.md`，了解记录方式。
4. 按首页链接阅读与当前任务相关的搭建日志、
   有效决策和设计文档，不必通读整个知识库。
5. 检查项目实际文件与记录是否一致。

恢复后简短说明：当前目标、已完成内容、待定事项、
准备接着做什么，再继续用户当前授权的任务。

历史日志用于解释过程，不能覆盖后续有效决定。
遇到记录与实际情况不一致时，先核实并说明差异。

若无法访问知识库，明确说明哪些上下文没有读到；
不要声称已经恢复上下文。

## 工作方式

- 实现新功能、工具或可复用流程前，先使用 search-first：
  检查本地已有内容，再检索现成方案，阅读候选的实际文档或实现。
- 普通记录更新和简单纠错无需重复完整检索。
- 优先利用已有记录，不让用户反复解释已经明确的内容。
- 尚未确定的事项随工作逐步讨论，不要求一次回答全部问题。
- 明确区分计划、已执行操作和验证结果。

## 当前团队与稳定入口（2026-11-11 起）

用户已确认的新任务流程为：大管家转交 → Plan 负责人调研与初案 → Plan
方案评审 → 负责人定稿 → Code 主编码实现 → 独立技术审核 → Plan 实际体验
检查 → 待用户验收。Plan 负责人是共享状态的唯一维护者；大管家只接单、转交
和汇报。一般小任务只启用一位主编码，协作编码仅用于明确的不重叠子任务。

| 角色 | 默认运行时与模型 | 思考程度 |
| --- | --- | --- |
| 大管家 | DSH / WorkBuddy DeepSeek V4.1 Flash | Low |
| Plan · 项目负责人 | DSH / WorkBuddy Kimi K3.1 Pro | High |
| Plan · 方案与体验评审 | DSH / WorkBuddy DeepSeek V4.1 Flash | High |
| Code · 主编码 | Antigravity / Gemini 3.8 Flash | High |
| Code · 独立审核 | DSH / WorkBuddy GLM-5.3-Flash | High |
| Code · 协作编码（按需） | DSH / WorkBuddy DeepSeek V4.1 Flash | High |
| 通用助手 | DSH / WorkBuddy DeepSeek V4.1 Flash | Low |

角色与模型仍然分离。真实 Bot ID 见
`integrations/openmausbot/team-v2/deployment.json`；声明配置见同目录
`roles.json`；职责和按需技能见 `agents/wf-*/`。DSH profile 为 `omb-wf-*`，
对应 `setup.sh --only wf-<角色>` 与 `run-acp-agent.sh wf-<角色>`。
上述默认分配不能覆盖用户后来手动选择的模型。

新六个 DSH profile 使用 `model-fallback` 额度策略：已核实免费线路优先，
然后比较国际/国内临期账号（区内遵循桌面 WorkBuddy 账号池规则），再其他
WorkBuddy 额度，最后才是已有 DeepSeek API。默认 DeepSeek 的首选路由仅在
同系列中调整；Kimi/GLM 先按角色设置请求，明确额度错误后才进入备用链。
当前目录、余额和促销必须实时核对，不能把历史免费标记当有效价格。
北京时间每日 **13:00** 为恢复边界，下一新回合生效，不打断正在执行的回合。
同一时间的 Codex 自动化 `bot` 执行已勾选国内账号签到和恢复状态检查；
签到必须读回确认，不重复领取、不扩大账号范围。说明见
`integrations/openmausbot/model-fallback/README.md` 与
`integrations/openmausbot/workbuddy/README.md`。
只改思考档位保留新档位并继续同系列省额度策略；真实手动换模型优先。
Antigravity 不自动跨运行时备用；工作台和桌面原默认配置不因额度路由改写。

新项目使用 `scripts/new-project.py ABSOLUTE_PATH --workflow plan-code`，
完整派单和证据约定见 `integrations/openmausbot/PLAN-CODE-WORKFLOW.md`。
方案讨论最多两轮，技术与体验返工共用最多两轮；代码变化后重新检查快照。
网页体验要有实际浏览器操作和截图，不能仅凭代码测试宣称体验通过。
浏览器与已验证能力见 `agents/wf-shared/BROWSER.md`、`CAPABILITIES.md`。
用户发任务和管理 Bot 不需要执行终端，说明见
`integrations/openmausbot/USER-GUIDE.zh-CN.md`。

工作台继续使用 OpenMausBot 0.1.143、同一服务和数据。精简页面通过项目内
独立前端副本加载，保留高级设置入口；不直接修改全局安装包。后台使用
`scripts/omb-public.sh`；生效版本由
`integrations/openmausbot/launchd/runtime.json` 指定，切换前必须核对空闲。
当前上线验收、旧 Bot 清理进度与未完成项目交接以 Obsidian 首页和
`integrations/openmausbot/team-v2/LEGACY-HANDOFF.md` 为准。

## 保留的兼容入口与基础机制（2026-11-06 起）

以下旧角色名称、模型分工及手动接力默认值是历史兼容说明，不能用于重建旧
工作台入口或替代上面的新团队流程；旧项目沿用其已有账本，续办时显式交接。

电脑端与手机端共用同一台 Mac 上的同一服务、同一数据目录。

| 用途 | 入口 |
| --- | --- |
| 日常公网后台启停与状态 | `./scripts/omb-public.sh up|down|restart|status`（macOS 用户级 launchd） |
| 公网手机邀请 | `./scripts/omb-public.sh pair` |
| 双 Agent 网页主入口 | OpenMausBot 0.1.143，本地 `http://127.0.0.1:8799` |
| 启动 / 停止本地服务 | `./run-omb.sh local`，Ctrl-C 停止 |
| 远程（内置 HTTPS，待登录后） | `./run-omb.sh remote` |
| 手机 client 邀请 | `./run-omb.sh pair '<本次实际 HTTPS origin>'` |
| ACP 协议入口 | `./run-acp-agent.sh coder` / `./run-acp-agent.sh doc` |
| Antigravity 协议入口 | `./run-agy-agent.sh` |
| 生成 profiles 与实例配置 | `./integrations/openmausbot/setup.sh`（幂等） |
| 生成独立 DeepSeek 编码配置 | `./integrations/openmausbot/setup.sh --only deepseek-coder` |
| Kimi/GLM 独立角色配置 | `./integrations/openmausbot/setup.sh --only kimi-planner` / `glm-planner` / `glm-reviewer` |
| Kimi/GLM ACP 入口 | `./run-acp-agent.sh kimi-planner` / `glm-planner` / `glm-reviewer` |
| 总控与通用助手配置 | `./integrations/openmausbot/setup.sh --only coordinator` / `assistant` |
| 总控与通用助手 ACP 入口 | `./run-acp-agent.sh coordinator` / `assistant` |
| 模型目录与安全切换 | `python3 scripts/bot-model.py list|refresh|switch`；默认仅当前任务，显式默认值修改带恢复记录 |
| DeepSeek 编码 ACP 入口 | `./run-acp-agent.sh deepseek-coder`（`omb-deepseek-coder`） |
| 不发 prompt 的握手验证 | `python3 tests/acp-smoke.py` |
| 两个 Bot 共享的验证项目 | `examples/omb-smoke/` |
| 初始化独立项目协作目录 | `python3 scripts/new-project.py <新目录或空目录>`；可选 `--git` |
| 新项目流程和持久交接 | 项目内 `PROJECT-WORKFLOW.md`、`.workflour/handoff.json`、`HANDOFF.md` |

两个 Agent 的模型与自动 skills 分开配置：Coder 用 `omb-coder`
（workbuddy / glm-5.3-flash，skill `code-assistant`），Doc 用 `omb-doc`
（workbuddy / deepseek-v4.1-flash，skill `doc-writer`）。
这是配置与角色分离，不是文件权限沙箱，两者共享工作目录。

另有独立 DeepSeek 编码角色 `omb-deepseek-coder`，模型为
workbuddy / deepseek-v4.1-flash，自动 skill 为 `code-collaboration`；原 Coder/Doc
保留。默认 setup 不重建这个可选角色，使用上表的 `--only deepseek-coder`。
群内咨询/审核优先复用原生 `coordinate_bots`，完成后自动回传；`post_to_room`
仅公告、不唤醒。每项任务一个实现负责人，审核和咨询不自动转移代码写入权。
操作和边界见 `integrations/openmausbot/DISCUSSION.md`。工作台新增DSH运行的
“项目总控”和“通用助手”，默认DeepSeek V4.1 Flash；当前Codex窗口用于维护和核验，
不是工作台内的Codex Bot。用户未授权由Bot代签最终验收。

Kimi 规划使用 `omb-kimi-planner` / `kimi-k3.1-pro`；GLM 规划和审核分别使用
`omb-glm-planner`、`omb-glm-reviewer`，初始默认均为 `glm-5.3`。这些与 DeepSeek
角色一样都是 DSH Agent：`dsh-connect-workbuddy` 只提供模型调用与额度通道，
不是独立 WorkBuddy Agent。Antigravity 保留独立 `agy` 运行时。规划与审核使用
独立 Bot/会话，角色指令约束不等于文件权限沙箱。默认 setup 范围仍为原 Coder/Doc/agy；
新增角色需明确 `--only` 生成，旧角色与历史保留。

角色与模型分开：全部已接入模型及其真实思考档位可按任务选择。DSH角色优先在
自身实例目录内换模型，保留profile技能；跨DSH/Antigravity使用安全切换工具新建任务，
附项目交接并保留旧会话。职责保存在Bot说明和项目材料中。原生顶部思考菜单会修改Bot默认，
不能把它当成仅改当前任务；总控设置入口使用安全工具区分当前任务/以后默认值。
使用说明见 `integrations/openmausbot/USER-GUIDE.zh-CN.md`，行为边界与恢复命令见
`integrations/openmausbot/MODEL-CONTROLS.md`。

总控的持久派单回执由 `scripts/coordinator-workflow.py` 管理；重复claim拒绝，
完成必须有回执和证据，修复复审最多两轮。新任务绑定总控会话，派单含唯一标记；
失败/停止后使用reconcile核对，retry保留旧尝试且最多一次，停止需明确继续来源。
已注册项目由workflow-observer只读同步到Obsidian自动记录区并显示异常，
不通过观察器派单/审批或修改共享任务状态。恢复和诊断见
`integrations/openmausbot/RECOVERY-AND-RECORDS.md`。回执一致性不能代替真实执行和用户验收。
DSH会话分类仅处理已确认属于本工作流的记录，使用原生工作区/标题/归档服务；
不改会话cwd、不直接改底层会话日志。ACP入口加载本地标题钩子，优先采用明确任务标题。

日常后台运行使用上表的 `omb-public.sh`；`run-omb.sh local` 保留作临时前台入口。
后台服务和 SSH 隧道由两个明确归属的 LaunchAgent 管理；主动 `down` 会取消登录启动，
`restart` 拒绝中断仍在运行的 Bot。安装、迁移和日志说明见
`integrations/openmausbot/launchd/README.md`。

Harness ACP 入口通过项目内薄适配将 OpenMausBot 的 `session/load` 请求转为
Harness 的 `session/resume`，恢复同一个持久 Agent；不修改产品安装包，不伪造
标准 ACP 历史重放能力。协议边界见 `integrations/openmausbot/ACP-RESUME.md`。
不同 Agent 之间仍须通过项目交接文件传递任务，不能依赖聊天自动共享。

新项目复用固定 Spec Kit 的中立脚手架，采用手动阶段接力；默认由 Coder 计划和实现、
Gemini 独立审查、Doc 写文档、协调者复核测试，最终由用户验收。这是可调整的实施默认，
不是永久角色承诺。代码变化后旧审查和验证快照失效。阶段检查器只核对材料一致性，
不能证明真实用户批准或测试覆盖完整。

旧的一次性 headless 入口 `run-agent.sh`、`setup-agents.sh` 与 `agent-coder`/`agent-doc`
profiles 保持原样，不要为了让新链路工作而改动它们。

细节与验证证据见 Obsidian：
`04-搭建/2026-11-06-实施OpenMausBot双Agent接入.md`、
`05-验证/2026-11-06-OpenMausBot双Agent本地阶段验证.md`。

## 产物与记录如何维护

- 代码、脚本、运行配置和测试放在本项目目录。
- 需求、调研、设计讨论、决策和搭建过程记录在 Obsidian。
- 记录关联实际文件、命令结果或提交，保留必要的验证证据。
- 有实质进展时更新相关笔记和首页的会话交接；
  重要结论和关键交接属于实质进展，零散讨论无需逐条记录。
- 交接写清：完成了什么、停在哪里、遗留问题、
  关键文件，以及下一项可执行操作。
- 当前进度和待办统一维护在 Obsidian，
  本文件只保存稳定的协作约定与入口。

## 小红书 Ubuntu 虚拟机入口

Windows 上带桌面的 Ubuntu 24.04 x86_64 接手小红书工作流，先读
`docs/xhs-ubuntu-handoff.zh-CN.md`；本场景不套用 Windows 原生部署步骤。
快速入口为 `scripts/xhs-ubuntu.sh`，先 install、目标机登录，再 configure/up/connect。
DSH 账号池默认从本机 web profile 读取，可显式指定
`WORKFLOUR_DSH_SOURCE_PROFILE`；Mac 原入口默认 desktop 不变。
用 start 子命令新建图文时，入口自动绑定真实工作台 threadId，不能用内部会话ID替代。
新机生成自己的 Bot ID、账号登录和内容目录；不复制Mac凭据或虚拟环境。
Linux CI 的安装、服务和渲染检查不代替目标虚拟机的账号/模型/配图验收。

## Ubuntu 完整开发团队入口

Ubuntu 24.04 x86_64 桌面虚拟机部署七个开发Bot，先读
`docs/ubuntu-deployment/00-从这里开始.md` 与 `01-给Ubuntu上的Agent.md`。
使用 `scripts/workflour-ubuntu.sh`：install → 本机登录 → configure → up → connect → doctor。
新机清单为 `~/.workflour/team-v2/deployment.json`，可用 `WORKFLOUR_TEAM_MANIFEST`
或 `provision-team.py --manifest` 指定；不复制Mac真实Bot ID。原Mac本机清单保留兼容。
账号源为本机DSH web profile，运行时、账号、聊天和计时器均留在新机。
知识库由 `WORKFLOUR_OBSIDIAN_VAULT` 指定，默认 `~/Documents/Obsidian/Workflour`。
角色文档中相对工具路径以部署说明中的仓库根解析，不能误用业务项目cwd。
后台使用systemd用户服务，自动记录20秒、国内已勾选账号签到/恢复检查北京时间13点；
Mac继续原launchd/Codex日程。安装与无账号Linux检查不证明订阅、读图或完整业务通过；
目标机按部署验收表实际核验。不要把Mac能力记录当成本机事实。
