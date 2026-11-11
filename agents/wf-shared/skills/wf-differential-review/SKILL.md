---
name: wf-differential-review
description: "Independently review changed code, callers and tests for concrete regressions; fall back to requirements review when no baseline exists."
license: CC-BY-SA-4.0
---

# Differential Review · Workflour

先确定实际代码快照和可用基线。已有项目按差异追相关调用者、输入和状态变化；新项目没有历史基线时直接对照用户需求、PLAN 与实际完整代码，不伪造 git diff，也不因没有 Git 拒绝审核。

优先检查会破坏用户路径的行为、输入边界、错误处理、状态/数据保存、权限和新增外部调用。风险决定深度，不因改动小就跳过关键逻辑。运行能验证结论的独立测试，检查测试本身是否捕获真实行为。需要高风险模式时读 [patterns.md](references/patterns.md)，威胁路径方法见 [adversarial.md](references/adversarial.md)。

返工后的复审从本轮实际 diff、已有发现的复现步骤和受影响路径开始。复用已经检查有效的测试和探针，在当前快照重跑需要的检查；独立判断不要求重写一套测试。仅对尚未覆盖的具体新风险补充最小验证，并说明它与本轮改动或已有发现的关系。不要把每次复审扩成重复的完整探索；若差异或新证据暴露更广风险，仍应扩大相应检查。

探针失败先核对 fixture 的初始状态、有效数据和操作后预期，再判断业务行为。断言用户可观察结果或明确语义，避免无关实现字符串精确匹配。测试自身预期写错应单独记录并修正，不列为业务缺陷，也不能随实际输出改低正确的验收标准。

在 records/code-review/ 写简短审核：被审快照、覆盖范围、实际命令/结果、逐项可复现缺陷、结论与剩余限制。结论为通过/需修复/受阻；测试通过不代表体验通过。普通审核不启动完整安全审计或额外代理，不替主编码修业务代码。

来源与改动见 [SOURCE.md](SOURCE.md)。
