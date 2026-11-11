---
type: implementation-plan
status: ready-for-gemini-not-executed
created: 2026-11-06
updated: 2026-11-06
---
# OpenMausBot 双 Agent 与手机接入实施计划

## 0. 给 Gemini 的接手指令

你负责按本文实施第一版最小系统。先读项目 AGENTS.md 和本库首页，再按本文逐阶段搭建。当前授权范围是本计划中的配置、脚本、测试项目和验证；不要把列出的未验证能力当成已经可用。本计划的作者只做了只读核对与文档交接，没有安装、启动服务、配对手机或调用模型。

复用已完成的 search-first 调研和本文固定版本依据，遇到实际版本或接口差异时再查官方资料。无需重新做大范围候选选型。先完成单 Coder，再接 Doc，最后接手机。每阶段交付可核对的结果，再进入下一阶段。

## 1. 已确认目标与本轮边界

用户在本次规划中明确选择：

| 项目 | 本轮选择 |
| --- | --- |
| 第一轮目标 | 双 Agent＋手机 |
| 新工作主要查看入口 | OpenMausBot；原 Harness 历史保留 |
| 手机入口 | 手机网页，可添加到主屏幕 |
| 远程连接 | OpenMausBot 内置托管 HTTPS |
| 代码和文档接力 | 手动接力 |
| 实施者 | Gemini；本助手提供计划与后续复核 |

电脑端第一版也使用 OpenMausBot 网页。电脑与手机连接同一台 Mac 上的同一服务、同一数据目录，避免启动两套互不相干的工作区。各 Agent 使用独立 profile、模型和自动 skills 清单，共享测试项目。这不是文件权限沙箱或完全独立安装。

本轮不接入 Antigravity、DSHL、MoA+、原生手机 App、云电脑/Local VM、宿主电脑远控、自动任务调度或旧历史迁移。不要求新会话同时显示在原 Harness 桌面。

## 2. 已知本机基线

- 项目：`<WORKFLOUR_ROOT>`。
- Obsidian：`<OBSIDIAN_VAULT>`。
- Mac：Apple Silicon arm64；本次核对 macOS 26.6.2、Node v26.10.0，符合服务 Node 24+ 要求。
- DeepSeek Harness 桌面：0.2.1-rc.2。
- 复用的 CLI：`/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh`，不依赖 PATH 中存在 dsh。
- DSH_HOME：`<HOME>/.dsh`。维持此根目录以复用 WorkBuddy 凭据库和登录；不要换成新的空 home。
- WorkBuddy：`dsh-connect-workbuddy@5.13.1`，provider ID 为 `workbuddy`。
- 现有 `agent-coder`：`glm-5.3-flash`，自定义 skill 为 `code-assistant`。
- 现有 `agent-doc`：`deepseek-v4.1-flash`，自定义 skill 为 `doc-writer`。
- 两套现有 skills 目录分别在项目 `agents/agent-coder/skills`、`agents/agent-doc/skills`。
- 现有 run-agent.sh 是一次性 headless 入口，不是 ACP 服务。
- 本次核对 OpenMausBot 尚未安装，`~/.openmausbot` 尚不存在，8799 未发现监听。实施时重新检查，不能据此覆盖后来出现的文件或终止未知进程。

保留现有 run-agent.sh、setup-agents.sh、agent-coder/doc profiles、desktop profile 与旧会话。仅在依赖或认证确实受影响时补做旧入口的真实调用，平时以文件差异和既有证据复核，避免重复消耗模型额度。

## 3. 第一版组成与产物

固定 OpenMausBot CLI 为 `0.1.143`，用 npm 发布包运行，无需首轮安装 Electron 桌面 App。OpenMausBot 负责网页、聊天记录和客户端配对；两个 customAcp 实例分别启动 Harness ACP profile，Harness 通过 WorkBuddy 调用模型。

项目中新增以下产物：

```text
workflour/
├── run-acp-agent.sh                  # coder|doc；协议启动入口
├── run-omb.sh                        # local|remote|pair <HTTPS origin>
├── integrations/openmausbot/
│   ├── setup.sh                      # 幂等生成新增配置，不启动模型任务
│   ├── profiles/coder.patch.yml       # 不含账号/凭据的模板
│   └── profiles/doc.patch.yml
├── tests/acp-smoke.py                 # 不发 session/prompt 的握手验证
└── examples/omb-smoke/                # 两个 Bot 共享的验证项目
```

