# 两轮规划与交叉回应

2026-11-10：新增流程规则。之前的实现只有三份独立提案加主持人整合，不能据此声称三人已经互相讨论。本协议复用已安装 OpenMausBot 0.1.143 的 `coordinate_bots`、自动回传和持久派单账本，不安装另一套框架。

## 阶段顺序与执行者

`planning（三份提案） → discussion（三份交叉回应） → plan（主持定稿） → implement → review → verify → 用户验收`

新 `coordinator-workflow.py init` 账本标记 `discussion_version:1`。旧账本保持旧顺序，正在编码的任务不倒退重跑。两个讨论回合固定为：第一轮独立提案；第二轮每人回应另外两位。主持最后定稿是整合，不再发第三轮讨论。

总控逐角色使用原生 `thread:new` 派单，claim/真实receipt/result按原机制保存；每次派单后结束回合等待原生回传。广播群消息不能替代派单。三位不要再向彼此嵌套派单，由总控一次性分发三份提案并收集回应，避免交叉等待。

## 回应产物

三位角色key沿用 `kimi`、`deepseek`、`glm-plan`，只用于身份和路径，不表示实际模型。默认目标分别为方案主持、协作编码、风险规划。当前手动模型选择保留，不为实现此协议强制换模型。

每位写自己独立的 `records/<role>/discussion.json`。示例结构（哈希必须自己读取实际文件计算，以下占位符不能交付）：

```json
{
  "role": "kimi",
  "round": 2,
  "proposal_sha256": {
    "kimi": "本次方案主持提案的SHA256",
    "deepseek": "本次协作编码提案的SHA256",
    "glm-plan": "本次风险规划提案的SHA256"
  },
  "responses": [
    {"to": "deepseek", "position": "change", "point": "对方提案中的具体接口选择", "reason": "我建议修改的内容和依据"},
    {"to": "glm-plan", "position": "agree", "point": "对方提案中的具体失败边界", "reason": "同意的原因及如何落实"}
  ]
}
```

`position` 只能是 agree/change/disagree；两项分别回应另两人，不能回应自己、用“都同意”占位或伪造另一人的观点。有理由的真实同意是有效回应，不强迫制造分歧。总控不得代写三份回应。

三位都完成后：

```sh
python3 scripts/coordinator-workflow.py --actor coordinator --project PROJECT advance plan
```

检查器确认三项均完成、各有独立回执、回应作者/轮次/覆盖正确、引用提案仍为同一版本。证据缺失或哈希变化则拒绝推进。检查器不判断观点是否聪明或真实理解；总控需看内容，真实模型往返以原生回执为准，单元测试不是实跑讨论。

## 主持定稿

主持必须读取三份提案和三份回应，用简表说明：分歧、各方意见、采纳/不采纳理由、最后决定。重大范围分歧交用户；范围内的小技术取舍由主持决定并解释。不能把一方未回应说成“达成共识”。

小功能默认材料预算：提案各500字内、回应各400字内、PLAN120行内、任务清单40行内；复杂任务需要更多时写出原因。保存原话、明确要求与来源、团队假设、待定项，不重复全文。

## 目录和停止保护

工作台当前原生委派只能继承发起会话cwd；已有任务PATCH没有cwd字段。不得修改全体Bot默认目录或重建活动任务来伪装修复。调用命令时使用工具显式cwd，或 `scripts/project-exec.py --project ABSOLUTE_PROJECT -- COMMAND ARG...`；读写文件用绝对项目路径。新创建的原生项目会话应在第一条消息前选真实目录。

用户停止后的旧项目请求不是新继续授权。先找到停止之后的用户明确继续消息，再运行retry；若没有就保留 stopped。平台拒绝后不换人/换线程绕过。

## 来源与复用

复用本项目近期调研的 [OpenMausBot](https://github.com/milind-soni/OpenMausBot) 原生委派；以本机0.1.143 `drivers/agents-catalog.js` 的 `coordinate_bots` schema及自动回传说明核对。它支持新会话、真实回执、自动返回；不提供现成的三方回应完整性检查，因此只扩展现有本地账本。不会改动产品安装包或新增服务。


## 实跑修正：回执与 JSON（2026-11-10）

- 第二轮给已完成首轮的同一成员派新工作，原生调用用 `rework:true` 和 `thread:new`；这是交叉回应阶段，不是重复首轮或消耗故障重试次数。若平台拒绝，因为原任务还在运行就等待，不能盲目重发。
- 派单标记统一使用 claim 返回的 `WF-DISPATCH:<uuid>`。漏冒号的 `WF-DISPATCH <uuid>` 现在可由只读适配器识别；仍核对完整UUID、目标Bot和发起会话，不能只凭角色名绑定。
- 严禁手改账本、删除/置空dispatch_token绕过receipt校验，严禁因为标记错误再派相同业务任务。旧回执已有而token被误清空，可用 `coordinator-workflow.py --actor coordinator --project PATH repair-token PHASE ROLE` 从唯一、归属正确的原生brief恢复，留下审计历史；若有冲突或多个标记则拒绝。
- discussion.json 必须是一个完整合法JSON对象，不能加Markdown围栏、注释或尾部 `STATUS: ...`。状态标记只能放在聊天回执里。主持定稿是汇总阶段，不称作第三轮讨论。
