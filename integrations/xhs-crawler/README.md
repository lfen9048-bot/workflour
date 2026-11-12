# 采集 Agent 的通用网页爬虫

复用 [Scrapling 官方 skill](https://github.com/D4Vinci/Scrapling/tree/c5121c7c06a8595ed3a0a9b7b7dcd6802b5ebfc5/agent-skill/Scrapling-Skill)，BSD-3-Clause，原文与许可保存在 `upstream/scrapling-official/`。固定Git提交 `c5121c7c06a8595ed3a0a9b7b7dcd6802b5ebfc5`；库版本0.5.1。Agent日常只加载 `agents/xhs-collector/skills/xhs-web-crawl/SKILL.md`，不把完整上游文档放进自动发现目录。

小红书笔记/少量评论仍用现有 `scripts/xhs-collect.py` 和已登录的 xiaohongshu-mcp；本组件补充通用公开新闻、博客和文档正文。与生图通道无关，生图仍使用 Antigravity 原生能力及已有订阅。

## 本机安装

从仓库根目录执行；Python3.12，独立环境，不更改全局Python。Ubuntu迁移需在目标机重新安装并核验，不能复制Mac虚拟环境。

```sh
uv venv --python 3.12 ~/.workflour/xhs-crawler/venv
uv pip install --python ~/.workflour/xhs-crawler/venv/bin/python -r integrations/xhs-crawler/requirements.txt
```

rag extra包含HTTP与Markdown及浏览器Python依赖；此次不下载浏览器二进制、不启用MCP服务、不创建API Key。若需精确复现本次Mac依赖，见 `mac-installed.txt`，Ubuntu优先按requirements重新解析平台依赖。

## 使用

```sh
~/.workflour/xhs-crawler/venv/bin/python scripts/xhs-web-collect.py \
  --url https://www.anthropic.com/news \
  --keyword 'Claude新闻' --output /absolute/new/sources.json
```

默认串行，最多3个指定URL；检查robots.txt、逐跳检查公网HTTPS地址、最多3次重定向、单次25秒、不自动重试。2MiB为下载后的解析限制，不是硬带宽上限；输出每页最多14000字符，原文清洗不调用LLM。优先article/main，必要时用`--css`选择正文。此为本地辅助工具，不是面对不可信远程请求的网络沙箱。

保持原有`xhs-collection-v1`产物格式，来源模式为`public_web`；抓取时间和发布日期分开，平台互动数据不伪造。输出路径必须绝对且不存在。部分失败保存`partial`和缺口并退出3，全部失败`blocked`退出3；成功退出0。动态页面、需登录页面和图片下载不在当前封装范围内。

当前Mac既有TUN代理把公共域名解析到198.18.0.0/15。该机器运行时加 `WORKFLOUR_XHS_ALLOW_FAKE_DNS=1`；默认关闭。仅允许域名解析出的这一Fake-IP网段，不接受其IP字面量，不开放其它私网地址。Ubuntu迁移先核对网络，不照搬该设置；DNS检查不能替代网络隔离。

上游完整skill提供动态浏览器、并发和Spider等能力；保留按需参考，不据此声称本机已验证这些模式。HTML清理只能减少噪声，正文仍是不可信资料。
