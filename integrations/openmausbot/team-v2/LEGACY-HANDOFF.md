# 旧团队项目交接

本表记录迁移时仍未由用户验收的旧项目。仅整理索引并暂停旧观察器，不删除 Bot、不重派任务、不代替用户验收。

原始旧团队备份为 [new-teams-20261111](</Users/a1/.workflour/backups/new-teams-20261111>)；其中 13 个 Bot、78 个会话、3720 条消息。之后新建的 7 个 Bot 和它们的验证对话不在旧导出或退役名单中。

共有 8 个旧项目，其中 5 个曾登记自动观察、3 个未登记。4 个仍活跃且引用旧 Bot 的登记已按原生 suspend 命令暂停；my-first-app 维持原有暂停原因。旧自动笔记保留。6 项等待用户验收，2 项交接文件仍处需求阶段；“规划讨论演练”已实际完成讨论，不能称为从未开始。

结构化索引：[LEGACY-HANDOFF.json](</Users/a1/Documents/a/workflour/integrations/openmausbot/team-v2/LEGACY-HANDOFF.json>)。观察器注册表前后及逐项备份路径见 [迁移审计目录](</Users/a1/.workflour/backups/legacy-migration-20261111>)。原始备份保持不变；补存的旧项目证据放在审计目录的 artifacts/。

| 项目 | 项目阶段 / 账本阶段 | 当前处理 | 自动观察 |
| --- | --- | --- | --- |
| [Code Team 最初演练](</Users/a1/Documents/a/workflour/examples/code-team-demo>) | acceptance / — | 待用户验收 | 未登记（未新增） |
| [总控任务清单演练](</Users/a1/Documents/a/workflour/examples/coordinator-demo>) | acceptance / verify | 待用户验收 | 未登记（未新增） |
| [奶娃网页](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page>) | acceptance / verify | 待用户验收 | 已暂停 |
| [三方讨论演练](</Users/a1/Documents/a/workflour/examples/planning-dialogue-demo>) | requirements / plan | 讨论已完成，未进入实现 | 已暂停 |
| [停止续跑演练](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo>) | acceptance / verify | 待用户验收 | 已暂停 |
| [词数统计演练](</Users/a1/Documents/a/workflour/examples/workflow-demo>) | acceptance / — | 待用户验收 | 未登记（未新增） |
| [第一个项目空模板](</Users/a1/Documents/a/workflour/projects/my-first-app>) | requirements / planning | 需求未开始 | 已暂停 |
| [黄色奶蛙网页](</Users/a1/Documents/a/workflour/projects/nailong-frog>) | acceptance / verify | 待用户验收 | 已暂停 |

会话索引的“仅执行目录关联”只表明旧任务的 cwd；历史任务曾有 cwd 仍指向父目录的问题，因此可能包含子项目对话，不作为执行归属或自动续跑的证明。账本/原生回执索引优先；缺失的会话不补造。

## 如何续办

用户明确要求续办某个旧项目时，由新大管家交给新 Plan 项目负责人，在新团队新建会话，先读取本表、项目 HANDOFF、需求、计划和当前证据；核对真实代码快照后再决定下一步。不要复用已退役 Bot ID 或旧原生恢复游标，不自动重跑已完成阶段。若代码改变，旧审核/测试证据须重新核对。新会话与观察器绑定完成后再恢复自动观察。

待验收项目仍由用户明确验收。奶蛙项目还缺 M1–M8 浏览器人工复核；本次只核对已有文件哈希，没有重跑项目测试或补签。

## Code Team 最初演练 · CODE-TEAM-001

项目：[/Users/a1/Documents/a/workflour/examples/code-team-demo](</Users/a1/Documents/a/workflour/examples/code-team-demo>)

- 项目阶段：`acceptance`；账本阶段：`未建账本`；用户验收：`pending`。
- 下一步：用户查看演练结果并验收，或指定第一个真实项目
- 历史差异／限制：没有 coordination.json；会话归属依靠原任务 cwd 或明确项目路径/标题，不补造委派回执。
- 原协调会话：没有可确认的独立协调 thread ID，未补造。
- 自动观察：原来未登记，本次未新增。
- 审核记录：`passed`；4 个快照文件与当前文件一致（本次未重跑）。
- 测试记录：`passed`；4 个快照文件与当前文件一致（本次未重跑）。

原 Bot / 会话索引：

