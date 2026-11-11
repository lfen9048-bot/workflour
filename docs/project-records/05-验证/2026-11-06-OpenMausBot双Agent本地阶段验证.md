---
type: verification
status: local-stages-passed-phone-pending
created: 2026-11-06
updated: 2026-11-06
---
# OpenMausBot 双 Agent 本地阶段验证

验证日期：2026-11-06（Asia/Shanghai）。
实施记录见 [04-搭建/2026-11-06-实施OpenMausBot双Agent接入](../04-%E6%90%AD%E5%BB%BA/2026-11-06-%E5%AE%9E%E6%96%BDOpenMausBot%E5%8F%8CAgent%E6%8E%A5%E5%85%A5.md)。

## 结论速览

| 检查项 | 状态 | 判定依据 |
| --- | --- | --- |
| 两个协议入口 | **已通过** | initialize / session/new / session/close 各 3 行纯净 JSON-RPC，退出码 0 |
| 模型路由 | **已通过** | 会话日志 `request/header` 实测 workbuddy + 各自模型 |
| skills 分开 | **已通过** | 两个会话的 `available_skills` 清单各自只含自己的 skill |
| 工具工作 | **已通过** | Coder 实际生成 4 个文件，我独立重跑测试 |
| 文档接力 | **已通过** | Doc 生成 README，示例输出与真实程序输出逐字一致 |
| 持久化 | **已通过** | 停服务重启后同一聊天可见，短标记被正确回忆 |
| 手机 | **等待用户确认** | 需要用户完成邮箱码登录与手机操作 |
| 原基线 | **已通过** | 6 个基线文件 SHA-256 全一致 |

## 1. 协议入口（阶段 2）

命令：`python3 tests/acp-smoke.py`
证据：`tests/evidence/acp-smoke-20261106-203315.json`

| 角色 | initialize | session/new | session/close | stdout 行数 | 退出码 |
| --- | --- | --- | --- | --- | --- |
| coder | OK 0.5s，protocolVersion=1 | OK，sessionId 非空 | OK | 3（全为合法 JSON-RPC） | 0 |
| doc | OK 0.5s，protocolVersion=1 | OK，sessionId 非空 | OK | 3（全为合法 JSON-RPC） | 0 |

通过条件中的「stdout 非空行均为有效 JSON-RPC」由脚本逐行校验，不是目测。

### 一次真实失败的留证

首次运行（`acp-smoke-20261106-202827.json`）未通过：

```text
问题: ['非 JSON: [llm-deepseek-account] model listing from https://api.deepseek.com/models loaded 2 model(s), skipped 0 row(s)']
```

原因与修复见搭建记录「差异 2」。修复后同一脚本通过，说明校验确实在起作用。

## 2. 模型路由

不采信模型自报名称，改用会话持久化日志中的 `request/header` 与 `request/context`。

| 角色 | 期望 | 实测 | 会话文件 |
| --- | --- | --- | --- |
| Coder | workbuddy / glm-5.3-flash | `{"provider":"workbuddy","model":"glm-5.3-flash"}` | `LOCAL-ID-015` |
| Doc | workbuddy / deepseek-v4.1-flash | `{"provider":"workbuddy","model":"deepseek-v4.1-flash"}` | `LOCAL-ID-016` |

会话目录：`~/.dsh/sessions/--Users-a1-Documents-a-workflour-examples-omb-smoke--/`

另有一致证据：`session/new` 返回的 configOptions 中，model 选项的 `currentValue`
分别是 `["workbuddy","glm-5.3-flash"]` 和 `["workbuddy","deepseek-v4.1-flash"]`。

## 3. skills 分开

从各自会话的 system-reminder 实际注入清单取，不是模型自述：

| 角色 | 注入的 available_skills |
| --- | --- |
| Coder | 只有 `code-assistant` |
| Doc | 只有 `doc-writer` |

Doc 的会话日志里还能看到它主动调用 `skill` 工具加载 `doc-writer`：

```json
{"name":"skill","arguments":"{\"name\":\"doc-writer\"}"}
```

**证据局限**：这证明自动 skills 清单是分开的，**不**等于文件系统权限隔离。
两个 Bot 共享同一测试目录，且都有文件读写能力。计划 §9 也要求不要把
「文件读取权限」误写成「隔离成功」。

## 4. 工具工作（阶段 B，Coder）

Coder 在 `examples/omb-smoke/` 实际生成：

| 文件 | 说明 |
| --- | --- |
| `textstats.py` | 读 UTF-8 文本，stdout 输出 `{"lines":…, "characters":…}` |
| `test_textstats.py` | unittest，覆盖空文本 / 英文多行 / 中文 / 文件不存在 |
| `sample.txt` | 示例输入（3 行含中文，28 字节） |
| `HANDOFF.md` | 改动清单、真实测试输出、输入输出约定、文档待写事项 |

我没有预写这些文件。Coder 汇报后我独立重跑核对：

```console
$ python3 textstats.py sample.txt
{"lines": 3, "characters": 18}
退出码 0

$ python3 -m unittest test_textstats.py -v
test_chinese_text … ok
test_empty_text … ok
test_english_multiline … ok
test_file_not_found … ok
----------------------------------------------------------------------
Ran 4 tests in 0.082s
OK
退出码 0
```

