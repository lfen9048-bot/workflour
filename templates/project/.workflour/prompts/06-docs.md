# 给 Doc：配套文档

先读 AGENTS、handoff，以及实际 spec / plan / tasks / review / verification。只修改文档，保留代码和当前实现快照。

编写用户能使用的说明：用途、要求、安装/运行命令、真实示例、错误情况、已知限制。核对命令和输出；无法执行则写明未验证，不照抄模型断言。用 documentation.md 记录实际改动文档路径及核对结果，更新 handoff 的 docsartifact 和下一步。

发现代码问题时记录 blockers 并交回 Coder；不要在文档阶段悄悄改代码，也不要提前写用户验收通过。结束交给协调者准备验收。
