---
type: build-log
status: implemented-local-stages
created: 2026-11-06
updated: 2026-11-06
---
# 实施 OpenMausBot 双 Agent 接入（阶段 1–3）

## 目的

按 [03-设计/2026-11-06-OpenMausBot双Agent与手机接入实施计划](../03-%E8%AE%BE%E8%AE%A1/2026-11-06-OpenMausBot%E5%8F%8CAgent%E4%B8%8E%E6%89%8B%E6%9C%BA%E6%8E%A5%E5%85%A5%E5%AE%9E%E6%96%BD%E8%AE%A1%E5%88%92.md) 逐阶段落地第一版最小系统：
ACP profiles → 协议握手 → 单 Coder → 双 Agent 接力 → 重启续聊 → 手机外网验证。

本轮实际完成到**重启续聊**为止；手机外网阶段需要用户完成账号邮箱码登录与手机端操作，尚未验证。

## 开始前的基线与差异核对

实施前先核对本机与计划记录的一致性，实际结果与计划 §2 一致：

| 项 | 计划记录 | 本次实测 |
| --- | --- | --- |
| macOS / 架构 | 26.6.2 / arm64 | 26.6.2 / arm64，一致 |
| Node | 24+ | v26.10.0（npm 11.19.1），满足 |
| DeepSeek Harness | 0.2.1-rc.2 | `dsh --version` = 0.2.1-rc.2，一致 |
| `~/.openmausbot` | 不存在 | 实施前确实不存在 |
| 8799 端口 | 未监听 | 实施前确实无监听 |
| 原 6 个基线文件 | 应保持原样 | 实施后 SHA-256 全部一致（见下） |

基线快照保存在项目 `.baseline/2026-11-06-before.txt`，实施后逐个比对通过：

```text
run-agent.sh                       b9b27d53…6140f
setup-agents.sh                    d6876f62…1387c
agents/agent-coder/cordis.patch.yml 8b71d7bc…ac270
agents/agent-doc/cordis.patch.yml   53df2bee…27c2e1
agents/agent-coder/skills/code-assistant/SKILL.md 2b0bac70…6048b
agents/agent-doc/skills/doc-writer/SKILL.md       5dc9175a…6b6b3d
```

`~/.dsh/sessions` 原有 19 个会话目录保留未动。

## 阶段 1：ACP profiles

### 实际产物

```text
workflour/
├── run-acp-agent.sh                       # coder|doc [+ --version]
├── run-omb.sh                             # local|remote|pair <origin>
├── integrations/openmausbot/
│   ├── setup.sh                           # profiles + config.json 合并
│   └── profiles/{coder,doc}.patch.yml     # 不含账号的模板
├── tests/acp-smoke.py                     # 不发 prompt 的握手验证
└── examples/omb-smoke/                    # 两个 Bot 共享的验证项目
```

新增本机配置：

- `~/.dsh/profiles/omb-coder`、`~/.dsh/profiles/omb-doc`（package.json / cordis.yml / pnpm-workspace.yaml / 真实 cordis.patch.yml / node_modules 软链接）。
- `~/.openmausbot/config.json` 中的两个 customAcp 实例。

### 与计划的实现差异（三处，均已实测）

**差异 1：`run-acp-agent.sh` 必须支持 `--version`。**
计划 §4 只写了「只接受两个已知角色」。实际 customAcp 驱动会先跑
`<cli> --version` 做安装探测（`server/drivers/acp/core.js` 的 `snapshot()`，
8 秒超时），不支持就显示 "version check failed"、实例状态 `unavailable`。
脚本因此接受可选第二参数 `--version`，转给内置 dsh，输出 `0.2.1-rc.2`。

**差异 2：必须关闭 `llm-deepseek-account`，否则 stdout 被污染。**
首次握手失败，stdout 混入非 JSON 行：

```text
[llm-deepseek-account] model listing from https://api.deepseek.com/models loaded 2 model(s), skipped 0 row(s)
```

来源是该插件用 `console.info(LOG_TAG, message)` 直接写 stdout
（`dsh-llm-deepseek-account/lib/index.js`，其注释明确写 "product profiles mount no console exporter for ctx.logger"）。
本方案模型全走 WorkBuddy，不需要这条路由，因此在两个 patch 模板里加：

```yaml
- id: llm-deepseek-account
  disabled: true
```

按计划 §9「stdout 出现启动提示或普通日志：修复包装/日志输出，不能通过丢弃协议行掩盖」处理：
这是配置层修复，验证脚本仍然逐行检查 stdout，没有放过任何非协议行。

**差异 3：账号块从 `--dump-config` 组合树抽取，而不是从旧 patch 文件复制。**
旧 patch 文件里只有 `accounts.cn` 和整段 `regions`，而插件运行后会把目录/选择写回。
`setup.sh` 优先沿用目标 patch 里已有的 workbuddy 条目（保留插件新状态），
否则从 `dsh --profile agent-coder --dump-config` 的组合结果里截取该条目。
运行 patch 是真实文件而非指向项目模板的软链接，避免插件把账号配置写回项目目录。

### 组合结果核对

