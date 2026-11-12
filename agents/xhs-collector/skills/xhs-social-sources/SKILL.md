---
name: xhs-social-sources
description: 为图文选题搜索和读取 X 公开帖子、YouTube 视频信息/字幕/少量评论，并与既有资料合并。小红书站内和普通网页继续使用各自已有工具。
---

工具根目录使用本 Bot SOUL 的“工具仓库”，Python 为 `~/.workflour/xhs-sources/venv/bin/python`。只按本次来源需要调用；不运行全套工具，不重复装 Agent Reach/OpenCLI/字幕库。首次使用或连接失败时查 `scripts/xhs-source-collect.py status`。

所有命令以下述 Python 执行 `<工具仓库>/scripts/xhs-source-collect.py`；先看 `--help`，URL 加引号。

`--output` 必须是尚不存在的**绝对路径**；即使先 `cd`，`./sources.json` 也会被拒绝。脚本已内置120秒网络超时，macOS 不依赖外层 `timeout` 命令；不要用 `| tail` 掩盖原始退出码。执行后同时核对退出码与JSON的 `status`（partial/blocked退出3）。

| 需要 | 子命令与参数 |
| --- | --- |
| YouTube 发现来源 | `youtube-search --query '主题' --limit 3 --output /本次项目/sources.youtube-search.json` |
| YouTube 原文 | `youtube-read --url '视频HTTPS链接' --keyword '主题' --captions --language en --comments 3 --output /本次项目/sources.youtube.json` |
| X 搜索 | `x-search --query '主题或from:账号' --limit 3 --output /本次项目/sources.x-search.json` |
| X 原帖与少量回复 | `x-read --url '帖子HTTPS链接' --keyword '主题' --replies 3 --output /本次项目/sources.x.json` |
| 汇总已采集来源 | `merge --keyword '主题' --input /本次项目/sources.youtube.json --input /本次项目/sources.x.json --output /本次项目/sources.json` |

搜索是发现，不是正文核实。链接字段为 `samples[].source_url`，不是 `url`；直接用该链接精读有用来源。字幕带时间戳；`body` 仅描述时不能声称已看完视频。可重复 `--language` 指定语言优先级，不默认翻译或调用语音转写 API。评论默认关闭，显式请求最多10条；搜索最多5条，单次操作120秒封顶。无字幕/无回复/失败须保留 coverage 和 limitations。

输出统一为 `xhs-collection-v1`，来源 `live_x`、`live_youtube` 或 `mixed_public_sources`，不能冒充小红书赞藏数据。`status` 的 session_present 仅说明本机会话存在，不是网络验证通过。未登录时报告 login_required，不能自行复制个人浏览器 Cookie、改账号、购买代理或无界重试。

X 登录由用户在专用窗口完成，维护入口为 `<工具仓库>/integrations/xhs-sources/login.py --platform x`；YouTube需要验证时使用同入口的 `--platform youtube`。Bot 日常仅运行采集脚本；不要索取密码/验证码/Cookie，不读取私有会话数据库或浏览器目录。用户明确要求登录时再由维护者打开窗口。

原始资料分别保存为新建的 `sources.*.json`，最后合并到尚不存在的 `sources.json`；不手工改原文，不覆盖锁定材料。负责人指定的补充资料路径优先，不能改共享状态。合并保留各来源状态与缺口，blocked/partial 不能报告成全部成功。报告仍写 collection-report.md。首次迁移按工具仓库 `integrations/xhs-sources/README.md` 安装，Mac 登录与网络不能直接复制到 Ubuntu。