| 原 Bot | Bot ID | 原会话与本地导出 | 归属依据 |
| --- | --- | --- | --- |
| Code Team · 独立审核 | e1c0943d-e409-421d-9bb9-f98a240585d9 | [2eb25673-f0a9-484d-a1f1-9430f95a3e99](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/e1c0943d-e409-421d-9bb9-f98a240585d9/2eb25673-f0a9-484d-a1f1-9430f95a3e99.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 独立审核 | e1c0943d-e409-421d-9bb9-f98a240585d9 | [d022703e-83f9-4275-96aa-6e61be7c07a4](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/e1c0943d-e409-421d-9bb9-f98a240585d9/d022703e-83f9-4275-96aa-6e61be7c07a4.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 主力编码 | da2fa5b9-9f4f-4163-b2ce-7a078a777508 | [b8b437b4-ca72-48a7-8057-1bc1fc0dea42](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/da2fa5b9-9f4f-4163-b2ce-7a078a777508/b8b437b4-ca72-48a7-8057-1bc1fc0dea42.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 主力编码 | da2fa5b9-9f4f-4163-b2ce-7a078a777508 | [847cd5d1-b4ba-42b5-84d0-4b80e1f2809b](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/da2fa5b9-9f4f-4163-b2ce-7a078a777508/847cd5d1-b4ba-42b5-84d0-4b80e1f2809b.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 风险规划 | a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b | [54e0bd8d-b448-4275-88e2-f8b91e67cf74](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b/54e0bd8d-b448-4275-88e2-f8b91e67cf74.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 风险规划 | a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b | [30219b64-2416-4877-a85e-3539010ab416](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b/30219b64-2416-4877-a85e-3539010ab416.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [0af8b071-89ea-4045-bdef-f203a2889fed](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/0af8b071-89ea-4045-bdef-f203a2889fed.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [3bbe4876-061a-4dd8-8f8d-5ba120db515b](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/3bbe4876-061a-4dd8-8f8d-5ba120db515b.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [d4dc44c8-45fe-42e2-befc-528a7c5acae4](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/d4dc44c8-45fe-42e2-befc-528a7c5acae4.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [29aab1a7-9f75-44a3-a141-ea93e476236a](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/29aab1a7-9f75-44a3-a141-ea93e476236a.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 方案主持 | 77b711cf-81a4-450f-b2fd-45ba77cfc6ec | [9aeb7b7c-1ad8-4af3-8f05-0dca5b5f9883](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/77b711cf-81a4-450f-b2fd-45ba77cfc6ec/9aeb7b7c-1ad8-4af3-8f05-0dca5b5f9883.md>) | 仅执行目录关联（归属需核对） |

材料与证据：

| 材料 | 当前位置 |
| --- | --- |
| .workflour/evidence/20261109-231304-5d518c5c.txt | [打开文件](</Users/a1/Documents/a/workflour/examples/code-team-demo/.workflour/evidence/20261109-231304-5d518c5c.txt>) |
| .workflour/evidence/20261109-231306-0bd4fb9f.txt | [打开文件](</Users/a1/Documents/a/workflour/examples/code-team-demo/.workflour/evidence/20261109-231306-0bd4fb9f.txt>) |
| .workflour/handoff.json | [打开文件](</Users/a1/Documents/a/workflour/examples/code-team-demo/.workflour/handoff.json>) |
| ACCEPTANCE.md | [打开文件](</Users/a1/Documents/a/workflour/examples/code-team-demo/ACCEPTANCE.md>) |
| HANDOFF.md | [打开文件](</Users/a1/Documents/a/workflour/examples/code-team-demo/HANDOFF.md>) |
| PLAN.md | [打开文件](</Users/a1/Documents/a/workflour/examples/code-team-demo/PLAN.md>) |
| README.md | [打开文件](</Users/a1/Documents/a/workflour/examples/code-team-demo/README.md>) |
| evidence/verification.md | [打开文件](</Users/a1/Documents/a/workflour/examples/code-team-demo/evidence/verification.md>) |
| records/deepseek/proposal.md | [打开文件](</Users/a1/Documents/a/workflour/examples/code-team-demo/records/deepseek/proposal.md>) |
| records/glm-plan/proposal.md | [打开文件](</Users/a1/Documents/a/workflour/examples/code-team-demo/records/glm-plan/proposal.md>) |
| records/glm-review/review.md | [打开文件](</Users/a1/Documents/a/workflour/examples/code-team-demo/records/glm-review/review.md>) |
| records/kimi/proposal.md | [打开文件](</Users/a1/Documents/a/workflour/examples/code-team-demo/records/kimi/proposal.md>) |

## 总控任务清单演练 · COORD-001

项目：[/Users/a1/Documents/a/workflour/examples/coordinator-demo](</Users/a1/Documents/a/workflour/examples/coordinator-demo>)

- 项目阶段：`acceptance`；账本阶段：`verify`；用户验收：`pending`。
- 下一步：等待用户对 COORD-001 的最终验收；用户确认后填写 acceptance.source/quote/at 与 snapshot 并执行 check --stage done
- 历史差异／限制：旧账本缺少 coordinator_thread 与 worker ID；使用原生 assignment ID 对照导出时回执补充只读索引，不改旧账本。
- 原协调会话：`5a502357-8ca7-4d5f-993f-c3f3cf3c483e`；来源：原生委派发起会话（旧账本漏填）。
- 自动观察：原来未登记，本次未新增。
- 审核记录：`passed`；4 个快照文件与当前文件一致（本次未重跑）。
- 测试记录：`passed`；4 个快照文件与当前文件一致（本次未重跑）。

原 Bot / 会话索引：

| 原 Bot | Bot ID | 原会话与本地导出 | 归属依据 |
| --- | --- | --- | --- |
| Code Team · 方案主持 | 77b711cf-81a4-450f-b2fd-45ba77cfc6ec | [303b8b45-ade2-4c92-950d-3991ffe2891e](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/77b711cf-81a4-450f-b2fd-45ba77cfc6ec/303b8b45-ade2-4c92-950d-3991ffe2891e.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [8d3e37bb-d37c-466b-b435-ee4b6a1fa599](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/8d3e37bb-d37c-466b-b435-ee4b6a1fa599.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 风险规划 | a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b | [b0cf12b7-603b-4c3c-aeb2-a1088d4cb3b2](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b/b0cf12b7-603b-4c3c-aeb2-a1088d4cb3b2.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 方案主持 | 77b711cf-81a4-450f-b2fd-45ba77cfc6ec | [29f27c59-198d-4264-826f-bdfd743d4f53](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/77b711cf-81a4-450f-b2fd-45ba77cfc6ec/29f27c59-198d-4264-826f-bdfd743d4f53.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 主力编码 | da2fa5b9-9f4f-4163-b2ce-7a078a777508 | [4086be27-cd02-4a08-9707-152601a838b7](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/da2fa5b9-9f4f-4163-b2ce-7a078a777508/4086be27-cd02-4a08-9707-152601a838b7.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [9bc87481-f743-4ad7-823d-8362fe6b4887](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/9bc87481-f743-4ad7-823d-8362fe6b4887.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 独立审核 | e1c0943d-e409-421d-9bb9-f98a240585d9 | [bb6f83e1-9879-4f93-b01d-304ac933e3a6](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/e1c0943d-e409-421d-9bb9-f98a240585d9/bb6f83e1-9879-4f93-b01d-304ac933e3a6.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 总控 | adca447b-321c-4f29-b6b0-9310b95c5970 | [5a502357-8ca7-4d5f-993f-c3f3cf3c483e](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/adca447b-321c-4f29-b6b0-9310b95c5970/5a502357-8ca7-4d5f-993f-c3f3cf3c483e.md>) | 原生委派发起会话（旧账本漏填）; 仅执行目录关联（归属需核对） |
| Code Team · 总控 | adca447b-321c-4f29-b6b0-9310b95c5970 | [a1e95f6d-bb33-4117-9992-2daf1f1a0618](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/adca447b-321c-4f29-b6b0-9310b95c5970/a1e95f6d-bb33-4117-9992-2daf1f1a0618.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 总控 | adca447b-321c-4f29-b6b0-9310b95c5970 | [9e3d64f6-dea3-4d39-8a9d-ce4bfe69288d](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/adca447b-321c-4f29-b6b0-9310b95c5970/9e3d64f6-dea3-4d39-8a9d-ce4bfe69288d.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 独立审核 | e1c0943d-e409-421d-9bb9-f98a240585d9 | [38195878-16fe-47f4-bfd5-c25389770f71](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/e1c0943d-e409-421d-9bb9-f98a240585d9/38195878-16fe-47f4-bfd5-c25389770f71.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 主力编码 | da2fa5b9-9f4f-4163-b2ce-7a078a777508 | [b9f29e07-dcd1-4da4-9445-09a937185ddb](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/da2fa5b9-9f4f-4163-b2ce-7a078a777508/b9f29e07-dcd1-4da4-9445-09a937185ddb.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 风险规划 | a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b | [c42a960b-04fc-42fa-9752-11f8f35df57a](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b/c42a960b-04fc-42fa-9752-11f8f35df57a.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [3af62cd5-76e4-4a63-ac34-e49c655f3ed3](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/3af62cd5-76e4-4a63-ac34-e49c655f3ed3.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [cc6289ff-4a83-4f1a-8e62-b463ecbbff6f](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/cc6289ff-4a83-4f1a-8e62-b463ecbbff6f.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 方案主持 | 77b711cf-81a4-450f-b2fd-45ba77cfc6ec | [a4f4439c-0f50-4703-bc4f-d77c8fd19486](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/77b711cf-81a4-450f-b2fd-45ba77cfc6ec/a4f4439c-0f50-4703-bc4f-d77c8fd19486.md>) | 仅执行目录关联（归属需核对） |
| Code Team · 方案主持 | 77b711cf-81a4-450f-b2fd-45ba77cfc6ec | [4c3586e0-daf9-47ee-b3ed-1c0ac5c4aa10](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/77b711cf-81a4-450f-b2fd-45ba77cfc6ec/4c3586e0-daf9-47ee-b3ed-1c0ac5c4aa10.md>) | 仅执行目录关联（归属需核对） |

材料与证据：

| 材料 | 当前位置 |
| --- | --- |
| .workflour/coordination.json | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/.workflour/coordination.json>) |
| .workflour/evidence/20261110-134434-dff96f3a.txt | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/.workflour/evidence/20261110-134434-dff96f3a.txt>) |
| .workflour/handoff.json | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/.workflour/handoff.json>) |
| ACCEPTANCE.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/ACCEPTANCE.md>) |
| HANDOFF.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/HANDOFF.md>) |
| PLAN.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/PLAN.md>) |
| README.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/README.md>) |
| evidence/verification.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/evidence/verification.md>) |
| records/deepseek/proposal.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/records/deepseek/proposal.md>) |
| records/glm-plan/proposal.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/records/glm-plan/proposal.md>) |
| records/glm-review/review.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/records/glm-review/review.md>) |
| records/kimi/proposal.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/records/kimi/proposal.md>) |
| task_cli.py | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/task_cli.py>) |
| test_cli.py | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/test_cli.py>) |

## 奶娃网页 · NAIWA-001

项目：[/Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page>)

- 项目阶段：`acceptance`；账本阶段：`verify`；用户验收：`pending`。
- 下一步：等待用户本人验收：确认「奶娃网页」主题/内容/风格是否符合预期。材料见 ACCEPTANCE.md；用户确认前保持 acceptance/pending，不得标记 done，不得代签。
- 原协调会话：`af1be50e-3896-4235-936d-6941be450ba4`；来源：旧账本协调会话字段。
- 自动观察：已暂停。团队迁移，旧聊天已导出；需续办在新团队新会话。原自动笔记：[项目记录](</Users/a1/Documents/Obsidian/多Agent协作开发工作流/07-自动记录/naiwa-page-0694dc9a34>)。
- 审核记录：`passed`；4 个快照文件与当前文件一致（本次未重跑）。
- 测试记录：`passed`；4 个快照文件与当前文件一致（本次未重跑）。

原 Bot / 会话索引：

| 原 Bot | Bot ID | 原会话与本地导出 | 归属依据 |
| --- | --- | --- | --- |
| Code Team · 方案主持 | 77b711cf-81a4-450f-b2fd-45ba77cfc6ec | [4c3586e0-daf9-47ee-b3ed-1c0ac5c4aa10](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/77b711cf-81a4-450f-b2fd-45ba77cfc6ec/4c3586e0-daf9-47ee-b3ed-1c0ac5c4aa10.md>) | 旧账本 + 原生委派回执 |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [cc6289ff-4a83-4f1a-8e62-b463ecbbff6f](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/cc6289ff-4a83-4f1a-8e62-b463ecbbff6f.md>) | 旧账本 + 原生委派回执 |
| Code Team · 风险规划 | a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b | [c42a960b-04fc-42fa-9752-11f8f35df57a](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b/c42a960b-04fc-42fa-9752-11f8f35df57a.md>) | 旧账本 + 原生委派回执 |
| Code Team · 方案主持 | 77b711cf-81a4-450f-b2fd-45ba77cfc6ec | [a4f4439c-0f50-4703-bc4f-d77c8fd19486](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/77b711cf-81a4-450f-b2fd-45ba77cfc6ec/a4f4439c-0f50-4703-bc4f-d77c8fd19486.md>) | 旧账本 + 原生委派回执 |
| Code Team · 主力编码 | da2fa5b9-9f4f-4163-b2ce-7a078a777508 | [b9f29e07-dcd1-4da4-9445-09a937185ddb](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/da2fa5b9-9f4f-4163-b2ce-7a078a777508/b9f29e07-dcd1-4da4-9445-09a937185ddb.md>) | 旧账本 + 原生委派回执; 旧账本 |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [3af62cd5-76e4-4a63-ac34-e49c655f3ed3](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/3af62cd5-76e4-4a63-ac34-e49c655f3ed3.md>) | 旧账本 + 原生委派回执; 旧账本 |
| Code Team · 独立审核 | e1c0943d-e409-421d-9bb9-f98a240585d9 | [fe9228c7-ca1a-4efe-88d9-5b8a9ec86f1e](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/e1c0943d-e409-421d-9bb9-f98a240585d9/fe9228c7-ca1a-4efe-88d9-5b8a9ec86f1e.md>) | 旧账本 + 原生委派回执 |
| Code Team · 主力编码 | da2fa5b9-9f4f-4163-b2ce-7a078a777508 | [c3af086b-6959-4d09-8f5e-cb62706cb96b](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/da2fa5b9-9f4f-4163-b2ce-7a078a777508/c3af086b-6959-4d09-8f5e-cb62706cb96b.md>) | 旧账本 + 原生委派回执 |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [1ede19c8-b372-4a54-b927-fa1498872a10](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/1ede19c8-b372-4a54-b927-fa1498872a10.md>) | 旧账本 + 原生委派回执 |
| Code Team · 独立审核 | e1c0943d-e409-421d-9bb9-f98a240585d9 | [7f5527b0-8c1c-4dd6-813b-c7976e7fe03e](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/e1c0943d-e409-421d-9bb9-f98a240585d9/7f5527b0-8c1c-4dd6-813b-c7976e7fe03e.md>) | 旧账本 + 原生委派回执; 旧账本 |
| Code Team · 总控 | adca447b-321c-4f29-b6b0-9310b95c5970 | [af1be50e-3896-4235-936d-6941be450ba4](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/adca447b-321c-4f29-b6b0-9310b95c5970/af1be50e-3896-4235-936d-6941be450ba4.md>) | 旧账本协调会话字段 |

材料与证据：

| 材料 | 当前位置 |
| --- | --- |
| .workflour/coordination.json | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/.workflour/coordination.json>) |
| .workflour/evidence/20261110-190540-ee7a0559.txt | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/.workflour/evidence/20261110-190540-ee7a0559.txt>) |
| .workflour/evidence/20261110-195359-77e0b137.txt | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/.workflour/evidence/20261110-195359-77e0b137.txt>) |
| .workflour/evidence/20261110-202643-ff6406f2.txt | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/.workflour/evidence/20261110-202643-ff6406f2.txt>) |
| .workflour/evidence/20261110-205341-1dc7af9b.txt | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/.workflour/evidence/20261110-205341-1dc7af9b.txt>) |
| .workflour/handoff.json | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/.workflour/handoff.json>) |
| ACCEPTANCE.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/ACCEPTANCE.md>) |
| HANDOFF.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/HANDOFF.md>) |
| PLAN.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/PLAN.md>) |
| README.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/README.md>) |
| evidence/verification-browser.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/evidence/verification-browser.md>) |
| evidence/verification.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/evidence/verification.md>) |
| records/agy/repair-d1.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/records/agy/repair-d1.md>) |
| records/coordinator/reconcile-implement.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/records/coordinator/reconcile-implement.md>) |
| records/coordinator/recovery-review1.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/records/coordinator/recovery-review1.md>) |
| records/coordinator/review1-check.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/records/coordinator/review1-check.md>) |
| records/deepseek/proposal.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/records/deepseek/proposal.md>) |
| records/deepseek/repair-d2.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/records/deepseek/repair-d2.md>) |
| records/glm-plan/proposal.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/records/glm-plan/proposal.md>) |
| records/glm-review/review-round1.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/records/glm-review/review-round1.md>) |
| records/glm-review/review.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/records/glm-review/review.md>) |
| records/kimi/proposal.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/records/kimi/proposal.md>) |
| records/maintenance/browser-repaired.json | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/records/maintenance/browser-repaired.json>) |
| specs/001-naiwa-page/spec.md | [打开文件](</Users/a1/Documents/a/workflour/examples/coordinator-demo/naiwa-page/specs/001-naiwa-page/spec.md>) |

