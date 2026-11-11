# 来源与维护

本模板复用了 GitHub Spec Kit **v1.3.2** 的 `none` 中立脚手架，固定提交：

`55264c2f2f2d1146f02abc543cb913dcdf1f9342`

- [固定版本源码](https://github.com/github/spec-kit/tree/v1.3.2)
- [2026-11-06 发布记录](https://github.com/github/spec-kit/releases/tag/v1.3.2)
- [中立集成说明](https://github.github.io/spec-kit/integrations/none.html)
- [Harness 集成及其 headless 路由](https://github.github.io/spec-kit/integrations/dsh.html)
- [Antigravity 集成及技能目录](https://github.github.io/spec-kit/integrations/agy.html)
- [原始 MIT 许可](https://github.com/github/spec-kit/blob/v1.3.2/LICENSE)

`.specify/` 中的 20 个中立文件由固定版官方 `specify init PROJECT --integration none --script sh --non-interactive` 生成并原样保留；没有带入研究时的 feature、`specs/` 或 `.specify/feature.json`。原始 MIT 许可保存在 `vendor/spec-kit/LICENSE`，来源及每个复用文件的 SHA-256 在 `vendor/spec-kit/source.json`。

本地增加了七阶段手动协作说明、按角色提示、审查/验证/文档/验收模板和交接检查工具。这些补充不是 Spec Kit 官方功能，也不改变既有 Harness profiles 或技能目录。

升级时先在隔离目录生成新版本、比较变化并重新验证；不要用 main 或浮动 latest 直接覆盖项目。上游自动 workflow 的 dsh 适配使用通用 headless profile，因此当前保留中立集成，沿用已配置的 OpenMausBot ACP 角色手动接力。
