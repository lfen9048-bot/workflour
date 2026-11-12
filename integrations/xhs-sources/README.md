# X 与 YouTube 资料采集

这是小红书三角色中“采集”Bot 的两个互补工具：

| 来源 | 工具 | 分工 |
| --- | --- | --- |
| X | [twscrape](https://github.com/vladkens/twscrape) 0.21.0 / MIT | 关键词、作者公开帖子、单帖、少量回复 |
| YouTube | [yt-dlp](https://github.com/yt-dlp/yt-dlp) 2026.10.26 / 源码Unlicense | 搜索、视频描述、原语言字幕、少量顶层评论 |
| 普通网页 | 既有 Scrapling | 继续使用 xhs-web-collect.py |
| 小红书 | 既有 xiaohongshu-mcp | 继续使用 xhs-collect.py |

不再安装功能重叠的 Agent Reach/OpenCLI/Twikit/youtube-transcript-api。工具调用不发模型请求，正文分析沿用工作流现有模型；没有新增付费 API、语音转写或下载视频的默认步骤。

## 独立安装

从仓库根目录：

```sh
uv venv --python 3.12 ~/.workflour/xhs-sources/venv
uv pip install --python ~/.workflour/xhs-sources/venv/bin/python -r integrations/xhs-sources/requirements.txt
~/.workflour/xhs-sources/venv/bin/python scripts/xhs-source-collect.py status
```

YouTube 使用已有 Node（上游要求支持的 JS 运行时）和 yt-dlp-ejs，文本采集无需 FFmpeg。requirements 固定主包版本；本次 Mac 完整包清单保存在 mac-installed.txt。Playwright 仅用于用户在独立 Chrome 登录后把该平台会话保存给对应采集器；不下载浏览器二进制，不使用个人 Chrome 目录。

## 平台登录

```sh
~/.workflour/xhs-sources/venv/bin/python integrations/xhs-sources/login.py --platform x
```

启动已安装的普通 Chrome 独立 profile，用户自己完成 X 登录；辅助程序只获取该专用 profile 的 X auth_token/ct0，写入本机私有 `~/.workflour/xhs-sources/x-accounts.db`。不会读取个人浏览器 Cookie、打印凭据或写进项目。用户名槽位固定为 xhs-research；状态检查只返回数量，存在会话不代表实采成功。匿名聚合遥测关闭。登录窗口只为本次授权任务使用，默认等待15分钟后结束。

Chrome 若拒绝登录，不关闭安全设置、不自动处理验证码或反复尝试；记录阻碍。初次 Playwright 启动曾被用户报告“不安全”，因此改为普通 Chrome 进程启动，使用仅本机开放的调试连接。登录结果以本次测试证据为准，不以窗口打开当作成功。

YouTube 公开搜索无需登录；详情若提示验证，再执行同一命令加 `--platform youtube`，由用户在独立窗口登录。仅导出该专用窗口的 youtube.com 会话到本机 `youtube-cookies.txt`，不读取个人浏览器或导出其他站点登录。该文件权限600，采集器自动复用；仍受平台限制时返回 partial，不以 Cookie 存在推断验证通过。

## 使用和输出

```sh
~/.workflour/xhs-sources/venv/bin/python scripts/xhs-source-collect.py youtube-search \
  --query 'Anthropic Claude official' --limit 3 --output /absolute/project/sources.youtube-search.json
~/.workflour/xhs-sources/venv/bin/python scripts/xhs-source-collect.py youtube-read \
  --url 'https://www.youtube.com/watch?v=VIDEO_ID' --keyword Claude --captions --language en \
  --comments 3 --output /absolute/project/sources.youtube.json
~/.workflour/xhs-sources/venv/bin/python scripts/xhs-source-collect.py x-search \
  --query 'from:AnthropicAI Claude' --limit 3 --output /absolute/project/sources.x.json
~/.workflour/xhs-sources/venv/bin/python scripts/xhs-source-collect.py merge \
  --keyword Claude --input /absolute/project/sources.youtube.json --input /absolute/project/sources.x.json \
  --output /absolute/project/sources.json
```

单来源保留 `xhs-collection-v1`，source_mode 区分 live_x/live_youtube；合并时保留样本来源、失败状态和限制，按来源URL去重。仅写新绝对路径，不覆盖历史资料。采集最多5个搜索结果、每篇最多10评论/回复、正文或字幕最多14000文字字符/500时间片，120秒总超时。字幕仅选来源语言，不自动下载翻译字幕或调用识别API；截断和缺失会显式记录。正常 collected 退出0，partial/blocked退出3。

合并包顶层 `collected_at` 是本次合并时间；`inputs[].collected_at` 保留各输入包自己的时间（输入也是合并包时，该值仍是其合并时间）。样本原始采集时间关联在 `source_collected_at`，已有的 `fetched_at` 保持原样。URL去重及再次合并时，旧观测与各自时间继续保留；旧合并包缺少样本原始时间时记录为null，不能用合并时间补写或推断指标新鲜度。旧资料包不自动改写，若此前已丢失采集时间，需要从原始输入重建到新文件。

现有工作流接受这种 sources.json；Bot 只补原始材料和 collection-report.md，不写共享状态。其他Bot默认模型、权限、历史项目保持不变。

## 迁移与限制

Ubuntu 重新建 venv、安装 Node 与 Chrome/Chromium，需要登录时有可见桌面。重新建立自己的会话，不复制Mac凭据或虚拟环境。YouTube 对出口IP/访问频率的限制、X非公开接口变化可能影响采集；不承诺全量评论、完整历史、所有字幕或无人值守可靠性。当前验证范围见本日证据，不等同 Ubuntu 已实测。

2026-11-12 Mac直接实采：X搜索2条、单帖3回复；YouTube搜索2条、用户登录后158段英文字幕/5470字符/3评论；合并成功，37项单元/回归检查通过。原生采集Bot指令读回通过。Gemini隔离调用两次均无业务产物：首次读取目录被拒，用户授权加入工作区后仍被Antigravity拒绝无沙箱执行status命令。模型回执合计55155 tokens，未继续绕过拒绝或重试；不能称为Gemini自主调用或完整三Bot流程通过。详见 [精简证据](../../docs/evidence/2026-11-12/xhs-social-sources-summary.json)。