## 三方讨论演练 · unassigned

项目：[/Users/a1/Documents/a/workflour/examples/planning-dialogue-demo](</Users/a1/Documents/a/workflour/examples/planning-dialogue-demo>)

- 项目阶段：`requirements`；账本阶段：`plan`；用户验收：`pending`。
- 下一步：填写需求与验收条件，再使用 Spec Kit 创建 feature
- 历史差异／限制：已完成三方提案、交叉回应和主持定稿，共 7 条 completed 派单；handoff 仍为 requirements/unassigned，coordination 为 plan。仅保留差异，未进入实现，不自动补写阶段。
- 原协调会话：`bc82be3b-3dc1-4cc1-aa05-094db33bc42b`；来源：旧账本协调会话字段。
- 自动观察：已暂停。团队迁移，旧聊天已导出；需续办在新团队新会话。原自动笔记：[项目记录](</Users/a1/Documents/Obsidian/多Agent协作开发工作流/07-自动记录/planning-dialogue-demo-e62eba661c>)。
- 审核记录：`pending`；0 个快照文件无已通过快照（本次未重跑）。
- 测试记录：`pending`；0 个快照文件无已通过快照（本次未重跑）。

原 Bot / 会话索引：

| 原 Bot | Bot ID | 原会话与本地导出 | 归属依据 |
| --- | --- | --- | --- |
| Code Team · 方案主持 | 77b711cf-81a4-450f-b2fd-45ba77cfc6ec | [8b739815-3296-42c5-99e6-d68f9f8b130e](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/77b711cf-81a4-450f-b2fd-45ba77cfc6ec/8b739815-3296-42c5-99e6-d68f9f8b130e.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [d0e43b19-0da3-45e8-b32b-f2b9174f69e5](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/d0e43b19-0da3-45e8-b32b-f2b9174f69e5.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 风险规划 | a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b | [004b2b80-0bc5-42fc-a574-eea5b55f37c4](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b/004b2b80-0bc5-42fc-a574-eea5b55f37c4.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 方案主持 | 77b711cf-81a4-450f-b2fd-45ba77cfc6ec | [0284825d-fe08-42b9-b4ec-3d16a0736f14](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/77b711cf-81a4-450f-b2fd-45ba77cfc6ec/0284825d-fe08-42b9-b4ec-3d16a0736f14.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [e838f963-036f-4713-b241-523c0c2ccfba](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/e838f963-036f-4713-b241-523c0c2ccfba.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 风险规划 | a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b | [a5def909-c730-43b5-969e-0a1bb201d1ec](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b/a5def909-c730-43b5-969e-0a1bb201d1ec.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 方案主持 | 77b711cf-81a4-450f-b2fd-45ba77cfc6ec | [8cdb7c95-f516-448e-97ac-d1b816cb9ee5](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/77b711cf-81a4-450f-b2fd-45ba77cfc6ec/8cdb7c95-f516-448e-97ac-d1b816cb9ee5.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 总控 | adca447b-321c-4f29-b6b0-9310b95c5970 | [bc82be3b-3dc1-4cc1-aa05-094db33bc42b](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/adca447b-321c-4f29-b6b0-9310b95c5970/bc82be3b-3dc1-4cc1-aa05-094db33bc42b.md>) | 旧账本协调会话字段; 仅执行目录关联（归属需核对） |

材料与证据：

| 材料 | 当前位置 |
| --- | --- |
| .workflour/coordination.json | [打开文件](</Users/a1/Documents/a/workflour/examples/planning-dialogue-demo/.workflour/coordination.json>) |
| .workflour/handoff.json | [打开文件](</Users/a1/Documents/a/workflour/examples/planning-dialogue-demo/.workflour/handoff.json>) |
| HANDOFF.md | [打开文件](</Users/a1/Documents/a/workflour/examples/planning-dialogue-demo/HANDOFF.md>) |
| README.md | [打开文件](</Users/a1/Documents/a/workflour/examples/planning-dialogue-demo/README.md>) |
| records/chair/PLAN.md | [打开文件](</Users/a1/Documents/a/workflour/examples/planning-dialogue-demo/records/chair/PLAN.md>) |
| records/deepseek/discussion.json | [打开文件](</Users/a1/Documents/a/workflour/examples/planning-dialogue-demo/records/deepseek/discussion.json>) |
| records/deepseek/proposal.md | [打开文件](</Users/a1/Documents/a/workflour/examples/planning-dialogue-demo/records/deepseek/proposal.md>) |
| records/glm-plan/discussion.json | [打开文件](</Users/a1/Documents/a/workflour/examples/planning-dialogue-demo/records/glm-plan/discussion.json>) |
| records/glm-plan/proposal.md | [打开文件](</Users/a1/Documents/a/workflour/examples/planning-dialogue-demo/records/glm-plan/proposal.md>) |
| records/kimi/discussion.json | [打开文件](</Users/a1/Documents/a/workflour/examples/planning-dialogue-demo/records/kimi/discussion.json>) |
| records/kimi/proposal.md | [打开文件](</Users/a1/Documents/a/workflour/examples/planning-dialogue-demo/records/kimi/proposal.md>) |

## 停止续跑演练 · RECOVERY-001

项目：[/Users/a1/Documents/a/workflour/examples/recovery-flow-demo](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo>)

- 项目阶段：`acceptance`；账本阶段：`verify`；用户验收：`pending`。
- 下一步：等待用户对 RECOVERY-001 明确验收；材料见 specs/001-text-count-tool/acceptance.md。用户确认前不得改为 done。
- 原协调会话：`0c6b02da-2e61-4460-8839-790d8e8d1097`；来源：旧账本协调会话字段。
- 自动观察：已暂停。团队迁移，旧聊天已导出；需续办在新团队新会话。原自动笔记：[项目记录](</Users/a1/Documents/Obsidian/多Agent协作开发工作流/07-自动记录/recovery-flow-demo-d57a3f0997>)。
- 审核记录：`passed`；2 个快照文件与当前文件一致（本次未重跑）。
- 测试记录：`passed`；2 个快照文件与当前文件一致（本次未重跑）。

原 Bot / 会话索引：

| 原 Bot | Bot ID | 原会话与本地导出 | 归属依据 |
| --- | --- | --- | --- |
| Code Team · 方案主持 | 77b711cf-81a4-450f-b2fd-45ba77cfc6ec | [c207cd1c-4253-4cb5-b70c-8271518ceaae](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/77b711cf-81a4-450f-b2fd-45ba77cfc6ec/c207cd1c-4253-4cb5-b70c-8271518ceaae.md>) | 旧账本 + 原生委派回执; 旧账本; 仅执行目录关联（归属需核对） |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [d128fdd2-ec73-4ca7-95b7-662dcf838307](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/d128fdd2-ec73-4ca7-95b7-662dcf838307.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 风险规划 | a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b | [8290d37f-3c43-44b4-9613-f81aea1c8179](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b/8290d37f-3c43-44b4-9613-f81aea1c8179.md>) | 旧账本 + 原生委派回执; 旧账本; 仅执行目录关联（归属需核对） |
| Code Team · 方案主持 | 77b711cf-81a4-450f-b2fd-45ba77cfc6ec | [82af1ea9-e304-45ee-973e-88e1d13773e9](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/77b711cf-81a4-450f-b2fd-45ba77cfc6ec/82af1ea9-e304-45ee-973e-88e1d13773e9.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 主力编码 | da2fa5b9-9f4f-4163-b2ce-7a078a777508 | [96516d28-6162-4b9b-ba69-4659a200ec89](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/da2fa5b9-9f4f-4163-b2ce-7a078a777508/96516d28-6162-4b9b-ba69-4659a200ec89.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [e6e85526-4773-48a9-b8d0-62617dfb412b](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/e6e85526-4773-48a9-b8d0-62617dfb412b.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 独立审核 | e1c0943d-e409-421d-9bb9-f98a240585d9 | [3e1e5af2-bb49-42ce-97a1-bba06e1acc13](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/e1c0943d-e409-421d-9bb9-f98a240585d9/3e1e5af2-bb49-42ce-97a1-bba06e1acc13.md>) | 旧账本 + 原生委派回执; 仅执行目录关联（归属需核对） |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [2dfbb37b-5e79-463a-b982-4d56ac6ac9fb](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/2dfbb37b-5e79-463a-b982-4d56ac6ac9fb.md>) | 旧账本 + 原生委派回执; 旧账本; 仅执行目录关联（归属需核对） |
| Code Team · 总控 | adca447b-321c-4f29-b6b0-9310b95c5970 | [0c6b02da-2e61-4460-8839-790d8e8d1097](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/adca447b-321c-4f29-b6b0-9310b95c5970/0c6b02da-2e61-4460-8839-790d8e8d1097.md>) | 旧账本协调会话字段; 仅执行目录关联（归属需核对） |

材料与证据：

| 材料 | 当前位置 |
| --- | --- |
| .workflour/coordination.json | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/.workflour/coordination.json>) |
| .workflour/evidence/20261110-153006-93deb515.txt | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/.workflour/evidence/20261110-153006-93deb515.txt>) |
| .workflour/handoff.json | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/.workflour/handoff.json>) |
| HANDOFF.md | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/HANDOFF.md>) |
| README.md | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/README.md>) |
| counts.py | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/counts.py>) |
| records/coordinator/recovery.md | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/records/coordinator/recovery.md>) |
| records/deepseek/plan.md | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/records/deepseek/plan.md>) |
| records/glm-plan/plan.md | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/records/glm-plan/plan.md>) |
| records/glm-review/review.md | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/records/glm-review/review.md>) |
| records/kimi/plan.md | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/records/kimi/plan.md>) |
| specs/001-text-count-tool/acceptance.md | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/specs/001-text-count-tool/acceptance.md>) |
| specs/001-text-count-tool/plan.md | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/specs/001-text-count-tool/plan.md>) |
| specs/001-text-count-tool/spec.md | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/specs/001-text-count-tool/spec.md>) |
| specs/001-text-count-tool/tasks.md | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/specs/001-text-count-tool/tasks.md>) |
| specs/001-text-count-tool/verification.md | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/specs/001-text-count-tool/verification.md>) |
| test_counts.py | [打开文件](</Users/a1/Documents/a/workflour/examples/recovery-flow-demo/test_counts.py>) |

