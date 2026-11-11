# 给 Coder 和协调者：真实验证与返工

先读 handoff、独立审查材料和当前实现。核对 code_files 是否完整以及 review.snapshot 是否仍匹配；不匹配先回到独立审查。

从项目根用 `python3 .workflour/check.py test -- CMD ARG...` 执行本轮实际测试，不使用模型自述或历史输出充当证据。针对当前快照保留每条有效命令的最新真实结果和证据；历史失败不抹除。将需求覆盖、命令、退出码、输出和未验证项写入 verification.md。

失败时写 blockers，退回 implement 修复，之后重新审查和重跑。成功后运行阶段 check 并生成 HANDOFF.md。协调者独立核对实际结果，再交给 Doc；不要把技术通过写成用户已验收。
