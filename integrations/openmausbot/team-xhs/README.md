# 小红书图文：三个 Agent

用户确认先做图文，并要求精简流程、节省额度。第二套保留三个岗位：

| 入口 | 默认运行时/模型 | 思考档位 | 职责 |
| --- | --- | --- | --- |
| 小红书 · 采集 | DSH / WorkBuddy DeepSeek V4.1 Flash | Low | 获取来源与素材，交 sources.json |
| 小红书 · 思考 | DSH / WorkBuddy MiMo-V2.6-Pro | High | 轻量负责人：安排采集、短简报、安排写作、最终检查 |
| 小红书 · 写作 | Antigravity / Gemini 3.8 Flash | Low | 文案、卡片内容、按需生图和实际图片交付 |

日常向「小红书 · 思考」说主题即可。默认一篇采集/思考/写作各一轮，标题和标签并入写作，审稿/初期复盘并入思考。已有编程团队保持原有职责、模型和项目，不把小红书任务送入 Plan/Code 多阶段链路。

2026-11-11 初次多模型接入遵循用户“先接入，不测试”，后续已获准进行小样本通道检查。2026-11-12 用户明确选择 DeepSeek 采集并授权技能实测，采集新默认更新为上表；GLM-5.3-Flash Low、MiniMax-M3.1-Flash Low 仍可选。新默认用于以后新任务，既有任务固定原模型；用户后续手动选择优先，不自动轮流比较。单项采集验证不能代替完整图文工作流验收。

## 本机安装与部署

以下是维护 Agent 的操作接口，不要求用户执行终端。

```sh
./integrations/openmausbot/setup.sh --only xhs-collector
./integrations/openmausbot/setup.sh --only xhs-planner
./integrations/openmausbot/setup.sh --only xhs-writer
./integrations/openmausbot/setup.sh --only xhs-writer-dsh
python3 scripts/provision-xhs-team.py prepare
python3 scripts/provision-xhs-team.py create
python3 scripts/provision-xhs-team.py verify
```

setup 只生成选定 profile 和实例，没有模型任务。`xhs-writer` 登记/复用 `agy-gemini`；可选 `xhs-writer-dsh` 生成 `omb-xhs-writer-dsh`，作为同一个写作 Bot 的 WorkBuddy 正文通道，加载同一套写作职责与技能，仍然只有三个 Bot。模型卡识别小红书写作身份后优先使用该 DSH 实例；切 GLM 正文时沿用安全切换工具的跨运行时新任务与交接，生图继续调用 Gemini 原生 print。运行服务读取新实例前应核对空闲并通过现有后台入口安全重启；不强行中断 Bot。`create` 只创建机器清单中缺失的三 Bot，不重复创建、不发消息、不改已有 Bot 的手动模型、不重排现有团队。源文件变更后用 `instructions`，它会先要求这三 Bot 全部空闲，只更新三者职责说明。

`roles.json` 仅保存相对文件路径和初始默认。真实 ID 默认保存在 `~/.workflour/xhs/deployment.json`；可用环境变量 `XHS_DEPLOYMENT_MANIFEST`（兼容 `WORKFLOUR_XHS_DEPLOYMENT`）或 `--manifest PATH` 指定私有机器文件。新电脑生成自己的清单，不复制 Mac Bot ID、原生会话或账号配置。职责中的 `{{ROOT}}` 占位由部署器动态解析为本机仓库路径。

部署器和工作流共用 `scripts/xhs_paths.py`：优先 `XHS_DEPLOYMENT_MANIFEST`，其次兼容变量 `WORKFLOUR_XHS_DEPLOYMENT`，最后默认路径，均展开 `~`。部署器的 `--manifest` 仅覆盖该次部署命令；后续工作流使用自定义清单时，也要设置同一环境变量。

`models.json` 声明 GLM-5.3-Flash、MiMo-V2.6-Pro、MiniMax-M3.1-Flash、DeepSeek V4.1 Flash 四个 WorkBuddy 模型与各角色选项。setup 仅将其合入三个小红书 DSH profile 的 `enabledModelIds` / `imageModelIds`，不修改 desktop、账号选择或账号池。图片输入勾选不等于生图权限。MiniMax 的上游默认档位为 Max，采集选择时显式设 Low。

两个默认 DSH 角色与可选写作 DSH 实例只扫描各自角色技能目录。ACP 启动继续同步桌面已勾选账号池，保留既有额度失败策略：默认 DeepSeek 的同系列路由优先核实免费、临期与其他 WorkBuddy 额度；GLM、MiMo、MiniMax 先按所选模型请求。此次没有把 MiMo/MiniMax 扩入自动省额度候选枚举，不能声称它们已覆盖整条免费→临期→其他额度链。用户手动换模型优先；价格和促销实时核对，历史缓存不等于免费。Antigravity 不加载 DSH 额度策略，也不自动跨运行时备用。