## 词数统计演练 · 001-word-count

项目：[/Users/a1/Documents/a/workflour/examples/workflow-demo](</Users/a1/Documents/a/workflour/examples/workflow-demo>)

- 项目阶段：`acceptance`；账本阶段：`未建账本`；用户验收：`pending`。
- 下一步：用户可按README复核演练产物并反馈；如明确确认，再记录真实验收来源/原话/时间/当前快照并进入done。真实产品项目仍待选择。
- 历史差异／限制：没有 coordination.json；会话归属依靠原任务 cwd 或明确项目路径/标题，不补造委派回执。
- 原协调会话：没有可确认的独立协调 thread ID，未补造。
- 自动观察：原来未登记，本次未新增。
- 审核记录：`passed`；2 个快照文件与当前文件一致（本次未重跑）。
- 测试记录：`passed`；2 个快照文件与当前文件一致（本次未重跑）。

原 Bot / 会话索引：

| 原 Bot | Bot ID | 原会话与本地导出 | 归属依据 |
| --- | --- | --- | --- |
| Gemini | e4794be2-ea6f-43d6-9b30-ac3060c24b72 | [7683ff6d-aaa9-4746-a934-69d32d65091b](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/e4794be2-ea6f-43d6-9b30-ac3060c24b72/7683ff6d-aaa9-4746-a934-69d32d65091b.md>) | 仅执行目录关联（归属需核对） |
| Doc | b37d94a0-951e-4b23-b2cc-2e5ee1bf9512 | [900162fc-d093-430d-8939-cddc3d474b80](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/b37d94a0-951e-4b23-b2cc-2e5ee1bf9512/900162fc-d093-430d-8939-cddc3d474b80.md>) | 仅执行目录关联（归属需核对） |
| Coder | 124f95f2-56b0-4fab-b9d8-413da31e1dc8 | [a84c789f-f396-439f-92f0-6142d1335149](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/124f95f2-56b0-4fab-b9d8-413da31e1dc8/a84c789f-f396-439f-92f0-6142d1335149.md>) | 仅执行目录关联（归属需核对） |

