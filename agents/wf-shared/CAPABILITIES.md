# 本机能力实测（2026-11-11）

- 七个新角色均实际执行命令、读写文件成功；六个 DSH 请求记录和 AGY 的 ACP 回执确认了对应模型及思考档位。不要为自报模型再扫描环境、账号配置或原生日志；普通业务任务无需重复核查模型。
- Kimi Plan、DeepSeek Plan 评审、Gemini 主编码均使用真实图像工具正确识别了随机图片内容。视觉审核仍需逐张读取当前成品截图，不能引用探针替代成品检查。
- Plan 评审实际用 Playwright 操作了桌面和 375px 页面、断言点击结果、保存并读取截图。
- Python 入口：`/Users/a1/Documents/a/workflour/.tools/browser/bin/python`，Playwright 1.65.0；启动 `p.chromium.launch(channel="chrome", headless=True)`，使用新建的隔离 context。不要接管用户 Chrome profile 或登录。用法见 [BROWSER.md](BROWSER.md)。
- DSH `web_search` 实测可用。`web_fetch` 在本机对 MDN/GitHub 等公开页面出现网络解析拒绝；对同一失败类型不要反复换域名重试。可以使用命令工具以 HTTPS 读取明确的公开资料地址（实测 curl 成功），保留 URL 和真实引用；不要绕过登录、付费墙或权限限制，失败仍需如实记录。
- OpenMausBot 自带的桌面屏幕控制是单独的产品能力；当前编程流程用 DSH/AGY 自身的 Full 文件与命令工具以及隔离浏览器测试。不要为此把工作台 `computer` 改成 `local`，该项需要桌面程序授权，会在模型启动前阻断此部署。
- 有效证据与当前代码快照一致时复用；没有代码变化或新疑点，不为写进度回复重复跑同一测试。

证据：[模型实调核验](../../tests/evidence/team-v2-20261111/capability/model-runtime-check.json)、[能力探针](../../tests/evidence/team-v2-20261111/capability/)。这些是本机当前能力记录，不是对以后网络或额度的保证。


## 2026-11-11 技能实跑后的能力补充

当前额度路由可能选中 WorkBuddy 国际 `deepseek-v4.1-flash-sg`。本轮该实际模型的 `read_image` 明确返回未声明图像输入；桌面插件也没有勾选该精确 ID 的图片开关。以前普通 DeepSeek/Kimi/Gemini 的图片探针不能证明此线路现在可读图。不能擅自打开未知图片能力、换模型或改默认。

因此在该线路进行体验检查时，记录已实际观察的交互和明确的读图缺口，向负责人回传 blocked；不得把截图文件、DOM、几何测量或像素哈希当成看过图。已确认读图不可用后及时结束，不继续叠加设备实验。需要完整视觉验收时，由负责人明确安排已验证可读图的当前任务配置并重新核验。

本轮 Antigravity 实际读取前端技能和局部修复说明成功；独立完整 UX 样例在180秒内未完成，不能写成已通过。技能方法接入与运行时完成全部体验是两项不同验证。
