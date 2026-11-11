# 原生派单要点

- 标题：职责 · 任务编号 · 简短任务名；新项目创建独立会话，确认真实 cwd。
- 保留用户原话和项目绝对目录、阶段、职责、验收标准、共享材料及允许写入的文件范围。
- 带负责人 claim 返回的真实 WF-DISPATCH 标记；派单工具返回后保存真实 assignment_id。
- 受派者只更新自己的记录和被授权代码，不改共享 handoff/coordination；通过原派单回传。
- 提供完成证据、测试记录、失败/停止/能力受阻原因与下一步。不把调用成功当作任务通过。
- Code 测试用 check.py test --files 实际代码文件 --files 测试文件 -- COMMAND，默认 detached；将打印的 test_record 路径回传负责人导入。
- Plan 体验审查按 experience.example.json 留下真实浏览器证据；缺少工具就明确 blocked。
