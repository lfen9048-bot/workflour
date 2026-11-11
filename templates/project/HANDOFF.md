# {{PROJECT_NAME}}：初始交接

当前任务尚未分配，阶段为 `requirements`，由协调者整理需求，下一角色以 `.workflour/handoff.json` 的 `next_owner` 为准。尚未执行实现、审查、测试、文档或用户验收。

下一步：按 `PROJECT-WORKFLOW.md` 创建 feature，填写真实需求和验收条件，更新 `.workflour/handoff.json`，然后执行：

```bash
python3 .workflour/check.py handoff
```

执行后本文件由 JSON 重新生成。接手者以 JSON 和对应实际材料为准；不要把本初始说明当成阶段已通过。
