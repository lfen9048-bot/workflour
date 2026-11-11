---
type: decision
status: accepted-scope-pending-implementation
created: 2026-11-06
updated: 2026-11-06
---
# OpenMausBot 首轮范围与主入口

## 用户确认的选择

2026-11-06，用户在规划问答中选择：首轮双 Agent＋手机；新工作主要在 OpenMausBot 查看，原 Harness 历史保留；手机使用网页；通过内置 HTTPS 连接；Coder 与 Doc 先手动接力。之后用户说明由 Gemini 实施，要求本助手把计划写详细。

这调整了最初“原 Harness 桌面集中查看所有 CLI 记录”的首轮验收要求：新会话以 OpenMausBot 为主，不再要求两边同时显示；旧历史不迁移、不删除。

## 技术方案的状态

使用固定版 CLI 服务、两个新增 ACP profiles 和 customAcp 的方案来自助手设计及只读核对，见 [03-设计/2026-11-06-OpenMausBot双Agent与手机接入实施计划](../03-%E8%AE%BE%E8%AE%A1/2026-11-06-OpenMausBot%E5%8F%8CAgent%E4%B8%8E%E6%89%8B%E6%9C%BA%E6%8E%A5%E5%85%A5%E5%AE%9E%E6%96%BD%E8%AE%A1%E5%88%92.md)。具体兼容性、模型请求、持久化续聊与手机连通均待 Gemini 实施验证，不得把范围确认等同于运行成功。

本轮不扩展 Antigravity、自动调度或远控能力。后续需求仍逐步讨论。

## 关联

- [首页](../%E9%A6%96%E9%A1%B5.md)
- [01-需求/目标与待定事项](../01-%E9%9C%80%E6%B1%82/%E7%9B%AE%E6%A0%87%E4%B8%8E%E5%BE%85%E5%AE%9A%E4%BA%8B%E9%A1%B9.md)
- [04-搭建/2026-11-06-形成OpenMausBot实施交接](../04-%E6%90%AD%E5%BB%BA/2026-11-06-%E5%BD%A2%E6%88%90OpenMausBot%E5%AE%9E%E6%96%BD%E4%BA%A4%E6%8E%A5.md)
