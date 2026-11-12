# 编码、调试、测试与审核技能再调研

后续测试及当前配置以 [复验结论](../../SKILLS-REVALIDATION.zh-CN.md) 为准；本文件是测试前的来源调查。

日期：2026-11-12。范围：七开发角色中的主编码、协作编码、独立审核及与其相接的验证方法。本轮仅调研，未修改活动技能、角色、业务、账号或模型配置；未调用本地 Agent 推理、安装依赖或读取密钥。

## 结论

现有 16 项方法已经覆盖主要类别；问题不是再添几个名称。更值得验证的是：是否依据契约解释失败、是否识别测试自身错误、是否保留正确的取消与缺省行为、是否在证据充分后停止、是否把小修复扩成框架或设计重建。

**建议保留现有薄适配，先做未见过的盲测，再按失败点小改。** 新候选中，Google 工程实践适合校准审核阻断标准，Hypothesis 官方资料适合补强性质/状态模型与反例的理解，Microsoft 实现适合澄清浏览器自动化证据的边界；Sentry 的轻量 code-review 可作为独立交叉依据。没有发现值得整套替换本地编程流程的包。

本报告不是行为效果证明。网页营销、星数和发布时间没有被当成有效性证据。共核对七个独立发布来源；Sentry code-simplifier 明确派生自 Anthropic，因此该条不计作第二份独立方法证据。

## 检索与本地覆盖

使用 search-first：读取本地技能目录和全部 16 项入口的名称/触发说明，完整阅读与编码相关的 systematic-debugging、test-driven-development、receiving-code-review、verification-before-completion、differential-review、test-coverage-review、property-based-testing、sharp-edges；进一步读了本地错误路径、属性编写及失败归因参考。其它八项作为路由上下文核对，未借本任务重审研究、Obsidian 或产品设计全套。

现有目录：调研/计划类 search-first、research-synthesis、requirements-interview、writing-plans；编码验证类 systematic-debugging、test-driven-development、receiving-code-review、verification-before-completion、differential-review、test-coverage-review、property-based-testing；体验类 sharp-edges、frontend-design、webapp-testing、ux-critique；记录类 obsidian-markdown。

通用检索包括：

- GitHub agent skills code review test coverage debugging property based testing SKILL.md
- GitHub superpowers systematic debugging test driven development skill
- GitHub Google engineering practices code review guidelines testing
- Sentry skills code-review/find-bugs、Hypothesis stateful/model/shrinking 官方资料

检索用公开通用词，不提交用户代码。GitHub connector 用于读取候选实际文件、固定提交、许可和仓库维护元数据；搜索页面只发现入口，结论以原始文件为准。未进行 npm/PyPI 安装或注册表横向包性能比较，本轮目标是方法选型。

## 固定版本与维护状态

GitHub 的更新时间可能只是仓库活动，不能当成方法文件已改进。以下记录读取时的默认分支提交；是否维护与是否适合当前任务分开判断。

