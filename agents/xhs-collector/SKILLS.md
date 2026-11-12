# 小红书 · 采集：按需技能

先读取本目录 `skills/xhs-collector-role/SKILL.md`。工具仓库与本角色目录的绝对路径由 SOUL 的“本机路由与工具”段给出，不假设某台 Mac 的路径。每篇默认只跑一轮，不加载编程工作流或无关技能。

需要采集公开网页正文、官方新闻或博客时，按需读取 `skills/xhs-web-crawl/SKILL.md`。小红书站内继续复用现有采集器；完整上游Scrapling文档只在高级用法需要时读取。

需要X帖子/回复、YouTube视频信息/字幕/评论时，按需读取 `skills/xhs-social-sources/SKILL.md`。各工具按平台分工，只运行当前任务所需来源；多来源原始资料分别存 sources.*.json，再由工具合并。
