# Workflour：Plan / Code 协作流程

用户只需在工作台向「大管家」说明要做什么、项目位置和验收条件。目录与模板初始化、派单、检查均由团队完成，不要求用户执行终端命令。

## 实际分工

| 顺序 | 负责人 | 应交付的材料 |
| --- | --- | --- |
| 接单 | 大管家 | 原始需求转给 Plan 负责人，不重复长规划 |
| research | plan-lead | 调研来源、初案、原话/约束/假设/验收标准 |
| plan-review | plan-review | 对初案和来源的独立意见，引用具体问题 |
| plan | plan-lead | 结合意见的简明定稿和任务安排 |
| implement | code-main | 完整实现、自测、代码清单和证据 |
| review | code-review | 独立技术审核，核对实际代码和当前测试 |
| experience | plan-review | 真实使用成品，桌面/手机截图、关键交互结果 |
| acceptance | plan-lead → 用户 | 对照需求交付、说明限制，等待用户确认 |

普通小任务只安排一位主编码；协作编码仅用于可以独立完成的子任务。视觉项目先由主编码做可运行关键页面，再向非祖先的 Plan 体验评审做一次 native consult，带原始需求、验收标准、URL 和截图。派单成功后结束当前回合，咨询返回后继续同一 implement 任务，不提前完成实现、不改共享账本；该反馈不等于最终 experience 通过。不因此要求每一步都找用户确认。技术审核与产品体验返工共用两轮预算，仍无法收敛交用户决定。

## 负责人操作

以下是 Agent 的执行接口，不是用户操作清单。工具包位于 `/Users/a1/Documents/a/workflour`。

```bash
python3 /Users/a1/Documents/a/workflour/scripts/coordinator-workflow.py --project /实际项目目录 --actor plan-lead init TASK-ID '用户原始任务' --thread-id 当前Plan负责人会话ID
```

默认按 project.json 启用 plan-code。负责人自身的研究和定稿用 `record research --evidence records/plan-lead/research.md`、`record plan --evidence records/plan-lead/plan.md`；不向自己派单，不编造原生回执。

其他阶段依次 `claim PHASE ROLE --bot-id 当前角色ID`，将返回的 `WF-DISPATCH:<dispatch_token>` 原样放进原生委派。收到真实原生回执后 `receipt PHASE ROLE ASSIGNMENT-ID`，读取结果和文件后 `result PHASE ROLE completed --evidence 项目相对路径`。再 `advance NEXT-PHASE`。Bot ID 从当前团队路由读取，不从历史记录复制。领取后拒绝重复领取；等待与审批中不能重派。

可选协作编码：在实现前 `enable-helper --reason '具体独立子任务及文件范围' --evidence records/plan-lead/helper-scope.md`。启用后实现阶段必须有两位编码者的真实回执；不要为小任务强制拆文件。

失败/停止先 `reconcile PHASE ROLE`。确认终止、检查副作用后 `retry ... --reason ... --evidence ...`，停止还需 `--resume-authorization '用户明确继续及来源'`。沿用返回的新 claim，不能再 claim 一次。每阶段每角色仅一次恢复重试。业务返工使用 `rework --reason ... --evidence ...`，从 review 或 experience 回到 implement，两种返工共用两轮。

## 共享交接与测试

`.workflour/handoff.json` 中：

- `owner` 固定 `plan-lead`；`next_owner` 表示当前负责人，`next_action` 说明下一步。
- `original_request` 保存原话，`assumptions` 单列团队假设；`requirements` 每项有 `id/criterion`。
- `planning.participants` 为 `plan-lead/plan-review`；两份独立 `contributions` 各有 `owner/record`；`sources` 各有 `url/title/decision`。定稿后 `status:settled`、`discussion_rounds:1` 或 `2`。
- `work_items` 包含 `id/owner/files/status`。通常 owner 只有 `code-main`；启用 helper 的项目另写 `independent_reason`。主编码的初始 `files` 可为空，由主编码决定内部结构；实际实现完成后负责人据其回传补齐精确文件归属并覆盖全部 `code_files`。独立 helper 必须预先划清文件范围。
- `code_files` 包含实现、测试和依赖；`baseline` 为实现前快照，新文件为 null。审核快照必须匹配真实当前文件。
- Code 运行 `python3 .workflour/check.py test --files 实现文件 --files 测试文件 -- 真实命令 参数...`（重复 `--files` 覆盖所有实际实现、测试和依赖文件；已有完整 code_files 时可省略），生成独立 JSON 记录及原始输出，不写 handoff。负责人用 `python3 .workflour/check.py --actor plan-lead import-test .workflour/evidence/实际记录.json` 导入，保留失败历史；另写 `artifacts.verification` 所指的覆盖说明。
- 负责人以 `python3 .workflour/check.py --actor plan-lead handoff` 更新可读摘要。

检查器阶段沿用 `requirements → plan → implement → review → verify → experience → acceptance → done`。派单账本的 research/plan-review 是准备阶段；不是所有阶段都需要一次模型派单。开始工作检查上一已完成阶段，结束时检查本阶段；pending 的本阶段不是开工阻塞。