材料与证据：

| 材料 | 当前位置 |
| --- | --- |
| .workflour/evidence/20261109-180210-d00b6372.txt | [打开文件](</Users/a1/Documents/a/workflour/examples/workflow-demo/.workflour/evidence/20261109-180210-d00b6372.txt>) |
| .workflour/evidence/20261109-201228-de31510b.txt | [打开文件](</Users/a1/Documents/a/workflour/examples/workflow-demo/.workflour/evidence/20261109-201228-de31510b.txt>) |
| .workflour/evidence/20261109-201328-115a9ce2.txt | [打开文件](</Users/a1/Documents/a/workflour/examples/workflow-demo/.workflour/evidence/20261109-201328-115a9ce2.txt>) |
| .workflour/evidence/20261109-201644-bc98fc55.txt | [打开文件](</Users/a1/Documents/a/workflour/examples/workflow-demo/.workflour/evidence/20261109-201644-bc98fc55.txt>) |
| .workflour/handoff.json | [打开文件](</Users/a1/Documents/a/workflour/examples/workflow-demo/.workflour/handoff.json>) |
| HANDOFF.md | [打开文件](</Users/a1/Documents/a/workflour/examples/workflow-demo/HANDOFF.md>) |
| README.md | [打开文件](</Users/a1/Documents/a/workflour/examples/workflow-demo/README.md>) |
| specs/001-word-count/acceptance.md | [打开文件](</Users/a1/Documents/a/workflour/examples/workflow-demo/specs/001-word-count/acceptance.md>) |
| specs/001-word-count/docs.md | [打开文件](</Users/a1/Documents/a/workflour/examples/workflow-demo/specs/001-word-count/docs.md>) |
| specs/001-word-count/plan.md | [打开文件](</Users/a1/Documents/a/workflour/examples/workflow-demo/specs/001-word-count/plan.md>) |
| specs/001-word-count/review.md | [打开文件](</Users/a1/Documents/a/workflour/examples/workflow-demo/specs/001-word-count/review.md>) |
| specs/001-word-count/spec.md | [打开文件](</Users/a1/Documents/a/workflour/examples/workflow-demo/specs/001-word-count/spec.md>) |
| specs/001-word-count/tasks.md | [打开文件](</Users/a1/Documents/a/workflour/examples/workflow-demo/specs/001-word-count/tasks.md>) |
| specs/001-word-count/verification.md | [打开文件](</Users/a1/Documents/a/workflour/examples/workflow-demo/specs/001-word-count/verification.md>) |

