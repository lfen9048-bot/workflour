# Plan 派单前检查

复用本机 DSH 0.2.1-rc.2 `tools/pre-execute`、`tools/execute`，只为
`wf-plan-lead` 启用。它不改 OpenMausBot 安装包、不替代原生审批、不发送独立请求。

先正常 `claim`，再准备完整参数：

```sh
python3 scripts/prepare-dispatch.py prepare --project ABSOLUTE_PROJECT --actor plan-lead \
  implement code-main --message-file ABSOLUTE_BRIEF --title '主编码 · 任务编号'
```

把返回的 `native_arguments` 原样交给原生 `coordinate_bots`。实际调用之前校验
精确内容、Bot、线程、原 claim token 和 `WF-INTENT`，并原子写入 `sending`。
不可变的职责、范围和能力声明整体计算摘要，通过 `WF-CONTRACT` 写入原生 brief；
接收端读回原生 brief 与该摘要，单独改掉 image 声明不能静默降级。
原生返回后只读数据库核对回执，记录 `sent`；没有可确认回执记 `uncertain`。
`sending`、`uncertain`、`sent` 均不能再次调用。发送不确定时用 CLI 的 `finish`
只读核对并更新自己的日志，不能重派。显式故障恢复仍走原项目恢复流程。

补充单使用 `--supplement --reason '有界补充原因' --evidence records/plan-lead/scope.md`；
保留主 token 与同一 worker thread，发送成功后继续使用原 `supplement` 命令登记。
不能因为漏标记、回执未登记或超时再发送一次补充。

网页 `experience` 自动声明 `required_capabilities:["image"]`，CLI 项目不声明；
其他确需图片的派单可显式 `--require-image`。要求写进项目 intent，接收端用原生
Bot/thread 绑定和真实 assignment 定位，不通过提示词关键词推断。

项目记录在 `.workflour/dispatch-intents/`，私有定位索引在
`~/.workflour/dispatch-intents/`（测试可用 `WORKFLOUR_DISPATCH_HOME`）。索引只含
项目路径，不存 MCP 认证或密钥。真实会话绑定由 ACP bridge 写入
`$DSH_HOME/workflour-session-bindings/<sessionId>.json`。

该机制防止常规模型派单失误，不是文件权限沙箱。历史无 intent 派单不会补造历史；
原生 `consult:true` 且未混入派单标记/answers 的咨询继续可用，不作为正式阶段
完成依据；咨询的无操作要求是原生职责约束，不是文件权限沙箱。`reply:none`
仍会原生入队执行，因此不能绕过检查。首版不放行 `answers` 捷径；原生适配会
丢弃空白答案 ID，外部调用也可能跳过问答匹配，不能据此保证只答已有问题。
正式追加范围须使用带凭据的补充单；真正的问题答复受阻时保留现场并报告。

最终 `experience` 会使用 `rework:true` 和独立新线程，因为同一 Plan 评审 Bot
已经完成前面的方案评审；原生同 parent/Bot 的完成保护不因 `thread:new` 取消。
这是新阶段的显式工作，不是重发旧 intent。
