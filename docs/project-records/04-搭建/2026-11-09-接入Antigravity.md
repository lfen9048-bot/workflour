---
type: build-log
status: implemented-and-verified
created: 2026-11-09
updated: 2026-11-09
---
# 接入 Antigravity（Gemini）

## 目的

把用户已有的 Antigravity Pro 订阅接进同一套 OpenMausBot 界面，与 Coder/Doc 并列使用。
这是首轮明确留待后续的项（[06-决策/0002-OpenMausBot首轮范围与主入口](../06-%E5%86%B3%E7%AD%96/0002-OpenMausBot%E9%A6%96%E8%BD%AE%E8%8C%83%E5%9B%B4%E4%B8%8E%E4%B8%BB%E5%85%A5%E5%8F%A3.md) 第 19 行）。

## 开始前的实际环境

| 项 | 实际值 | 说明 |
| --- | --- | --- |
| `agy` 路径 | `~/.local/bin/agy` | 与调研记录一致 |
| `agy` 版本 | **1.5.3** | 调研时记录的是 2.28.2（那是 App 版本）；本次接入期间 agy 自动从 1.4.12 升到 1.5.3 |
| 登录状态 | **已登录** | `agy models` 能列出模型，说明 Google 账号凭据有效 |
| 可用模型 | 6 个 | gemini-3.8-flash(low/medium/high)、claude-sonnet-4-6、claude-opus-4-6-thinking、gpt-oss-120b-medium |
| OpenMausBot 版本 | 0.1.143 | 自带 `antigravityAgent` 驱动 |

## 关键发现：不需要下载官方运行时

调研笔记原本指向 OpenMausBot 的 `antigravityAgent` 原生驱动。读源码后发现该驱动要求：

```js
// 必须两个文件同时存在，否则报错
executablePath = agy_acp_server.par
harnessPath    = localharness_external
```

对应 Google CDN 上的 `agy-acp-server-1.4.3-darwin-arm64.zip`（约 114MB，解压后 280MB+）。

**但本机 agy 1.5.3 自带 `agy acp --stdio`**，本身就是标准 ACP 服务：

```text
Usage: agy acp [flags]
  Start the Agent Client Protocol (ACP) stdio server
  --stdio   Use stdio JSON-RPC transport (default)
```

所以改用 **customAcp 包装**，省掉 114MB 下载，也避免依赖 Google 的运行时分发。

## 实际握手验证（不是只读源码）

先用独立脚本直连 `agy acp --stdio` 验证协议：

```text
initialize -> protocolVersion=1
              loadSession=true
              sessionCapabilities: resume / close / load / list
session/new -> sessionId 非空
              currentModelId: gemini-3.8-flash-high
              availableModes: default / accept-edits / ...
session/prompt -> 回复 "AGY-OK"
               usage: inputTokens 8252, outputTokens 361
```

**在 1.4.12 和 1.5.3 两个版本上都验证通过。**

## 实现

### 新增 `run-agy-agent.sh`

与 `run-acp-agent.sh` 并列的第三个 ACP 入口。差异：

| 项 | run-acp-agent.sh | run-agy-agent.sh |
| --- | --- | --- |
| 身份来源 | DSH profile + WorkBuddy 凭据 | agy 自己的 Google 登录 |
| 需要 `--profile` | 是 | 否 |
| 需要 `DSH_HOME` | 是 | 否 |
| `--version` 探测 | 支持（customAcp 要求） | 支持 |

`--version` 必须支持，否则 customAcp 会把实例显示为 unavailable（这是 2026-11-06 实施时已记录的差异 1）。

### 实例注册

`~/.openmausbot/config.json` 新增：

```json
"agy-gemini": {
  "driver": "customAcp",
  "displayName": "Antigravity (Gemini)",
  "config": {"cli": "<WORKFLOUR_ROOT>/run-agy-agent.sh"}
}
```

