---
type: build-log
status: verified-local-ui
created: 2026-11-08
updated: 2026-11-08
---
# OpenMausBot 本机入口与 UI 复核

## 目的

处理本机浏览器打开 `1deMacBook-Air.local` 时出现 “unauthorized: this browser is not signed in” 的现象，并把本机可用入口复核到可发消息的程度。

## 实际操作与结果

1. 用 Chrome 打开本机入口 `http://127.0.0.1:8799/`，而不是 `http://1deMacBook-Air.local:8799/`。
2. 本机界面能看到 Coder、Doc、MausBot，旧对话记录也正常显示。
3. 首次进入的引导里选择了现有 Coder 作为总协调机器人。
4. 给 Coder 发送最小验证消息：“只回复：OK。不要修改任何文件。”，Coder 回复 `OK`。
5. 切换到 Doc，发送同样最小验证消息，Doc 回复 `OK`。
6. 重新执行无提示 ACP 握手检查：`python3 tests/acp-smoke.py`。

ACP 握手结果：

```text
coder: initialize OK / session/new OK / session/close OK，退出码 0
doc:   initialize OK / session/new OK / session/close OK，退出码 0
证据: <WORKFLOUR_ROOT>/tests/evidence/acp-smoke-20261108-170622.json
```

## 为什么 `.local` 会要求配对

服务日志里的本地入口是 `http://127.0.0.1:8799`。  
`1deMacBook-Air.local` 是另一条主机名入口，浏览器当时没有完成登录/配对，因此 OpenMausBot 显示配对页。  
这不是服务装错了，也不是 Bot 不可用。

同机日常使用建议固定打开：

```text
http://127.0.0.1:8799
```

## 未做

- 没有完成 OpenMausBot 账号邮箱码登录。
- 没有启动 `remote` / HTTPS 隧道。
- 没有做手机配对或蜂窝网络验证。

## 下一步

如果继续手机方案，下一步是登录 OpenMausBot 账号、启动 remote 隧道、生成手机配对邀请并验证。  
如果以后想换自制界面，可以在本机验证通过的基础上再评估 MCP 或直连 ACP 方案。

## 相关

- [首页](../%E9%A6%96%E9%A1%B5.md)
- [04-搭建/2026-11-06-实施OpenMausBot双Agent接入](2026-11-06-%E5%AE%9E%E6%96%BDOpenMausBot%E5%8F%8CAgent%E6%8E%A5%E5%85%A5.md)
- [05-验证/2026-11-06-OpenMausBot双Agent本地阶段验证](../05-%E9%AA%8C%E8%AF%81/2026-11-06-OpenMausBot%E5%8F%8CAgent%E6%9C%AC%E5%9C%B0%E9%98%B6%E6%AE%B5%E9%AA%8C%E8%AF%81.md)
- [03-设计/2026-11-06-OpenMausBot双Agent与手机接入实施计划](../03-%E8%AE%BE%E8%AE%A1/2026-11-06-OpenMausBot%E5%8F%8CAgent%E4%B8%8E%E6%89%8B%E6%9C%BA%E6%8E%A5%E5%85%A5%E5%AE%9E%E6%96%BD%E8%AE%A1%E5%88%92.md)