HANDOFF.md 里记录的耗时是 `0.088s`，我重跑是 `0.082s`——耗时随运行浮动，
用例数与结果一致，属正常差异，不是伪造。

## 5. 文档接力（阶段 B，Doc）

把 `examples/omb-smoke/HANDOFF.md` 的位置和文档任务手动交给 Doc（两个 Bot 的聊天不自动同步）。

Doc 实际产出 `README.md`（9161 字节），内容包括用途、运行要求、命令、
输出说明、错误情况表格、测试方法、已知限制。

逐字核对示例输出：

| 项 | README 写的 | 我实际运行 |
| --- | --- | --- |
| 正常输出 | `{"lines": 3, "characters": 18}` | `{"lines": 3, "characters": 18}` ✓ |
| 缺参数 | 用法提示，退出码 2 | 用法提示，退出码 2 ✓ |
| 文件不存在 | 错误信息，退出码 1 | `错误: 文件不存在: nope.txt`，退出码 1 ✓ |

Doc 只改了文档，未改代码；没有出现需要退回 Coder 的代码错误。

## 6. 持久化（阶段 C，重启续聊）

步骤与结果：

1. 在 Coder 现有聊天中给短标记 `PINEAPPLE-7421`，要求不写进项目文件。
   - Coder 回复「已记住」，digest 显示只更新了 MEMORY.md。
   - `grep -rl PINEAPPLE-7421 <WORKFLOUR_ROOT>` → **无匹配**，确认未写进项目。
   - 标记落在 `~/.openmausbot/` 下的应用数据（native ndjson、messages.db-wal、workspace MEMORY.md）。
2. `pkill -f openmausbot` 停止服务；确认 8799 无监听、无 `run-acp-agent` 残留进程。
3. 重新 `serve` 启动。
4. 旧聊天仍可见：Coder 的 threadId 未变，13 条消息（含标记那条）完整存在。
5. 在同一聊天询问标记与任务状态，Coder 回答：

```text
短标记是 PINEAPPLE-7421；本目录任务已全部完成——textstats.py、test_textstats.py、
sample.txt、HANDOFF.md 都已建好，python3 -m unittest test_textstats.py -v 真实运行
4 个测试全部通过，只差把 HANDOFF.md 交给 Doc 写文档这一步未做。
```

**兼容点实测结果**：DSH rc.2 支持 `session/resume`，而通用 customAcp 默认尝试
`session/load`（`server/drivers/acp/core.js` 按 `support.resumeMethod` 分支，
只有内置 deepseek 驱动设成 `"resume"`）。因此重启后底层 DSH session ID 会变化
（新会话 `54a4ed41-…`，旧会话 `173f162a-…` 保留），上下文靠 OpenMausBot 的
`recoveryText` 重建。这与计划 §7C 的预期一致，本轮接受该恢复方式。

**边界说明**：这证明「应用保存记录并恢复上下文」，不证明「原生 session 原样恢复」。
按计划要求，没有把它写成原生恢复通过。

## 7. 原基线未受影响

| 文件 | 结果 |
| --- | --- |
| `run-agent.sh` | SHA-256 未变 |
| `setup-agents.sh` | SHA-256 未变 |
| `agents/agent-coder/cordis.patch.yml` | SHA-256 未变 |
| `agents/agent-doc/cordis.patch.yml` | SHA-256 未变 |
| 两个 `SKILL.md` | SHA-256 未变 |
| `~/.dsh/sessions` 旧会话 | 19 个目录保留 |

新增内容全部是新文件（`run-acp-agent.sh`、`run-omb.sh`、`integrations/`、`tests/`、`examples/`）
和新的 profile/实例，没有改动旧入口。

## 8. 手机阶段：等待用户确认

前置条件尚未满足：

- `openmausbot status` 显示本机**未登录** OpenMausBot 账号；
- `serve --tunnel` 需要先 `openmausbot login`（邮箱验证码），这是隧道账号，不是模型提供方登录；
- 手机配对需要用户本人在手机上完成。

因此本轮**没有**执行 `serve --tunnel`、没有生成任何配对邀请、没有做过外网访问。
`run-omb.sh` 的 local / remote / pair 三个分支只做了参数校验测试（占位符和 http 地址会被拒绝，退出码 2），
没有真实启动隧道。

后续步骤见首页交接。

## 相关

- [04-搭建/2026-11-06-实施OpenMausBot双Agent接入](../04-%E6%90%AD%E5%BB%BA/2026-11-06-%E5%AE%9E%E6%96%BDOpenMausBot%E5%8F%8CAgent%E6%8E%A5%E5%85%A5.md)
- [03-设计/2026-11-06-OpenMausBot双Agent与手机接入实施计划](../03-%E8%AE%BE%E8%AE%A1/2026-11-06-OpenMausBot%E5%8F%8CAgent%E4%B8%8E%E6%89%8B%E6%9C%BA%E6%8E%A5%E5%85%A5%E5%AE%9E%E6%96%BD%E8%AE%A1%E5%88%92.md)
- [05-验证/2026-11-06-双Agent最小系统复核](2026-11-06-%E5%8F%8CAgent%E6%9C%80%E5%B0%8F%E7%B3%BB%E7%BB%9F%E5%A4%8D%E6%A0%B8.md)（接入前的基线验证）
- [首页](../%E9%A6%96%E9%A1%B5.md)
