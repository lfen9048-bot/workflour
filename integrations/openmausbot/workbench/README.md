# Workflour 工作台界面精简层

复用 OpenMausBot 0.1.143 原生界面，增加“高级设置”切换。日常视图保留外观、通知、用量、手机配对；收起账户、系统维护、公司成员、导入、活动审计、云订阅、电脑后端、登录资料、引擎和密钥接入。

日常 AI 页说明怎样向大管家或通用助手打开安全模型设置，并提醒区分当前任务和以后默认值。它不代发消息、不切换模型；只有说明已成功插入后才隐藏原生引擎列表，避免空白页。全体 Bot 的原生模型菜单和项目安全设置卡仍保留。

这是显示层。模型/思考菜单、新任务、停止、记录、Bot 权限、登录认证和后端接口均由原产品处理，不禁用任何后端能力。高级设置可恢复收起的项目；原生“高级模式”也仍可进入完整产品界面。

## 准备与校验

在项目根目录执行：

```sh
python3 scripts/prepare-workbench.py
python3 scripts/prepare-workbench.py --verify
```

默认输出 `~/.workflour/runtime/openmausbot-0.1.143-workbench/cli.js`。脚本只准备文件，不改服务配置、不启动或重启服务。部署者应在空闲后把 launchd 的 CLI 指向输出路径，继续复用原数据目录、端口、鉴权及网络配置。

`source-lock.json` 固定上游版本及关键服务、设置组件和样式 SHA256。不同版本或源文件变化会拒绝准备；不能只改版本号跳过核对。已存在输出仅允许校验；修改精简层后用新的 `--out` 路径生成，再切换服务入口。复原服务入口到原生 CLI 即撤销部署，不修改 Bot 数据。

## 私有运行目录布局

- 复制 `cli.js`、`package.json`、`dist-server/openmausbot.js`。复制 CLI 的 `serverEntry()` 选择私有 `dist`，通过原生 `OMB_STATIC_DIR` 传入未改动的服务器。
- 其余服务文件、依赖、原 assets 和 skills 使用指向固定安装的符号链接；不修改全局 npm 包。
- 只向私有 `dist/index.html` 注入同源 CSS 和 JS 文件。没有内联脚本、代理、fetch 包装或登录拦截。
- `.workflour-workbench.json` 保存复制文件和符号链接清单，支持重跑校验。

## 界面行为与回退

设置页右上角“高级设置”只控制精简层，记在当前浏览器 `localStorage`，不改服务器设置。浏览器禁止存储时，当前页面仍可切换。可用 `?workflourView=full` 暂时恢复完整内容；不删除或重写现有 URL 参数。切换不会操作模型或任务。

隐藏规则仅限定 `data-settings-sheet` 且原生 `data-settings-look="simple"` 的设置页，使用 0.1.143 实际存在的 `data-settings-block` 和 `data-settings-disclosure`。不按中文文本猜按钮、不碰模型弹窗、任务记录或停止按钮。未知原生布局按原样显示，不扩大隐藏范围。

视觉验收需在部署后检查深浅色、桌面及手机宽度、键盘焦点、高级开关、外观/通知/用量/配对以及模型/思考/停止/记录。准备脚本与静态检查通过不能代替实际界面验收。

2026-11-11 的早期验证证据在 `tests/evidence/team-v2-20261111/ui/VALIDATION.json`。安全模型卡实际显示 20 个模型及来源，第二步显示 Low/High/Max，以及“仅当前任务”和“设为 Bot 默认”两个作用范围；没有提交最终应用或改变模型。

第三版已部署并在已登录 Chrome 检查，真实截图以 `final-live-v3-` 开头，汇总为 `final-live-v3-qa.json`。桌面及 375×812 手机的深浅色均无横向溢出；高级开关可恢复 16 个原生引擎；配对、用量、安全模型卡及新对话入口保留。全部检查对象当时空闲，因此没有为了测试停止按钮而新派任务，也没有宣称停止操作已实测。检查结束恢复高级设置关闭、跟随系统、默认浏览器尺寸并停在大管家待验收回复。

这次实服检查发现：从 AI 切到其他设置页后，模型说明会残留。第四版仅修正说明的清理与显示范围，新增离线 DOM 切页回归在旧代码上复现失败、修后通过。准备脚本 5 项测试、1 项浏览器切页回归、8 组原生 DOM 深浅色/尺寸渲染、JavaScript 语法及针对项目精简层的 impeccable 检查均通过。证据为 `v4-preparation-validation.json`、`preview-v4-verification.json`；`preview-v4-` 图片是离线副本，不能当作实服截图。

第四版已由部署者启用，运行目录为 `~/.workflour/runtime/openmausbot-0.1.143-workbench-v4/cli.js`，manifest 校验通过，原第三版运行文件未改变。已登录 Chrome 的最终实服回归见 `final-live-v4-qa.json`：页面实际载入第四版 CSS/JS hash；AI 页说明只有一份，切到通用、设备和用量后均清除；高级设置恢复原生引擎；安全模型卡仍显示真实思考档位与任务/默认作用范围，未提交任何修改。设备配对与用量入口经真实截图复核仍可见，未生成邀请或宣称读到了额度金额。

最终七个业务入口及大管家待验收回复截图为 `final-live-v4-workbench-1440x900.jpg`，设置截图为 `final-live-v4-general-after-ai-desktop.jpg`。本轮只验证第四版的切页修复和保留入口，没有重跑第三版完整验收。结束时高级关闭、跟随系统、停在大管家；已取消尺寸模拟，实际浏览器当前默认尺寸为 1200×717（此前窗口为 1200×661）。Chrome 自动翻译会改写部分原生中文标签及截图里的角色名称，本次未改其设置或 Bot 名称。停止操作仍属于未在本次 UI 检查中实际执行的范围。

上游来源：https://github.com/milind-soni/OpenMausBot （Apache-2.0）。本机核对依据：`src/components/SettingsSimplePages.tsx`、`SettingsModal.tsx`、`EnginesSettings.tsx`、`SettingsPrimitives.tsx`。
