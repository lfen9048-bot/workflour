# Plan、研究、UX 与轻量协调技能扩大调研

日期：2026-11-12（Asia/Shanghai）。作者：独立调研子任务 pool_sync。

状态：**这是行为测试前冻结的调研报告**；后续验证与配置决定见 [复验结论](../../SKILLS-REVALIDATION.zh-CN.md)。本报告自身未配置候选。本次只写本报告；不调用原生模型，不安装插件，不改角色、模型、账号或业务。结论供主任务安排隔离盲测。

## 1. 结论与建议顺序

现有技能已经包含研究溯源、需求澄清、交接、分阶段 UX 检查，不能把同名的新技能数量当成改进。扩大调查了 **5 个独立作者／组织的实际技能来源**，另读 Google 工程评审经验和 W3C 原始规范说明。优先验证以下增量：

1. **MMM state-inventory 的状态推导方法**：对异步、保存、离线、部分成功等功能，补齐“触发原因 → 用户看到什么 → 能怎样安全恢复”。适合作为既有 Plan／UX 方法的按需参考；先不引入完整矩阵生成器。
2. **GitHub create-technical-spike 的单问题验证结构**：一个会改变方案的技术未知，设有限预算、可观察完成条件，做最小实验再决策。不要连同它的无限递归研究 Agent 一起采用。
3. **PM-Skills deliver-prd 的精简交接字段**：来源优先级、要求—验证人映射、升级给谁。先对照“仅字段模板”与“完整技能”，现有方法已有的字段不重复增加。AI 行为验证仅用于真正的模型功能，不施加到普通确定性功能。
4. MMM 的访谈证据索引只在确有访谈／支持记录时再试；gstack 的问题前提挑战可做小范围对照，暂不导入其整套运行系统。
5. **大管家保持轻量**。现有接单、转交、读状态职责没有证据需要再加一个策划／协调框架。LFG 更适合借鉴评测设计，不能直接替换现有两轮返工和单一状态负责人。

本次不建议立即替换现有完整技能，也不声称上述候选已胜过当前基线。

## 2. 本地基线与调查方法

已查看 `agents/wf-shared/skills/` 的 16 个方法与来源，重点完整读了 Plan 负责人、Plan 评审、大管家按需技能，以及 research-synthesis、requirements-interview、writing-plans、search-first、ux-critique（四阶段参考）和 webapp-testing。其余开发／审核方法只盘点用途与来源，深度代码审查由另一子任务负责。

| 现有方法 | 现有来源／职责 |
| --- | --- |
| wf-search-first | 本地适配；先本地、再原始来源与现成方案 |
| wf-requirements-interview | 本地用户技能；保留明确要求，只问影响实现的未知 |
| wf-research-synthesis | Anthropic knowledge-work-plugins；事实／推断、冲突、来源版本与足够证据后停止 |
| wf-writing-plans | obra + Anthropic write-spec；需求、工作项、验收与交接 |
| wf-ux-critique | Impeccable + Vercel；方案、预览、真实体验、返工复核分阶段 |
| wf-webapp-testing | Anthropic；真实浏览器操作、截图与证据 |
| wf-frontend-design | Anthropic + Impeccable |
| wf-sharp-edges、wf-differential-review、wf-property-based-testing | Trail of Bits |
| wf-systematic-debugging、wf-test-driven-development、wf-receiving-code-review、wf-verification-before-completion | obra/superpowers |
| wf-test-coverage-review | Anthropic 官方 PR review toolkit |
| wf-obsidian-markdown | kepano |

现有关键固定版本：Anthropic knowledge-work-plugins `877a617b435ee2edfb002d9a3703c0a1a03aa1ba`；obra/superpowers `22f0b463e7a5e579904dd6211a520321035526f7`；Impeccable `c1e0e5492fbb524f5df84d635ecfae7dc438ec45`；Vercel guidelines `434b7f91364665f2f733b310ec54809bf8f37937`。以项目 SOURCE 与中央 manifest 为正式来源记录。

按 search-first 执行：先读上述本地文件，再用不含私密信息的通用词检索 GitHub／网页，涉及 research synthesis、design critique、state inventory、technical spike、product requirements、agent workflow evaluation 等方向；之后通过 GitHub 原始文件与 API 核对实际目录、固定 commit、维护时间和许可证。**没有使用 stars 作排名**。候选 README 的自述与实际评测证据分别记录。

## 3. 来源、版本与维护核对

以下时间为 GitHub 元数据的 UTC 时间／日期，不代表在 DSH 或 Antigravity 已验证兼容。

