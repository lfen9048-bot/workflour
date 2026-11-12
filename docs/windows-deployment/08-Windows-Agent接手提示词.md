# 可直接复制给 Windows Agent 的接手任务

以下整段可复制。必须先学习当前架构和重要记录，再做安装；不是要求使用者替 Agent 执行终端命令。

---

请在这台 Windows 电脑上，基于私有仓库 https://github.com/lfen9048-bot/workflour 的源码，部署与已有 Mac 相同方法的多 Agent 编程工作流。使用这台电脑已有授权的GitHub登录克隆，不在命令/聊天里放token。请执行盘点、必要安装、Windows 移植、配置和真实验证，不只写建议。当前仓库保存的是 Mac 已实施版本和工作记录，Windows 适配尚未验收；不得假称克隆后可直接运行。

**第一步必须恢复上下文，暂不急着运行旧脚本。**依次读：

1. 根 README.md、AGENTS.md。
2. docs/PROJECT-OUTLINE.zh-CN.md、docs/CURRENT-STATUS.zh-CN.md。
3. docs/project-records/首页.md、01-需求/目标与待定事项.md、记录约定.md；再按首页读相关有效决策、搭建、验证记录，查看docs/evidence/2026-11-11/README.md中的脱敏结果与真实截图。Mac Obsidian 路径不可访问就使用这些仓库副本，明确哪些原始证据没有随库携带。
4. integrations/openmausbot/PLAN-CODE-WORKFLOW.md、team-v2/README.md、team-v2/roles.json；七个 agents/wf-*/SOUL.md 和 SKILLS.md；agents/wf-shared/CAPABILITIES.md、BROWSER.md；model-fallback/README.md、workbuddy/README.md。
5. docs/windows-deployment/00、01、02、03、04、05、06、09；需要找资料时查07索引。

恢复后简短说明：用户目标、Mac 已验证什么、真实遗留问题、Windows 差距、准备先做什么。历史双 Bot、8 Bot、三方长讨论、固定双编码和 08:00 均不是当前部署目标。记录与源码冲突时先核对，不能把历史 PASS 当 Windows 通过。

当前主流程是：大管家 → Plan 负责人调研初案 → Plan 评审 → 负责人定稿 → Gemini 主编码 → GLM 独立技术审核 → Plan 实际体验 → 用户验收。共七 Bot、六个 DSH profile 与一个独立 Antigravity 运行时，通常只有五角色参加主流程。协作编码与通用助手按需使用。

默认模型：大管家 DeepSeek V4.1 Flash/Low；Plan 负责人 Kimi K3.1 Pro/High；Plan 评审 DeepSeek Flash/High；Code 主编码 Gemini 3.8 Flash/High；Code 审核 GLM-5.3-Flash/High；协作编码 DeepSeek Flash/High；通用助手 DeepSeek Flash/Low。准确实例键见 roles.json。角色与模型分开，目标机实际目录不支持时明确报告，不用相似名字假装接入。

大管家只转交和汇报，不读业务源码重审。Plan 负责人是共享项目状态唯一维护者，记录原始需求、来源、假设与验收标准；技术内部设计交 Code。Plan 两人真实给出初案与独立意见，普通小任务不强制 helper。网页关键页面先做一次 preview consult，最终仍做独立浏览器体验。方案最多两轮，技术／产品返工共用两轮；真实回执、补充队列与安全续跑遵循 PLAN-CODE-WORKFLOW，不能用群公告替派单、不能清账本重派。最终停在待用户验收。

推荐源码 C:\workflour，项目 C:\workflour-projects，知识库 C:\workflour-notes\多Agent协作开发工作流。先盘点已有安装与目录；不覆盖非空项目。将真实程序路径、版本、数据目录、Windows 新 Bot ID 登记到本机私有部署记录。不要复用 Mac UUID、账号凭据、SSH 私钥、原任务数据库或公网配置。保留供应商许可证和技能来源。旧headless的setup-agents.sh/run-agent.sh不是本次新机安装入口，不直接运行。

从第02文档的官方来源安装 PowerShell、Node、Python、Git、DSH、WorkBuddy、已固定的 dsh-connect-workbuddy 5.13.1、独立 Antigravity CLI、OpenMausBot 0.1.143、Obsidian 和实际浏览器工具。先复用已装的软件，安装前核对当前版本。DSH 是六个 profile 共用一个程序；WorkBuddy 只提供调用与额度；AGY 用原生 agy acp（Mac的--stdio须目标版本支持才沿用），不能换 Gemini CLI 冒充。用户只负责账号登录及必要系统交互，不在聊天粘贴密钥。

