# {{PROJECT_NAME}}：项目协作流程

这套流程沿用 GitHub Spec Kit 1.3.2 的中立模板和官方 Bash helpers，补充 manual 手动接力及 code-team 工作台总控、独立审查、真实测试证据和最终用户验收。初始化命令只创建文件；实际派单由工作台总控在接到任务后进行。初始化不会切换既有模型或 skills。

## 从这里开始

在项目根目录执行所有命令。没有 Git 也能用；初始化时加 `--git` 才会创建本地仓库，不会提交或推送。

```bash
# 先创建一个 feature；说明换成实际需求，不要直接使用示例需求
bash .specify/scripts/bash/create-new-feature.sh --json --short-name your-feature '实际需求说明'
```

官方脚本会生成 `specs/NNN-your-feature/spec.md`，并将当前 feature 位置存入 `.specify/feature.json`。之后每个 Agent 都能找到同一 feature，不依赖上一轮终端的环境变量。

初始化后的 `.workflour/handoff.json` 是未分配任务的起点。填写真实 `task_id`、`requirements`、各项 `artifacts` 路径和 `next_action`。JSON 中的路径相对项目根目录，所有材料保存在项目内，不写账号或凭据。

## 七个阶段

### 可选 code-team 流程

初始化加 `--workflow code-team` 启用本流程，默认 manual 兼容原流程。
当前模式以 `.workflour/handoff.json` 的 `workflow.kind` 为准。

- 工作台 DSH「Code Team · 总控」协调（默认 DeepSeek V4.1 Flash，角色不绑定模型）；Kimi 主持，DeepSeek 与 GLM Planner 参与规划。
- 新账本采用两轮：三位各自短提案 → 三位各读另外两份并独立交叉回应 → 方案主持定稿。不是“三份提案直接拼接”。
- `discussion_version:1` 的账本新增 discussion 阶段，三份回应 JSON 与原生回执齐全且提案哈希一致才可进入 plan。旧运行账本不自动迁移。协议见 `{{TOOLKIT_ROOT}}/integrations/openmausbot/PLANNING-DISCUSSION.md`。
- 小任务建议每提案≤500字、每交叉回应≤400字、PLAN≤120行、tasks≤40行；必要超出需说明原因。
- 原话、明确约束、团队假设、待确认项分列；不能把团队选定的技术方案写成用户硬性要求。
- `planning.participants` 固定本任务三个角色；`contributions` 为三项
  `{"owner":"Kimi","record":"records/kimi/plan.md"}`，路径必须分别指向真实非空记录。
  形成一致计划后设 `status:"settled"`，实际讨论轮数写 `discussion_rounds`。
- Code Team · 总控核对原需求及阻塞后自动派发，不对范围内每一步额外请求用户确认。
- Antigravity 主编码和整合；DeepSeek 并行负责独立模块。`work_items` 每项包含
  `id`、`owner`、`files`（精确项目相对文件路径）及 `status`（pending/running/completed）。
  文件归属不得重复，实现阶段起 `files` 合集须与 `code_files` 双向完全覆盖。
  这里只列实现/测试/依赖文件，日志和讨论不列入；共享文件串行交接并由协调者更新归属。
- GLM Reviewer 用独立 Bot/会话审核，不能是任何一个编码负责人；先读取需求、最终计划、代码和测试。
  按需调阅规划记录并注明来源，不能把同模型的新会话称为完全无偏或权限隔离。
- 同一阶段只有协调者更新 handoff.json；各 Agent 写自己的 `records/<role>/` 工作记录。
  工作记录相互可按需读取，不能写入凭据或未脱敏 native trace。Obsidian 入口链接项目资料和记录。
- `workflow.docs_required:false` 表示报告暂缓，verify 后直接进入 acceptance，不生成虚假 docs 材料。
  用户验收门保持不变；独立测试、代码快照、审核失效规则仍全部适用。
- 普通修复最多两轮复审；仍阻塞则交给用户。此上限由Code Team · 总控与持久派单账本共同约束，检查器不自动调度或强制中断。

以下七阶段表是 manual 的默认角色；code-team 按本节覆盖角色与 docs 阶段。

本轮默认角色安排如下，可按实际项目调整。共享目录按顺序交接，一次只有一个实现写入者。