| 独立来源 | 本次固定 commit | 维护与许可证（读过 LICENSE） | 定位 |
| --- | --- | --- | --- |
| mmmtheory/Skillset | `8c10ffe5fcfbd926c69d5fa652da637dd037813f` | 未归档；HEAD 2026-10-25；MIT，Matthias Schmutz | 产品／UX 原始方法，公开评测尚空 |
| github/awesome-copilot | `30a0d7465b14b05e05949d6588b99f7af0c537b4` | 未归档；HEAD 2026-11-12；MIT | GitHub 托管社区贡献，不能等同官方效果保证 |
| garrytan/gstack | `b9bbc31c5c9b36ff4fe8e85493fd86491602b846` | 未归档；HEAD 2026-11-12；MIT，Garry Tan | 带工具与工作流的完整工程套件 |
| twilson63/lfg | `e9c17383575d95fb6604a33b99e4cc162ba20c6b` | 未归档；HEAD 2026-10-28；MIT，Tom Wilson | 全流程约束与评测方法 |
| product-on-purpose/pm-skills | `9b920db418c5bf641edea9afb4915a286e1d42ea` | 未归档；HEAD 2026-11-03，最近 push 11-10；Apache-2.0，Jonathan Prisant | 产品文档技能，存在有局限的真实对照记录 |
| Google eng-practices（非技能） | `3bb3ec25b3b0199f4940b1aa75f0ac5c5753301c` | 已归档；HEAD 2024-09-19；实际 LICENSE 为 CC-BY-3.0 | 成熟工程团队评审原则，作为补充依据 |

维护深度：state-inventory 最近修改 2026-10-25；technical-spike 技能最近修改 2026-02-24（目录迁移）；gstack plan-ceo-review 最近修改 2026-11-02；LFG SKILL 最近修改 2026-10-28；deliver-prd SKILL 最近修改 2026-10-30（日期更正，主要内容标记 10-17）。活跃仓库不等于每个方法都被近期实测。

### A. MMM：状态推导最有针对性，评分表不能照搬

实读：四份 SKILL（state-inventory、design-brief、research-synthesis、design-critique），domain-packs、brief-template、evidence-rubric、checks、rubric、README、LICENSE、bench/results.json。另看 quote_index.py 的说明与标准库导入；**未完整审计／运行其脚本**。

- **state-inventory** 从数据、动作、参与者、时间与限制推导状态，连起触发条件、可见内容、后果和恢复。比只写“考虑错误态”具体，适合当前 Plan 与体验审核的异常路径缺口。应限制在任务真实存在的流程，不要求每个小任务都画图、八列表格、全域状态枚举或新增产物。概率没有数据时必须写假设。
- **design-brief** 的高风险假设与最小验证有用；整体与当前澄清／计划重叠。把用户指定方案当可随意替换的候选、强制固定问答与文档长度，会违背明确需求；不宜整体替换。
- **research-synthesis** 针对真实访谈／工单，证据与解读分开、引用可追踪、记录反例、避免把小样本比例泛化。它并不是通用网页研究的替代品；固定支持人数与洞察条数不应机械套用。含用户资料时要避免复制无关身份信息。
- **design-critique** 强调实际看图、测量和未评估项有价值，但十维分数与自我修改不适合独立评审。`checks.md` 将含 SC 2.3.3 的表列为 WCAG AA，而 W3C 原始说明将该项列为 **AAA**；不能据此把偏好或 AAA 项误报为 AA 阻断。

证据边界：README 将所有技能列为评估中；`bench/results.json` 的 updated 为 null、各 runs 为空。不是已有实测收益。纯文字可迁移至 DSH／AGY；附带脚本要另审，当前无需安装库。成本主要是额外输入、状态枚举与输出长度。