## 第一个项目空模板 · unassigned

项目：[/Users/a1/Documents/a/workflour/projects/my-first-app](</Users/a1/Documents/a/workflour/projects/my-first-app>)

- 项目阶段：`requirements`；账本阶段：`planning`；用户验收：`pending`。
- 下一步：填写需求与验收条件，再使用 Spec Kit 创建 feature
- 历史差异／限制：空脚手架，账本无派单；原协调会话未包含在备份且历史已报 404。保留既有暂停理由，不猜测替代会话。
- 原协调会话：`62b7ef2e-79de-498e-9018-6261afbf0259`；来源：旧账本协调会话字段。
- 自动观察：已暂停。旧登记会话62b7ef2e在工作台读取返回404，账本无派单且工作台无对应任务；暂停重复同步，保留项目和旧记录，核对正确会话后resume。。原自动笔记：[项目记录](</Users/a1/Documents/Obsidian/多Agent协作开发工作流/07-自动记录/my-first-app-a67b7b9f95>)。
- 审核记录：`pending`；0 个快照文件无已通过快照（本次未重跑）。
- 测试记录：`pending`；0 个快照文件无已通过快照（本次未重跑）。

原 Bot / 会话索引：

| 原 Bot | Bot ID | 原会话与本地导出 | 归属依据 |
| --- | --- | --- | --- |
| 归属未确认 | — | `62b7ef2e-79de-498e-9018-6261afbf0259`（原备份无此会话） | 旧账本协调会话字段 |

