# {{PROJECT_NAME}}

这是多 Agent 项目的初始目录，尚未生成产品代码，也未完成任何项目验收。

先阅读 [PROJECT-WORKFLOW.md](PROJECT-WORKFLOW.md)。项目采用固定版 GitHub Spec Kit 1.3.2 中立脚手架：先写需求与验收条件，再规划任务、实现、独立审查、测试、文档和用户验收。

默认不会创建 Git 仓库、启动 Agent、调用模型或修改已有账号、模型和 skills。Codex、Harness、Antigravity 或其他 Agent 都应从同一个工作目录读取相同的持久交接文件，按 `.workflour/handoff.json` 的 workflow.kind 执行：manual 手动接力，code-team 由工作台「项目总控」自动组织已授权的工作。

来源和许可见 [.workflour/SOURCES.md](.workflour/SOURCES.md)。
