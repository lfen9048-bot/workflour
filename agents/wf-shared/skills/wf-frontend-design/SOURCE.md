# 来源与适配

适配日期：2026-11-11。作者：Workflour 项目维护者。

| 来源 | 固定版本与文件 | 原文件 SHA256 |
|---|---|---|
| Anthropic frontend-design | [原技能](https://github.com/anthropics/skills/tree/2c5958ecac7cee2b583967a2c4981d0f4a75c579/skills/frontend-design)，提交 `2c5958ecac7cee2b583967a2c4981d0f4a75c579` | `d91970639e9f5c37682ac7ab60094d35f1c7c1f38d731bd56396563aee10c1d3` |
| Impeccable | [`polish.md`](https://github.com/pbakaus/impeccable/blob/c1e0e5492fbb524f5df84d635ecfae7dc438ec45/.agent/skills/impeccable/reference/polish.md)，提交 `c1e0e5492fbb524f5df84d635ecfae7dc438ec45` | `b5f4fbb4a044c3f5ec14adc847222488f00fccabbf79ecd0b21084c8d319d616` |

许可证均为 Apache-2.0；保留原有 [LICENSE](LICENSE)，新增 Impeccable 原许可 [LICENSE-IMPECCABLE](LICENSE-IMPECCABLE)。本地原文：[Anthropic](../../../../integrations/openmausbot/team-v2/sources/anthropic/frontend-design/)、[Impeccable polish](../../../../integrations/openmausbot/team-v2/sources/impeccable/polish.md)。来源原文用于审计，不在每次执行时全量加载。

保留原有短设计入口，按已有职责与原生交接工作。新增视觉收尾参考，提炼 Impeccable 的保留既有设计、功能与状态优先、整体路径一致、最小正确修复和实际渲染验证方法。新页面或重要方向变更保留关键预览，局部修复不自动重新设计或再次咨询。

未移植上游 context/detector/hooks、critique-storage 命令、独立快照账本或额外子 Agent。收尾复用现有浏览器证据，只覆盖相关改动，不要求运行完整长清单；不代替独立审核、Plan 体验检查和用户验收。
