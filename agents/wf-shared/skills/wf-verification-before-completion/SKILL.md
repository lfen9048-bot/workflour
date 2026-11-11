---
name: wf-verification-before-completion
description: "Check claims against actual artifacts and tests for the current code snapshot; distinguish technical pass from user acceptance."
license: MIT
---

# Verification Before Completion · Workflour

先确定本次交付阶段，再核对其所需证据。初案评审需要意见文件和相关依据；早期预览需要实际关键页面观察；正式技术审核需要当前代码及测试；最终体验需要当前成品的实际操作与视觉证据。阶段完成不要求提前取得后续阶段的全部产物，也不需要重新研究检查器内部实现。

完成声明与证据范围一致：实际文件/差异、相关命令及退出码、当前快照、需要的浏览器观察各证明其对应结论。不能把 worker 自述、模型目录名称或服务已启动当作运行成功。本机已验证工具能力复用 [CAPABILITIES.md](../../CAPABILITIES.md)，具体产品结论仍依据当前产物。

同一快照的有效证据可复用，不为每条进度消息重跑测试。代码变化、环境变化影响结论或证据过期时重验相应部分。记录范围和没检查的事项；受阻给出具体原因，不能把未验证标通过。

技术审核、实际体验、用户最终验收分别报告。只有用户能确认最终验收；团队完成时停在待用户验收。停止/失败先对账，不按超时猜测重新派单。

来源与改动见 [SOURCE.md](SOURCE.md)。