材料与证据：

| 材料 | 当前位置 |
| --- | --- |
| .workflour/coordination.json | [打开文件](</Users/a1/Documents/a/workflour/projects/my-first-app/.workflour/coordination.json>) |
| .workflour/handoff.json | [打开文件](</Users/a1/Documents/a/workflour/projects/my-first-app/.workflour/handoff.json>) |
| HANDOFF.md | [打开文件](</Users/a1/Documents/a/workflour/projects/my-first-app/HANDOFF.md>) |
| README.md | [打开文件](</Users/a1/Documents/a/workflour/projects/my-first-app/README.md>) |

## 黄色奶蛙网页 · NAILONG-FROG-001

项目：[/Users/a1/Documents/a/workflour/projects/nailong-frog](</Users/a1/Documents/a/workflour/projects/nailong-frog>)

- 项目阶段：`acceptance`；账本阶段：`verify`；用户验收：`pending`。
- 下一步：等用户本人验收。自动测试侧已通过（0 阻断级问题，3 条命令退出码 0，变异测试证明非空转）；但 M1–M8 八项浏览器侧人工复核未执行（tests/manual-checklist.md 结果列留空），总控不预填、不代签。验收入口：直接双击 index.html 离线打开。
- 历史差异／限制：技术验证记录为 passed；M1–M8 浏览器人工复核未执行，不能视为完整验收。
- 原协调会话：`5232779e-9e2a-4b1e-956e-7ca6e6816cc8`；来源：旧账本协调会话字段。
- 自动观察：已暂停。团队迁移，旧聊天已导出；需续办在新团队新会话。原自动笔记：[项目记录](</Users/a1/Documents/Obsidian/多Agent协作开发工作流/07-自动记录/nailong-frog-b67225621a>)。
- 审核记录：`passed`；7 个快照文件与当前文件一致（本次未重跑）。
- 测试记录：`passed`；7 个快照文件与当前文件一致（本次未重跑）。

原 Bot / 会话索引：

| 原 Bot | Bot ID | 原会话与本地导出 | 归属依据 |
| --- | --- | --- | --- |
| Code Team · 方案主持 | 77b711cf-81a4-450f-b2fd-45ba77cfc6ec | [23dc8ceb-17f5-422a-ab83-e3aa1010058a](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/77b711cf-81a4-450f-b2fd-45ba77cfc6ec/23dc8ceb-17f5-422a-ab83-e3aa1010058a.md>) | 旧账本 + 原生委派回执 |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [dffdef75-3d38-4c6e-a1e6-97dedc72dc94](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/dffdef75-3d38-4c6e-a1e6-97dedc72dc94.md>) | 旧账本 + 原生委派回执 |
| Code Team · 风险规划 | a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b | [53e47f0a-77cb-4105-b6cc-4c30562a9433](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b/53e47f0a-77cb-4105-b6cc-4c30562a9433.md>) | 旧账本 + 原生委派回执 |
| Code Team · 方案主持 | 77b711cf-81a4-450f-b2fd-45ba77cfc6ec | [d81de5fb-211b-4e08-8d8e-0daee3110eb8](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/77b711cf-81a4-450f-b2fd-45ba77cfc6ec/d81de5fb-211b-4e08-8d8e-0daee3110eb8.md>) | 旧账本 + 原生委派回执 |
| Code Team · 主力编码 | da2fa5b9-9f4f-4163-b2ce-7a078a777508 | [8332e5f0-c08c-4f1b-8e6f-2ee5a6459ddb](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/da2fa5b9-9f4f-4163-b2ce-7a078a777508/8332e5f0-c08c-4f1b-8e6f-2ee5a6459ddb.md>) | 旧账本 + 原生委派回执 |
| Code Team · 协作编码 | 5e229ff6-7661-4301-bbcb-ee1621ea507e | [99ac8f91-2bd0-4adb-9f45-33ba49dfe969](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/5e229ff6-7661-4301-bbcb-ee1621ea507e/99ac8f91-2bd0-4adb-9f45-33ba49dfe969.md>) | 旧账本 + 原生委派回执 |
| Code Team · 独立审核 | e1c0943d-e409-421d-9bb9-f98a240585d9 | [0dc70bf0-c0d4-49d6-b3fc-376a049da909](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/e1c0943d-e409-421d-9bb9-f98a240585d9/0dc70bf0-c0d4-49d6-b3fc-376a049da909.md>) | 旧账本 + 原生委派回执 |
| Code Team · 方案主持 | 77b711cf-81a4-450f-b2fd-45ba77cfc6ec | [359e9e49-f726-488d-a3bd-1a0f78a356db](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/77b711cf-81a4-450f-b2fd-45ba77cfc6ec/359e9e49-f726-488d-a3bd-1a0f78a356db.md>) | 旧账本 + 原生委派回执; 旧账本 |
| Code Team · 总控 | adca447b-321c-4f29-b6b0-9310b95c5970 | [5232779e-9e2a-4b1e-956e-7ca6e6816cc8](</Users/a1/.workflour/backups/new-teams-20261111/chats/bots/adca447b-321c-4f29-b6b0-9310b95c5970/5232779e-9e2a-4b1e-956e-7ca6e6816cc8.md>) | 旧账本协调会话字段 |

