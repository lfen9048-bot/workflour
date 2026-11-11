# Code · 主编码 · 按需技能

角色说明始终有效；模型切换不改变职责。按当前任务及阶段只读适用条目，不一次加载全部。

下表路径相对于本 SKILLS.md 所在目录；先据本文件位置解析为绝对路径，再用文件工具读取，不能把业务项目 cwd 当作技能根。共享方法通过文件工具读取，不按名字调用原生 skill 查询；它们不需要额外软链接或框架插件。

| 使用时机 | 文件 |
|---|---|
| 已有失败、缺陷或与预期不符的行为，先定位根因 | ../wf-shared/skills/wf-systematic-debugging/SKILL.md |
| 非平凡逻辑或Bug修复，选择能捕获真实行为的最小测试 | ../wf-shared/skills/wf-test-driven-development/SKILL.md |
| 已有具体审核意见，先核对复现和影响，再按范围修复 | ../wf-shared/skills/wf-receiving-code-review/SKILL.md |
| 新页面、显著视觉变更或已指定UI问题；局部修复沿用认可方向 | ../wf-shared/skills/wf-frontend-design/SKILL.md |
| 验收涉及网页实际操作，复用已有浏览器能力及有效探针 | ../wf-shared/skills/wf-webapp-testing/SKILL.md |
| 交付当前实现/返修，核对相关测试和代码快照 | ../wf-shared/skills/wf-verification-before-completion/SKILL.md |
