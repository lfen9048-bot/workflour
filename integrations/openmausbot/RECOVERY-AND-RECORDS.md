# 安全续跑与自动记录

适用于本机 OpenMausBot 0.1.143 / DSH 工作台。沿用原生派单、持久交接与角色配置；不新增模型或远程服务。

## 恢复规则

`coordinator-workflow.py` 不发送消息。每次修改在项目锁内读取并原子写入账本。

1. 初始化绑定总控工作台会话 `init TASK REQUEST --thread-id UUID`。
2. `claim PHASE ROLE --bot-id UUID` 返回 `dispatch_token`；原生派单正文必须含 `WF-DISPATCH:<token>`，再以 `receipt` 保存真实派单ID。receipt校验来源、接收Bot和标记，旧尝试ID不能绑定到新尝试。
3. `reconcile PHASE ROLE` 只读原生记录。若回执丢失，用唯一标记找回；多匹配、来源/目标不符、已绑定回执缺失时拒绝继续。
4. 原生运行/排队/审批/等待：继续等。原生完成：核对文件与结果，再settle，不重发。模型说完成不能替代测试。
5. 原生failed/cancelled：写实际部分改动与测试检查证据，`retry PHASE ROLE --reason ... --evidence ...`。停止/interrupted/denied需额外 `--resume-authorization` 记录实际继续来源。
6. retry保存完整旧attempt、证据、恢复时code_files哈希，新建claim/token。直接派新任务并绑定receipt，不再次claim。同一阶段/角色/修复轮最多一次恢复重试；业务缺陷另走最多两轮rework。
7. 未绑定且没有原生匹配的claim：先reconcile；旧总控会话停止/空闲后，维护者可用 `release-claim`，必须提供原因、证据、明确继续来源。仍在运行的旧sender会被拒绝。有原生匹配时必须找回原任务。旧格式没有token的未绑定claim不能据“没找到”推断没派出，需要人工找回真实receipt。

同一个总控Bot换到新对话/运行时后，可在旧对话和派单全部停止或完成、核对交接并得到明确继续指令后，用 `adopt-origin --thread-id 新会话 --reason 原因 --evidence 交接文件 --resume-authorization 继续来源` 接管。只允许同Bot，拒绝旧会话仍活跃，保留原会话链和旧回执；普通同会话重启无需此操作。

所有写命令前缀：

```bash
python3 scripts/coordinator-workflow.py --actor coordinator --project /项目路径
```

`--actor`和继续来源是误操作防护/审计记录，不是身份认证。共享目录不具备OS级角色沙箱。原生派单和项目账本不是同一数据库事务；不声称严格exactly-once，尤其不能防止有权限者手工改文件、绕开工具或同时从另一路派单。

原生HTTP查询要求活跃Bot capability。本地维护适配器 `native_assignments.py` 使用 SQLite `mode=ro`、`query_only`、按requester_thread_id过滤并校验version=1；只返回ID、状态、Bot/会话、次数和UUID标记，不输出原prompt、结果或token。没有修改产品数据库或借用内部MCP凭据。产品升级改变schema时应先核对适配器。

## 自动记录

`workflow-observer.py register --project PATH`只登记明确项目。总控init自动尝试登记；如果DSH文件权限阻止访问注册表，会单独报错：账本已经提交，不可重复init，只需重新登记/处理相应权限。

`workflow-observer.py install`安装用户级 `com.workflour.workflow-observer` LaunchAgent，每20秒运行一次sync；单实例/单项目锁避免手动sync和后台写入冲突。Mac睡眠、注销或离线会延迟同步，不保证秒级实时。

只读协调账本、交接、代码快照和明确派单对应会话，复用已有限定范围的可见消息导出器。在知识库 `07-自动记录/`生成：项目首页、进度、异常、角色记录、已有代码/审核/测试证据链接。旧会话文件仍保留在索引中。手写笔记和其他项目不扫描、不覆盖；不导出原生trace、工具参数/结果、隐藏推理。可见文本的凭据模式脱敏是尽力检查，非任意秘密识别保证。

自动记录不更改任务状态、不派单、不审批、不自动验收。同步失败保留上一版角色记录，写项目 `.workflour/observer-status.json` 和本机 `~/.workflour/observer/{status.json,异常.md}`，下轮重试。整个知识库不可写时，本机诊断仍可查。`status`超过120秒心跳会提示过时；日志在同目录。长期大规模性能未压力测试。

DSH分类器写 `~/.dsh/workflour-session-queue/diagnostics.json`，暂时失败保留队列，恢复成功后清除当前告警。生产者入队失败写stderr并尽量写项目 `session-title-error.json`，需要检查权限后重新入队；不能声称丢失的队列会自动重建。桌面关闭时由下次打开继续分类。归组范围仍仅本工作流目录及其真实子目录。

## 使用入口

日常直接对项目总控说“继续这个项目，先核对旧派单，完成的不要重做”。
通用助手可在原总控空闲时协助释放确认未派出的claim；恢复后回原总控推进。

```bash
python3 scripts/workflow-observer.py status
python3 scripts/workflow-observer.py sync --project /已登记项目
```

已安装后台时，通常不需在每次阶段手动sync；这样可避免反复外部目录审批。

## 选型依据

- 继续扩展本项目账本、导出器和固定版本原生派单。无新增依赖/账号/订阅，未复制上游实现。
- [Temporal retry policies](https://docs.temporal.io/encyclopedia/retry-policies)：参考按失败活动重试、限制尝试次数原则，不引入需另部署的完整调度服务，也不采用无限重试默认。只读文档，不采用其代码，因此未新增许可证依赖。
- [Obsidian data storage](https://obsidian.md/help/data-storage)：本地Markdown会由现有Obsidian读取刷新，无需另装同步插件。

核对日期：2026-11-10。实际验收证据：`tests/evidence/recovery-flow-20261110/`；完整流程是否通过以summary.json为准。


## 2026-11-10 交叉回应与旧记录维护

新账本使用 discussion_version:1，按 planning→discussion→plan 推进；三人逐一回复另两人，证据缺失或提案变更则不能推进。详见 [交叉回应协议](PLANNING-DISCUSSION.md)。旧账本不自动迁移。

停止后先取新的用户继续消息及来源，再retry；原来的完整项目委托不能充当新的继续授权。当前CLI只校验授权材料存在，不验证自然语言授权真假；原生停止保护仍为最后一道约束，不能声称已实现完整身份认证。

观察器增加 suspend/resume。暂停前备份注册表，不删除项目/聊天/已导出的记录；暂停项目在首页明确显示暂停及原因，不再每20秒请求已确认失效的会话。HTTP404与网络故障分别提示，自动改绑会话仍禁止。
