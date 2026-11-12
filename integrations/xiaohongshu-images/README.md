# 小红书插图：Antigravity 原生通道

默认使用已登录的 Antigravity CLI **print 模式**和内置生图能力，每次只请求一张图。它复用本机已有订阅登录，不创建 API Key、不接第三方图像 API，不执行小红书发布或互动。图文卡片排版仍由 `render-xhs-cards.py` 完成；模板卡片与原创 AI 插图分别记录。

## 调用

先完成文章和配图简报，再调用一次。简报放在输出目录之外，输出目录必须是新的空目录，路径使用绝对路径：

```sh
python3 scripts/xhs-image.py status --output-dir /absolute/fresh/status-directory
python3 scripts/xhs-image.py generate \
  --prompt-file /absolute/brief.txt \
  --output-dir /absolute/fresh/image-directory \
  --max-images 1
```

`generate` 只发一个任务，不自动重试、重派或生成变体。默认超时 420 秒，上限 900 秒；失败保留本次证据，由负责人判断下一步。每次选择新输出目录，不覆盖旧图和旧回执。`status` 只检查 CLI 是否接受本次收费设置，不发模型 prompt，也不证明图像额度或生图能力。

运行时使用 `AGY_BIN` 指定的程序，或 `~/.local/bin/agy`。实际命令参数为：

```text
--settings {"useG1Credits":false}
--model gemini-3.8-flash-low --effort low
--output-format json --print-timeout 420s --print <单张配图任务>
```

不传 `--agent image-generator`，由默认 Agent 调用其内置生图专员。AGY 1.5.0 起，print 模式会等待后台任务完成；封装等待完整进程退出、最终 JSON `status: SUCCESS` 和实际图片文件，不会在“已启动，正在等待”这类中间答复处关闭会话。超时会终止本次进程组，返回 `blocked`，不再次消耗额度。

生图进程在项目外的私有临时目录运行，只收到本次配图简报，避免因项目工作目录自动加载整套编程工作流和仓库文件。临时目录中的最终图片在退出前复制到指定输出目录。此措施减少无关上下文，具体节省量仍以实际 usage 为准。

`useG1Credits:false` 是会话级覆盖，不保存到用户配置；用于禁用本次 Google AI credits 超额使用。子进程还移除 API Key/ADC 选择环境变量，既不写入密钥，也不修改当前进程或全局环境。原有登录、权限和收费设置保持原样；不使用 `--dangerously-skip-permissions`。新电脑仍需核对自己的账号、订阅和实际额度，不能从 Pro 名称推断生图免费或无限。

## 回执与验图

标准输出为精简 JSON，完整安全回执为输出目录下的 `image-evidence.json`，权限为 0600。成功结果含 `status: generated_pending_visual_review`、`backend: print`、`prompt_sent`、`billing_override`、`exit_code`、`native_image_tool_observed`，以及 `images` 数组。每张图记录相对 `file`、`media_type`、`dimensions`、`bytes` 和 `sha256`。

回执只保留公开最终回答、工具名称、允许的数值 usage、模型请求与档位、时间和实际图片的格式/尺寸/字节数/哈希。不保留原生会话全文、隐藏思考、原始工具参数/返回、stderr 或凭据。不会执行模型答复中的命令。

仅接受本任务输出目录，或 AGY 默认 `~/.gemini/{antigravity,antigravity-cli}/{brain,artifacts}` 中本次新产生的 PNG/JPEG/WebP。路径经过真实解析和目录检查，拒绝越界符号链接、任意外部绝对路径、旧图片和只有文件名的答复。外部图片复制进输出目录，保留原文件且不覆盖已有文件；文件内容必须具有有效图像结构，不能用 SVG、文字或占位文件冒充成功。

原生 print 可能返回 `SUCCESS`，公开回答却仍只有“等待专员”而不带图片路径。封装会额外检查最终 JSON 明确返回的那个 `conversation_id` 对应 brain 目录中的新图片；不会扫描其他会话。此次私有临时工作目录也允许收图，目录会在复制完成后删除。

`generated_pending_visual_review` 表示 CLI 完成并取得实际图片，仍需负责人实际读图，检查构图、文字、事实和适用性。聊天模型是 Gemini，并不证明底层图像型号；回答中声称“Imagen 3”或“Nano Banana Pro”也不作为独立认证。工具未暴露可核验的型号时，`image_model` 保持 `unverified`。

`native_image_tool_observed:false` 不代表图片不存在：主 Agent 的日志可能只显示 `invoke_subagent`，真实 `generate_image` 发生在内置专员内部。封装只从本次会话的指定日志提取工具名称，不把主 Agent 的文字声称当作工具证据。图片文件验证和工具可见性分开记录。

## ACP 诊断与当前证据

`status --backend acp` 保留无 prompt 的 ACP 握手诊断；ACP 不再承担 `generate`。历史 ACP 的 `blocked / IMAGE_TOOL_UNAVAILABLE` 仅约束 ACP，不阻止默认 print。旧 `--probe` 参数仅为兼容保留，print 不需要它。

2026-11-11 的 ACP 探针先返回内置生图专员仍在运行，旧客户端过早结束；直接指定 `--agent image-generator` 又返回无生图工具。随后 AGY 1.5.5 默认 print 模式完成第一张实际插图，最终状态 `SUCCESS`，生成 JPEG 并由负责人验图。成功通道和历史失败分别保存在 `capability.json` 的 `backends.print` 与 `backends.acp`，不得把 ACP 限制推广到整个产品。

第一张已验图文件位于 `examples/xhs-claude-demo/image-versions/gemini-v1/claude-cover.jpg`。Ubuntu 需安装并登录自己的 AGY、核对本机 `agy --help` / `agy changelog` 与账号；本次 Mac 成功不代表 Linux 已验证。

公开产品背景：[Antigravity Nano Banana Pro](https://antigravity.google/blog/nano-banana-pro/)。具体入口和参数以本机 CLI 帮助、版本日志及实际文件证据为准。

两张真实原图及四页图文均已读图，最新版本见 `examples/xhs-claude-demo/image-versions/gemini-v1/`。第二张曾因公开答复漏路径而需维护恢复，原 blocked 回执与 image-recovery.json 分开保存；未重跑生图。修复后52项小红书针对性测试及真实旧产物收图复验通过，具体额度节省未量化。