新增本机运行配置：

- `~/.dsh/profiles/omb-coder`、`~/.dsh/profiles/omb-doc`。
- `~/.openmausbot/config.json`：合并新增 instances，保留其它键。
- 服务自己的聊天、数据库、登录和配对数据继续放 `~/.openmausbot`，不写入项目或 Obsidian。

生成配置前对将修改的既有配置做私有备份。已有新增 profile 或 instance 名称时先检查归属：可复用本方案匹配项；遇到无关项不直接覆盖。重复执行 setup 不产生重复 Bot，不清空已有会话或 WorkBuddy 运行状态。

## 4. Harness ACP profiles 的准确配置

两个新 profile 的 package.json 使用下列 composition；不要复制 desktop 全部组件，也不要沿用 dsh-headless bundle：

```json
{
  "private": true,
  "dependencies": {
    "dsh-connect-workbuddy": "5.13.1"
  },
  "dsh": {
    "profile": {
      "bundles": [
        "@deepseek-ai/dsh-base",
        "@deepseek-ai/dsh-acp-app",
        "dsh-connect-workbuddy"
      ]
    }
  }
}
```

按当前 profile 机制准备 `cordis.yml` 为 `[]`、`pnpm-workspace.yaml` 为 `packages: []`；复用 `~/.dsh/profiles/desktop/node_modules`。先确认目标真实存在且能解析 WorkBuddy，不升级或修改共享依赖。此方式只分离配置和角色，不宣称依赖完全隔离。

Coder patch 模板核心如下：

```yaml
- id: acp
  config:
    provider: workbuddy
    model: glm-5.3-flash

- id: skill-filesystem
  config:
    includeDefaultRoots: false
    customSkillDirs:
      - <WORKFLOUR_ROOT>/agents/agent-coder/skills

- id: system-prompt
  config:
    personaPrefix: "You are Agent Coder, an automated coding specialist."
```

Doc 使用相同结构，分别替换为 `deepseek-v4.1-flash`、agent-doc 的 skills 目录与文档助手 persona。

关键事实：ACP bundle 名为 `@deepseek-ai/dsh-acp-app`，其注入的插件条目却是 `id: acp`、`name: @deepseek-ai/dsh-acp`。对现有条目按 id 覆盖配置即可；只配置 `agent-default-model` 不足以固定 ACP 模型。

账号配置只在新 profile 的本机私有 patch 中合并：从相应旧 profile 读取 WorkBuddy 的账号引用和启用区域等必要配置。凭据正文仍留在现有 DSH_HOME。项目模板不要写入账号 ID、token、完整凭据库或账号导出文件。新运行 patch 不要软链接到项目模板，以免插件后续持久化账号配置时写回项目；setup 应按配置条目合并，并保留插件已经写入的新状态。

`run-acp-agent.sh coder|doc` 的约束：

1. 仅接受两个已知角色，映射到 omb-coder / omb-doc；未知角色以非零退出。
2. 指定当前 DSH_HOME，最终使用 exec 启动内置 dsh 和对应 --profile。
3. 不带任务文本、不添加 headless 参数、不启动 Electron 独占的 desktop profile。
4. 不向 stdout 打印 echo、横幅、调试文字；stdout 留给 ACP JSONL。必要诊断写 stderr。
5. 不重定向丢弃 stdin；输入结束或进程被停止后应正确退出。

## 5. 先验证协议，再接 OpenMausBot

