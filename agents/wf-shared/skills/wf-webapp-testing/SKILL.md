---
name: wf-webapp-testing
description: "Exercise a real running web app with available browser tools and preserve desktop/mobile screenshots, interaction results and limitations."
license: Apache-2.0
---

# Webapp Testing · Workflour

用于已有可运行页面的预览或成品检查。初案评审阶段只对会改变方案的具体疑点做最小验证，不创建一套假想产品或浏览器实验集。

复用 [CAPABILITIES.md](../../CAPABILITIES.md) 中已实测的能力和 [BROWSER.md](../../BROWSER.md) 中的 Playwright 入口、隔离方式与视口设置。仅在实际调用失败、环境变化或明确缺少所需能力时定向诊断，不重新探测安装、改写 CDP 或重复能力探针。先确认本次目标 URL、现有服务和检查范围。不得停止或替换既有用户服务；自己启动的测试服务记录 PID 并在结束时清理。

导航后等待明确可见元素或应用就绪状态；长连接页面不要强制等 networkidle。先检查渲染 DOM/界面，再选择真实存在的定位器操作。早期预览围绕一处关键方向给简短反馈；正式成品体验覆盖约定验收路径、关键错误处理、键盘及桌面/手机布局。记录相关 console/pageerror 和实际结果，已有充分证据后结束本阶段，不继续增加无关实验。

复审复用有效浏览器脚本，优先已有缺陷复现与受影响回归；新的具体风险才补检查。每个用例先明确 fixture 初始数据和预期状态变化，核对有效条目、计数与操作目标。优先用可访问角色、名称、状态和可见结果断言行为；样式状态确需检查时用相关 class token 或实际计算样式，不比较整段 className 的空格和顺序。除非文本逐字相等本身就是验收要求，不用偶然的实现字符串替代用户语义。失败要区分产品问题与探针预期错误，修正后保留原失败原因与范围，不能把修探针写成修产品。

保存桌面/手机截图，必须用运行时真实读图能力检查视觉；多模态模型目录不证明插件传图成功。缺浏览器、无法打开截图或关键路径受阻时，明确回传 blocked 和缺失能力，不能用单元测试或主编码自述替代体验通过。

证据写入当前项目 records/plan-review 或测试证据目录，关联当前快照、URL、视口、步骤、期望与实际。格式遵循项目 PLAN-CODE-WORKFLOW.md；没有观察到的交互不要编造。上游辅助启动脚本仅留作来源，本适配不默认安装依赖或执行外部脚本。

来源与改动见 [SOURCE.md](SOURCE.md)。