## 内容项目与原生派单

思考为唯一共享状态维护者；collector 只写 sources.json/collection-report.md，writer 只写 draft.md、cards.json、output/*、writing-report.json。

维护工具为 `scripts/xhs-workflow.py`：

```sh
python3 scripts/xhs-workflow.py init --project /实际项目目录 --topic '用户主题' --planner-thread 当前会话ID
python3 scripts/xhs-workflow.py status --project /实际项目目录
python3 scripts/xhs-workflow.py receipt --project /实际项目目录 --stage collect --id 真实原生回执
python3 scripts/xhs-workflow.py record --project /实际项目目录 --stage collect --file sources.json --receipt 真实原生回执 --thread worker真实会话
python3 scripts/xhs-workflow.py record --project /实际项目目录 --stage brief --file BRIEF.md
python3 scripts/xhs-workflow.py receipt --project /实际项目目录 --stage draft --id 真实原生回执
python3 scripts/xhs-workflow.py record --project /实际项目目录 --stage draft --file draft.md --receipt 真实原生回执 --thread worker真实会话
python3 scripts/xhs-workflow.py finish --project /实际项目目录
```

init会生成本项目独立的 `state.dispatch_tokens.collect/draft` 两个UUID。专业任务用原生 `coordinate_bots`，必须 `mode=work`，采集/写作任务正文分别带 `WF-DISPATCH:<对应阶段UUID>`，记录准确 requestId。receipt会核对真实requester为本套planner、target为正确worker、原生work类型和该项目token；其他项目和consult回执不能冒充本阶段完成。成功派单后结束当前回合等原生回传，不轮询、不反向委派、不重复派单。派单首行可用「工作流会话标题：小红书 · 采集/写作 · 主题」复用现有 DSH 标题钩子；在仓库范围内的真实 cwd 由现有单写者归组，无新增角色白名单。

以上子命令只维护项目材料，不派消息、不发布。脚本检查材料/哈希/顺序不能代替内容事实、实际生图或用户验收。工作只到草稿待用户确认，所有发布/上传/排期/互动都不在本套当前范围。

X/YouTube限额在派单前通过 `collection-limits --project ABS --source all --candidates 3 --details 2 --comments 2` 设置；可另设source=x/youtube更小额度。新init默认10/5/10，start默认3/2/2；候选与精读为两平台合计，comments为每次精读。采集器按输出目录定位项目，在网络请求前锁定并记录 `.xhs/social-usage.json`，失败也占用额度，新文件名不能重置；派单/请求开始后拒绝改限额。旧项目无此字段时保留原接口，不补造历史次数。该约束作用于本项目的X/YouTube适配器，不是文件沙箱，也不限制上游接口内部预取，更不代表其他采集器已具有同样的累计检查。

局部改稿顺序固定：先record首稿，再 `revise --project ABS --reason TEXT --evidence review.md` 归档/登记范围/换draft token，最后原生 `mode=work,rework:true` 携新token派给writer，最多一次。不先发无token补充再补账；`amend-receipt`仅用于维护登记已发生的异常，不能当日常派单入口。维护人工编辑另存`draft.reviewed.md`，标明`base_draft_sha256`与`author`，保留已锁定模型原稿。

`receipt`/`record` 会核对该阶段token的全部原生派单；除主回执及明确登记的补充外，任何额外派单均会阻止继续，即使额外派单已失败或取消，也需先核对，不能据此静默忽略重复执行。登记补充时也检查是否存在第三单，校验失败不修改账本；合法补充仍须与主单都完成后才能record成稿。

## 采集与图片能力

以下 Mac 试稿和生图证据来自此前 Gemini 通道实测；本次多模型接入没有重跑它们，也不据此证明新增模型组合可完成相同流程。

采集工具为 `scripts/xhs-collect.py`，先阅读其 `--help` 和集成说明，不能猜接口。未登录时如实记录缺口；任务允许站外来源时，可以用官方原始网页完成资料包，但不能把站外资料写成小红书采集成功。

官方采集直接 `python3 scripts/xhs-collect.py official --url 官方HTTPS链接 --keyword 主题 --output 项目绝对路径/sources.json`，保留`xhs-collection-v1`及`samples/source_url/body`，不把原文改成新schema，摘要另存MD。成稿正文提供官方来源链接；不虚构“很多人都以为/我看到大家”等见闻，不从coming soon推导全球未上线，开放范围未知不写“人人/全员”。

Gemini 推理模型、读图能力与专用生图模型分开。Mac 已通过 AGY 1.5.5 原生 print 和已有登录实际生成两张 896×1200 JPEG，并完成读图，独立图文版本含四张1080×1440 PNG。`scripts/xhs-image.py` 默认 print，不传 `--agent`，单次一张、无自动重试，每篇最多两次。输出目录保持独立；CLI 在项目外私有临时目录运行，避免加载编程项目规则。实际图片、回执与能力状态见[生图集成说明](../../xiaohongshu-images/README.md)和同目录 `capability.json`；旧 ACP 的 blocked 仅保留为 backends.acp 历史。

调用使用会话级 `useG1Credits:false` 禁止自动使用额外 Google AI credits，不改全局配置。精确扣额与图片后台型号未独立认证，不承诺免费，不依据模型自述认定 Imagen/Nano Banana。原写作 Bot 已实际执行第二张生图；用户只批准本次命令，长期权限保留。原生 SUCCESS 答复漏报图片路径，首次封装未取回，维护者从该精确会话找回图片；原 blocked 回执保留，修复另有 image-recovery.json。收图缺口已修复并通过52项针对性测试及真实旧产物复验，未多跑第三次生图；完整无人干预与实际节省额度尚未证明。官方参数见 [headless 文档](https://antigravity.google/docs/cli/headless/)和 [CLI credits 文档](https://antigravity.google/docs/cli/credits/)。

`scripts/render-xhs-cards.py --project ABS --input cards.json` 渲染实际 output PNG、preview.html 和 render-manifest；可用 `--output-dir image-versions/gemini-v1/output` 单独输出新版本，以 `card.layout: image-cover` 排版实际插图，保留旧产物。模板信息卡与 AI 插图分别记录，不能互相冒充；writing-report.images 列出最终图片。每次生成仍须按集成说明保存回执并实际读图，只有完整交付后才更新报告状态，不能由单张图成功推定整篇完成。

收尾时`image_generation.status=passed`或AI图`reused`需提供`evidence`/`source_evidence`：项目内image-evidence.json路径（字符串或数组）。工具验证原生SUCCESS、退出0、完成时间、实际原图及SHA256，并把回执/原图纳入不可变快照；失败不部分修改账本。非AI素材复用显式`ai_generated:false`，提供`reused_image_path`与`reused_image_sha256`，不附伪造生图回执。此检查不证明模型实际看图、不保证它会主动等待后台命令，也不替代用户验收；现有旧回执原样保留，不回填“成功”。

## Ubuntu 迁移边界

本套角色和内容项目没有写死 `/Users/a1`。setup 动态渲染目标路径；DSH 优先使用显式 `DSH_BIN`，其次保留 Mac 原入口，Mac 路径不存在时从 PATH 查找 dsh；AGY 继续支持 `AGY_BIN`。新机器仍需安装并登录 DSH/WorkBuddy、AGY 和采集依赖，建立自己的本地账号/模型目录。

现有 `omb-public.sh` 采用 macOS launchd。Ubuntu 后台托管需要另做 systemd 等适配；本轮 Mac 部署成功不能称为 Ubuntu 已验证。不复制 Mac 凭据或复用旧原生会话，Linux 生图/浏览器/登录均需独立核验。

2026-11-11后续按用户新授权做极简通道检查：GLM/MiMo/MiniMax各一条Low短请求，均返回OK；接口合计254 tokens，未走Agent长上下文、无工具/重试/新稿/生图。仅验证模型通道，未证明完整新分工效果，默认配置保持。详见[摘要](../../../docs/evidence/2026-11-11/xhs-model-tiny-smoke.json)。

## 2026-11-12：采集Bot补充X与YouTube

按用户授权，采集Bot新增按需技能 `xhs-social-sources`：twscrape负责X，yt-dlp负责YouTube，旧小红书MCP与Scrapling职责不变。来源分别写sources.*.json并由工具合并，保留事实原文、URL、时间和partial/blocked缺口。未增加Bot、修改默认模型或发布权限；安装/登录/使用见 [来源工具说明](../../xhs-sources/README.md)，Mac实际测试见 [证据](../../../docs/evidence/2026-11-12/xhs-social-sources-summary.json)。Ubuntu仍需独立验证。

## 2026-11-12：DeepSeek采集实测

用户明确选择DeepSeek V4.1 Flash Low，原生采集Bot已自行调用X/YouTube/Scrapling并合并3条来源。X搜索2条/精读1帖（回复0），YouTube搜索1条/158段英文字幕/2评论，网页4019字符。命令初始有4次执行/路径错误并自行修正；报告中未采集的X收藏数由维护者纠正。17测试及技能校验通过，详见[脱敏证据](../../../docs/evidence/2026-11-12/xhs-deepseek-collector-smoke.json)。技能增加用法提示后未另跑模型回合；这是Mac单项采集验证，未证明GLM对照优势、完整图文流程或Ubuntu通过。