已同步写进 `integrations/openmausbot/setup.sh`，保证可重建。
重跑 setup 验证幂等：`[=] 实例 agy-gemini 已是最新`。

### Bot 创建

| 项 | 值 |
| --- | --- |
| 名称 | Gemini |
| Bot ID | `LOCAL-ID-012` |
| 实例 | `agy-gemini` |
| cwd | `examples/omb-smoke` |
| approvalMode | `ask` |

**过程记录**：创建时用 POST 传了 `cwd` 但没生效（返回 `cwd: None`），
改 cwd 的 PATCH 又把 `approvalMode` 从 ask 改成了 `full`。
已用第二个 PATCH 改回 `ask`。以后建 Bot 要分两步：先 POST 建，再 PATCH 设 cwd 与 approvalMode。

## 验证结果

### 三个实例并列可用

```text
Harness Coder:        available v0.2.1-rc.2  auth=True
Harness Doc:          available v0.2.1-rc.2  auth=True
Antigravity (Gemini): available v1.5.3       auth=True
```

### 最小回复

用户消息「只回复：GEMINI-READY」→ Bot 回复 `GEMINI-READY`。

### 工具能力（关键）

让 Gemini 读 `examples/omb-smoke/textstats.py` 并报告函数名：

```text
回复：textstats.py 中定义了以下 2 个函数：
      - count_stats (L21-L26)
      - main (L29-L56)
digest：tools: shell ×1
```

对照真实文件：

```text
21:def count_stats(text: str) -> dict:
29:def main(argv: list) -> int:
```

**函数名与行号完全正确**，说明它真的读了文件，不是编的。

### 原有 Bot 未受影响

Coder、Doc 仍是 `available`，approvalMode 仍为 `ask`，会话与历史保留。

### 公网入口

`https://your-public-host.example:8443/api/health` 返回 200，手机端可访问同一批 Bot。

## 已知限制

- **模型选择在 Bot 层是 `agent-default`**：实际用哪个模型由 agy 内部决定（当前默认 `gemini-3.8-flash-high`）。若要逐 Bot 指定 Gemini / Claude，需在 OpenMausBot 的模型选择器里改，尚未验证该路径。
- **没有逐 Bot 的 skills 隔离**：Antigravity 的 skill 机制与 DSH 的 `available_skills` 不是一回事，本轮未做隔离验证。
- **agy 会自动升级**：本次接入期间从 1.4.12 升到 1.5.3。若未来升级破坏 ACP 兼容，需重新验证。建议关注 `agy acp --help` 是否仍存在。
- **审批模式**：当前 `ask`。Antigravity 的权限模型（`default` / `accept-edits`）与 DSH 的不完全相同，审批卡是否正常弹出尚未专门测试。

## 相关

- [首页](../%E9%A6%96%E9%A1%B5.md)
- [05-验证/2026-11-09-Antigravity接入验证](../05-%E9%AA%8C%E8%AF%81/2026-11-09-Antigravity%E6%8E%A5%E5%85%A5%E9%AA%8C%E8%AF%81.md)
- [02-调研/2026-11-06-OpenMausBot调研](../02-%E8%B0%83%E7%A0%94/2026-11-06-OpenMausBot%E8%B0%83%E7%A0%94.md)
- [02-调研/2026-11-05-现有工具与Harness多实例隔离](../02-%E8%B0%83%E7%A0%94/2026-11-05-%E7%8E%B0%E6%9C%89%E5%B7%A5%E5%85%B7%E4%B8%8EHarness%E5%A4%9A%E5%AE%9E%E4%BE%8B%E9%9A%94%E7%A6%BB.md)
- [04-搭建/2026-11-09-部署VPS公网HTTPS入口](2026-11-09-%E9%83%A8%E7%BD%B2VPS%E5%85%AC%E7%BD%91HTTPS%E5%85%A5%E5%8F%A3.md)