| 阶段 | 默认负责人 | 输入与实际动作 | 结束材料与下一步 |
| --- | --- | --- | --- |
| `requirements` 需求和验收定义 | 协调者与用户 | 将目标、范围、不做什么、需求编号和验收条件写入官方 `spec.md`；首次使用补足 `.specify/memory/constitution.md` | 需求可验证，建议和假设有标记；交给 Coder |
| `plan` 方案和任务 | Coder | 运行官方 `setup-plan.sh`、`setup-tasks.sh`，填写技术取舍、任务顺序、改动文件和需求对应关系 | `plan.md`、`tasks.md`；不把占位模板当成计划完成 |
| `implement` 实现 | Coder | 只处理本轮任务；更新实现、测试和必要依赖；记录实际改动与未完成项 | 完整 `code_files` 和交接；交给 Gemini |
| `review` 独立审查 | Gemini | 只读实现，核对需求、实际改动和边界；写 `review.md`；不代替 Coder 悄悄修代码 | 问题清单与当前代码快照；有问题退回实现，解决后重新审查 |
| `verify` 测试和返工 | Coder 执行，协调者核对 | 用 `check.py test` 执行当前实现的有效测试；写 `verification.md` | 真实命令、输出和退出码；失败退回实现，成功交给 Doc |
| `docs` 文档 | Doc | 读取需求、实现、审查及验证材料；写配套说明，核对命令与示例 | `documentation.md` 验证说明和实际文档；交给协调者 |
| `acceptance` 验收 | 协调者准备，用户决定 | 逐条将需求映射到代码、测试和文档证据，写 `acceptance.md` | 待用户验收；记录明确用户确认后才进入 `done` |

每阶段可复制 `.workflour/prompts/` 中对应提示到 OpenMausBot 的目标 Agent，先替换任务编号和文件路径，再发送。协调者负责实际选择会话、检查结果和推进；打开提示词文件本身不会执行工作。

官方 helpers 的常用命令：

```bash
bash .specify/scripts/bash/setup-plan.sh --json
bash .specify/scripts/bash/setup-tasks.sh --json
bash .specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks
```

这些检查用于确定 feature 和材料位置，不会证明需求语义、代码质量或验收结果。中立脚手架保留上游 `speckit/workflow.yml` 作为原始产物，本项目的 `none` 集成不能 dispatch Agent prompt；manual 按上表手动执行；code-team 使用工作台原生委派，不运行另一条 headless 自动流程。

## 持久交接与阶段检查

`.workflour/handoff.json` 是机器可检查的当前任务记录；`HANDOFF.md` 是由它生成的人可读交接。原始 `review.md`、`verification.md`、文档和验收材料路径放在 `artifacts` 中。

```bash
# 核对当前阶段；也可检查准备进入的阶段
python3 .workflour/check.py check
python3 .workflour/check.py check --stage review

# 打印 code_files 的真实哈希；独立审查者核对后记录 review.snapshot
python3 .workflour/check.py snapshot

# 真实运行测试，并记录命令、退出码、输出证据和实现快照
# 此例假设项目使用 tests/ 目录；请替换为 plan.md 约定的实际测试命令
python3 .workflour/check.py test -- python3 -m unittest discover -s tests -v

# JSON 更新后重新生成交接摘要
python3 .workflour/check.py handoff
```

`stage` 是当前正在执行的阶段。开工前检查上一已完成阶段，完成后检查本阶段；例如 Gemini 开始审查时检查 `--stage implement`，审查完成后才检查 `--stage review`。尚未生成的本阶段产物或 pending 状态不是开工阻塞。

`check` 只读检查；`snapshot` 打印当前值；`test` 会执行明确命令并记录结果；`handoff` 更新生成文件。命令默认以 `.workflour/check.py` 所在项目为根，也支持 `--project PATH`。

### 填写交接的规则

