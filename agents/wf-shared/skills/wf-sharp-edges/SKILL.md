---
name: wf-sharp-edges
description: "Review consequential API and configuration choices for misleading defaults, silent failure, and misuse risks; use product evidence for UX critique."
license: CC-BY-SA-4.0
---

# Sharp Edges · Workflour

只分析本次方案或改动确实暴露的选择点：默认值、边界输入、相似选项、开关组合和失败提示。先说明哪条用户路径会受影响，再核查容易走的路径能否得到预期结果。不要把参考分类变成每个小项目都要遍历的清单。给出具体触发条件、证据、影响和建议。

用与当前阶段匹配的证据核实发现。初案阶段检查已有来源、用户目标和必要约束，把尚未实现的边界写成明确编码/验收建议；只有决定可行性的真实疑点才需要最小实验。收到实际网页预览或成品后再按需使用 wf-webapp-testing。风险分类不自动扩大为完整安全审计、视觉检查或额外原型开发。

按需查 [配置模式](references/config-patterns.md)、[认证模式](references/auth-patterns.md)、[密码 API](references/crypto-apis.md)、[语言索引](references/language-specific.md)。这是 Trail of Bits 方法的 Workflour 适配版；保留原许可，外部 agent 名称不构成本机可用工具。

来源与改动见 [SOURCE.md](SOURCE.md)。
