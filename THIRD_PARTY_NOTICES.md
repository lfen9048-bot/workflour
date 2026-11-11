# 第三方来源与许可

本仓库包含工作流自有实现、第三方技能适配和脚手架。没有给整仓库新增统一开源许可证；各上游材料按原许可证保留，适配说明见对应 `SOURCE.md`、清单或 `SKILL.md`。

| 材料 | 上游 | 许可与仓库内位置 |
| --- | --- | --- |
| 规划、调试、测试、完成验证等技能 | [obra/superpowers](https://github.com/obra/superpowers) | MIT，`integrations/openmausbot/team-v2/sources/superpowers/LICENSE` |
| sharp-edges、differential-review | [trailofbits/skills](https://github.com/trailofbits/skills) | CC-BY-SA-4.0，`integrations/openmausbot/team-v2/sources/trailofbits/LICENSE`；本地适配保留署名、许可及改动说明 |
| frontend-design、webapp-testing | [anthropics/skills](https://github.com/anthropics/skills) | Apache-2.0，两个 source 目录内 `LICENSE.txt` |
| Obsidian Markdown 技能 | [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | MIT，`integrations/openmausbot/team-v2/sources/obsidian/LICENSE` |
| Spec Kit 中立模板 | [github/spec-kit](https://github.com/github/spec-kit) | MIT，`templates/project/.workflour/vendor/spec-kit/LICENSE`、`source.json` |

固定 revision、路径、原始文件哈希和来源链接见 [技能来源清单](integrations/openmausbot/team-v2/sources/manifest.json)。共享技能的对应目录也保留了许可证和来源记录。

运行依赖 OpenMausBot、DeepSeek Harness、WorkBuddy 插件、Antigravity 等须自行从其官方渠道安装。本仓库不携带它们的已安装程序、登录凭据或订阅额度；安装与版本边界见 [Windows 来源说明](docs/windows-deployment/09-来源版本与交付边界.md)。本机 `dsh-connect-workbuddy` 5.13.1 的公开接口和 MIT 账号池规则被当前额度层复用，插件包本身没有被修改或打包上传。


2026-11-11技能补强新增来源：Anthropic knowledge-work-plugins（knowledge-synthesis、write-spec，Apache-2.0）、Anthropic claude-plugins-official PR Review Toolkit（Apache-2.0）、pbakaus/impeccable（Apache-2.0）、vercel-labs/web-interface-guidelines（MIT）和Trail of Bits property-based-testing（CC-BY-SA-4.0）。固定提交、原文件哈希和相应许可证在 `team-v2/sources`；混合衍生入口保留对应许可义务，不把上游Agent或编排规则当作已安装运行时插件。
