---
name: wf-systematic-debugging
description: "Reproduce failures, locate the failing boundary, test a specific cause, and verify the smallest justified repair."
license: MIT
---

# Systematic Debugging · Workflour

先读实际错误与退出码，用最小输入复现。区分网页连接、ACP 会话、模型请求和额度错误；等待慢不等于断线，断线不等于额度不足。对多层问题检查失败边界的输入/输出和最近变动，不输出密钥或整份环境。

提出一个可证伪原因，改变最少变量验证；从坏值反向追到产生处。修复后重跑原始失败路径及受影响回归。未复现或外部故障时写清证据与缺失，不能假装修好。持续失败带已尝试方案回报 Plan 负责人，由共同的返工预算控制，不私自开启无限循环。

需要更细的追踪方式时读 [root-cause-tracing.md](references/root-cause-tracing.md)；需要修复多层防线时读 [defense-in-depth.md](references/defense-in-depth.md)；异步条件等待见 [condition-based-waiting.md](references/condition-based-waiting.md)。这些参考中的外部工具或流程名称只是上游示例，执行仍服从当前项目。

来源与改动见 [SOURCE.md](SOURCE.md)。