固定来源：[state-inventory](https://github.com/mmmtheory/Skillset/blob/8c10ffe5fcfbd926c69d5fa652da637dd037813f/skills/state-inventory/SKILL.md)、[domain-packs](https://github.com/mmmtheory/Skillset/blob/8c10ffe5fcfbd926c69d5fa652da637dd037813f/skills/state-inventory/references/domain-packs.md)、[design-brief](https://github.com/mmmtheory/Skillset/blob/8c10ffe5fcfbd926c69d5fa652da637dd037813f/skills/design-brief/SKILL.md)、[research-synthesis](https://github.com/mmmtheory/Skillset/blob/8c10ffe5fcfbd926c69d5fa652da637dd037813f/skills/research-synthesis/SKILL.md)、[checks](https://github.com/mmmtheory/Skillset/blob/8c10ffe5fcfbd926c69d5fa652da637dd037813f/skills/design-critique/references/checks.md)、[公开结果](https://github.com/mmmtheory/Skillset/blob/8c10ffe5fcfbd926c69d5fa652da637dd037813f/bench/results.json)、[LICENSE](https://github.com/mmmtheory/Skillset/blob/8c10ffe5fcfbd926c69d5fa652da637dd037813f/LICENSE)。规范对照：[W3C SC 2.3.3](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html)。

### B. GitHub technical-spike：取有限验证，舍弃无限搜索

实读插件 README、create-technical-spike SKILL、research-technical-spike agent 与 LICENSE。旧的 prompts 路径返回 404 后用仓库搜索找到了当前 skills 路径。

正向增量：明确哪个未知会改变决策、研究预算、可观察完成条件、查文档／现有实现／最小实验、证据与最后决策。这适合“插件是否真的能传图”等需要实际验证的任务，不能只用模型规格表推论。

不采用部分：原模板约 250 行、默认周级时限和独立 spike 文件，对小任务太重；研究 Agent 反复要求穷尽与递归跟进每条线索，还依赖 VS Code 工具名、固定路径、逐工具记录和审批停顿。此行为与用户希望省额、少等待冲突。**只验证单问题／有限预算的字段结构，不导入整位研究 Agent。**

DSH／AGY 可读 Markdown，但必须去掉 VS Code 插值和工具别名；读取官方网页和已有代码不需新服务，实验按已有工具与权限进行。无额外软件许可费用，研究调用量仍会消耗模型额度。

固定来源：[插件 README](https://github.com/github/awesome-copilot/blob/30a0d7465b14b05e05949d6588b99f7af0c537b4/plugins/technical-spike/README.md)、[SKILL](https://github.com/github/awesome-copilot/blob/30a0d7465b14b05e05949d6588b99f7af0c537b4/skills/create-technical-spike/SKILL.md)、[研究 Agent](https://github.com/github/awesome-copilot/blob/30a0d7465b14b05e05949d6588b99f7af0c537b4/agents/research-technical-spike.agent.md)、[LICENSE](https://github.com/github/awesome-copilot/blob/30a0d7465b14b05e05949d6588b99f7af0c537b4/LICENSE)。

### C. gstack：可研究局部方法，不把大管家变成 CEO 审议流程

实读 README 的安装／依赖／隐私与兼容段、两份长 SKILL 的元数据、范围、关键方法和执行段，以及 agents-digest；**不是对其全部工具实现的安全审计**。

可借鉴：先检查真实目标与代理指标、最小可行范围、既有能力、仅因新证据重开已定决策。适合 Plan 评审防止做错问题。

主要代价：CEO／设计审议含较多停顿、模式选择、强制外部意见、默认范围扩展或视觉产物，长 SKILL 加运行账本与辅助命令；直接装会与现有角色分工、两轮预算、用户明确范围冲突。完整工具需要 Git、Bun（文档测试 1.4.2／最低 1.3.3）及浏览器辅助，Windows 另涉及 Node；部分外部评审使用已有登录的其它模型，不能因仓库默认启用就自动获得授权。

真实兼容边界：README 声明 **AGY CLI 为实验性 host**，不是完全不支持；DSH 未列出原生 host，纯指令摘要可读不等于运行套件兼容。遥测默认关闭，但更新检查有网络行为；某些设计能力需要额外 API。当前不安装，不额外开模型。

固定来源：[README](https://github.com/garrytan/gstack/blob/b9bbc31c5c9b36ff4fe8e85493fd86491602b846/README.md)、[plan-ceo-review](https://github.com/garrytan/gstack/blob/b9bbc31c5c9b36ff4fe8e85493fd86491602b846/plan-ceo-review/SKILL.md)、[plan-design-review](https://github.com/garrytan/gstack/blob/b9bbc31c5c9b36ff4fe8e85493fd86491602b846/plan-design-review/SKILL.md)、[轻量摘要](https://github.com/garrytan/gstack/blob/b9bbc31c5c9b36ff4fe8e85493fd86491602b846/agents-digest/gstack-AGENTS.md)、[LICENSE](https://github.com/garrytan/gstack/blob/b9bbc31c5c9b36ff4fe8e85493fd86491602b846/LICENSE)。

### D. LFG：有用的是评测边界，整套流程与本项目重复

实读 README、SKILL、fast-path 评测说明、LICENSE。它强调质量先于速度、按风险决定流程强度、未知不能当通过、交接文件留证、返工先改变诊断。

但当前版本对轻任务也要求 architecture／feature-map／design 等产物；完整路径还含 PRD、进度 HTML、交接、全套测试与三次重规划，和现有 Plan 负责人、最多两轮返工明显冲突。原创性评分也不适合成为普通修复的强制阻断。原文本可跨 DSH／AGY 读取，辅助校验涉及 Python／pytest，选用 Jev 还可能引入外部付费服务；无需为了方法引入它。

值得借鉴的是其评测区分：静态合同／模板测试、路由评测、真实完成编码任务是三回事；要隔离工作目录，固定模型和工具，重复并轮换次序。仓库已有某些 e2e 是校验器／模板冒烟，不证明真实多 Agent 工作更好。保留现有协调机制，拿它检查我们的试验设计即可。

固定来源：[README](https://github.com/twilson63/lfg/blob/e9c17383575d95fb6604a33b99e4cc162ba20c6b/README.md)、[SKILL](https://github.com/twilson63/lfg/blob/e9c17383575d95fb6604a33b99e4cc162ba20c6b/SKILL.md)、[fast-path 评测](https://github.com/twilson63/lfg/blob/e9c17383575d95fb6604a33b99e4cc162ba20c6b/docs/evaluation/fast-path.md)、[LICENSE](https://github.com/twilson63/lfg/blob/e9c17383575d95fb6604a33b99e4cc162ba20c6b/LICENSE)。

### E. PM-Skills：交接结构有价值，作者的对照结果也否定“长指令必然更好”

实读 README 的功能／安装／维护段、deliver-prd SKILL、完整模板、HISTORY、评测方法页与一次弱模型试验记录、LICENSE。

与当前链路最相关的字段是：权威来源与冲突优先级、不应修改的对象及原因、每项要求的验证办法和验证人、遇到什么情况交给谁决定。AI 模型输出还需区分行为与确定性检查、预先确定判定规则、拒答／未知情形、分步骤证据，不把人为挑选的小样本冒充线上错误率。这些可融入已有交接，**不需另建一个 PRD 系统**。

原技能覆盖完整产品文档、指标、里程碑，对小任务过重；基线／目标没有用户依据时不能编造。`.claude/pm-skills.local.md` 只是可选记忆，写入规则也不是运行时并发保护，不能取代本项目单一状态负责人和 Obsidian。文字方法可迁移，Claude 子 Agent／钩子不能原样视为 DSH／AGY 兼容。核心 Markdown 无新依赖；整个插件装入 68 个技能有路由与上下文成本，伴随 MCP 已处维护模式，当前不需要。

**真实公开证据（作者记录，未独立重跑）**：HISTORY 报告强模型＋完整输入未测得技能收益；小模型＋薄输入有狭窄收益且主要来自模板；计数式后续试验因评分器不稳定而不可测。另一次弱模型跨技能试验按预注册规则判为无有效结论。不能把 README 的生产可用自述当成已证实的优越性；这些记录反而支持比较“现有方法、仅字段模板、完整候选”三臂。

固定来源：[SKILL](https://github.com/product-on-purpose/pm-skills/blob/9b920db418c5bf641edea9afb4915a286e1d42ea/skills/deliver-prd/SKILL.md)、[模板](https://github.com/product-on-purpose/pm-skills/blob/9b920db418c5bf641edea9afb4915a286e1d42ea/skills/deliver-prd/references/TEMPLATE.md)、[HISTORY 与对照](https://github.com/product-on-purpose/pm-skills/blob/9b920db418c5bf641edea9afb4915a286e1d42ea/skills/deliver-prd/HISTORY.md)、[评测方法](https://github.com/product-on-purpose/pm-skills/blob/9b920db418c5bf641edea9afb4915a286e1d42ea/site/src/content/docs/reference/evals.md)、[无结论试验](https://github.com/product-on-purpose/pm-skills/blob/9b920db418c5bf641edea9afb4915a286e1d42ea/docs/internal/release-plans/v2.33.0/records/output-eval-weak-model-20260816.md)、[LICENSE](https://github.com/product-on-purpose/pm-skills/blob/9b920db418c5bf641edea9afb4915a286e1d42ea/LICENSE)。

### F. Google：减少“品味审核”误伤交付

实读 reviewer standard、README 与 LICENSE。事实／数据优于个人偏好，细节建议应标明非阻断，合理改进不必等完美。这可用来约束 Plan 体验评审的误报；不能把“允许合理改进”曲解为代替用户验收或放过功能故障。仓库已归档，适合稳定原则参考，不能当新 Agent 平台指导；纯文本零运行依赖，采用须保留署名许可。

固定来源：[standard](https://github.com/google/eng-practices/blob/3bb3ec25b3b0199f4940b1aa75f0ac5c5753301c/review/reviewer/standard.md)、[README](https://github.com/google/eng-practices/blob/3bb3ec25b3b0199f4940b1aa75f0ac5c5753301c/README.md)、[LICENSE](https://github.com/google/eng-practices/blob/3bb3ec25b3b0199f4940b1aa75f0ac5c5753301c/LICENSE)。

## 4. 具体盲测假设与配置门槛

下表是**未执行的试验建议**，不是答案文件；需由另一评测者生成未见过的任务、固定判据与隐藏缺陷，避免把本报告变成考题答案。

| 试验 | 比较与可证伪假设 | 关键失败信号 |
| --- | --- | --- |
| 研究决定 | 当前 research-synthesis 对照加入有限 spike 结构；版本矛盾、同源转载和关键能力未知材料混合时，能以较少无关抓取形成有证据的决定 | 无实际验证就声称支持；无限追踪；把同源转载当多源证明 |
| 需求与交接 | 当前 writing-plans／requirements 对照仅精简交接字段、完整 PRD 三臂；薄输入下减少真实阻断问题，同时保留用户必需交付 | 自造指标；擅自替换明确需求；重复问已给信息；为了完整模板增设无关阶段 |
| 异常状态 | 当前 UX 对照加入有限 state-inventory；新异步任务场景中更完整覆盖未知结果、部分成功、重试和数据保留 | 把超时等同失败；诱发重复提交；枚举大量不适用状态；虚构发生概率 |
| 真实体验 | 两臂使用相同未见网页、真实桌面／窄屏／键盘／错误操作与截图；候选增加证据支持的发现且不增加偏好误报 | 只读源码当体验；没有看图却断言视觉正常；把 AAA 条目当 AA 必须项 |
| 能力受限 | 实际无法读图或浏览器不可用的隔离条件；能及时说明阻碍并保持未通过 | 反复无边界探测、用测试日志代替视觉通过、编造截图观察 |
| 轻量大管家 | 现有职责与加入短协调提示对照；已存在派单回执的状态查询只读取并汇报 | 重复派单、自行长方案、重开已完成阶段；没有提升则不新增技能 |

试验控制与通过条件：

- 主任务本轮执行顺序（已协调）：各臂共享相同短 JSON 输出契约与结构要求，先比较“无额外方法”与“当前方法”；看到具体差异后，再针对缺口加入更短方法或替代候选第三臂。这样控制调用量，也避免将格式要求的收益误归因于方法本身。
- 优先选上表前 3 类，以当前方法为真实基线，而非弱化的随口提示。一次只改变一个方法增量；模板有价值时增加模板臂，不捆绑一整套技能后归因。
- 每个关键场景建议至少 3 组独立匹配重复，交替运行顺序。此数量只是发现明显差异的起点，不能推导线上成功率或宣称统计显著。真实缺陷发现／需求保留优先于文笔评分。
- 固定实际运行模型、思考档、工具、权限、输入、时间／调用预算与资料快照。用户允许验证时用 MiMo 代替 Kimi，只限隔离验证会话；同一对照两臂均用 MiMo，结果不能外推为已验证 Kimi 的效果。
- 每次新会话与独立工作目录；不得让候选读基线答案、其它评测结论或隐藏评分材料。审阅者看匿名产物，隐藏组名，按预定功能／证据规则评分；主观等级有分歧时保留分歧。
- 记录真实模型与工具回执、输入／输出 token、工具次数、运行时间、阻碍和人工提示次数。来源缺失、通道／视觉不通单列为 blocked／不可比较，不能算技能失败或成功。
- 任何新增候选必须在预定缺口有可复现收益，且不新增越权、重复派单、假通过或大量无关产物。若仅模板与完整技能持平，优先较短模板；若无收益，保留现状。
- 真实网页验收仍需浏览器操作和实际读图。截图工具能返回文件不等于当前模型读过图。

## 5. 调查限制与下一步

网络与 GitHub 原始文件读取可用；本次没有上传用户材料。搜索结果页只用于发现，结论依赖上述实际文件。未安装、运行或审计这些仓库的所有脚本，未测 DSH／AGY 全套集成，没有依据声称任一作者方法是最优。源站维护／README 主张和本项目效果已分开。

本地 Obsidian 首页与记录约定已核对：上一轮 16 方法接入及部分真实测试是事实，但含视觉阻碍、超时及维护者准备的样例，不等于本轮独立候选比较完成。本轮主任务负责统一记录与配置；本子任务仅提供调研和可证伪假设。下一步先生成隔离盲测任务并跑当前基线，再测试少量候选；不因调研完成直接改七个角色。
