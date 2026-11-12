# Ubuntu 虚拟机快速接入小红书工作流

目标：Windows 上带桌面的 **Ubuntu 24.04 x86_64/amd64** 虚拟机。所有命令在 Ubuntu 终端执行，浏览器也在 Ubuntu 内打开。三个 Bot 为 DeepSeek Low 采集、MiMo Pro High 思考、Antigravity/Gemini Low 写作；只生成草稿，最终由用户确认。

## 1. 克隆并安装

```bash
sudo apt-get update
sudo apt-get install -y git python3
git clone https://github.com/lfen9048-bot/workflour.git
cd workflour
./scripts/xhs-ubuntu.sh install --system-deps
```

安装器准备中文字体、密钥环依赖、Node 24+、固定版 DSH/OpenMausBot/WorkBuddy 插件、独立 Python 环境、Chromium、登录浏览器及固定版小红书采集服务。首次下载需要一些时间。Node 不够新时在用户目录安装校验过 SHA256 的固定版本，不替换系统 Node。版本见 [versions.json](../integrations/ubuntu/versions.json)。

以桌面普通用户执行，不给整条命令加 sudo；仅系统依赖步骤调用 sudo。虚拟机需要能访问 GitHub、npm、PyPI、浏览器下载站及模型服务。固定采集版本暂只支持 Linux amd64；ARM 目标会拒绝安装。

## 2. 登录模型通道

先启动 DSH Web：

```bash
./scripts/xhs-ubuntu.sh auth-workbuddy
```

在 Ubuntu 浏览器打开 `http://127.0.0.1:3080`，进入 WorkBuddy 设置，登录自己的账号，保存国内/国际账号池选择和模型配置。确认能看到 DeepSeek V4.1 Flash 与 MiMo-V2.6-Pro。完成后在终端按 Ctrl-C 关闭这个设置窗口对应的服务。

安装官方 Antigravity CLI，并登录现有订阅：

```bash
curl -fsSL https://antigravity.google/cli/install.sh -o /tmp/workflour-agy-install.sh
bash /tmp/workflour-agy-install.sh
./scripts/xhs-ubuntu.sh auth-gemini
```

按 CLI 提示完成登录；看到登录完成后退出交互界面。AGY 的账号授权依赖 Linux 用户密钥环，建议保持当前桌面用户登录。若有密钥环提示，在 Ubuntu 桌面自行解锁。Gemini 订阅、生图可用性和精确扣额需要目标机实测；安装完成不代表账号已通过验证。

## 3. 配置并启动三个 Bot

```bash
./scripts/xhs-ubuntu.sh configure
./scripts/xhs-ubuntu.sh up
./scripts/xhs-ubuntu.sh connect
```

`configure` 生成本机角色配置和新的 Bot ID 清单；`up` 创建并启动两个用户级 systemd 服务；`connect` 从当前实际模型目录核对并创建三个 Bot，不发送试稿请求。采集服务首次启动还会下载并解压自己的内置浏览器，可能需要几分钟；用 `doctor` 确认采集服务就绪后再派稿。若工作台尚未启动完成，稍等后重跑 `connect`，不会重复创建已存在的 Bot。已有模型的手动选择保留。

在 Ubuntu 浏览器打开 **http://127.0.0.1:8799**。这里的 127.0.0.1 是虚拟机自身，不是 Windows 主机。若已有工作台在运行，`configure` 会先要求空闲停机，不会强行重启。

## 4. 登录需要的采集平台

按需执行，每次在打开的独立浏览器窗口自行登录：

```bash
./scripts/xhs-ubuntu.sh login-xhs
./scripts/xhs-ubuntu.sh login-x
./scripts/xhs-ubuntu.sh login-youtube
```

小红书、X、YouTube 登录状态只保存在当前 Ubuntu 用户目录。可以先只采公开网页；没有登录的平台如实保留缺口。X/YouTube 的浏览器登录可能受平台验证限制，不能把保存 Cookie 等同于网络验证成功。自装浏览器可用 `XHS_CHROME_BIN` 指定可执行文件。

## 5. 自检与第一篇草稿

```bash
./scripts/xhs-ubuntu.sh doctor
./scripts/xhs-ubuntu.sh start \
  --topic 'Claude 最近一条官方公告，有什么值得普通用户了解的变化' \
  --project "$HOME/xhs-drafts/claude-first"
```

