# 给 Gemini：独立审查

先读 AGENTS、PROJECT-WORKFLOW、handoff 和当前 spec / plan / tasks。你是本轮默认独立审查者；只读实现，仅写本轮 review.md 和相关审查字段，不改实现、测试或依赖。

依据真实文件和需求检查实现、错误处理、边界行为、测试有效性和范围变化。用 `python3 .workflour/check.py snapshot` 取得当前 code_files 快照，写入 review.snapshot。逐项问题说明编号、严重程度、具体文件/行号、证据、影响和建议。

存在未处理问题时不得写 passed；Coder 修复后独立复核至 verified。接受例外必须有清楚 resolution，标 waived。没有发现问题也记录审查范围和未验证项。更新交接并停止，等待协调者手动接力。

审查开工前核对的是上一已完成阶段（`--stage implement`），不要要求待产出的review已通过。若协调者负责保存材料，可只返回带文件/行号、证据和结论的审查报告，由协调者按已有handoff结构记录；不需要另造或全库搜索JSON schema。