- `task_id` 对应本轮 feature，`stage`、`owner`、`next_owner`、`next_action` 说清停止位置和接力对象。
- `requirements` 的每项有 `id` 和 `criterion`；`artifacts` 填真实材料路径，不能只写“见上次聊天”。
- `changed_files` 记录本轮全部改动；`code_files` 包含真实实现、测试和依赖配置，不能漏掉关键文件，也不放交接、日志和纯文档。
- `baseline` 在实现前采集，保留改动前的真实哈希；新增文件的基线为 `null`。`review.snapshot` 和 `verification.snapshot` 分别记录审查、验证时的当前快照。删除文件仍保留在 `code_files`，基线保留删除前哈希，当前快照为 `null`；不要移除条目或手填预期哈希绕过检查。
- `implementation_owner` 记录实际实现者，`review.reviewer` 必须是其他独立审查者。独立审查通过时写 `review.status: "passed"` 并记录完整当前快照。每个问题有 `id`、`severity`、`status`、`resolution`；验收时应是 `verified` 或有明确理由的 `waived`。
- `test` 为每次运行保留证据和快照；当前快照相同命令的最新结果用于判断，历史失败不抹除。代码变化后旧审查和验证失效，先重新审查，再重跑当前有效测试。
- Doc 的纯文档改动不应使代码快照失效；如果文档暴露了代码问题，退回实现后照常重审和重测。
- `acceptance.status` 初始是 `pending`。用户确认来源、原话、时间和接受时的代码快照放在 `acceptance.source`、`quote`、`at`、`snapshot`；接受后代码变化会使 done 检查失败。检查器不证明这段记录真的得到用户授权。

## 返工与重启

审查或测试发现可立即修复的问题时，将当前阶段退回 `implement`，在 `review.findings` 和 `next_action` 记录具体问题。`blockers` 只记录让当前工作无法继续的外部依赖、缺失信息或待决定事项，不用它阻止已授权的返工。修复后更新文件范围、重新审查、重新测试，不沿用旧快照。新增需求先回到 `requirements` 更新验收条件，不把临时建议直接当成用户决定。

重启、切换模型或新会话接手时，先读取 `AGENTS.md`、`handoff.json`、`HANDOFF.md` 和当前材料，核对文件快照，再继续 `next_action`。原生会话能恢复也必须核对磁盘；恢复失败时，文件仍能提供事实和下一步。若任务被中断，检查已落盘的副作用，不盲目重跑已完成命令。

## 当前状态

新项目只有模板和检查工具，尚未执行七个阶段。阶段材料模板位于 `.workflour/templates/`，默认分工可以调整。没有自动部署、发布、推送或自动用户验收。

## code-team 的派单、恢复与自动记录

工作流工具包位于 `{{TOOLKIT_ROOT}}`。本节的 `scripts/` 指工具包中的目录，
不是新项目内的目录；`.workflour/check.py` 则是本项目的本地检查器。

日常向 OpenMausBot 的「大管家」交任务，由它转交「Code Team · 总控」；也可直接找团队总控。大管家不直接派5个成员、不写本项目状态；当前 Codex 窗口只维护工作流。
总控用 `coordinator-workflow.py init TASK REQUEST --thread-id 当前总控会话ID`
建立账本，每次 `claim PHASE ROLE --bot-id 目标ID` 后，把返回的
`WF-DISPATCH:<dispatch_token>` 原样放进原生派单正文，随后保存真实 receipt。
模型和思考程度按任务设置，不改变职责或旧记录。

失败或停止后，先 `reconcile PHASE ROLE` 核对原生状态；完成的读取结果，
活跃/审批中的继续等待。确认终止后检查部分文件和测试，记录恢复证据，再用
`retry PHASE ROLE --reason 原因 --evidence 证据路径`，直接使用返回的新 claim，
不再 claim 一次。停止任务还必须提供 `--resume-authorization '用户继续指令及来源'`。
每一角色的同一阶段只允许一次恢复重试；业务修复另走最多两轮的 rework。
未绑定回执的 claim 不自动重发：先按派单标记找回回执；确无派单时，在旧总控
会话已停止/空闲后由维护入口执行 `release-claim`，同样保留证据和用户继续来源。
这些检查不是权限沙箱，禁止手工清空账本绕过。

自动记录通过本机 `scripts/workflow-observer.py` 注册和读取本项目。
总控初始化时注册当前项目；后台仅对注册项目生成 Obsidian 项目首页、阶段、
可见角色对话及异常，不导出隐藏推理、工具参数/结果或原生凭据。
失败、停止、等待审批、缺少回执、记录同步失败分别提示，并说明下一步。
项目内 `.workflour/observer-status.json` 是同步诊断，工作流知识库
`07-自动记录/首页.md` 是统一入口。自动区不要手工改；其他笔记不会被覆盖。
