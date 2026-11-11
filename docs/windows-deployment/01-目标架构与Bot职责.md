# 当前架构与七个 Bot

更新：2026-11-11。本章取代历史 8 Bot、Code Team 总控＋三位规划者的部署目标。

## 一条完整流程

```text
使用者 → OpenMausBot 网页 → 大管家
                             │ 原生委派，保留真实回执
                             ▼
                    Plan · 项目负责人
                    调研、初案、共享状态
                             ↕
                    Plan · 方案与体验评审
                    核查依据、给具体改进意见
                             │ 负责人定稿
                             ▼
                    Code · 主编码（Gemini）
                    技术设计、完整实现、自测
                      ↔ 协作编码（独立子任务才加入）
                             ▼
                    Code · 独立审核
                    当前代码、测试、错误处理
                             ▼
                    Plan · 实际体验与目标核对
                             ▼
                    Plan 交付 → 大管家汇报 → 用户验收

6 个 DSH profile → WorkBuddy 模型/额度与既有 DeepSeek API
1 个独立 Antigravity CLI → Google 模型通道
项目文件保存共享上下文；各角色 records 隔离；Obsidian 观察进度
```

Bot 是职责和对话入口，profile 是配置；不需要下载七份模型或安装六个 DSH 版本。WorkBuddy 是调用与额度通道，执行任务的仍是 DSH。Antigravity 是另一运行时。

## 默认模型与路径

以 `integrations/openmausbot/team-v2/roles.json` 为机器可读角色清单；Windows 生成新的 Bot ID，重写文件路径。下表是部署目标，目标机必须核对目录、档位与真实调用。

| Bot | 实例／运行时 | 默认模型 | 思考 | 主要职责 |
| --- | --- | --- | --- | --- |
| 大管家 | `omb-wf-manager`／DSH | WorkBuddy DeepSeek V4.1 Flash | Low | 接单、转交 Plan、汇报与设置 |
| Plan · 项目负责人 | `omb-wf-plan-lead`／DSH | WorkBuddy Kimi K3.1 Pro | High | 调研、初案、定稿、协调交付，唯一共享状态维护者 |
| Plan · 方案与体验评审 | `omb-wf-plan-review`／DSH | WorkBuddy DeepSeek V4.1 Flash | High | 核查方案和依据，最终真实体验 |
| Code · 主编码 | `agy-gemini`／Antigravity | Gemini 3.8 Flash | High | 技术设计、完整实现、自测、返修 |
| Code · 独立审核 | `omb-wf-code-review`／DSH | WorkBuddy GLM-5.3-Flash | High | 独立技术审查、回归和测试证据 |
| Code · 协作编码 | `omb-wf-code-helper`／DSH | WorkBuddy DeepSeek V4.1 Flash | High | 有明确独立范围时按需加入 |
| 通用助手 | `omb-wf-assistant`／DSH | WorkBuddy DeepSeek V4.1 Flash | Low | 临时讨论、资料与模型设置 |

职责源分别是 `agents/wf-角色/SOUL.md`、`SKILLS.md`、`skills/wf-角色-role/SKILL.md`。专业技能在 `agents/wf-shared/skills/`，按需读取，不让每个 Bot 加载整套开发技能。许可证、来源和必要引用一并保留；不可再分发的本地技能不能悄悄复制到公开仓库。

角色不绑定模型。模型菜单 ID 用 ACP 实际返回值，不拼猜编码。同名模型还需区分区域、运行时和额度来源；目录显示不证明可调用。

## 每层只做自己的工作

**大管家**保持轻量：转交一个 Plan 负责人任务后结束回合，等待原生回传；进度依据 Plan 阶段账本、汇总和证据索引。它不自行读业务源码、计算代码哈希、重跑测试或做第二次审核。信息冲突交 Plan 核对，阶段返回不能说成全部完成。

**Plan 负责人**保留用户原话、来源、目标、验收条件及假设，维护共享状态；技术内部文件结构让主编码决定。初案与定稿是负责人自身工作，用 `record` 留证，不向自己派单、不伪造回执。Plan 评审给针对性意见，不重新写另一套长计划，不每次重探已验证工具。

**主编码**通常独立完成产品。只有清楚的独立文件或任务范围才启用 helper。网页首次关键页面可用时，主编码对非祖先的 Plan 评审做一次原生 preview consult，返回后继续同一实现任务；方向反馈不是最终体验通过。

**独立审核**检查实际需求、当前代码、测试与差异。复审优先真实 diff、原问题复现和受影响回归，复用有效探针；有具体新增风险再补检查，不每轮重做一套。断言面向用户行为和明确 fixture，不机械比较完整 CSS 字符串。

**最终体验**由 Plan 评审实际操作成品。网页保存桌面／手机截图和交互证据，截图须被图像工具读到才能宣称视觉判断。未使用浏览器不等于没有浏览器能力。纯 CLI 项目可明确设 `product_surface:cli`，保留真实命令、输出和逐需求观察，不能用 CLI 证据替网页通过。

## 持久流程与限制

账本阶段：`research → plan-review → plan → implement → review → experience → acceptance`。详细接口见 [PLAN-CODE-WORKFLOW](../../integrations/openmausbot/PLAN-CODE-WORKFLOW.md)。

- 新任务独立原生会话，共享项目需求、计划、交接；各角色写 `records/<role>/`。Plan 独占共享账本和 handoff，Code 返回 detached 测试记录，由 Plan 导入。
- 原生 `coordinate_bots` 才派单；`post_to_room` 仅公告。真实 assignment ID 与 thread ID 分开，不能互换。
- 方案最多两轮、preview 最多一次、技术与体验返工共用两轮；失败/停止的恢复 retry 按阶段角色最多一次，不能清账本重置预算。
- 运行中补充可能成为同 worker 的新 queued 回执，必须登记 supplement。主单及全部补充都完成、最新测试有效后才复审；补充失败不能重派整个主任务。
- 代码变更会使旧审核／测试快照失效。最终保留 `acceptance.status:pending`，只有用户确认才通过。
- 普通问题直接答；问进度不授权重派；停止后要核对对应停止之后的明确继续来源。

## 设置和权限

所有七个 Bot 都可选择已接入且可用的模型和真实思考档位。用大管家／助手的模型设置卡区分“当前任务”和“以后默认值”；顶部原生菜单可能修改默认，不冒称它只改当前任务。忙碌任务先完成或用户停止。跨 DSH／AGY 新建任务并读取交接、保留旧聊天；原生 Ask 审批限制不能绕过，也不能冒称自动继承 Full。

正式团队按用户授权使用 Full；DSH 新会话的实际权限单独读回。Full 仍受 Windows 当前用户权限限制，不等于管理员／SYSTEM，也不是严格文件沙箱。角色职责要写入原生 Bot 设置，手动换模型后仍保留。AGY 自动发现技能未经统一保证，需实际读取自己的 SKILLS.md。