先跑通一个 DSH profile 和一个 AGY 会话，再扩展全部七角色。第04文档列出的 Windows 适配必须真正完成：启动器/.cmd/stdio、fcntl/O_NOFOLLOW/原子替换、路径与UTF-8、幂等 setup、runtime识别、真实Bot映射、项目checker复制、observer/vault、桌面会话分类、浏览器环境。额外注意本机 WorkBuddy bridge 调用 Ruby YAML、签到用 python3+fcntl、pool-sync用POSIX用户/进程与文件权限假设，这些不是 Windows 可直接运行实现。优先成熟跨平台组件，不通过删除锁、假装成功或全量skip来凑通过。

额度策略：已核实免费（国际优先）→ 国际／国内临期账号 → 其余 WorkBuddy 积分 → 用户已有 DeepSeek API。区内先按插件池规则，再比较两区队首最早到期；不固定A/B轮流、不保证扣指定积分包。国内仅勾选账号，国际池关闭仅当前选中账号。默认DS可做等价通道选择，Kimi/GLM原模型正常保留，明确额度问题后才进入备用链。目录与价格实时校验，旧0折缓存不证明现在免费；网络、普通429、排队、认证错误和停止不授权跳付费API。

每天北京时间13:00执行国内个人账号签到并检查恢复；新回合重新检查原模型，正在执行的不打断，手动选择不覆盖。签到先查、未签才领、读回才算成功；已签也是成功，超时未确认不重复领取。Windows须适配锁和计划任务，不能复制Mac Codex automation id当成已安装。AGY没有自动跨运行时备用，阻塞须如实报告。

全部Bot可换模型和真实思考程度；设置卡默认只改当前任务，显式设默认才影响以后任务。跨运行时新建任务并交接，保留旧记录与原生审批要求。按已授权Full配置并核对DSH实际权限；Full不等于Windows管理员，也不代替用户验收。

后台采用同一已登录Windows用户、单实例、有界恢复、明确归属、活跃任务拒绝维护重启；主动down不被立即拉起。Obsidian观察已登记项目，显示阶段、角色记录、证据与异常；不通过观察器派单。分类使用真实cwd、工作区和标题，保留旧执行目录，不整理无关项目。

完成后必须从OpenMausBot网页向大管家交一个小网页需求，经Plan真实方案评审、单主编码、独立技术审核、桌面/手机浏览器体验，停在待验收。记录截图、交互、真实测试输出、当前代码快照与完整原生回执。你可以维护排障，但不可直接代发每个成员任务后称“自主跑通”；发生维护介入要记录。另验证停止/失败/补充队列/审批/重启对账/模型设置作用范围/额度错误分类和签到去重。

新功能先复用近期检索结果；版本变化或新约束补查官方实现，不上传我的材料。边实施边记录“计划、已执行、真实验证、未完成”，更新Windows知识库首页与交接。可独立解决的问题继续处理；只有登录、必要选择或外部阻塞才请我介入，并说明具体原因。

最后交付：可打开入口、七Bot模型和职责清单、Windows启停方式、完整演练证据、逐项验收结果、剩余问题、一页简单中文使用说明。区分“软件安装完成”“核心协作通过”“Windows全部验收通过”，不能让Mac证据代替Windows验证。

---


2026-11-11 历史配置曾补充研究综合、UX评审、测试覆盖/错误路径及属性与边界检查；当前启用状态以下方2026-11-12复验补充为准。请读 `integrations/openmausbot/team-v2/SKILLS.md` 和 `docs/SKILLS-SPECIALIZATION.zh-CN.md`：共享路径相对于角色SKILLS文件解析，使用文件工具读取，不为这四项方法新增软链接或安装整套Claude插件。按需加载，局部修复不重设设计。实际渠道无法读图就明确blocked，不能用截图存在/DOM检查冒充视觉验收。

## 2026-11-12 技能复验补充

先读 `docs/SKILLS-REVALIDATION.zh-CN.md` 与各角色当前 `SKILLS.md`。16项文件不代表16项都启用或已证明有效：研究综合限冲突/适用性问题按需使用，新UX、覆盖审核、PBT是候选。公开fixture已作为开发集使用，不能再称未见过的最终验收。Mac的HY3零倍率活动、图片配置和验证启动器不应复制为Windows免费保证；目标机重新核对，不自动退到付费。