先创建空测试目录。tests/acp-smoke.py 分别启动两个角色，按响应顺序发送以下 JSON-RPC，逐行读 stdout，stderr 单独收集；不得调用 session/prompt：

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{},"clientInfo":{"name":"workflour-acp-smoke","version":"0.1.0"}}}
```

收到 id=1 的成功响应后发送：

```json
{"jsonrpc":"2.0","id":2,"method":"session/new","params":{"cwd":"<WORKFLOUR_ROOT>/examples/omb-smoke","mcpServers":[]}}
```

读取返回的 sessionId，发送 session/close，再关闭 stdin、等待退出。首轮冷启动允许最多 180 秒，已启动后每项协议响应最多 30 秒；失败时终止本次子进程并保留脱敏错误，不无限重试。

通过条件：initialize 和 session/new 成功，获得 sessionId；stdout 非空行均为有效 JSON-RPC；会话关闭与进程退出可控。模型配置以 session 返回的当前配置和实际调用证据继续核对。

这里的“无模型推理验证”仅指不发 prompt。插件仍可能联网刷新目录或认证，session/new 也可能落盘，不能写成离线或零副作用检查。

## 6. 配置 OpenMausBot 和两个 Bot

停止服务后，向 `~/.openmausbot/config.json` 合并下列 instances；不要整体替换已有配置：

```json
{
  "instances": {
    "omb-coder": {
      "driver": "customAcp",
      "displayName": "Harness Coder",
      "config": {
        "cli": "<WORKFLOUR_ROOT>/run-acp-agent.sh coder"
      }
    },
    "omb-doc": {
      "driver": "customAcp",
      "displayName": "Harness Doc",
      "config": {
        "cli": "<WORKFLOUR_ROOT>/run-acp-agent.sh doc"
      }
    }
  }
}
```

本地启动命令：

```sh
npx --yes openmausbot@0.1.143 serve
```

serve 可直接加载配置，不需要为了走 setup 向导另开 AI 供应商账号。电脑本地首次使用实际输出的 owner 登录/配对入口。只运行一份该工作区的服务；8799 如被占用先辨明是否本服务，不随意杀进程。

优先通过本地 owner 接口 `POST /api/bots` 创建 Bot；若该版本实际界面更方便，也可在 UI 按同样字段设置。Coder 请求体：

```json
{
  "name": "Coder",
  "modelSelection": {
    "instanceId": "omb-coder",
    "model": "agent-default"
  },
  "cwd": "<WORKFLOUR_ROOT>/examples/omb-smoke",
  "approvalMode": "ask",
  "computer": "off"
}
```

Doc 替换 name 和 instanceId，其它设置相同。创建前查询已有 Bot；创建后读取实际 Bot ID，记录供后续使用，不编造 ID、不重复创建。界面中的模型应显示 Agent default。使用该版本真实的本地授权机制，不关闭认证来方便自动化。

不要误选内置 deepseekAgent：该版本的专用驱动带 DeepSeek 官方 key 检查且固定 profile acp，不等同于本方案的 WorkBuddy 自定义 profiles。也不要开启外部 Bot API/webhook 来代替普通聊天；它是另一条受限调用路径。

## 7. 分阶段验证任务

### A. 单 Coder

先只向 Coder 发一条最短消息，要求回复就绪并列出已提供的自定义 skill 名称，不遍历磁盘寻找其它 skills。预期 code-assistant。

从配置、ACP 会话信息和实际请求/运行日志核对 provider=workbuddy、model=glm-5.3-flash。模型自报名称不能作为唯一证据。skills 以实际加载清单为主，自述辅助；无法取得清单时明确证据局限，不把文件读取权限误写为隔离成功。

### B. 两个 Agent 手动接力

Coder 的任务限定在 examples/omb-smoke，生成：

- textstats.py：读取 UTF-8 文本文件，向 stdout 输出含 lines、characters 的 JSON；lines 按 splitlines() 计数，characters 按完整解码文本长度计数，包含换行字符。
- test_textstats.py：使用 Python unittest 覆盖空文本、英文多行、中文、文件不存在等行为；读取失败返回非零并输出清晰错误。
- sample.txt：用于文档中可复现的示例。
- HANDOFF.md：列出改动、实际执行的测试命令/结果、输入输出约定和待写文档事项。

Coder 实际运行测试并报告结果。Gemini 核对文件存在和测试输出，不能自己预先把演示代码写好再宣称由 Coder 完成。

之后把 HANDOFF.md 的位置和文档任务手动交给 Doc。Doc 阅读实际代码和交接，生成 README.md，包含用途、运行要求、命令、准确输出、错误情况及测试方法。Doc 主要修改文档；发现代码错误时返回明确问题交给 Coder，不悄悄改写分工。

核对 Doc 实际走 workbuddy / deepseek-v4.1-flash，自动提供的自定义 skill 为 doc-writer。执行 README 示例并对照真实输出。这一轮也验证两个 Bot 能在同一目录接力，而不是要求两边聊天自动同步。

### C. 重启续聊

在一个现有聊天中给出一个不写进项目文件的短标记，停止服务后重启，确认旧聊天仍可见，再在同一聊天询问该标记及当前任务状态。验证应用保存记录并恢复上下文。

已知兼容点：DSH rc.2 使用 session/resume，通用 customAcp 默认尝试 session/load；失败后 OpenMausBot 可建立新会话并通过 recoveryText 恢复上下文。本轮接受这种恢复方式，不要求底层 DSH session ID 固定，但必须实际验证，不能把读过源码当成通过。

## 8. 手机网页与内置 HTTPS

本地阶段通过后，由用户完成 OpenMausBot 账号邮箱码登录。这是隧道账号，不是模型提供方登录。使用固定版本：

```sh
npx --yes openmausbot@0.1.143 login
```

停止本地服务，再以前台远程模式启动同一工作区：

```sh
caffeinate -i npx --yes openmausbot@0.1.143 serve --tunnel --no-pair
```

run-omb.sh 的 local/remote 分别封装这两种启动方式；pair 子命令接收本次实际 HTTPS origin，执行下面的 client 配对命令。运行时不把 Mac 永久设为不休眠；停止远程服务后 caffeinate 应退出。

在第二个终端生成手机普通客户端邀请：

```sh
npx --yes openmausbot@0.1.143 pair --client --label Phone --public-url '<本次实际 HTTPS origin>'
```

不要把示例占位符直接运行。不要把电脑首次 owner/admin 邀请发给手机。托管连接可能安装官方固定版本 cloudflared，使用官方流程；不自行开放原始服务端口或另搭公网代理。

由用户在手机完成以下操作，Gemini 提供实际地址或二维码：

1. iPhone 用 Safari、Android 用 Chrome 打开 HTTPS 网页。Android 的默认二维码可能是 App 链接，网页方案使用打印的 web 地址和配对码。
2. 点击连接并完成 client 配对；不能仅因二维码显示或被扫描就判定成功。
3. 确认能看到刚才两个 Bot 和已有聊天。
4. 关闭 Wi-Fi、改用蜂窝网络，发送一条短任务，看到结果返回，电脑端出现同一记录。
5. 测试一次刷新/短暂断网重连，然后按需要添加到主屏幕；若主屏幕窗口隔离存储，重新配对该窗口。

手机权限应为 client：可以聊天、处理支持的审批，不管理全局设置或配对他人。只有 DSH 实际发出 session/request_permission 时才能验证审批卡；设置 Ask 本身不能证明所有底层工具都经过审批。若没有触发请求，记录为“本轮未触发/未验证”，不把它伪装为通过，也不扩大首轮为权限系统改造。

主机必须在线、服务运行且保持唤醒。手机 PWA 本身不提供离线聊天或推送。看不到手机实际结果时，Gemini 应写明“等待用户手机确认”，而不是自行声称外网验证通过。

## 9. 验收证据、故障处理与恢复

| 检查项 | 必须保留的证据 |
| --- | --- |
| 两个协议入口 | 各自 initialize/session/new 成功、stdout 协议检查、退出结果 |
| 模型路由 | profile 配置及真实会话/请求证据；不能只引用模型自述 |
| skills 分开 | 实际自动提供的自定义 skills 清单；不是 filesystem 权限沙箱 |
| 工具工作 | Coder 实际生成的文件、实际测试命令和输出 |
| 文档接力 | Doc 的实际改动、README 示例与程序输出一致 |
| 持久化 | 重启前后同一应用聊天可见、续聊标记恢复结果 |
| 手机 | client 配对、蜂窝网络任务与两端同记录；标明亲自观察或用户确认 |
| 原基线 | 原脚本/旧 profiles 无意外改动，旧历史保留 |

故障优先在当前阶段解决：

- stdout 出现启动提示或普通日志：修复包装/日志输出，不能通过丢弃协议行掩盖。
- 默认走 DeepSeek 官方或缺 key：检查 id:acp 的 provider/model，以及是否误选专用 deepseekAgent。
- WorkBuddy 未登录：核对 DSH_HOME、账号引用和插件版本；不另换模型接入掩盖问题。
- 重启后没有上下文：检查 customAcp 恢复路径，保留失败证据，不宣称原生恢复。
- 隧道/账号/手机配对失败：保留已通过的电脑阶段；停止远程实例后可用 local 模式继续工作。

本轮不为通过验收而升级 Harness、改造上游协议、关闭认证、切换付费 API 或引入额外编排平台。若固定组合存在实质兼容阻断，交付已完成阶段、具体错误、最小复现和建议下一步，不写“全流程通过”。

停止与恢复：前台 Ctrl-C 停服务，确认本次服务及其 ACP 子进程退出；手机不用时撤销对应配对，保留数据库和旧聊天。需要撤销本轮配置时，仅移除本方案新增的 instances/profiles/脚本，恢复本次备份中的受改项，不删除整个 ~/.dsh 或 ~/.openmausbot，不覆盖用户新增数据。

## 10. 记录与最终交付

每阶段有实质进展后更新 Obsidian 搭建日志、验证笔记和首页。区分“已生成”“已运行”“已通过”“等待用户确认”“未验证”。日志和截图不包含 token、验证码、活跃配对链接、完整账号导出或私有配置。

最终向用户给出：实际安装版本、两个实例/Bot 的对应关系、电脑本地入口、手机使用方法、启动停止命令、验收表、已知限制和下一步。不要自动开始 Antigravity 或自动编排阶段。

本次交接及配套 5 份笔记写入回读一致，本库 121 处双向链接目标均存在；所有系统接入验收仍为待实施。

## 11. 固定版本依据与关联

以下资料已只读核对，查阅日期 2026-11-06：

- [OpenMausBot v0.1.143](https://github.com/milind-soni/OpenMausBot/releases/tag/v0.1.143)
- [自定义引擎](https://github.com/milind-soni/OpenMausBot/blob/v0.1.143/docs/custom-engines.md)
- [CLI 入口与配对实现](https://github.com/milind-soni/OpenMausBot/blob/v0.1.143/server/cli.ts)
- [customAcp](https://github.com/milind-soni/OpenMausBot/blob/v0.1.143/server/drivers/acp/custom.ts) 与 [协议/恢复核心](https://github.com/milind-soni/OpenMausBot/blob/v0.1.143/server/drivers/acp/core.ts)
- [内置 DeepSeek 驱动](https://github.com/milind-soni/OpenMausBot/blob/v0.1.143/server/drivers/acp/deepseek.ts)
- [Bot 创建路由](https://github.com/milind-soni/OpenMausBot/blob/v0.1.143/server/routes/bots-create.ts) 与 [创建 schema](https://github.com/milind-soni/OpenMausBot/blob/v0.1.143/server/new-bot-defaults.ts)
- [服务与 HTTPS](https://github.com/milind-soni/OpenMausBot/blob/v0.1.143/docs/self-hosting.md)、[CLI 配置](https://github.com/milind-soni/OpenMausBot/blob/v0.1.143/docs/cli-onboarding.md)、[手机网页](https://github.com/milind-soni/OpenMausBot/blob/v0.1.143/docs/phone-web-app.md)
- Harness 的 composition、ACP 插件名/patch、凭据根目录规则已按本机 app.asar 与已安装 WorkBuddy5.13.1 的文档及实现核对；参考 [上游 ACP 文档](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/bundle/acp-app/README.md)。

- [首页](../%E9%A6%96%E9%A1%B5.md)
- [01-需求/目标与待定事项](../01-%E9%9C%80%E6%B1%82/%E7%9B%AE%E6%A0%87%E4%B8%8E%E5%BE%85%E5%AE%9A%E4%BA%8B%E9%A1%B9.md)
- [06-决策/0002-OpenMausBot首轮范围与主入口](../06-%E5%86%B3%E7%AD%96/0002-OpenMausBot%E9%A6%96%E8%BD%AE%E8%8C%83%E5%9B%B4%E4%B8%8E%E4%B8%BB%E5%85%A5%E5%8F%A3.md)
- [02-调研/2026-11-06-OpenMausBot调研](../02-%E8%B0%83%E7%A0%94/2026-11-06-OpenMausBot%E8%B0%83%E7%A0%94.md)
- [05-验证/2026-11-06-双Agent最小系统复核](../05-%E9%AA%8C%E8%AF%81/2026-11-06-%E5%8F%8CAgent%E6%9C%80%E5%B0%8F%E7%B3%BB%E7%BB%9F%E5%A4%8D%E6%A0%B8.md)
- [04-搭建/2026-11-06-形成OpenMausBot实施交接](../04-%E6%90%AD%E5%BB%BA/2026-11-06-%E5%BD%A2%E6%88%90OpenMausBot%E5%AE%9E%E6%96%BD%E4%BA%A4%E6%8E%A5.md)
