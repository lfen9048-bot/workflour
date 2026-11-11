---
type: worklog
status: complete
created: 2026-11-06
updated: 2026-11-06
---
# 调研 OpenMausBot

用户在双 CLI 最小系统复核后，请求检索一个类似 Grok Bot 的开源项目，并明确名称 OpenMausBot。

按 search-first 检索 GitHub 与网页，阅读项目 README、许可说明、自定义 ACP 引擎文档、MCP 控制面、Antigravity 驱动和 Harness ACP 文档。实际结论与来源见 [02-调研/2026-11-06-OpenMausBot调研](../02-%E8%B0%83%E7%A0%94/2026-11-06-OpenMausBot%E8%B0%83%E7%A0%94.md)。

主要发现：该项目已有统一多 Bot 聊天与协作界面；当前 main 有 Antigravity 专用驱动，也支持通用 stdio ACP CLI。现有 Harness 可作为协议对接候选，但当前 headless 启动脚本不能直接当 ACP 服务使用，具体兼容尚未实测。

已记录为候选调研，没有作出采用或迁移决定。本轮没有安装、登录、启动项目、请求模型或修改现有系统。

## 记录检查

笔记写入与双向链接检查：已通过；本次 3 份笔记写入回读一致，本库 79 处双向链接目标均存在。

## 关联

- [首页](../%E9%A6%96%E9%A1%B5.md)
- [05-验证/2026-11-06-双Agent最小系统复核](../05-%E9%AA%8C%E8%AF%81/2026-11-06-%E5%8F%8CAgent%E6%9C%80%E5%B0%8F%E7%B3%BB%E7%BB%9F%E5%A4%8D%E6%A0%B8.md)

## 后续核对：手机伴侣

用户追问手机与电脑互通。核对 iPhone App Store、Android APK Release、phone-web-app 与 ios-companion 文档，确认已有原生客户端及浏览器/PWA 入口，支持远程对话、任务和审批；执行仍在在线主机。电脑控制需要另授权限且有目标范围，不能承诺宿主 Mac 全桌面远控。详细来源已补入关联调研。

本次只读，没有安装、配对、开放远程访问或改动现有系统。没有将用户的问题改写为已确认需求。本次三份笔记写入回读一致，本库 101 处双向链接目标均存在。
