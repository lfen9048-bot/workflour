# Code · 协作编码 · 按需技能

角色说明始终有效；模型切换不改变职责。按当前任务及阶段只读适用条目，不一次加载全部。

下表路径相对于本 SKILLS.md 所在目录；先据本文件位置解析为绝对路径，再用文件工具读取，不能把业务项目 cwd 当作技能根。共享方法通过文件工具读取，不按名字调用原生 skill 查询；它们不需要额外软链接或框架插件。

| 使用时机 | 文件 |
|---|---|
| 在已分配子任务中定位具体失败，保持写入范围 | ../wf-shared/skills/wf-systematic-debugging/SKILL.md |
| 子任务包含非平凡逻辑或Bug修复，补真实行为测试 | ../wf-shared/skills/wf-test-driven-development/SKILL.md |
| 子任务涉及解析、排序、数据转换或状态不变量，检查边界和反例 | ../wf-shared/skills/wf-property-based-testing/SKILL.md |
| 处理分配范围内的具体审核意见 | ../wf-shared/skills/wf-receiving-code-review/SKILL.md |
| 仅在被明确分配独立UI组件或指定视觉修复时 | ../wf-shared/skills/wf-frontend-design/SKILL.md |
| 仅在子任务验收需要真实网页操作时 | ../wf-shared/skills/wf-webapp-testing/SKILL.md |
| 向主编码回传子任务产物、测试和限制，不改共享账本 | ../wf-shared/skills/wf-verification-before-completion/SKILL.md |
