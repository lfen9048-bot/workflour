# 来源与适配

- 原作者与项目：Anthropic，`claude-plugins-official` 的 `pr-review-toolkit`。
- 固定版本：`43fd1f9db0941b2b83cb62268e35970d4a67c202`。
- 原始材料为 Claude 插件的 Agent Markdown，而非独立 SKILL.md；本目录是方法适配，不要求安装 Claude 插件。
- 原文：[pr-test-analyzer.md](https://github.com/anthropics/claude-plugins-official/blob/43fd1f9db0941b2b83cb62268e35970d4a67c202/plugins/pr-review-toolkit/agents/pr-test-analyzer.md)、[silent-failure-hunter.md](https://github.com/anthropics/claude-plugins-official/blob/43fd1f9db0941b2b83cb62268e35970d4a67c202/plugins/pr-review-toolkit/agents/silent-failure-hunter.md)。
- 许可证：[Apache-2.0](LICENSE)，本地保留上游全文；[上游许可证](https://github.com/anthropics/claude-plugins-official/blob/43fd1f9db0941b2b83cb62268e35970d4a67c202/plugins/pr-review-toolkit/LICENSE)。
- 原文副本：[anthropic-pr-review](../../../../integrations/openmausbot/team-v2/sources/anthropic-pr-review/)。
- 适配日期：2026-11-11；改写者：Workflour 项目维护者。

改动：中文重写并合并行为覆盖审核与错误路径方法；仅在相关代码变化时加载错误路径参考。允许本地差异和无基线的新项目，不要求 PR、Claude Task 工具或额外代理；移除 model/color 配置与固定监控依赖。严重度按实际用户影响，不把正常取消、可选缺失或所有捕获都判为缺陷；区分已复现问题与覆盖缺口，保留最小复现、角色写入边界和现有测试框架。

可由 DSH 或 Antigravity 按本项目的角色技能索引读取 Markdown；技能文本不选择模型、思考档位或运行时，不宣称已完成部署后的真实模型验证。

原文 SHA256：

| 文件 | SHA256 |
| --- | --- |
| `pr-test-analyzer.md` | `fcb1cde9ba7b21694b508766a8d6a79bc91bed9982f828f816210059934f46b4` |
| `silent-failure-hunter.md` | `fa9b0daec5a267e7e66435cc48b3328301fc9f70c3af259fe248881327a1babc` |

- 2026-11-11 实跑反馈：增加证据充分后停止及单次结论汇总，减少同一判断的重复证明；当前任务的输出位置优先于角色默认记录位置。

- 2026-11-11 独立前向复核：澄清覆盖结论仅对应实际输入；幂等关系有效但不是完整正确性证明，测试库与方法本身须区分。
