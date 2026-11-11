# Code · 独立审核 · 按需技能

角色说明始终有效；模型切换不改变职责。按当前任务及阶段只读适用条目，不一次加载全部。

下表路径相对于本 SKILLS.md 所在目录；先据本文件位置解析为绝对路径，再用文件工具读取，不能把业务项目 cwd 当作技能根。共享方法通过文件工具读取，不按名字调用原生 skill 查询；它们不需要额外软链接或框架插件。

| 使用时机 | 文件 |
|---|---|
| 对本轮差异和相关调用者独立检查；无基线时对照需求审实际模块 | ../wf-shared/skills/wf-differential-review/SKILL.md |
| 检查需求行为与已有测试对应、漏测风险；涉及I/O/重试再读错误路径参考 | ../wf-shared/skills/wf-test-coverage-review/SKILL.md |
| 解析、排序、转换或状态逻辑有明确不变量，或需要复核属性测试/反例 | ../wf-shared/skills/wf-property-based-testing/SKILL.md |
| 仅在本轮技术问题需要实际网页复现时使用，不替代最终产品体验 | ../wf-shared/skills/wf-webapp-testing/SKILL.md |
| 给出通过/需修复/受阻，核对所审快照及实际执行证据 | ../wf-shared/skills/wf-verification-before-completion/SKILL.md |
