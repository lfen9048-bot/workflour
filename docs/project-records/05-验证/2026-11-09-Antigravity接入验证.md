---
type: verification
status: passed
created: 2026-11-09
updated: 2026-11-09
---
# Antigravity 接入验证

验证日期：2026-11-09（Asia/Shanghai）。
实施记录见 [04-搭建/2026-11-09-接入Antigravity](../04-%E6%90%AD%E5%BB%BA/2026-11-09-%E6%8E%A5%E5%85%A5Antigravity.md)。

## 结论速览

| 检查项 | 状态 | 判定依据 |
| --- | --- | --- |
| agy 登录状态 | **已通过** | `agy models` 列出 6 个模型 |
| ACP 协议握手 | **已通过** | initialize / session/new / session/prompt 全成功 |
| 跨版本兼容 | **已通过** | 1.4.12 与 1.5.3 两个版本均验证 |
| 实例注册 | **已通过** | 三个实例并列 `available`，版本各自正确 |
| 最小回复 | **已通过** | 回复 `GEMINI-READY` |
| 工具能力 | **已通过** | 读出真实函数名与行号，digest 显示 `shell ×1` |
| 原有 Bot 未破坏 | **已通过** | Coder/Doc 仍 available，approvalMode 仍为 ask |
| 公网可访问 | **已通过** | `/api/health` 200 |
| setup.sh 幂等 | **已通过** | 重跑输出 `[=] 实例 agy-gemini 已是最新` |
| 逐 Bot 模型选择 | **未验证** | Bot 层为 `agent-default`，未测指定具体模型 |
| skills 隔离 | **未验证** | Antigravity 的 skill 机制与 DSH 不同，本轮未做 |
| 审批卡触发 | **未验证** | 未专门触发 `session/request_permission` |

## 1. 环境事实

| 项 | 值 |
| --- | --- |
| agy 路径 | `~/.local/bin/agy` |
| agy 版本（接入时） | 1.5.3（期间从 1.4.12 自动升级） |
| 二进制大小 | 208,900,592 字节（约 199MB） |
| 登录 | 已登录，Google 账号凭据有效 |
| OpenMausBot | 0.1.143 |

可用模型：

```text
gemini-3.8-flash-high    Gemini 3.8 Flash (High)
gemini-3.8-flash-medium  Gemini 3.8 Flash (Medium)
gemini-3.8-flash-low     Gemini 3.8 Flash (Low)
claude-sonnet-4-6        Claude Sonnet 4.6 (Thinking)
claude-opus-4-6-thinking Claude Opus 4.6 (Thinking)
gpt-oss-120b-medium      GPT-OSS 120B (Medium)
```

## 2. ACP 协议握手（直连验证）

用独立 Python 脚本直接与 `agy acp --stdio` 对话，不经 OpenMausBot：

### initialize

```json
{
  "protocolVersion": 1,
  "agentCapabilities": {
    "loadSession": true,
    "promptCapabilities": {"image": true, "embeddedContext": true},
    "sessionCapabilities": {"resume": {}, "close": {}, "load": {}, "list": {}}
  },
  "agentInfo": {"name": "Antigravity ACP Ser..."}
}
```

`loadSession: true` 与 `sessionCapabilities.resume` 说明**支持原生会话恢复**，
比 DSH 走 `recoveryText` 重建要强。

### session/new

```json
{
  "sessionId": "LOCAL-ID-019",
  "models": {
    "availableModels": [ ...6 个模型... ],
    "currentModelId": "gemini-3.8-flash-high"
  },
  "modes": {
    "currentModeId": "default",
    "availableModes": ["default", "accept-edits", ...]
  }
}
```

### session/prompt

```text
发送：只回复：AGY-OK。不要修改任何文件。
回复：AGY-OK
result: {"stopReason": "end_turn",
         "usage": {"inputTokens": 8252, "outputTokens": 361,
                   "thoughtTokens": 357, "totalTokens": 8613}}
```

**能返回 token 用量**，这比 customAcp 走 DSH 时 `usageStatus: unavailable` 要好。

### 跨版本复测

agy 在接入期间自动从 1.4.12 升到 1.5.3（二进制 mtime 为 2026-11-09 16:47）。
升级后重跑同一脚本，仍然通过：

```text
chunk: AGY-OK
result: {"stopReason": "end_turn", "usage": {"inputTokens": 8254, ...}}
```

## 3. 实例状态