## 真实体验与最终验收

网页项目 `product_surface:web` 必须浏览器实测。纯命令行项目由负责人明确设 `product_surface:cli`，体验 JSON 设同样 `surface:cli` 并记录实际 `command` 参数数组、`exit_code:0`、时间、逐需求操作结果及交互日志；无需网页截图。不能用 CLI 检查替代网页体验。

体验材料使用 `.workflour/templates/experience.example.json` 所示结构，保存为 `records/plan-review/experience.json`，其路径放到 `artifacts.experience`。必须包含实际浏览器、地址、时间、当前代码快照、每项验收标准的动作与观察、交互日志及其哈希、桌面和手机截图及其哈希。能力或连接缺失时 status 写 blocked，不能伪造 passed。

`check --stage acceptance` 同时检查独立审核、真实测试证据、体验记录与当前代码快照，以及验收说明。此检查只能证明材料一致，不能证明观察的真实性或覆盖完整。最后保留 `acceptance.status:pending`；用户确认后才记录 source/quote/at/snapshot 并进入 done。

旧项目和旧账本保持原版本，不迁移原 ACP 会话。观察器只同步已注册项目到 Obsidian，不派单、审批或修改状态。

## Agent 执行速查（首次完整任务）

命令中 `L` 表示 `python3 /Users/a1/Documents/a/workflour/scripts/coordinator-workflow.py --project 项目绝对路径 --actor plan-lead` 的完整前缀；`C` 表示项目内 `python3 .workflour/check.py`。这是说明中的简写，不是预装命令。执行时使用真实参数和明确 cwd，不将字符串拼接成不受控 shell。

1. **初始化**：新建空目录模板，阅读项目 AGENTS；将 handoff 的 `task_id/original_request/requirements/artifacts.spec/next_action` 填实，保留 `owner:plan-lead`、`acceptance.status:pending`。当前原生会话 ID 必须是 Plan 负责人接单的会话，不是大管家或之前探针的会话。`L init TASK 原话 --thread-id 当前会话` 只建账本，不派单。`in_my_folder:true` 只继承父会话目录；父目录不是项目时，工具命令必须另指定实际项目 cwd 或用 `project-exec.py`，不能声称继承后自动换了目录。
2. **调研初案**：保留真实来源、假设与可验收需求，`C check --stage requirements`；完成材料后 `L record research --evidence records/plan-lead/research.md`，再 `L advance plan-review`。已记录的 research 文件保留原样，定稿另写文件。
3. **独立方案意见**：`L claim plan-review plan-review --bot-id 精确ID`，带返回 token 原生派单，绑定真实 `receipt plan-review plan-review ID` 并结束回合。回传后读取意见与材料，`result plan-review plan-review completed --evidence records/plan-review/proposal-review.md`，再 `advance plan`。这一阶段无需实现代码、技术审核或测试已经通过。
4. **定稿**：负责人整理最终 plan/tasks，填写两位规划角色的独立 contributions、sources 和 `planning.status:settled/discussion_rounds`。创建一个主编码 work_item（初始 files 可空），`C check --stage plan`。`L record plan --evidence records/plan-lead/plan.md` 后 `advance implement`，仅给 code-main 正式派单。派单包括早期 preview consult 要求和测试 `--files` 接口。
5. **实现返回**：主编码回传实际文件与测试记录后，负责人先补齐 `code_files/baseline/work_items`（新文件 baseline 为 null），将完成 work_item 设 completed。导入 detached 测试记录，编写 verification 覆盖说明，`C check --stage implement`，再 `L result implement code-main completed --evidence records/code-main/implementation.md` 和 `advance review`。此时 review 仍 pending 是正常待做状态，不要提前 `check --stage review`。
6. **技术审核返回**：code-review 独立读取当前需求、代码及测试，记录自己的实际快照和结论。负责人核对后更新 `review.status/reviewer/findings/snapshot`，导入审核者的实际测试记录。技术通过才执行 `C check --stage review` 和 `C check --stage verify`，随后保存审核 result、`L advance experience`。发现真实缺陷按下表返工，不能只改 passed 字段。
7. **实际体验返回**：给 plan-review 新会话派发体验任务，明确 `rework:true` 以允许再次委派同一角色；它不能复用此前方案意见或 preview 作为最终体验。保存单独 `experience.json`、截图和交互日志。负责人填 `artifacts.experience`，`C check --stage experience`，再记录 `result experience plan-review completed --evidence records/plan-review/experience.json`。
8. **待验收**：负责人编写 `artifacts.acceptance` 所指的逐项对照说明，更新 `handoff.stage:acceptance`、`next_owner:User`、下一步等待用户验收，保持 `acceptance.status:pending`。`C check --stage acceptance` 和 `L advance acceptance` 均通过后，用 `C --actor plan-lead handoff` 生成交接并通过原派单返回。不要新增 verify/acceptance worker，也不要调用 `check --stage done` 或把用户验收写成 accepted。

