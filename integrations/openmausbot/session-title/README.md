# DSH 会话标题与工作区整理

新 ACP 会话通过本地 `sessionTitle` provider 原生保存标题，无额外模型请求。
总控派发的第一条消息加入一行：

```text
工作流会话标题：[DeepSeek] TASK-001 · 存储模块
```

插件限定工作流目录；缺少明确标题时使用角色与短会话编号。DSH 原生标题服务
负责持久化、取消及用户改名优先级。此功能更新的是 DSH 标题；它与 OpenMausBot
的任务标题分别保存。真实验证见 `tests/evidence/dsh-organize-20261110/title-provider-live.json`。

## 整理历史

先生成只读清单，输出是权限 0600 的新文件，不覆盖旧清单：

```sh
python3 scripts/dsh-session-organize.py scan \
  --capture-bots Coder,Doc \
  --out tests/evidence/dsh-organize-20261110/next-before.json
```

仅覆盖本工作流的明确项目目录。CAPTURE 还必须匹配原生维护提示、唯一 Bot、
工作流 Bot 目录和完成轮次，无法确认的会话跳过。用户已经改过的标题保留。
清单不复制聊天内容、凭据或工具输入。

工作区先用 DSH 原生 UI 注册正确目录。**注册工作区不会自动收纳旧 ACP 会话**；
官方启动 bootstrap 只在首次初始化运行，普通重启不会补齐历史归属。
历史整理器调用公开的 `workspace.attachSession`，不修改会话 cwd。

实际整理需全部 Bot 空闲、保存交接并退出 DSH 桌面。必要时先停止托管 OMB，
等待 ACP 子进程退出后使用明确维护模式：

```sh
python3 scripts/dsh-session-organize.py apply \
  --manifest tests/evidence/dsh-organize-20261110/next-before.json \
  --desktop-stopped --service-stopped \
  --out tests/evidence/dsh-organize-20261110/next-receipt.json
```

该模式检查 OMB 已停止且无 ACP 桥接/角色进程。工具先在 `~/.dsh/backups/`
私有目录保存工作区原始备份，再用安装版本的官方 Host 服务 attach/rename/archive；
不直接修改数据库、header、日志或缓存。锁冲突和活动归档拒绝不会强制绕过。
CAPTURE 的旧临时目录已删除时，原生 rename 可能拒绝；结果中分别记录改名与
归档，不能把归档成功称为改名成功。整理后重新启动服务与桌面，并核对实际显示。

## 还原

保存原始清单和实际 receipt。相同维护条件下，`undo` 通过原生服务恢复成功改过
的标题、取消本次新增归档、移除新增归属并恢复工作区注册/名称；不删除会话或文件：

```sh
python3 scripts/dsh-session-organize.py undo \
  --manifest tests/evidence/dsh-organize-20261110/next-before.json \
  --receipt tests/evidence/dsh-organize-20261110/next-receipt.json \
  --baseline tests/evidence/dsh-organize-20261110/workspace-original-baseline.json \
  --desktop-stopped --service-stopped \
  --out tests/evidence/dsh-organize-20261110/next-undo-receipt.json
```

baseline 必须是对应那一轮修改前的工作区清单；首轮原生 UI 修改另有
`workspace-original-baseline.json`。还原前检查是否已有后续手动修改。
原来没有标题的会话不能用受支持 API 删除标题事件，清单会明确标记需人工处理，
不会伪造“已恢复空标题”。

验证：Python `test_dsh_session_organize.py`、Node `test_dsh_session_organize_host.mjs`
与 `test_dsh_session_title.mjs`。历史整理是可重复的空闲维护流程。

## 新会话持续归组

标题 provider 只把本工作流的会话 ID、真实 cwd 和标题原子写入
`~/.dsh/workflour-session-queue/<sessionId>.json`，每会话独立文件。
ACP 进程不写全局工作区注册表。队列目录和文件分别使用 0700/0600 权限。

桌面 profile 单独加载 `autogroup.mjs`，由唯一桌面消费者每三秒处理队列。
它用公开只读 persistence handle 核对真实 header、真实最新标题及项目路径，
标题尚未提交或原生服务未就绪时保留重试。通过官方 projection cache 服务刷新
冷会话显示，再用官方工作区服务 attach，处理回执放 `receipts/`；重复项幂等。
归组后从公开 `sessionController.list` 冷读真实会话摘要，通过公开
`api-session/added` 通知桌面列表更新，不恢复会话或抢占 ACP 的写锁。
跨项目和符号链接指向外部的目录均拒绝。桌面关闭时队列保留，下次打开处理。
没有隐藏模型调用、持久化原始聊天或多 ACP 进程并发改全局工作区。

安装仅修改用户 desktop profile，先退出桌面；原 patch 保存在私有备份目录：

```sh
python3 scripts/dsh-session-organize.py install-desktop --desktop-stopped \
  --out tests/evidence/dsh-organize-20261110/desktop-plugin-install.json
```

原生 UI 的最终显示仍以实测为准。队列消费的隔离 Host 启动和 scope/幂等/延迟标题
测试分别见 `autogroup-isolated-host.json` 与 `tests/test_dsh_session_autogroup.mjs`。
真实新会话的原生标题、消费回执和项目归属证据在
`tests/evidence/dsh-organize-20261110/autogroup-live.json`。
补齐列表通知后，另一个全新 READY 会话在不重开、不手动刷新桌面的情况下
直接出现在正确工作区；视觉与原生回执见
`tests/evidence/dsh-organize-20261110/live-sidebar-verification.json`。

无 prompt 的模型目录/协议探针可能留下空会话，它们不会触发首条消息标题队列。
人工历史清单可以按其真实项目目录收纳，但不会猜测这些空会话是否可删除或归档。
仅有第一条实际工作消息的会话会走持续自动命名与归组。