```text
Harness Coder:        available  v0.2.1-rc.2  auth=True
Harness Doc:          available  v0.2.1-rc.2  auth=True
Antigravity (Gemini): available  v1.5.3       auth=True
```

版本号各自正确，说明 OpenMausBot 通过 `--version` 探测拿到了 agy 的真实版本。

## 4. Bot 列表

| 名称 | 实例 | approvalMode |
| --- | --- | --- |
| Gemini | agy-gemini | ask |
| Doc | omb-doc | ask |
| Coder | omb-coder | ask |
| MausBot | omb-coder | full |

MausBot 的 `full` 是系统自带协调机器人原有的设置，本轮未改动。

## 5. 功能验证

### 最小回复

```text
[user] 只回复：GEMINI-READY。不要修改任何文件。
[bot]  GEMINI-READY
[bot]  [digest] · no tool activity observed in this turn · files: none changed
```

### 工具能力（决定性证据）

```text
[user] 读取当前目录下的 textstats.py，只告诉我它定义了哪几个函数名，不要修改任何文件。
[bot]  textstats.py 中定义了以下 2 个函数：
       - count_stats (L21-L26)
       - main (L29-L56)
[bot]  [digest] · tools: shell ×1 (from tool previews) · files: none changed
```

对照真实文件内容：

```text
21:def count_stats(text: str) -> dict:
29:def main(argv: list) -> int:
```

**函数名与行号完全一致**，且 digest 记录了 `shell ×1`，说明是真实执行工具读文件，
不是模型凭上下文编造。这是「工具真的能用」的证据。

## 6. 幂等性

重跑 `integrations/openmausbot/setup.sh`：

```text
[+] 已备份 <HOME>/.openmausbot/config.json
[=] 实例 agy-gemini 已是最新
[=] 实例 omb-coder 已是最新
[=] 实例 omb-doc 已是最新
[=] config.json 无需改动
```

不产生重复条目，不破坏已有配置。

## 7. 未验证项（明确列出）

以下没有做，不能算通过：

1. **逐 Bot 指定模型**：Bot 层是 `agent-default`，实际用 `gemini-3.8-flash-high`。
   想给某个 Bot 单独指定 `claude-opus-4-6-thinking` 的路径未测。
2. **skills 隔离**：Antigravity 的 skill 机制（`--include-default-customizations`）
   与 DSH 的 `available_skills` 不是一回事，两边隔离行为未验证。
3. **审批卡**：`approvalMode: ask` 下，Antigravity 发 `session/request_permission` 时
   OpenMausBot 是否正常弹出审批卡、用户批准后是否继续，未专门测试。
4. **长任务与中断**：多轮工具调用、中断恢复未测。
5. **手机端操作 Gemini**：公网接口通，但未用手机实际给 Gemini 发消息。

## 8. 风险与维护提醒

- **agy 会自动升级**：本次从 1.4.12 升到 1.5.3。若未来某版本破坏 `agy acp`，
  实例会变 unavailable。排查第一步是 `agy acp --help` 是否仍存在。
- **版本漂移影响可复现性**：记录里写的 1.5.3 可能很快过时。
  如需固定，要关闭 agy 的自动更新（未做，需先确认其更新机制）。
- **199MB 二进制**：agy 体积较大，属官方发行包。

## 证据

- 包装脚本：`<WORKFLOUR_ROOT>/run-agy-agent.sh`
- 实例配置：`<HOME>/.openmausbot/config.json`（备份在 `backups/`）
- 配置生成：`<WORKFLOUR_ROOT>/integrations/openmausbot/setup.sh`
- 握手测试脚本：`/tmp/test-agy-prompt.py`（临时，未纳入项目）

## 相关

- [首页](../%E9%A6%96%E9%A1%B5.md)
- [04-搭建/2026-11-09-接入Antigravity](../04-%E6%90%AD%E5%BB%BA/2026-11-09-%E6%8E%A5%E5%85%A5Antigravity.md)
- [02-调研/2026-11-06-OpenMausBot调研](../02-%E8%B0%83%E7%A0%94/2026-11-06-OpenMausBot%E8%B0%83%E7%A0%94.md)
- [05-验证/2026-11-09-VPS公网HTTPS入口验证](2026-11-09-VPS%E5%85%AC%E7%BD%91HTTPS%E5%85%A5%E5%8F%A3%E9%AA%8C%E8%AF%81.md)