每次完成 result 或本地 record 会锁定**当时的证据文件哈希和代码快照**。先整理共享 handoff、再记录完成，紧接着 advance；之后不要改已完成报告或偷偷替换截图。技术/产品返工保留旧报告与旧测试，使用带轮次的新文件，避免覆盖历史证据。

| 状态 | 含义与处理 |
| --- | --- |
| 原生 assignment completed | 该 Agent 已返回；仍需读产物，不能推导质量通过 |
| 审核报告 changes_requested | 原生执行完成；记录审核结果后 `L rework --reason 具体问题 --evidence 原报告`，保留旧轮次 |
| 模型/工具失败，或体验 blocked | 如实记 failed/阻塞与证据，留在当前阶段；不能为凑完整链写 completed/passed，不把能力故障计成代码修复 |
| 原生 waiting / needs_input / queued / running | 保留当前派单，等原生回传或实际审批；不再次 claim 或派单 |
| stopped / cancelled | 先 reconcile 和副作用检查；收到对应停止之后的明确继续来源才 retry |
| handoff acceptance.status pending | 等用户验收；这与模型工具的等待审批不同，也不阻止整理交付记录 |

预算分别计数：方案评审最多两轮（负责人记录真实轮数）；早期 preview 咨询最多一次；技术/体验业务返工共享 `repair_round` 最多两轮；每个阶段/角色因失败或停止的恢复 retry 最多一次。已有新 claim 时不要再 claim。预算耗尽或范围需要改变时，带具体问题及选项交用户，不能清账本重置计数。

原生 receipt 绑定必须匹配当前负责人会话、精确目标 Bot、派单中的唯一 `WF-DISPATCH` token。未知回执先 reconcile，不能填 local-test 或假 UUID；负责人自身 research/plan 走 record。`result failed` 和 `result stopped` 不等于可直接重发，仍按恢复规则核对。角色键使用 `plan-lead/plan-review/code-main/code-review/code-helper`，不是模型名或 manifest 中带 `wf-` 的 profile 键。

原生 `coordinate_bots` 的 `rework:true` 仅表示允许对已完成角色再次委派一个明确的新阶段/新会话，**不等于**账本 `L rework`，不会自行消耗业务返工轮数。最终 experience 与早期方案/preview 使用不同会话和不同证据文件；不能因为同一位评审已有旧回执就跳过本次派单。


## 运行中补充：一项业务可以有多个串行回执

本机 DSH/Antigravity 使用的 ACP adapter 没有即时 `steer` 能力。对正在工作的同一个 worker thread 调用 `coordinate_bots`，原生服务可能排入一个新的 `queued` assignment，等上一回合结束后再执行；这仍是同一业务阶段，但**不是只存在一个原生回执**。不能声称追加内容已被正在运行的回合读到，不能用主回执先返回的旧报告开始复审。

按原生返回判断：

- `injected` 且 requestId 仍为原主回执：内容已交给该回合，保留原回执，无需登记第二个。
- 返回不同 requestId（即使 threadId 相同、内容引用原 WF-DISPATCH）：先写单独、之后不再覆盖的补充说明，再显式登记该真实回执。
- 拒绝/失败或缺少可验证回执：如实报错，不编造补充，不再次 claim 整个任务。

补充说明记录来源、精确新增范围、主与补充回执、同一 worker thread，以及为什么属于本轮修复。它不能只是“同一个会话所以算补充”，也不能把完整任务重复派发包装成补充。沿用原 `WF-DISPATCH:<token>`；每一个新的原生 requestId 必须逐个登记：

```bash
L supplement implement code-main 真实补充ASSIGNMENT-ID --reason '用户补充了满额提示的准确含义，属于当前返工' --evidence records/plan-lead/supplement-scope.md
L reconcile implement code-main
```

`L` 仍是前文完整 CLI 前缀。命令只登记已经存在的回执，不发消息、不改变原生记录，不改主 `assignment_id`、token、attempt 或 repair_round。只能由当前共享状态负责人调用；必须同 sender Bot/thread、同 worker Bot/thread、创建时间晚于主单、不同的具体工作 brief，并带原派单 token。来源说明会保存 SHA256，之后修改会阻止完成。未经登记的同 token 回执仍报冲突，不能靠清 token 或“优先取主 ID”绕开。

登记后结束回合，等待原生回传。主单与**所有已登记补充**都 `completed`、worker 没有其他活跃续接，负责人读取最新实现与真实测试后，才做一次 `result PHASE ROLE completed --evidence 最新报告`，再 `advance`。两个入口都会重新核对原生回执；补充排队或运行时，主单完成不代表实现阶段完成。观察器分别显示主回执和补充状态。

若补充失败或停止，先 `L reconcile implement code-main`，保留各自结果和部分改动，明确报出失败的是哪一项。首版拒绝对含补充的阶段调用普通 `retry`，防止把已经完成的主任务重跑；需维护者检查失败补充的实际副作用后再制定有界恢复，不能通过删除补充、改 completed 或重置轮次继续。普通没有 supplements 的旧账本维持原恢复规则。
