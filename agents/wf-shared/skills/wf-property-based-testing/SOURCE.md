# 来源与适配

- 原作者与项目：Trail of Bits，`skills` 项目的 `property-based-testing`。
- 固定版本：`e4dd0bb5b15535f7c5a0834187dffba6ac37e4ff`。
- 原文：[SKILL.md 与参考目录](https://github.com/trailofbits/skills/tree/e4dd0bb5b15535f7c5a0834187dffba6ac37e4ff/plugins/property-based-testing/skills/property-based-testing)。
- 许可证：[CC-BY-SA-4.0](LICENSE)，保留上游全文；本目录的改编技能与参考同样采用 CC-BY-SA-4.0，不据此改变仓库其他独立文件的许可证。[上游许可证](https://github.com/trailofbits/skills/blob/e4dd0bb5b15535f7c5a0834187dffba6ac37e4ff/LICENSE)。
- 原文副本：[property-based-testing](../../../../integrations/openmausbot/team-v2/sources/trailofbits/property-based-testing/)。
- 适配日期：2026-11-11；改写者：Workflour 项目维护者。

改动：中文重写并聚焦通用 Python/JavaScript 工作流，按编写和复核/失败归因渐进加载。移除 effort 元数据、固定属性强度排名、智能合约专用内容、强制重构与统一严重度。补充契约和前置条件、往返共享缺陷、部分属性不足、生成器有效样例、变异输入隔离、明确错误拒绝与普通回归的关系。沿用现有库与框架；没有专用 PBT 库时，准确说明实际进行的有限示例、枚举、抽样或输入生成。不自动安装依赖，不声称未执行的覆盖或自动缩减。

可由 DSH 或 Antigravity 读取 Markdown，不依赖 Claude 专有工具，不修改角色或模型设置。检查性质并不以安装专用库为前提；专用框架及其自动缩减等能力则需要相应依赖和实际执行证据。这里只提供方法，不能据此宣称当前环境已经安装或执行这些库。

原文 SHA256：

| 文件 | SHA256 |
| --- | --- |
| `SKILL.md` | `9448cacb65c6237a7c22dc59602667177ecae405524079ae9ff92240590b995a` |
| `references/generating.md` | `c0e72dfc89babe3c32de718b81b94044362c85e776d7475e950dfeaab78bb58e` |
| `references/reviewing.md` | `110b08118a1e7b1a2566def6e9d2a0bf43fc2deefce857d2ce3b4382b07bc774` |
| `references/interpreting-failures.md` | `dbae7db8773712ba03268a3d56ea5aa6720af0650a5189580bfd88aa2edc3f9a` |
| `references/refactoring.md` | `6eb5c206f575704791f089608bb06e41d6eed91b9d3c7fb27912f969aed07a18` |
| `references/libraries.md` | `f7218acf8e668130ef3048983472579d04e12030c5401926f666363e5f69c686` |

- 2026-11-11 独立前向复核：澄清覆盖结论仅对应实际输入；幂等关系有效但不是完整正确性证明，测试库与方法本身须区分。