项目目录必须是全新绝对路径。这个入口先创建原生工作台任务，取得真实 threadId 并绑定账本，再发送主题；思考 Bot 不必猜内部会话 ID。默认只做两张模板卡片。若要授权最多一次 Gemini 原生配图，在 `start` 后加 `--image`。

后续到工作台对应任务看进度和 `output/preview.html`。确认正文、原始链接、日期、实际图片和报告后再决定修改或发布。本工作流不自动发布、点赞、评论、关注或私信。

`doctor` 只检查依赖、保存的配置及本地服务，不调用模型；返回 3 表示尚有缺项。报告明确区分配置就绪与账号认证，不能把它当成全流程验收。`doctor --offline` 不探测工作台；仍检查本机文件和程序。

## 日常维护

```bash
./scripts/xhs-ubuntu.sh status
./scripts/xhs-ubuntu.sh down
journalctl --user -u workflour-xhs-workbench.service -n 80 --no-pager
journalctl --user -u workflour-xhs-collector.service -n 80 --no-pager
```

`down` 在 Bot 运行中会拒绝停止。这里的 systemd 服务随桌面用户登录启动；退出登录、暂停虚拟机或 Windows 休眠会影响任务。没有自动开启系统级常驻或修改 Windows 电源设置。

更新仓库后，等 Bot 空闲，执行 `down` → `configure` → `up` → `connect`。若角色指令更新，再运行：

```bash
python3 scripts/provision-xhs-team.py instructions
```

不要为同一篇重复执行 `start`。发送响应丢失时，`.xhs/launch.json` 会记为 `delivery_unknown`；先在对应工作台任务核对，不自动新建或重派。需要新模型时在工作台手动选择；真实可用目录和档位以目标机为准。

## 目录和兼容边界

| 内容 | 目标机位置 |
| --- | --- |
| 本套运行时、非秘密安装设置 | `~/.workflour/xhs-ubuntu/` |
| 目标机 Bot ID 清单 | `~/.workflour/xhs/deployment.json` |
| DSH Web 账号设置与私有凭据 | `~/.dsh/` |
| 小红书采集登录与服务 | `~/.workflour/xiaohongshu/` |
| X/YouTube 工具与登录 | `~/.workflour/xhs-sources/` |
| 通用网页采集环境 | `~/.workflour/xhs-crawler/` |
| 图文项目 | 用户在 `--project` 指定的位置 |

不要从 Mac 复制虚拟环境、账号文件、Cookie、Bot ID 或原生聊天记录。默认从 Linux 的 `web` profile 读取账号池与插件依赖；已有目标机可在安装前指定 `WORKFLOUR_DSH_SOURCE_PROFILE` 和 `DSH_HOME`。Mac 原入口继续默认使用 desktop。

`--tools-only` 和 `--skip-xhs` 是隔离测试/工具安装选项；跳过运行时或采集二进制后，不应直接使用完整后台启动流程。普通部署使用上面的默认安装命令。

## 验证范围与已知问题

本机 Mac 已跑过完整三角色图文、真实 Gemini 插图及一次局部返工；过程发生过写作提前返回、采集上限不遵守及日期表述错误，需要维护补交或人工核对。已补提示约束，但不能承诺模型永远遵守。

仓库包含 [Ubuntu 自动检查](../.github/workflows/xhs-ubuntu.yml)：在全新 Ubuntu runner 安装工具，跑隔离测试，真实启动工作台/采集服务并渲染中文卡片。它不带账号，不调用模型；CI 通过也不能替代这台 Windows 虚拟机上的登录、订阅、生图和业务验收。实际运行状态见 GitHub Actions，未运行的项目不能写成通过。

## 方案来源

本入口在已有项目脚本上加薄封装：复用 [DSH 的 Web profile](https://github.com/deepseek-ai/deepseek-harness)（MIT）、[dsh-connect-workbuddy](https://github.com/dingminhua/dsh-connect-workbuddy)（MIT）、[OpenMausBot](https://github.com/milind-soni/OpenMausBot)（Apache-2.0）、[Antigravity Linux CLI](https://antigravity.google/docs/cli/install/)、[Playwright 的 Linux 浏览器安装](https://playwright.dev/python/docs/browsers)。固定版依赖不随安装自动升级；账号与实际模型目录必须在目标机确认。
