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
