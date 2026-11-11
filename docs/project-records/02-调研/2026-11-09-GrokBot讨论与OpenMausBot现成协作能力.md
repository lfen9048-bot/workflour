---
type: research
status: source-verified-integration-not-tested
created: 2026-11-09
updated: 2026-11-09
---
# Grok Bot 讨论与 OpenMausBot 现成协作能力

用户希望在正式 code 工作流中加入 Bot 之间的讨论，并借鉴 Grokbot。本轮按 search-first 读取现有记录、官方文档、社区实际提示词及本机固定发行版源码；没有安装、升级、创建群组、改模型配置或发送真实 Bot 消息。

## Grok Bot 官方能确认什么

实际阅读 [Message and collaborate](https://docs.x.ai/grok-bot/chat-and-collaboration)（页面标记2026-10-29更新）和 [How Grok Bot works](https://docs.x.ai/grok-bot/how-grok-bot-works)，查阅日期2026-11-09：

- 群聊容纳2–6个Bot，支持自然讨论、@点名和回复指定消息。
- Bot之间可以异步发消息和交接；官方建议每阶段有单一负责人。
- 群内讨论与Bot私信不同，私信结果不会自动全部回到群。
- 每个Bot有自己的规则和工作记录，不能理解为所有聊天、工具结果和记忆自动共享。
- 官方没有提供禁止Bot互发消息的开关，未公开硬轮数限制；群聊和互发回复会计入用量。

官方产品是服务，不是可直接复制的开源调度器。内部队列、上下文拼接和防循环算法没有在上述文档公开，本轮不猜其实现，也不新增该服务订阅。

## 贴近代码协作的社区实例

[reichenbach/grokbot-agent-bots](https://github.com/reichenbach/grokbot-agent-bots)：实际读了README、[SETUP_PROMPT.md](https://github.com/reichenbach/grokbot-agent-bots/blob/main/SETUP_PROMPT.md)和[MIT许可](https://github.com/reichenbach/grokbot-agent-bots/blob/main/LICENSE)。未归档，调研可见最近push为2026-11-03。

它用主Bot派工、本地编码CLI执行、另一Bot审查、结果回报主Bot。强调交接要明确要求行动，普通FYI不一定唤醒下一方；同一分支三次返工后交人处理。“三次”是社区提示词规则，并非Grok官方硬限制。项目主要是可复制设置提示词，不是独立消息服务。复用其角色/交接思路，不照搬headless命令、全局权限设置、定时任务或审批要求；这些均不由本次检索自动授权。

## 本机OpenMausBot 0.1.143已有能力

当前固定发行版已提供群聊、默认响应者、@点名，以及agents MCP的coordinate_bots委派和consult咨询。post_to_room只发公告，不唤醒回复。无需先升级软件或新建消息总线。主体Apache-2.0，复用当前安装不增加新服务；模型调用仍消耗现有账户额度。

只读源码位置（根目录 `/opt/homebrew/lib/node_modules/openmausbot/dist-server/`）：

- `server/routes/groups.js`：群组创建和配置；响应者可为mentions、member、everyone、auto。
- `scripts/mcp-server.js`：外部控制面的create_channel、send_channel_message、get_channel_messages、wait等工具。
- `server/host/teammate-prompts.js`：委派结果返回原会话并恢复发起者；未完成委派不得盲目重复发送。
- `server/host/work-thread.js`：同一委派工作线程的续接边界。
- `server/drivers/acp/core.js`：customAcp支持agentsMcp。

群聊@接力存在MAX_GROUP_HOPS=1、同一轮每Bot最多一次的限制，不能把群聊当无限多轮辩论。需由主持者明确开启下一轮。customAcp群聊走legacy transcript路径，读取窗口30条；不能把之前单聊原生恢复验收等同于群聊长期上下文已验收。

正式委派还有另一套限制：`server/runtime-coordinator.js`默认最大深度4、根请求最多64个请求/96次执行，拒绝回派祖先和交叉等待，支持去重与明确rework。用户停止后有24小时重新派发拦截。这些不等同于项目可直接配置的“三轮讨论”产品开关。

`consult:true`通过任务信封要求咨询而非执行工作，但没有单独移除写文件工具或创建只读沙箱。因此“只讨论/只审核不改业务代码”是工作约束，不是强制权限隔离。正式代码审核应以带验收条件的审核任务委派，而不是把consult当作安全开关。关键实现还有`server/drivers/agents-catalog.js`、`server/runtime/envelope.js`、`server/peer-provenance.js`。

既有demo三个角色的native协议记录中，session/new/load已携带名为agents和data的MCP配置。本轮只核对名字，未输出token。此证据只证明已注入连接参数，不证明DeepSeek/Gemini实际看见并成功执行coordinate_bots；仍需真实往返验证。

当前Codex窗口尚不是群内常驻Bot。源码提供外部runtime协调入口候选，需绑定身份、线程和凭据并验证。不能把“Codex当前可操作本机”说成“已全天自动主持讨论”。

## 选型结论

优先采用现有OpenMausBot原生群组、点名和委派，围绕现有项目交接文件增加讨论规则。Grok提供交互参考，社区实例提供代码审查往返参考；不新造聊天系统，不迁移已跑通ACP入口。具体设计见 [03-设计/2026-11-09-Code工作流Bot讨论设计](../03-%E8%AE%BE%E8%AE%A1/2026-11-09-Code%E5%B7%A5%E4%BD%9C%E6%B5%81Bot%E8%AE%A8%E8%AE%BA%E8%AE%BE%E8%AE%A1.md)。

## 后续补充：新任务、重置与复制Bot

2026-11-09，用户追问上下文处理并要求图文解释，重新查阅官方文档（bots页更新2026-11-05，how-grok-bot-works页更新2026-11-06）。以下是Grok Bot事实，不能直接套成本机OpenMausBot的功能。

- [官方Bot管理文档](https://docs.x.ai/grok-bot/bots#what-resets-or-deletes-memory)明确：Reset重新开始聊天历史，保留记忆、文件、例行任务和设置。文档具体入口是消息受阻后可能出现的Reset提示，不据此宣称任意位置都有统一清空按钮。
- 同页Organize your roster明确iPhone可Duplicate Bot：复制配置、设置、启用技能、例行任务和头像，不复制聊天历史、学到的记忆和附件；随后改名并交代新范围。复制范围不等于复制全部工作环境，也不表示记忆中的长期规则会一并带走。
- [官方记忆说明](https://docs.x.ai/grok-bot/how-grok-bot-works#1-it-checks-its-memory)：记忆包含偏好、规则和工作日志；部分用户事实跨Bot共享。可通过聊天要求查看、修正或忘记。长期规则与一次性任务分别交代。
- Bot管理文档明确群中可用私聊告诉它的内容；记忆库不直接共享给其他Bot，但发言会被全群看到。因此新群不是无旧背景的保证。
- [技能文档](https://docs.x.ai/grok-bot/skills-routines-and-automations#save-a-skill)：技能是可复用方法，技能库可跨Bot使用并按Bot启用。它与学到的记忆不是同一层。
- 所有Bot共用持久云端电脑，文件与登录可能继续存在。复制或删除Bot均不能当成电脑环境完全隔离。未在已查文档找到Grok Bot通用compact命令、记忆总开关或严格项目隔离承诺；Grok Build/API的同名命令不适用。

本轮仅调研和制作图解，没有重置本机Bot、调整记忆策略或部署新复制功能。对本项目的借鉴建议：复用通用技能/岗位配置，给不同项目独立任务背景和记忆范围；实现状态见[03-设计/2026-11-09-Bot配置与任务上下文边界](../03-%E8%AE%BE%E8%AE%A1/2026-11-09-Bot%E9%85%8D%E7%BD%AE%E4%B8%8E%E4%BB%BB%E5%8A%A1%E4%B8%8A%E4%B8%8B%E6%96%87%E8%BE%B9%E7%95%8C.md)。

关联：[首页](../%E9%A6%96%E9%A1%B5.md)、[03-设计/2026-11-09-Code工作流模型分工草案](../03-%E8%AE%BE%E8%AE%A1/2026-11-09-Code%E5%B7%A5%E4%BD%9C%E6%B5%81%E6%A8%A1%E5%9E%8B%E5%88%86%E5%B7%A5%E8%8D%89%E6%A1%88.md)、[04-搭建/2026-11-09-Code工作流分工盘点](../04-%E6%90%AD%E5%BB%BA/2026-11-09-Code%E5%B7%A5%E4%BD%9C%E6%B5%81%E5%88%86%E5%B7%A5%E7%9B%98%E7%82%B9.md)。
