---
name: wf-test-driven-development
description: "Use meaningful behavior tests and a red-green loop for nontrivial logic or bug repairs, without discarding existing code."
license: MIT
---

# Test Driven Development · Workflour

先列出用户可观察行为和关键失败输入。复杂逻辑或修 Bug 时，先建立能捕获缺陷的最小测试，确认因预期原因失败，再修实现并确认通过。已有实现不因测试顺序而删除；用当前实现补真实回归覆盖。

测试应调用真实生产入口，断言结果或副作用，避免断言代码字符串、复制算法、只测 mock。纯文字、低影响可逆配置和视觉微调通常直接验证实际结果，不为凑数加测试。完成后运行受影响测试和项目要求的检查；只有新改动、失败或未决风险才扩大/重复测试。

测试输出保存命令、cwd、退出码和代码快照。网页交互与视觉需要真实浏览器证据，单元测试不能替代。写测试时可按需读 [writing-good-tests.md](references/writing-good-tests.md)。

来源与改动见 [SOURCE.md](SOURCE.md)。
