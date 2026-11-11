# 通用助手 · 按需技能

角色说明始终有效；模型切换不改变职责。按当前任务及阶段只读适用条目，不一次加载全部。

下表路径相对于本 SKILLS.md 所在目录；先据本文件位置解析为绝对路径，再用文件工具读取，不能把业务项目 cwd 当作技能根。共享方法通过文件工具读取，不按名字调用原生 skill 查询；它们不需要额外软链接或框架插件。

| 使用时机 | 文件 |
|---|---|
| 问题需要外部事实或寻找现成工具/方案时 | ../wf-shared/skills/wf-search-first/SKILL.md |
| 需要整理多来源材料、辨明版本冲突或结论依据时 | ../wf-shared/skills/wf-research-synthesis/SKILL.md |
| 明确要求创建/整理Obsidian笔记时，保留来源和现有记录组织 | ../wf-shared/skills/wf-obsidian-markdown/SKILL.md |
| 明确换模型/思考或打开设置；不把普通讨论交给开发团队 | ../shared/skills/model-settings/SKILL.md |