| 独立来源 | 固定提交 | 最近提交日期（UTC）/状态 | 许可核对 |
|---|---|---|---|
| obra/superpowers | [`22f0b463e7a5e579904dd6211a520321035526f7`](https://github.com/obra/superpowers/commit/22f0b463e7a5e579904dd6211a520321035526f7) | 2026-11-03；未归档 | MIT |
| trailofbits/skills | [`e4dd0bb5b15535f7c5a0834187dffba6ac37e4ff`](https://github.com/trailofbits/skills/commit/e4dd0bb5b15535f7c5a0834187dffba6ac37e4ff) | 2026-11-06；未归档 | CC-BY-SA-4.0 |
| anthropics/claude-plugins-official | [`e37d307bd9f85dab6fea5dfb5e3dc146753b2d2d`](https://github.com/anthropics/claude-plugins-official/commit/e37d307bd9f85dab6fea5dfb5e3dc146753b2d2d) | 2026-11-11；未归档 | PR Review Toolkit 的 Apache-2.0 |
| google/eng-practices | [`3bb3ec25b3b0199f4940b1aa75f0ac5c5753301c`](https://github.com/google/eng-practices/commit/3bb3ec25b3b0199f4940b1aa75f0ac5c5753301c) | 2024-09-19；已归档 | 文档 CC-BY-3.0 |
| getsentry/skills | [`e94f22214528d69899d09c627b3315ddc3544816`](https://github.com/getsentry/skills/commit/e94f22214528d69899d09c627b3315ddc3544816) | 2026-11-05；未归档 | Apache-2.0 |
| HypothesisWorks/hypothesis | [`9ab0be61aaaa27396fc1bbf4b34e7925cc68d1e2`](https://github.com/HypothesisWorks/hypothesis/commit/9ab0be61aaaa27396fc1bbf4b34e7925cc68d1e2) | 2026-11-06；未归档 | 代码 MPL-2.0；本轮仅引用文档，不移植其全文 |
| microsoft/playwright | [`bac1f9f67e9cff2a8e7ecbac25d56ec3bb1d15c6`](https://github.com/microsoft/playwright/commit/bac1f9f67e9cff2a8e7ecbac25d56ec3bb1d15c6) | 2026-11-12；未归档 | Apache-2.0 |

Google 仓库已归档，最近提交在 2024 年；其取舍原则仍可作为参考，不能称其技能活跃更新。Hypothesis 当前提交为 6.170.15；源码配置要求 Python ≥3.11、sortedcontainers，源码构建使用 maturin/Rust。它兼容现有 unittest/pytest，不代表可以在用户项目擅自安装或更新。Playwright 引用的是固定源码提交，不是对本机版本升级的建议。

## 候选逐项比较

### 1. obra/superpowers：保留调试与测试方法，不安装整套流程

实际 SKILL 保留了有价值的最小复现、边界取证、单一假设与有针对性的修复。writing-good-tests 更具体地要求为测试指出能捕获的错误、独立推导预期、在不可控边界使用替身，并允许当参数/次数/顺序属于契约时验证它们。condition-based-waiting 区分等待业务条件与验证 debounce 等真实时间行为。[测试参考](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/test-driven-development/writing-good-tests.md)、[等待参考](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/systematic-debugging/condition-based-waiting.md)。

不直接采用整套：TDD 入口仍要求已先写实现就删除重来、例外询问人类、完成前跑全套项目测试；调试入口要求四阶段完整执行及三次失败后的架构讨论，还含没有实验依据的效果数字。它们会与本地两轮返工预算、既有实现和低影响修改范围冲突。Antigravity 的原生安装在 README 中有说明，但整包启动引导会介入会话流程；DSH 自动发现本轮未验证。纯方法通过现有文件工具读取即可，无必要引入插件启动框架。[TDD 入口](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/test-driven-development/SKILL.md)。

具体取舍：本地已经是同一固定版本的短适配，不应以“上游更完整”为由恢复这些强制流程。可以盲测“测试先报错究竟是 bug、预期错还是无关导入错”与“调用次数是否契约”两类判断；不能用一刀切的禁 mock 规则替代判断。

### 2. Trail of Bits：保留风险与反例方法，限制安全审计与性质等级

PBT 的失败参考明确区分实现违约、生成域错误、性质错误、规格未定；reviewing 还承认不明显纯函数的重复调用可以验证确定性。这些都比只看装饰器或测试数量有价值。[失败分类](https://github.com/trailofbits/skills/blob/e4dd0bb5b15535f7c5a0834187dffba6ac37e4ff/plugins/property-based-testing/skills/property-based-testing/references/interpreting-failures.md)。

缺点：原始入口给出固定性质强弱排序；reviewing 使用固定 CRITICAL/HIGH 等级，要求列出所有级别；“没性质先重构”容易扩大范围。differential-review 原版是安全专项：必须 blame、定量调用半径、长报告，另有专用子 Agent；明确不适用于无基线的新代码。直接给日常独立审核会增加过程成本并误拒绝新项目。[差异安全审计入口](https://github.com/trailofbits/skills/blob/e4dd0bb5b15535f7c5a0834187dffba6ac37e4ff/plugins/differential-review/skills/differential-review/SKILL.md)。

本地已移除这些冲突，并补了无 Git 基线时需求审核、正常取消/缺省、有效证据复用、合法/非法输入的错误契约。因此优先检验适配是否真正执行，不再加另一套安全 Agent。保留 CC-BY-SA-4.0 来源与改编归属；没有将其许可改成 MIT。

### 3. Anthropic PR Review Toolkit：覆盖思路适用，silent-failure 原版误报风险高

pr-test-analyzer 关注行为覆盖、测试能否捕获回归、已有集成测试是否已经覆盖，以及新增测试的价值；不追求 100% 行覆盖，适合本地审核。[原始测试审核 Agent](https://github.com/anthropics/claude-plugins-official/blob/e37d307bd9f85dab6fea5dfb5e3dc146753b2d2d/plugins/pr-review-toolkit/agents/pr-test-analyzer.md)。

silent-failure-hunter 把任何未记录/未反馈的错误、宽泛捕获和空 catch 直接提升为严重问题，并绑定 Sentry/Statsig/errorIds，还建议用 Claude Task 子 Agent。这会误报约定内用户取消、可选文件不存在、顶层统一捕获，或要求各层重复日志。本地 error-paths 的契约优先版本更适合当前系统。[原始失败审核 Agent](https://github.com/anthropics/claude-plugins-official/blob/e37d307bd9f85dab6fea5dfb5e3dc146753b2d2d/plugins/pr-review-toolkit/agents/silent-failure-hunter.md)。

当前仓库提交比本地来源记录更新，但本轮没有证明这两份方法相对本地固定原文发生了有效改进；不能仅凭仓库更新就升级。移植的是 Markdown 方法而非 Claude 插件，原 model/color/Task 元数据不进入 DSH/AGY。

### 4. Google Engineering Practices：新的审核尺度参考

standard 要求基于事实与工程原则，避免用个人风格阻断整体改进；looking-for 明确测试本身也需要审查，关注复杂度是否来自当前真实问题，不为未来假设过度通用化。它也说明用户可见变化需要观察行为、局部审核应写清覆盖范围。[审核标准](https://github.com/google/eng-practices/blob/3bb3ec25b3b0199f4940b1aa75f0ac5c5753301c/review/reviewer/standard.md)、[具体检查项](https://github.com/google/eng-practices/blob/3bb3ec25b3b0199f4940b1aa75f0ac5c5753301c/review/reviewer/looking-for.md)。

取舍：这些方法可以用于评判审核输出是否过度，不需要新增“Google审核”技能或第二审核轮。它的公司角色、升级讨论和 CL/LGTM 术语不直接移植；技术审核的认可不等于本项目用户最终验收。文档许可实际为 CC-BY-3.0，GitHub 元数据 NOASSERTION 不是无许可；若以后改编文本应保留归属。无运行依赖，适合 DSH/AGY 纯文件参考。

### 5. Sentry Skills：轻量 code-review 值得对照，find-bugs/iterate-pr 不常驻

code-review 约 373 英文词，覆盖副作用、兼容性、行为测试和风险取舍，并明确不因风格偏好阻断。适合验证本地审核是不是只有“找错”而没有合理放行。[code-review](https://github.com/getsentry/skills/blob/e94f22214528d69899d09c627b3315ddc3544816/skills/code-review/SKILL.md)。

find-bugs 虽只有约 431 词，却要求对每个文件检查全部安全项、读取全 diff、每项逐项结账，并依赖 gh 查询默认分支；短不等于轻。iterate-pr 需要 authenticated gh、uv、当前仓库，含 commit/push、外部评论和 CI 轮询，会抢现有 Plan/Code 调度职责，不应由普通技能读取自动启用。[find-bugs](https://github.com/getsentry/skills/blob/e94f22214528d69899d09c627b3315ddc3544816/skills/find-bugs/SKILL.md)、[iterate-pr](https://github.com/getsentry/skills/blob/e94f22214528d69899d09c627b3315ddc3544816/skills/iterate-pr/SKILL.md)。

code-simplifier 强调保持行为与局部改动，但示例带 Sentry/React/ES module 约定，且声明派生自 Anthropic。可借鉴“维护性不等于行数最少”的判断，不复制固定代码风格，不把小错误修复附赠重构。README 采用通用 Agent Skills 格式；DSH/AGY 自动发现本轮未实测，手动文件读取没有特定运行依赖。

### 6. Hypothesis 官方：补强概念与状态模型，避免框架崇拜

quickstart 展示 @given 可在普通 unittest/pytest 使用。stateful 文档先指出简单情况不需要状态机；其真实数据库与独立 dict 模型对照示例，展示可复现操作序列、前置条件和逐步不变量。值得用来测试“多个动作组合才暴露问题”的能力，不能把它理解为每个任务都重建状态模型。[quickstart](https://github.com/HypothesisWorks/hypothesis/blob/9ab0be61aaaa27396fc1bbf4b34e7925cc68d1e2/hypothesis/docs/quickstart.rst)、[stateful](https://github.com/HypothesisWorks/hypothesis/blob/9ab0be61aaaa27396fc1bbf4b34e7925cc68d1e2/hypothesis/docs/stateful.rst)。

strategies-that-shrink 明确只有现有缩减效果导致实际成本时才调优；复杂生成器会影响缩减。优先使用已有公共 API，内部技巧可能在补丁版本变化，不适合写成本地通用步骤。[缩减设计说明](https://github.com/HypothesisWorks/hypothesis/blob/9ab0be61aaaa27396fc1bbf4b34e7925cc68d1e2/guides/strategies-that-shrink.rst)。

关键新发现：官方 README 就使用 sorted(set(xs)) 丢重复元素作为例子，与前轮 PBT 测试高度重合。那个样本可证明读取/执行，但不能独立证明陌生任务上的性质选择能力。新的盲测应换用协议字段、别名输入、状态序列和错误 oracle，并保留无缺陷负对照。没有 Hypothesis 时仍可用标准库做有界性质检查；不可声称执行了未运行的框架缩减。库实际依赖与 Python 版本应由目标项目约束决定，不能自动新增。[官方示例](https://github.com/HypothesisWorks/hypothesis/blob/9ab0be61aaaa27396fc1bbf4b34e7925cc68d1e2/README.md)、[实际依赖声明](https://github.com/HypothesisWorks/hypothesis/blob/9ab0be61aaaa27396fc1bbf4b34e7925cc68d1e2/hypothesis/pyproject.toml)。

### 7. Microsoft Playwright：具体工具语义比再加测试框架更重要

官方 best-practices 建议用户可观察行为、测试隔离、显式契约定位、自动重试断言和只模拟不可控外部边界。CI trace 按失败需要启用，而不是每个测试一直录制。它也含 JS runner、安装和 CI 建议，不应全部带进本机现成 Python Playwright 流程。[官方测试实践](https://github.com/microsoft/playwright/blob/bac1f9f67e9cff2a8e7ecbac25d56ec3bb1d15c6/docs/src/best-practices-js.md)。

实际 dom.ts 的 _performPointerAction 在操作前执行 scroll-into-view，再求可点击点。因此“定位器 click 成功”不能作为初始视口按钮可见的证据。这里已有源码级依据，不只是经验猜测。应在操作前记录视口/几何或截图，并与动作后的状态分开；自动滚动后成功不等于初始体验通过。[指针操作实现](https://github.com/microsoft/playwright/blob/bac1f9f67e9cff2a8e7ecbac25d56ec3bb1d15c6/packages/playwright-core/src/server/dom.ts)。

这项应补强现有 webapp-testing 的工具理解，而非新增第 17 套测试框架。运行仍使用本机已验证入口；缺浏览器、图片传输不支持和任务超时必须与技能文件读取成功分开报告。

## 最小取舍与加载方式

| 角色/方法 | 保留或补强方向 | 不引入 |
|---|---|---|
| 主编码：调试/TDD | 当前短入口 + 有具体失败才读 tracing/waiting；真实生产边界、独立预期、最小修复 | 全任务严格TDD、删除已有实现、每次全套测试、自动重设设计 |
| 独立审核：差异/覆盖 | 先需求与实际差异，再按风险追调用者；覆盖声明限实际输入；合理取消/缺省可放行 | 全文件安全清单、固定百分比/等级、审查者直接改业务、第二套循环 |
| 协作编码/审核：PBT | 有契约和组合输入价值才启用；独立模型、别名隔离、反例归因 | 无条件安装库、用固定性质排序判断优劣、把每个通过都当证明 |
| 网页主编码/体验检查 | 原始视口与自动操作后状态分别取证；限定范围复用脚本 | click成功=初始可见、DOM/哈希=读图、整套换runner/CI |
| 审核反馈处理 | 依据证据接受或反驳，非阻断建议不拖住交付 | 盲目照改、为了绿色改错验收、借小修复做代码整理运动 |

无需新增全局技能名。新参考若盲测证明有效，可只在现有文件加一条路由或一段短解释。上游长原文保留来源作用：例如 Superpowers 两个入口各约 1,450 英文词，Trail differential 约 1,088 词，Playwright 最佳实践约 2,742 词；不能一并常驻塞给每个 Bot。描述和角色索引负责低成本选路，只有当前问题需要才加载相关参考。

## 建议的盲测假设（尚未执行）

不是把以下答案写进 Agent 的 TASK。由独立制作方保留 oracle，Agent 只收到正常需求、原始实现与既有测试；任务中不提示埋了哪种缺陷。

| 新案例 | 要验证的判断 | 对照与失败信号 |
|---|---|---|
| 可选缓存读取 | FileNotFoundError 可默认空；权限拒绝/损坏不能被同一分支伪装成空 | 正确实现和 catch OSError 变体并列；把所有默认值都报错算误报 |
| 取消后清理 | 正常 cancelled、资源释放、不发第二次请求 | 一个真实错误变体把取消当成功/重试；无错误弹窗本身不能报 Bug |
| 错误预期与真实缺陷混合 | 从契约判断 CSV/协议转义后的条目，不按失败测试直接改生产代码 | 交换实现正确/预期错误与实现错误/预期正确两个版本；命中位置需有可重现输入 |
| 幂等与确定性 | 稳定规范化的 f(f(x)) 是有效性质；非纯序列化的重复调用可检验确定性 | 不充分性质与真正恒真断言同时存在；不能一概说“自己比自己” |
| 编解码双方共享错误 | roundtrip通过但固定格式的独立golden不符 | 字段大小端或版本位实现；要求判断是否真有格式契约，不能为了找问题自造标准 |
| 变异输入别名 | 操作原地改写输入后前后对象相同导致误通过 | 正确快照与同一引用对照；能发现测试问题而不是谎称实现不变 |
| 状态序列 | add/remove/retry 在独立简单模型下保持契约 | 含生产Bug、oracle模型Bug和未定义行为三种；不能把每个反例都归生产 |
| 异步边界 | 回执丢失但远端已完成时，先核对，不重复有副作用动作 | 纯本地fake远端，不调用真实收费/消息服务；不得误称额度不足 |
| 已认可页面单处修复 | 只验证失败提示与受影响布局，不重新设计、不创建框架 | 无新依赖、无额外预览轮、保留既有主题/行为；仍能报告缺图像能力 |
| 新项目无Git基线 | 可依据明确需求审核当前代码 | 不伪造diff、不因无PR/无gh拒绝；不启动完整安全审计 |

至少使用未见过的不同实现、输入形状与无缺陷负对照，不能只换昨天排序样例的数字。前后对照固定实际模型/额度线路、思考档位、权限、上下文和任务材料；随机化顺序，记录源码/技能快照。开发集上的修补另用未见过的 holdout 检查，避免把已知答案写回技能后测同一道题。

优先评价实质缺陷召回、无缺陷误报、错误预期归因、未授权修改/新依赖/委派、反例可复现性、按边界停止、观察与声称一致。工具次数/墙钟作为次要成本数据，运行时上下文 used 不等同累计收费token；超时和能力受阻单列。样本很少时只报告该组结果，不能推广成普遍提速或质量保证。

## 阅读登记与限制

下面是实际读取的固定文件。README 长文件只重点读取安装/支持平台/技能列表/许可部分；SKILL 和选中的关键参考已阅读，Playwright 实现只读取 _performPointerAction 相关段落，不声称通读框架。Google 完整许可头和 README 已核对为 CC-BY-3.0；其它许可也实际打开核对，不只依赖 GitHub SPDX 元数据。

### obra/superpowers

- [README.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/README.md)
- [LICENSE](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/LICENSE)
- [skills/systematic-debugging/SKILL.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/systematic-debugging/SKILL.md)
- [skills/systematic-debugging/condition-based-waiting.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/systematic-debugging/condition-based-waiting.md)
- [skills/test-driven-development/SKILL.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/test-driven-development/SKILL.md)
- [skills/test-driven-development/writing-good-tests.md](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/test-driven-development/writing-good-tests.md)

### trailofbits/skills

- [README.md](https://github.com/trailofbits/skills/blob/e4dd0bb5b15535f7c5a0834187dffba6ac37e4ff/README.md)
- [LICENSE](https://github.com/trailofbits/skills/blob/e4dd0bb5b15535f7c5a0834187dffba6ac37e4ff/LICENSE)
- [plugins/differential-review/skills/differential-review/SKILL.md](https://github.com/trailofbits/skills/blob/e4dd0bb5b15535f7c5a0834187dffba6ac37e4ff/plugins/differential-review/skills/differential-review/SKILL.md)
- [plugins/property-based-testing/skills/property-based-testing/SKILL.md](https://github.com/trailofbits/skills/blob/e4dd0bb5b15535f7c5a0834187dffba6ac37e4ff/plugins/property-based-testing/skills/property-based-testing/SKILL.md)
- [plugins/property-based-testing/skills/property-based-testing/references/reviewing.md](https://github.com/trailofbits/skills/blob/e4dd0bb5b15535f7c5a0834187dffba6ac37e4ff/plugins/property-based-testing/skills/property-based-testing/references/reviewing.md)
- [plugins/property-based-testing/skills/property-based-testing/references/interpreting-failures.md](https://github.com/trailofbits/skills/blob/e4dd0bb5b15535f7c5a0834187dffba6ac37e4ff/plugins/property-based-testing/skills/property-based-testing/references/interpreting-failures.md)

### anthropics/claude-plugins-official

- [plugins/pr-review-toolkit/LICENSE](https://github.com/anthropics/claude-plugins-official/blob/e37d307bd9f85dab6fea5dfb5e3dc146753b2d2d/plugins/pr-review-toolkit/LICENSE)
- [plugins/pr-review-toolkit/agents/pr-test-analyzer.md](https://github.com/anthropics/claude-plugins-official/blob/e37d307bd9f85dab6fea5dfb5e3dc146753b2d2d/plugins/pr-review-toolkit/agents/pr-test-analyzer.md)
- [plugins/pr-review-toolkit/agents/silent-failure-hunter.md](https://github.com/anthropics/claude-plugins-official/blob/e37d307bd9f85dab6fea5dfb5e3dc146753b2d2d/plugins/pr-review-toolkit/agents/silent-failure-hunter.md)

### google/eng-practices

- [README.md](https://github.com/google/eng-practices/blob/3bb3ec25b3b0199f4940b1aa75f0ac5c5753301c/README.md)
- [LICENSE](https://github.com/google/eng-practices/blob/3bb3ec25b3b0199f4940b1aa75f0ac5c5753301c/LICENSE)
- [review/reviewer/standard.md](https://github.com/google/eng-practices/blob/3bb3ec25b3b0199f4940b1aa75f0ac5c5753301c/review/reviewer/standard.md)
- [review/reviewer/looking-for.md](https://github.com/google/eng-practices/blob/3bb3ec25b3b0199f4940b1aa75f0ac5c5753301c/review/reviewer/looking-for.md)

### getsentry/skills

- [README.md](https://github.com/getsentry/skills/blob/e94f22214528d69899d09c627b3315ddc3544816/README.md)
- [LICENSE](https://github.com/getsentry/skills/blob/e94f22214528d69899d09c627b3315ddc3544816/LICENSE)
- [skills/code-review/SKILL.md](https://github.com/getsentry/skills/blob/e94f22214528d69899d09c627b3315ddc3544816/skills/code-review/SKILL.md)
- [skills/find-bugs/SKILL.md](https://github.com/getsentry/skills/blob/e94f22214528d69899d09c627b3315ddc3544816/skills/find-bugs/SKILL.md)
- [skills/code-simplifier/SKILL.md](https://github.com/getsentry/skills/blob/e94f22214528d69899d09c627b3315ddc3544816/skills/code-simplifier/SKILL.md)
- [skills/iterate-pr/SKILL.md](https://github.com/getsentry/skills/blob/e94f22214528d69899d09c627b3315ddc3544816/skills/iterate-pr/SKILL.md)

### HypothesisWorks/hypothesis

- [README.md](https://github.com/HypothesisWorks/hypothesis/blob/9ab0be61aaaa27396fc1bbf4b34e7925cc68d1e2/README.md)
- [LICENSE.txt](https://github.com/HypothesisWorks/hypothesis/blob/9ab0be61aaaa27396fc1bbf4b34e7925cc68d1e2/LICENSE.txt)
- [hypothesis/pyproject.toml](https://github.com/HypothesisWorks/hypothesis/blob/9ab0be61aaaa27396fc1bbf4b34e7925cc68d1e2/hypothesis/pyproject.toml)
- [hypothesis/docs/quickstart.rst](https://github.com/HypothesisWorks/hypothesis/blob/9ab0be61aaaa27396fc1bbf4b34e7925cc68d1e2/hypothesis/docs/quickstart.rst)
- [hypothesis/docs/stateful.rst](https://github.com/HypothesisWorks/hypothesis/blob/9ab0be61aaaa27396fc1bbf4b34e7925cc68d1e2/hypothesis/docs/stateful.rst)
- [guides/strategies-that-shrink.rst](https://github.com/HypothesisWorks/hypothesis/blob/9ab0be61aaaa27396fc1bbf4b34e7925cc68d1e2/guides/strategies-that-shrink.rst)

### microsoft/playwright

- [LICENSE](https://github.com/microsoft/playwright/blob/bac1f9f67e9cff2a8e7ecbac25d56ec3bb1d15c6/LICENSE)
- [docs/src/best-practices-js.md](https://github.com/microsoft/playwright/blob/bac1f9f67e9cff2a8e7ecbac25d56ec3bb1d15c6/docs/src/best-practices-js.md)
- [packages/playwright-core/src/server/dom.ts](https://github.com/microsoft/playwright/blob/bac1f9f67e9cff2a8e7ecbac25d56ec3bb1d15c6/packages/playwright-core/src/server/dom.ts)

未核对项：未逐条审计仓库全部脚本、供应链或所有历史 issue；未安装候选、未验证任何 DSH/AGY 自动发现、未评测新方法的真实模型表现；未验证 Windows/Ubuntu 安装、Playwright 当前源码与本机版本的所有差异；Hypothesis 原生构建/wheel 和文档单独授权细节未作分发审计。本轮引用官方文档理解方法，未复制其大段内容进入活动技能。Sentry 的企业工作流和 Google 的组织升级路径不是本项目已授权操作。

访问限制如实记录：首次 Sentry commits API 读取失败，随后通过 commits?per_page=1 得到固定提交；旧的 Hypothesis hypothesis-python/docs 路径返回404，经根目录核对后改读当前 hypothesis/docs。没有把404当成候选不存在，也没有以搜索摘要替代原文。
