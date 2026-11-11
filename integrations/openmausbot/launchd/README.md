# OpenMausBot 后台运行

`./scripts/omb-public.sh up` 把本机服务与已有自建HTTPS入口的SSH隧道交给macOS用户级launchd。两个任务在用户登录时恢复，服务/SSH异常退出时由launchd重启，不再依赖启动终端、nohup、PID文件或shell守护循环。

```bash
./scripts/omb-public.sh render --directory /tmp/omb-launchd-review  # 只生成，便于审查
./scripts/omb-public.sh up       # 安装/启动；重复执行不重启正常服务
./scripts/omb-public.sh status   # 区分launchd任务状态、本机健康、公网是否指向当前服务
./scripts/omb-public.sh restart  # 仅全部Bot空闲时有序重启
./scripts/omb-public.sh down     # bootout并移除plist，主动停止后不会重启或下次登录自动启动
./scripts/omb-public.sh pair     # 延用原手机邀请方式（生成有效期约5分钟的邀请）
```

## 管理边界

- plist：`~/Library/LaunchAgents/com.workflour.openmausbot.{serve,tunnel}.plist`。
- 日志：`~/.openmausbot/run/{serve,tunnel}.log`。
- 只操作本脚本写入且具有归属标记的两个精确label，不自动杀未知进程。
- SSH只绑定VPS的`127.0.0.1:9001`，公网仍由VPS Caddy的8443提供，不改原443。公网健康响应按设计隐藏PID，因此启动/状态核对会通过既有SSH账号只读请求VPS loopback的9001健康接口，与本机PID比较；不把公网脱敏当成故障。
- `up`只接受固定安装的OpenMausBot；不回退到会被清理的npx缓存。
- 保留稳定的Homebrew node软链接，不把具体Cellar版本写死进plist。Node或OpenMausBot安装位置改变后，应在Bot空闲时`restart`重新生成。
- `serve.pid`/`tunnel.pid`只在成功up后写给旧工具参考；新管理器的停止和状态判断均不信任它们。
- 用户注销或Mac休眠时不保证远程可用；本实现不阻止休眠。登录/唤醒后由系统和SSH心跳恢复。

## 首次迁移

`up`发现同端口手工服务或旧SSH连接时会拒绝，避免双开和误杀。迁移前先确保全部Bot空闲，然后有序停止已确认的前台服务以及原脚本的SSH守护和其子SSH，再执行up。不要只杀SSH子进程，否则旧循环会重建它。

主服务复用已安装OpenMausBot的`dist-server/server/service-unit.js`中的`launchdPlist`生成器，补齐本项目需要的`--public-url`、工作目录、独立label、重试节流和日志。隧道使用直接的系统`/usr/bin/ssh`，无需再安装autossh。主动停止使用`bootout`，避免只kill后被`KeepAlive`立即拉起。

首次由后台 Node 访问 Documents 中的项目时，macOS 可能显示文件夹访问授权。
本机迁移实测曾在这里等待约50秒，超过45秒健康检查窗口；任务仍由launchd托管，
授权完成后服务正常启动。若遇到这种情况，查看系统授权提示并再次运行`status/up`，
不要通过关闭系统权限保护解决。该等待不等于进程崩溃。

## 选型与来源（2026-11-09）

| 候选 | 核对与判断 |
| --- | --- |
| 系统launchd + 已有OpenMausBot服务生成器 | 已读本机`man launchctl`、`man launchd.plist`与实际产品源码。当前macOS自带，无新增依赖/付费/账号。支持精确任务管理与异常拉起，采用。Apple网页为归档文档，具体行为以当前系统man为准。 |
| PM2 | 已读官方startup文档及实际许可证；活跃维护的Node进程管理器，AGPL-3.0（许可证链接到GNU-AGPL-3.0.txt），但需新装npm依赖，macOS开机仍落到launchd。此处不引入额外守护层。 |
| Homebrew services | 已读官方services文档和brew的BSD-2-Clause许可证；活跃维护，实际也包装launchctl，但本项目不是已有formula，需自建formula或自定义service文件，收益小。 |
| macos-socks-proxy-tunnel-autostart | 已读实际README：近期仍有提交（检索页55次提交），使用launchd、SSH心跳和可选健康检查；需求为SOCKS/HTTP代理，还带gost，超出当前反向隧道需求；页面未展示许可，未复制其代码。README的KeepAlive.NetworkState用法与当前macOS man标明该条件已不再实现，故本实现使用KeepAlive=true。 |

来源：

- [Apple：Creating Launch Daemons and Agents](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)
- [Apple GitHub：launchd.plist man源码](https://github.com/apple-oss-distributions/launchd/blob/main/man/launchd.plist.5)
- [PM2 startup文档](https://pm2.keymetrics.io/docs/usage/startup/)，[PM2许可证](https://github.com/Unitech/pm2/blob/master/GNU-AGPL-3.0.txt)
- [Homebrew services文档](https://docs.brew.sh/Manpage#services-subcommand)，[BSD许可证](https://github.com/Homebrew/brew/blob/main/LICENSE.txt)
- [现成SSH常驻方案README](https://github.com/PavelSozonov/macos-socks-proxy-tunnel-autostart)

本实现没有复制其他GitHub候选的实现；OpenMausBot源码从当前固定安装导入生成器，不另行分发其代码。其本机`package.json`和实际发行LICENSE均为Apache-2.0。相关依赖既已安装，不新增成本。


## 精简工作台入口（2026-11-11）

`runtime.json` 是项目内显式入口选择。`mode: workbench` 选择指定的私有 `cli.js`，启动前核对固定上游和精简层的完整文件哈希/链接。继续复用原端口、数据目录、鉴权与公网 origin；不修改全局 npm 包。校验失败明确报错，不静默切换产品。

恢复原版：将同文件 `mode` 改为 `native`，在 Bot 空闲时执行正常 `restart`。重启会先校验目标运行目录，再停旧服务，避免坏路径把正常工作台停掉。修改入口本身不会自动中断任务。

若本机健康而隧道反复提示远端 9001 绑定失败，可能是 VPS 仍保留断网前的旧 SSH 会话。不要宽泛杀 SSH：先查 `ss -ltnp sport = :9001`，再核对该 sshd 的认证 key 指纹、启动时间和 socket；仅在确认是本工作流孤儿连接后处理具体 PID。本工具不会自动杀远端未知监听。


`run-omb.sh local|remote` 仍是固定版本的原生临时前台入口，不读取 `runtime.json`，因此不会加载精简界面。日常精简工作台使用 `scripts/omb-public.sh` 托管入口；不要在8799已有托管服务时再起一份前台服务。本轮没有改动临时入口。
