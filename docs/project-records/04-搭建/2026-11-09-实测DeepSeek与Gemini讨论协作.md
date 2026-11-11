---
type: build-log
status: core-trial-verified
created: 2026-11-09
updated: 2026-11-09
---
# 实测 DeepSeek 与 Gemini 讨论协作

用户在讨论设计后明确“好，你试试看”。本轮实际完成独立编码角色、项目群、真实咨询、代码修复、独立审核、结果回传、公告及完成后重启验证。不是只读调研，也没有据此创建后台常驻Codex总控。

## 实际改动

- 新增 `omb-deepseek-coder` profile/instance，模型 `workbuddy/deepseek-v4.1-flash`，独立自动skill `code-collaboration`；仍用同一Harness0.2.1-rc.2和原resume bridge，不安装另一版软件。
- `run-acp-agent.sh`支持deepseek-coder；`setup.sh --only deepseek-coder`只生成该角色，默认setup仍维护原有角色。运行配置账号状态留在用户目录，新增文件私有权限。原GLM Coder/Doc/Antigravity实例及原6个基线文件核对未变。
- 实际新增Bot **DeepSeek Coder**，保持ask；新增群 **Code 协作演练**，成员为DeepSeek Coder/Gemini，默认仅点名响应，工作目录 `examples/discussion-demo`。原Bot默认配置和原聊天选择保留。
- 当前Codex窗口用本地控制接口安排演练、核对审批与证据、独立运行测试；没有冒充群内常驻Bot。
- 新增只读审计工具 `tests/omb-discussion-audit.py`，按指定话题导出协调状态白名单；不保存任务正文、原始native参数、凭据或模型思考。

## 演练与结果

题目是合法整数端点的左闭右开时间段重叠判断。故意保留旧实现把相邻区间误判为重叠的缺陷；原2个测试通过，协调者先独立复现反例。

1. DeepSeek真实调用coordinate_bots咨询Gemini；Gemini给相邻端点反例；系统自动恢复DeepSeek总结，未人工搬运回复。
2. DeepSeek新增9个测试，11项中3项失败并保留evidence/before.txt；修改比较条件后11项全过，保留after.txt。
3. DeepSeek真实委派Gemini独立审核；Gemini读取实际文件、运行测试后PASS；结果再次自动恢复DeepSeek。Gemini的4个具体本地命令审批逐次allow-once，未放宽为full/always。
4. Codex独立执行11项测试通过，核对审查/代码快照相同、原2个测试AST保留。审核回复里“所有边界均已验证”的措辞超出11项用例能证明的范围，记录中明确不作为穷尽证明。
5. DeepSeek在新私聊任务调用post_to_room：群中只新增1条公告，39秒观察窗口内没有Gemini新消息或群运行；源码也确认该接口不启动成员。
6. 全部空闲后重启launchd托管服务；群字段、52条消息ID与内容哈希保持相同，本机/公网正常。未在委派进行中重启。

runtime.db只读元数据确认：咨询和审核各只有1个子请求、各执行1次、completed；两次结果inbox均delivered，两个父请求均有resume_due并执行2次。真实模型和agents/data MCP连接由脱敏协议字段核对。

## 文件与证据

项目根目录 `<WORKFLOUR_ROOT>`：

- `integrations/openmausbot/DEEPSEEK-CODER.md`、`DISCUSSION.md`：使用入口和边界。
- `examples/discussion-demo/HANDOFF.md`、`.workflour/discussion.json`：试验结论和下一步。discussion.json是独立试验元数据，不冒充完整项目检查器schema。
- `tests/evidence/discussion-20261109/summary.json`：总结果；coordination-audit.json：真实委派/回传；consult-complete.json、implement-complete.json：群证据；model-and-mcp.json：脱敏模型/连接字段；announcement-verification.json、restart-verification.json：公告与重启。
- 新角色3项离线回归通过；此前工具包合计37项回归通过；新只读审计工具另3项测试通过。新角色真实ACP握手通过，证据 `tests/evidence/acp-smoke-20261109-213314.json`。

## 停止位置和下一项

核心讨论/编码/审核往返已验证，Bot和演练群保留可查看，服务正常且任务空闲。正式项目仍由Codex当前会话推进阶段。可复用这条路径做真实项目；后续若要无人值守，需要另行接入持续总控并验证进行中重启、中断/排队边界、程序级议题轮数限制。未自动验收原workflow-demo，也未升级OpenMausBot或修改VPS服务。

关联：[首页](../%E9%A6%96%E9%A1%B5.md)、[03-设计/2026-11-09-Code工作流Bot讨论设计](../03-%E8%AE%BE%E8%AE%A1/2026-11-09-Code%E5%B7%A5%E4%BD%9C%E6%B5%81Bot%E8%AE%A8%E8%AE%BA%E8%AE%BE%E8%AE%A1.md)、[05-验证/2026-11-09-Bot讨论与交叉审核实测](../05-%E9%AA%8C%E8%AF%81/2026-11-09-Bot%E8%AE%A8%E8%AE%BA%E4%B8%8E%E4%BA%A4%E5%8F%89%E5%AE%A1%E6%A0%B8%E5%AE%9E%E6%B5%8B.md)。
