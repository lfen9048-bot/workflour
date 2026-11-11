# 来源与适配

适配日期：2026-11-11。作者：Workflour 项目维护者。

| 来源 | 固定版本与文件 | 原文件 SHA256 |
|---|---|---|
| Impeccable | [`critique.md`](https://github.com/pbakaus/impeccable/blob/c1e0e5492fbb524f5df84d635ecfae7dc438ec45/.agent/skills/impeccable/reference/critique.md)，提交 `c1e0e5492fbb524f5df84d635ecfae7dc438ec45` | `2ce5de79ab31016f1f0b34dea2eac6149e0df4a9e65edfaac2e1712bb9b7d19f` |
| Vercel Web Interface Guidelines | [`command.md`](https://github.com/vercel-labs/web-interface-guidelines/blob/434b7f91364665f2f733b310ec54809bf8f37937/command.md)，提交 `434b7f91364665f2f733b310ec54809bf8f37937` | `d246b026f4f29b5823a9cc857f9edf3d2507002e055e32040cadeaf3b38e0234` |

许可：Impeccable 为 Apache-2.0，原许可保存在 [LICENSE](LICENSE)；Vercel 指南为 MIT，含版权声明的原许可保存在 [LICENSE-MIT](LICENSE-MIT)。本目录包含两者改编内容，应保留两份许可和来源说明。

本地原文：[Impeccable](../../../../integrations/openmausbot/team-v2/sources/impeccable/critique.md)、[Vercel](../../../../integrations/openmausbot/team-v2/sources/vercel-guidelines/command.md)。来源原文用于审计，不在每次执行时全量加载。

改动：将认知负担、用户控制、状态反馈、一致性、错误恢复与视觉层级方法重写为中文阶段参考；Vercel 仅选取键盘、可访问名称、焦点、长内容和状态提示等相关原则。按初案、关键预览、真实最终体验和局部复审分别加载。

未移植：上游双子 Agent 编排、浏览器注入/overlay、检测器命令、固定十维评分、独立报告或快照系统、强制追问，以及逐项全量规则审计。没有引入额外二进制、MCP 或浏览器框架。使用项目已有工具、证据目录和返工预算；不扩大角色权限。
