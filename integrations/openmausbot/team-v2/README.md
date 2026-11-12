# 新团队角色与技能配置

`roles.json` 是七个新角色的默认模型/思考程度、运行时、职责文件和技能目录索引。
DSH 使用新的 `omb-wf-*` profile，Antigravity 复用独立 `agy-gemini` 实例。
Bot 与运行会话的实际模型、档位仍须通过原生 API 读回并真实调用验证。

`setup.sh --only wf-角色` 只建立所选角色；默认 setup 仍保留旧 Coder/Doc 范围。
`wf-code-main` 只登记 Antigravity 实例，不创建 DSH profile。
思考档位由工作台 Bot/任务配置设置；profile 不使用猜测的 ACP 参数。
角色与专业技能保存在 `agents/wf-*`，共用方法在 `agents/wf-shared/skills`。
每个 DSH profile 仅扫描自己的角色目录，禁用默认全局技能根；按需读取具体技能。
AGY 的自动 skill 发现未经证明，因此它的职责明确要求用文件工具读取 SKILLS.md。

`sources/manifest.json` 固定上游提交、原始 SKILL 哈希及许可证。
`sources/` 是来源证据，不是活动技能目录；上游原版的额外审批/框架/删除代码要求未接入运行时。
活动的 `wf-*` 技能有 SOURCE.md 与上游许可证；Trail of Bits 的两个衍生技能继续适用 CC-BY-SA-4.0，
其他来源分别保留 MIT/Apache-2.0。requirements-interview 是用户本机技能快照，没有推定公开再分发许可。

早期网页方向检查由主编码对 Plan 评审进行一次原生 consult，返回后继续原实现任务；
不提前完成账本实现阶段。正式技术/产品返工仍共同最多两轮。
本机浏览器工具说明在 `agents/wf-shared/BROWSER.md`，实际能力需实测，截图必须读图后才算视觉证据。

## 针对性方法补强

七角色按需索引与当前启用/候选状态见 [SKILLS.md](SKILLS.md)，2026-11-12 的先验证再配置结果见[复验结论](../../../docs/SKILLS-REVALIDATION.zh-CN.md)；上一轮见[历史实施记录](../../../docs/SKILLS-SPECIALIZATION.zh-CN.md)。新共享方法按角色索引的相对路径用文件工具读取，不新增软链接或框架插件；原文不作为活动目录。

## 项目经理与 Obsidian

现行项目经理为 `wf-plan-lead`（Plan · 项目负责人）。其 `SOUL.md`、角色技能和 `SKILLS.md` 已接入知识库的接手阅读顺序、实质进展记录与现有 `wf-obsidian-markdown` 方法。知识库由 `WORKFLOUR_OBSIDIAN_VAULT` 或 `scripts/workflour_paths.py` 的本机默认位置决定；依照同库 `记录约定.md` 更新手写笔记和首页，业务项目以项目名区分。共享状态仍在原项目账本，`07-自动记录/` 继续由观察器维护。

职责更新使用 `python3 scripts/provision-team.py instructions --role wf-plan-lead`，仅在负责人及其任务均空闲时应用并读回；不发送 prompt，不重启服务，不改模型或任务状态。其他电脑先配置自己的知识库位置，未配置时按仓库交接文档恢复，不创建 Mac 路径。

## Ubuntu 七角色入口

见[完整部署教程](../../../docs/ubuntu-deployment/00-从这里开始.md)。新机使用私有 `~/.workflour/team-v2/deployment.json`；声明只含相对角色路径，不复用原Mac ID。`--manifest` 或 `WORKFLOUR_TEAM_MANIFEST` 可显式选择本机清单，原Mac已有清单继续兼容。七角色的模型目录预检在创建前执行；重复create保留现有手选模型。职责更新/激活要求空闲，归属不明的ID拒绝覆盖；激活保留其他Bot入口顺序。verify缺角色或职责异常时失败，手选模型偏离初始值仅单独报告。
