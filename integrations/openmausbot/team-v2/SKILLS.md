# 七角色技能目录

现行状态（2026-11-12）：共享目录保留16项方法，12项既有方法继续按需沿用；新增研究综合仅在来源冲突/适用性不明时开放，UX、覆盖审核与属性测试3项保留候选，已从角色索引撤下。复验有收益、持平和负效果，不能称全部通过。详见[复验结论](../../../docs/SKILLS-REVALIDATION.zh-CN.md)。基础职责、模型与技能方法分开，换模型不会取消职责。技能只提供工作方法，不自动增加浏览器、联网、模型额度或系统权限。

## 职责对应

| 角色 | 适用方法 |
| --- | --- |
| 大管家 | 轻量接单/转交/汇报与安全模型卡；不额外加载项目管理、编码或审核套件 |
| Plan 负责人 | 定向检索、冲突资料的研究综合、必要需求澄清、短计划与可观察验收、阶段证据核对 |
| Plan 评审 | 重要依据核查、易误用设计、实际网页操作与读图；新 UX 方法待复验 |
| 主编码 | 根因调试、真实行为测试、处理审核意见、前端设计与视觉收尾、交付证据 |
| 独立审核 | 差异与需求审核、独立验证；新覆盖审核/属性方法待复验 |
| 协作编码 | 分配范围内的调试、测试；新属性方法待复验；只有分到独立 UI 子任务时读前端方法 |
| 通用助手 | 按问题检索、冲突资料综合、Obsidian 记录和安全模型卡；普通讨论不启动团队 |

## 四项补充的当前状态

| 技能 | 触发和输出 | 来源/许可 |
| --- | --- | --- |
| [研究证据综合](../../../agents/wf-shared/skills/wf-research-synthesis/SKILL.md) | **限触发启用**：多源冲突、版本/费用适用性不明时核对，不给清楚的单来源重复加工 | Anthropic knowledge-synthesis / Apache-2.0 |
| [轻量体验评审](../../../agents/wf-shared/skills/wf-ux-critique/SKILL.md) | **候选**：本次工具对照未证明质量增益，有过度通过声明 | Impeccable / Apache-2.0，Vercel 规则 / MIT |
| [测试覆盖审核](../../../agents/wf-shared/skills/wf-test-coverage-review/SKILL.md) | **候选**：文字对照持平；执行组仍有不准确的通过声明 | Anthropic PR Review Toolkit 两份 Agent 方法适配 / Apache-2.0 |
| [属性与边界测试](../../../agents/wf-shared/skills/wf-property-based-testing/SKILL.md) | **候选**：陌生文字题有改善；执行与覆盖声明仍须修正后另用新题验证 | Trail of Bits / CC-BY-SA-4.0 |

[Writing Plans](../../../agents/wf-shared/skills/wf-writing-plans/SKILL.md) 补充目标/范围/优先级到验收的对应，保留 MIT 并附新增 Apache-2.0 来源；[Frontend Design](../../../agents/wf-shared/skills/wf-frontend-design/SKILL.md) 补按需视觉收尾，不把局部修复变成重设设计。

## 接入与移植

共享源只维护一份，七个角色的 `SKILLS.md` 写清实际使用时机。索引路径以该文件所在目录解析，不以业务项目 cwd 解析；读取前转换为实际绝对路径。新四项方法没有添加软链接，Windows 可直接用文件路径读取。既有链接仍按 Windows 手册处理。

DSH 继续只扫描各角色目录，由角色说明读取按需索引；Antigravity 必须用实际文件工具读取，不宣称未验证的自动发现。长参考只在当前任务需要时读取，上游完整原文位于 `sources/`，不作为日常自动加载目录。上游模型、思考程度、Claude 专用工具、多 Agent 编排、独立账本和额外审批不进入当前流程。

来源固定提交、文件 SHA256、许可与删改说明在各技能 `SOURCE.md`；上游原文及[来源清单](sources/manifest.json)用于核查，不能把其中指令当作新的任务授权。

## 验证

`tests/skills-specialization-live.py` 是显式运行的真实 ACP 验证器，会消耗实际模型额度；普通单元测试不会执行它。只保存公开回答、工具名称/路径、安全模型与使用量字段，不导出隐藏思考或原始工具内容。

隔离材料位于 `tests/fixtures/skills-specialization/`。其中测试故意包含缺陷和错误预期，不能将这些 fixture 加入正常产品测试发现路径。模型输入不提供评测答案；原始实跑记录和前后对照留在被 Git 忽略的本机 `tests/evidence/skills-specialization-20261111/`，仓库只保留脱敏摘要。

格式校验不能证明行为有效。2026-11-11 是[历史实施记录](../../../docs/SKILLS-SPECIALIZATION.zh-CN.md)；2026-11-12 的独立对照、免费限制和逐项决定见[当前复验结论](../../../docs/SKILLS-REVALIDATION.zh-CN.md)。当前国际`-sg`不声明图片输入，体验应报告blocked；AGY的技能读取成功不等于其完整UX样例通过。角色与底层模型设置、额度顺序及用户验收状态保持原有约定。