材料与证据：

| 材料 | 当前位置 |
| --- | --- |
| .workflour/coordination.json | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/.workflour/coordination.json>) |
| .workflour/evidence/20261110-222950-74a45dc5.txt | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/.workflour/evidence/20261110-222950-74a45dc5.txt>) |
| .workflour/evidence/20261110-224306-5e5ce8a5.txt | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/.workflour/evidence/20261110-224306-5e5ce8a5.txt>) |
| .workflour/handoff.json | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/.workflour/handoff.json>) |
| HANDOFF.md | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/HANDOFF.md>) |
| PLAN.md | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/PLAN.md>) |
| README.md | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/README.md>) |
| records/coordinator/acceptance-pending.md | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/records/coordinator/acceptance-pending.md>) |
| records/coordinator/impl-verification.md | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/records/coordinator/impl-verification.md>) |
| records/coordinator/recovery.md | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/records/coordinator/recovery.md>) |
| records/coordinator/review-adjudication.md | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/records/coordinator/review-adjudication.md>) |
| records/coordinator/verification.md | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/records/coordinator/verification.md>) |
| records/deepseek/proposal.md | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/records/deepseek/proposal.md>) |
| records/glm-plan/proposal.md | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/records/glm-plan/proposal.md>) |
| records/glm-review/review.md | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/records/glm-review/review.md>) |
| records/kimi/proposal.md | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/records/kimi/proposal.md>) |
| specs/001-frog-site/spec.md | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/specs/001-frog-site/spec.md>) |
| specs/001-frog-site/tasks.md | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/specs/001-frog-site/tasks.md>) |
| tests/manual-checklist.md | [打开文件](</Users/a1/Documents/a/workflour/projects/nailong-frog/tests/manual-checklist.md>) |

## 旧 Bot 退役范围

下列 12 个 ID 属于原导出，可在新团队全部验证完成、再次核对空闲后按授权退役。此表生成时尚未删除。系统默认 MausBot 保留，只隐藏侧边栏。旧“大管家”与新“大管家”同名，必须按 ID 区分。

| 旧名称 | 待退役 ID |
| --- | --- |
| 大管家 | `25002ada-9065-4a6c-bac2-eae61782dd71` |
| 通用助手 | `c50a6ed1-f910-4890-baed-5cb342ab5295` |
| Code Team · 总控 | `adca447b-321c-4f29-b6b0-9310b95c5970` |
| Code Team · 独立审核 | `e1c0943d-e409-421d-9bb9-f98a240585d9` |
| Code Team · 主力编码 | `da2fa5b9-9f4f-4163-b2ce-7a078a777508` |
| Code Team · 风险规划 | `a9cedc58-2a06-4e09-b14c-c0e36fa2bd9b` |
| Code Team · 协作编码 | `5e229ff6-7661-4301-bbcb-ee1621ea507e` |
| Code Team · 方案主持 | `77b711cf-81a4-450f-b2fd-45ba77cfc6ec` |
| DeepSeek Coder | `a6032a2d-22b9-4a93-867e-8303082b5fd0` |
| Gemini | `e4794be2-ea6f-43d6-9b30-ac3060c24b72` |
| Doc | `b37d94a0-951e-4b23-b2cc-2e5ee1bf9512` |
| Coder | `124f95f2-56b0-4fab-b9d8-413da31e1dc8` |

保留的系统默认 Bot：`13862540-d136-4542-8bb4-3098aa3f34ef`。新团队 7 个 ID 仅在结构化索引的 new_bot_ids_excluded 中列出，绝不作为退役候选。

原生导出导入会创建新 ID，只恢复文字与记忆，不能无损恢复 ACP 会话、权限、模型选择或委派运行树。恢复边界见 [RESTORE-LIMITS.md](</Users/a1/.workflour/backups/new-teams-20261111/RESTORE-LIMITS.md>)。

## 旧演练群

两个旧群已经包含在原生备份和独立 Markdown 聊天导出中（78 个会话含以下 2 个群会话）。本次不删除群组。旧业务 Bot 退役后先核对成员和默认回复者；新团队使用新会话，不继续旧群委派。确认空群且无需工作台入口后，再通过原生群组管理整理，项目代码和证据目录保留。

| 旧群 | 群 ID | 原会话 / 消息数 | 独立可读记录 |
| --- | --- | --- | --- |
| Code Team 完整实践 | `b07032c4-4a30-4994-83a2-04aa7a8cb9d8` | `1b25cfbc-3836-470d-abbb-67cba3eb07d8` / 3 | [打开导出](</Users/a1/.workflour/backups/new-teams-20261111/chats/groups/b07032c4-4a30-4994-83a2-04aa7a8cb9d8/1b25cfbc-3836-470d-abbb-67cba3eb07d8.md>) |
| Code 协作演练 | `5834363b-7536-4e9e-b7dc-b13bee26ee47` | `9904f6a4-4241-4cf9-8ec7-39a108b634f1` / 52 | [打开导出](</Users/a1/.workflour/backups/new-teams-20261111/chats/groups/5834363b-7536-4e9e-b7dc-b13bee26ee47/9904f6a4-4241-4cf9-8ec7-39a108b634f1.md>) |

续办入口是新大管家 `3abc61c7-39bd-447d-88d0-7e486e50d15f`，再转交新 Plan 项目负责人；旧大管家 `25002ada-9065-4a6c-bac2-eae61782dd71` 已列入退役范围，仅保留导出记录，不保留其工作台身份。
