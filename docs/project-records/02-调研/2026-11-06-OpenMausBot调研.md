---
type: research
status: reviewed-not-installed
created: 2026-11-06
updated: 2026-11-06
---
# OpenMausBot 调研

## 调研来源与范围

用户询问一个类似 Grok Bot 的开源项目，随后明确名称为 OpenMausBot。本轮只检索、阅读实际文档与源码，不安装、不登录、不调用模型、不修改现有最小系统。其他初筛候选不是用户选定目标。

## 项目身份与维护

- 仓库：[milind-soni/OpenMausBot](https://github.com/milind-soni/OpenMausBot)。
- 官方网站：[openmausbot.com](https://www.openmausbot.com)。
- 别名 MausBot，前称 OpenGrokBot；独立社区项目，受 Grok Bot 启发。
- 仓库创建于 2026-08-11，2026-11-06 检索时未归档且当日仍有提交。
- 当时最新 release：[v0.1.142](https://github.com/milind-soni/OpenMausBot/releases/tag/v0.1.142)，北京时间 2026-11-06 发布。
- 下述能力来自本次实际阅读的 main 分支文档与源码，发布包逐项支持情况尚未在本机验证。

## 它提供什么

[实际 README](https://github.com/milind-soni/OpenMausBot/blob/main/README.md)

多个 Bot 在聊天应用里作为联系人出现，可分别配置模型、指令、skills 和电脑环境。提供群聊/频道、任务、审批、持续记录与外部应用连接。桌面界面背后由本地服务统一管理 Agent 进程和事件流。

本地数据使用 `~/.openmausbot`，不是现有 DeepSeek Harness 的数据目录。没有据此认定会自动导入已有 Harness 历史。

## 与现有资源的关系

### Antigravity Pro

当前 main 有专用 `antigravityAgent` 驱动，通过官方 ACP runtime 和独立 Google profile/OAuth 工作，源码中提供登录与模型发现。可作为复用 Google 账号权益的候选接入方式，但本机是否可直接使用现有登录、实际可选模型和额度行为均未验证。

来源：[Antigravity 驱动](https://github.com/milind-soni/OpenMausBot/blob/main/server/drivers/antigravity.ts)。

### DeepSeek Harness + WorkBuddy

[自定义引擎文档](https://github.com/milind-soni/OpenMausBot/blob/main/docs/custom-engines.md) 明确支持 stdio ACP CLI，`customAcp` 可指定完整命令、参数、环境变量和多个实例，并按 Bot 选择模型。它也支持直接接 OpenAI-compatible API，但这不是当前用户现有额度接入的同一条链路。

[Harness ACP 文档](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/bundle/acp-app/README.md) 说明 `dsh --profile acp` 提供 ACP v1 stdio 服务，可通过自定义 profile/patch 配置 provider、模型、工具与持久化。

**推论：存在 OpenMausBot → customAcp → Harness ACP profile → WorkBuddy 插件的对接路线。** 本轮没有验证两端兼容，也没有找到已经完成的本机接线。

现有 `<WORKFLOUR_ROOT>/run-agent.sh` 使用 headless profile，一次任务后退出；其输出协议不是 ACP，不能仅把这个脚本填入 customAcp 就声称接入成功。若后续获授权实施，应为 ACP 另配启动入口，保留当前已跑通的模型/skills/WorkBuddy 配置，并先做单 Bot 小验证。

### 作为统一协作入口

[官方 MCP 文档](https://github.com/milind-soni/OpenMausBot/blob/main/docs/mcp-server.md) 提供列出 Bot/频道、读取和搜索记录、发任务、等待完成、切模型和中断的控制面。由此可作为未来统筹多个执行器的候选工作台。现有 Harness 脚本和历史不因此自动迁移。

## 部署、成本与许可

- 提供 macOS Apple silicon / Intel 桌面安装包，发布版内嵌服务端；源码开发需要 Node 24+ 与 pnpm。
- 基础聊天可使用支持的本机 CLI 登录与已有订阅。模型调用仍受原账号权益限制。
- 云电脑、应用连接和语音等为可选功能，接入第三方服务时有相应配置和费用；不能把应用开源等同于所有服务免费。
- 普通本地使用与完整云端/电脑控制部署是不同复杂度；本轮未配置任何权限或服务。
- 主体为 Apache-2.0；`enterprise/` 为独立 source-available 许可，企业功能生产使用需要许可。已实际阅读 [LICENSE](https://github.com/milind-soni/OpenMausBot/blob/main/LICENSE)、[LICENSING.md](https://github.com/milind-soni/OpenMausBot/blob/main/LICENSING.md) 和 [enterprise/LICENSE](https://github.com/milind-soni/OpenMausBot/blob/main/enterprise/LICENSE)。

## 当前判断

值得作为“统一界面与协作层”候选评估，已有能力与用户希望集中管理不同 Agent 的方向接近。尚未决定替换 Harness 桌面或采用该项目。

关键缺口是本机 Antigravity 登录与 DSH/WorkBuddy ACP 接入的实际验证，以及历史和 skills 的具体呈现。没有开展安装或下一阶段实现。

## 手机与电脑互通：后续核对

用户追问是否打通手机和电脑。本次核对实际文档、客户端下载入口与发布页面，确认项目已有手机伴侣接入；未安装、配对或在本机验证。用户本次询问不等于已新增手机接入要求或决定采用该项目。

- **原生客户端已有分发**：[iPhone App Store](https://apps.apple.com/in/app/mausbot-private-ai-agents/id6803387923)，以及 [Android APK Release](https://github.com/milind-soni/OpenMausBot/releases/tag/android-v1.5.0)。仓库 [app-links.ts](https://github.com/milind-soni/OpenMausBot/blob/main/src/lib/app-links.ts) 对应这些入口。App Store 各地区可用性未核实。
- **工作仍由配对主机执行**：手机可查看 Bot、频道与会话，发任务、看流式结果、中断、回答问题和审批。手机通过二维码信任配对，可以使用受支持的可信本地网络、Tailscale 或启用后的托管 HTTPS；配对个人电脑时，该电脑必须保持唤醒并运行服务。另配常驻服务器或 Cloud 是不同部署方式，不意味着现有 Mac 关机后其本地任务仍能运行。[原生伴侣文档](https://github.com/milind-soni/OpenMausBot/blob/main/docs/ios-companion.md)
- **手机浏览器/PWA 也可用**：Safari/Chrome 打开可访问的 HTTPS 工作区链接、正常配对后添加主屏幕，使用同一工作区和会话。PWA 不额外提供离线聊天、推送或原生电脑控制，localhost 链接不能直接用于手机。[手机 Web App 文档](https://github.com/milind-soni/OpenMausBot/blob/main/docs/phone-web-app.md)
- **电脑控制有范围**：原生伴侣在主机另外授予 computer-access 后可访问指定 Bot 的云电脑或受支持的独享 Local VM；不能据此承诺手机可随意接管宿主 Mac 桌面。共享/池化 Local VM 与 VPS viewer 另有限制，实施前按版本再核对。[伴侣文档](https://github.com/milind-soni/OpenMausBot/blob/main/docs/ios-companion.md)、[路由实现](https://github.com/milind-soni/OpenMausBot/blob/main/companion/src/routes.ts)
- **资料时效性**：伴侣文档个别段落仍把分发、语音写为后续，但实际 App Store 已有对应发布与版本记录。不要沿用“尚无原生 App”的结论，也不要把 PWA 的离线/推送限制直接套用于原生客户端。本轮不承诺闭 App 后推送的稳定性。

对本项目的候选价值是“离开电脑也能查看 Agent 进度、派任务和处理审批”。要让现有 Harness/WorkBuddy Agent 出现在此入口，仍需此前未完成的 ACP 接入验证；已有 Harness 历史不会自动导入。

## 关联

- [首页](../%E9%A6%96%E9%A1%B5.md)
- [01-需求/目标与待定事项](../01-%E9%9C%80%E6%B1%82/%E7%9B%AE%E6%A0%87%E4%B8%8E%E5%BE%85%E5%AE%9A%E4%BA%8B%E9%A1%B9.md)
- [05-验证/2026-11-06-双Agent最小系统复核](../05-%E9%AA%8C%E8%AF%81/2026-11-06-%E5%8F%8CAgent%E6%9C%80%E5%B0%8F%E7%B3%BB%E7%BB%9F%E5%A4%8D%E6%A0%B8.md)
- [04-搭建/2026-11-06-调研OpenMausBot](../04-%E6%90%AD%E5%BB%BA/2026-11-06-%E8%B0%83%E7%A0%94OpenMausBot.md)