```text
omb-coder: acp.config = provider workbuddy, model glm-5.3-flash
           skill-filesystem.customSkillDirs = …/agents/agent-coder/skills
           system-prompt.personaPrefix = "You are Agent Coder, …"
omb-doc:   acp.config = provider workbuddy, model deepseek-v4.1-flash
           skill-filesystem.customSkillDirs = …/agents/agent-doc/skills
           system-prompt.personaPrefix = "You are Agent Doc, …"
```

`setup.sh` 重复执行幂等：第二次运行输出 `[=] 实例 omb-coder 已是最新`、
`[=] config.json 无需改动`。

## 阶段 2：协议握手

`python3 tests/acp-smoke.py` 分别启动两个角色，只发 `initialize` → `session/new`
→ `session/close`，不发 `session/prompt`。

```text
=== ACP 握手验证: coder ===
  [1/3] initialize OK（0.5s，protocolVersion=1，agent=deepseek-harness-acp）
  [2/3] session/new OK（当前模型=workbuddy / ["workbuddy","glm-5.3-flash"]）
  [3/3] session/close OK
  stdout 非空行: 3，退出码: 0

=== ACP 握手验证: doc ===
  [1/3] initialize OK（0.5s，protocolVersion=1，agent=deepseek-harness-acp）
  [2/3] session/new OK（当前模型=workbuddy / ["workbuddy","deepseek-v4.1-flash"]）
  [3/3] session/close OK
  stdout 非空行: 3，退出码: 0

=== 结论 ===
  coder: 通过
  doc: 通过
```

证据：`tests/evidence/acp-smoke-20261106-203315.json`（含完整 configOptions）。

失败的历史证据也保留：`acp-smoke-20261106-202827.json` 记录了 stdout 污染。

**注意**：这不是离线或零副作用检查。插件仍联网刷新目录，`session/new` 会落盘。

## 阶段 3：OpenMausBot 与单 Coder

### 安装与服务

- 版本：`openmausbot@0.1.143`，用 `npx --yes` 运行，未安装 Electron 桌面 App。
- 本地启动：`npx --yes openmausbot@0.1.143 serve` → `http://127.0.0.1:8799`。
- 数据目录：`~/.openmausbot`（聊天、数据库、登录、配对数据都在这里，不进项目/Obsidian）。

### 实例与 Bot 对应关系

| 实例 ID | 驱动 | 显示名 | 启动命令 |
| --- | --- | --- | --- |
| `omb-coder` | customAcp | Harness Coder | `run-acp-agent.sh coder` |
| `omb-doc` | customAcp | Harness Doc | `run-acp-agent.sh doc` |

两个实例 `snapshot.state` 均为 `available`，版本 `0.2.1-rc.2`。

| Bot | Bot ID | threadId | 实例 | 模型 | cwd | approvalMode |
| --- | --- | --- | --- | --- | --- | --- |
| Coder | `LOCAL-ID-010` | `085ccd7f-…` | omb-coder | agent-default | examples/omb-smoke | ask |
| Doc | `LOCAL-ID-011` | `1b9bac50-…` | omb-doc | agent-default | examples/omb-smoke | ask |

**过程失误记录**：首次用 shell 循环批量创建时，`POST /api/bots` 返回的是
`{"bot": {...}}` 嵌套结构，我的解析取错了层级，误以为失败而重复创建了一个 Coder，
随后用 `DELETE /api/bots/<id>` 删掉多余的那个。最终只剩 Coder、Doc 两个目标 Bot
加系统自带的 MausBot。

### 单 Coder 验证（阶段 A）

发一条最短消息，要求回复就绪并列出自定义 skill：

```text
bot: Coder 就绪  当前自动提供的自定义 skill：`code-assistant`。
```

模型路由从会话日志 `request/header` 核实，不采信模型自述：

```json
{"config": {"provider": "workbuddy", "model": "glm-5.3-flash", "reasoningEffort": "high"}}
```

会话文件：`~/.dsh/sessions/--Users-a1-Documents-a-workflour-examples-omb-smoke--/173f162a-…/session.v4.jsonl.zstd`

skills 以实际注入清单为准，来自同一会话的 system-reminder：

```text
<available_skills>
- `code-assistant`: Dedicated skill for Agent Coder to inspect code and perform architecture analysis.
</available_skills>
```

## 相关

- [03-设计/2026-11-06-OpenMausBot双Agent与手机接入实施计划](../03-%E8%AE%BE%E8%AE%A1/2026-11-06-OpenMausBot%E5%8F%8CAgent%E4%B8%8E%E6%89%8B%E6%9C%BA%E6%8E%A5%E5%85%A5%E5%AE%9E%E6%96%BD%E8%AE%A1%E5%88%92.md)
- [05-验证/2026-11-06-OpenMausBot双Agent本地阶段验证](../05-%E9%AA%8C%E8%AF%81/2026-11-06-OpenMausBot%E5%8F%8CAgent%E6%9C%AC%E5%9C%B0%E9%98%B6%E6%AE%B5%E9%AA%8C%E8%AF%81.md)
- [06-决策/0002-OpenMausBot首轮范围与主入口](../06-%E5%86%B3%E7%AD%96/0002-OpenMausBot%E9%A6%96%E8%BD%AE%E8%8C%83%E5%9B%B4%E4%B8%8E%E4%B8%BB%E5%85%A5%E5%8F%A3.md)
- [首页](../%E9%A6%96%E9%A1%B5.md)
