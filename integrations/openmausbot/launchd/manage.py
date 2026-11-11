#!/usr/bin/env python3
"""Manage this workspace's two user LaunchAgents; never adopt or kill foreign jobs."""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[3]
OWNER = "Managed by workflour scripts/omb-public.sh"
LABELS = {"serve": "com.workflour.openmausbot.serve", "tunnel": "com.workflour.openmausbot.tunnel"}
PUBLIC_URL = "https://198-44-111-185.sslip.io:8443"
VPS = "root@198.44.111.185"
LAUNCHCTL = "/bin/launchctl"


class ServiceError(RuntimeError):
    pass


def selected_cli(selection: Path | None = None) -> Path | None:
    """An explicit project switch selects the checked UI runtime; failure is visible."""
    selection = selection or WORKSPACE / 'integrations/openmausbot/launchd/runtime.json'
    if not selection.exists():
        return None
    try:
        config = json.loads(selection.read_text())
        if not isinstance(config, dict):
            raise ValueError('runtime selection must be a JSON object')
        if config.get('mode') == 'native':
            return None
        if config.get('mode') != 'workbench':
            raise ValueError('mode must be native or workbench')
        cli = Path(config['cli']).expanduser()
        if not cli.is_absolute() or cli.name != 'cli.js' or not cli.is_file():
            raise ValueError('workbench cli must be an existing absolute cli.js path')
        import importlib.util
        spec = importlib.util.spec_from_file_location('workbench_preparation', WORKSPACE / 'scripts/prepare-workbench.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        info = json.loads((cli.parent / module.MARKER).read_text())
        source = Path(info['source']).resolve(strict=True)
        lock = json.loads((module.OVERLAY / 'source-lock.json').read_text())
        verified = module.verify_runtime(cli.parent, source, lock)
        if Path(verified['cli']) != cli:
            raise ValueError('Runtime manifest cli does not match selected path')
        return cli
    except (ValueError, OSError, KeyError, TypeError) as error:
        raise ServiceError(f'精简工作台运行目录校验失败：{error}；未静默回退。把 runtime.json 的 mode 改为 native 可明确恢复原版。') from error


def find_cli() -> Path:
    selected = selected_cli()
    if selected is not None:
        return selected
    # A service must not depend on the evictable npx cache.
    for root in [Path("/opt/homebrew/lib/node_modules"), Path.home() / ".npm-global/lib/node_modules", Path("/usr/local/lib/node_modules")]:
        candidate = root / "openmausbot/cli.js"
        if candidate.is_file():
            return candidate
    raise ServiceError("找不到固定安装的 OpenMausBot；先安装已选定版本 openmausbot@0.1.143。")


def find_node() -> str:
    # Keep the stable Homebrew symlink, not its versioned Cellar target.
    for candidate in ["/opt/homebrew/bin/node", "/usr/local/bin/node", shutil.which("node")]:
        if candidate and os.path.isabs(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise ServiceError("找不到可执行的 node。")


class Manager:
    def __init__(self, home: Path | None = None, port: int | None = None):
        self.home = home or Path.home()
        self.port = port or int(os.environ.get("OMB_PORT", "8799"))
        if not 1 <= self.port <= 65535:
            raise ServiceError("OMB_PORT 必须是1到65535。")
        self.run_dir = self.home / ".openmausbot/run"
        self.agents = self.home / "Library/LaunchAgents"
        self.domain = f"gui/{os.getuid()}"
        self.forward = f"127.0.0.1:9001:127.0.0.1:{self.port}"
        self.key = self.home / ".ssh/codex_dedirock_ed25519"
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def target(self, kind: str) -> str:
        return f"{self.domain}/{LABELS[kind]}"

    def path(self, kind: str, directory: Path | None = None) -> Path:
        return (directory or self.agents) / f"{LABELS[kind]}.plist"

    def ctl(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([LAUNCHCTL, *args], text=True, capture_output=True, timeout=35)

    def loaded(self, kind: str) -> bool:
        return self.ctl("print", self.target(kind)).returncode == 0

    def pid(self, kind: str) -> int | None:
        result = self.ctl("print", self.target(kind))
        match = re.search(r"^\s*pid = (\d+)\s*$", result.stdout, re.M)
        return int(match[1]) if result.returncode == 0 and match else None

    def require_domain(self) -> None:
        if sys.platform != "darwin":
            raise ServiceError("此入口使用macOS用户LaunchAgent。")
        if self.ctl("print", self.domain).returncode:
            raise ServiceError("当前用户GUI登录域不可用；请先登录Mac桌面。")

    def plist(self, kind: str) -> dict:
        path = f"/opt/homebrew/bin:/usr/local/bin:{self.home}/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        env = {"HOME": str(self.home), "PATH": path}
        common = {
            "Label": LABELS[kind], "Comment": OWNER,
            "WorkingDirectory": str(WORKSPACE), "EnvironmentVariables": env,
            "RunAtLoad": True, "KeepAlive": True, "ThrottleInterval": 5,
            "ExitTimeOut": 30, "ProcessType": "Background", "Umask": 0o077,
            "StandardOutPath": str(self.run_dir / f"{kind}.log"),
            "StandardErrorPath": str(self.run_dir / f"{kind}.log"),
        }
        if kind == "serve":
            cli = find_cli()
            # Reuse the fixed installed product's service renderer; its public CLI
            # omits --public-url, while the renderer accepts explicit serveArgs.
            module = cli.parent / "dist-server/server/service-unit.js"
            spec = {"node": find_node(), "script": str(cli), "home": str(self.home),
                    "dataDir": str(self.home / ".openmausbot"),
                    "serveArgs": ["--port", str(self.port), "--data-dir", str(self.home / ".openmausbot"), "--no-pair", "--public-url", PUBLIC_URL]}
            # Static import requires a literal; pass the module as a dynamic import URL.
            source = "const {launchdPlist}=await import(process.argv[1]); process.stdout.write(launchdPlist(JSON.parse(process.argv[2])));"
            rendered = subprocess.run([find_node(), "--input-type=module", "-e", source, module.as_uri(), json.dumps(spec)], text=True, capture_output=True, timeout=10)
            if rendered.returncode:
                raise ServiceError("已安装OpenMausBot的服务模板生成失败；没有安装或启动任何任务。")
            base = plistlib.loads(rendered.stdout.encode())
            base.update(common)
            base["EnvironmentVariables"]["OMB_DATA_DIR"] = spec["dataDir"]
            return base
        common["ProgramArguments"] = [
            "/usr/bin/ssh", "-N", "-T", "-o", "BatchMode=yes",
            "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3",
            "-o", "ExitOnForwardFailure=yes", "-o", "TCPKeepAlive=yes",
            "-o", "ConnectTimeout=10", "-o", "ControlMaster=no", "-o", "ControlPath=none", "-i", str(self.key), "-R", self.forward, VPS,
        ]
        return common

    @staticmethod
    def owned(path: Path, label: str) -> bool:
        try:
            value = plistlib.loads(path.read_bytes())
            return value.get("Label") == label and value.get("Comment") == OWNER
        except (OSError, plistlib.InvalidFileException, ValueError):
            return False

    def ensure_ownership(self) -> None:
        for kind, label in LABELS.items():
            path = self.path(kind)
            if path.exists() and not self.owned(path, label):
                raise ServiceError(f"同名plist不是本脚本管理，拒绝覆盖: {path}")
            if self.loaded(kind) and not self.owned(path, label):
                raise ServiceError(f"同名LaunchAgent归属无法确认，拒绝操作: {label}")

    def health(self, public: bool = False) -> dict | None:
        url = PUBLIC_URL if public else f"http://127.0.0.1:{self.port}"
        try:
            with self.opener.open(url + "/api/health", timeout=4) as response:
                value = json.load(response)
            return value if value.get("app") == "openmausbot" else None
        except (OSError, ValueError):
            return None

    def tunnel_health(self) -> dict | None:
        # Public health deliberately omits pid. Probe the VPS's private forwarded
        # endpoint over the existing SSH account to verify it is this local server.
        command = ["/usr/bin/ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
                   "-o", "ControlMaster=no", "-o", "ControlPath=none", "-i", str(self.key), VPS,
                   "curl --noproxy '*' -sf --max-time 4 http://127.0.0.1:9001/api/health"]
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=14)
            value = json.loads(result.stdout) if result.returncode == 0 else None
            return value if isinstance(value, dict) and value.get("app") == "openmausbot" else None
        except (OSError, ValueError, subprocess.SubprocessError):
            return None

    def port_busy(self) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                return True
        except OSError:
            return False

    @staticmethod
    def matching_tunnels(text: str, forward: str) -> list[int]:
        matches = []
        for line in text.splitlines():
            parts = line.strip().split(None, 2)
            if len(parts) != 3:
                continue
            try:
                pid = int(parts[0])
                args = shlex.split(parts[2])
            except (ValueError, IndexError):
                continue
            if args and Path(args[0]).name == "ssh" and VPS in args:
                for index, arg in enumerate(args[:-1]):
                    if arg == "-R" and args[index + 1] == forward:
                        matches.append(pid)
                        break
        return matches

    def refuse_unmanaged(self) -> None:
        if not self.loaded("serve") and self.port_busy():
            raise ServiceError(f"本机{self.port}已有未托管服务；请先有序停止当前前台/旧服务，再执行up。不会自动杀进程。")
        table = subprocess.run(["/bin/ps", "-axo", "pid=,ppid=,command="], text=True, capture_output=True, timeout=5)
        if table.returncode:
            raise ServiceError("无法核对旧SSH隧道进程；拒绝可能重复建链的启动。")
        own = self.pid("tunnel")
        foreign = [pid for pid in self.matching_tunnels(table.stdout, self.forward) if pid != own]
        if foreign:
            raise ServiceError(f"检测到旧/未托管SSH隧道(pid {', '.join(map(str, foreign))})；请先停止已确认的旧守护及其SSH子进程。不会自动接管或杀进程。")

    @staticmethod
    def write_plist(path: Path, value: dict) -> None:
        content = plistlib.dumps(value, sort_keys=False)
        if path.exists() and path.read_bytes() == content:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
            os.chmod(temp, 0o600)
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def render(self, directory: Path) -> None:
        for kind in LABELS:
            self.write_plist(self.path(kind, directory), self.plist(kind))
            print(self.path(kind, directory))

    def up(self) -> None:
        self.require_domain()
        self.ensure_ownership()
        self.refuse_unmanaged()
        if not self.key.is_file():
            raise ServiceError("已配置的SSH私钥文件不存在；未启动任务。")
        desired = {kind: self.plist(kind) for kind in LABELS}
        for kind, value in desired.items():
            path = self.path(kind)
            if self.loaded(kind) and plistlib.loads(path.read_bytes()) != value:
                raise ServiceError("运行配置与生成配置不同；请在Bot空闲后执行restart。")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        for kind, value in desired.items():
            self.write_plist(self.path(kind), value)
            if not self.loaded(kind):
                self.ctl("enable", self.target(kind))
                result = self.ctl("bootstrap", self.domain, str(self.path(kind)))
                if result.returncode:
                    raise ServiceError(f"启动{kind}失败: {result.stderr.strip()}")
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            local = self.health()
            public = self.health(True) if local else None
            if local and public and all(self.pid(k) for k in LABELS):
                forwarded = self.tunnel_health()
                if not forwarded or forwarded.get("pid") != local.get("pid"):
                    time.sleep(1)
                    continue
                # Kept for old tooling only; stop/status never trust these pidfiles.
                for kind in LABELS:
                    (self.run_dir / f"{kind}.pid").write_text(str(self.pid(kind)) + "\n")
                print("本机服务和SSH隧道已交给launchd；离开终端后仍运行，异常退出会自动恢复。")
                print(f"公网检查通过: {PUBLIC_URL}")
                return
            time.sleep(1)
        raise ServiceError(f"任务已托管，但45秒内端到端检查未通过；查看 {self.run_dir} 的serve.log和tunnel.log。")

    def down(self) -> None:
        self.require_domain()
        self.ensure_ownership()
        stopped_service = self.loaded("serve")
        for kind in ["tunnel", "serve"]:
            if self.loaded(kind):
                result = self.ctl("bootout", self.target(kind))
                if result.returncode and self.loaded(kind):
                    raise ServiceError(f"停止{kind}失败: {result.stderr.strip()}")
            path = self.path(kind)
            if path.exists():
                path.unlink()  # Do not silently start again on next login after explicit down.
        # launchctl can finish removing the job before a child releases its
        # listener. Wait before restart/up, without signalling any other process.
        if stopped_service:
            deadline = time.monotonic() + 35
            while self.port_busy() and time.monotonic() < deadline:
                time.sleep(.2)
            if self.port_busy():
                raise ServiceError("托管任务已移除，但本机端口仍被占用；请核实后再up，不会自动杀进程。")
        print("两个托管任务已停止并取消登录启动；VPS上的Caddy保持运行。")

    def restart(self) -> None:
        if self.health():
            try:
                with self.opener.open(f"http://127.0.0.1:{self.port}/api/bots?messages=0", timeout=5) as response:
                    bots = json.load(response)["bots"]
            except (OSError, ValueError, KeyError):
                raise ServiceError("无法核实Bot空闲状态，拒绝重启。")
            if any(bot.get("busy") or any(task.get("busy") for task in bot.get("tasks", [])) for bot in bots):
                raise ServiceError("仍有Bot任务运行，请等任务结束或主动中断后再重启。")
        # Validate the selected runtime before touching a healthy service.
        self.plist("serve")
        self.plist("tunnel")
        if not self.key.is_file():
            raise ServiceError("SSH私钥文件不存在；保留现有服务，未重启。")
        self.down()
        self.up()

    def status(self) -> None:
        self.require_domain()
        local, public, forwarded = self.health(), self.health(True), self.tunnel_health()
        for kind in LABELS:
            print(f"{kind}: " + (f"launchd运行中 (pid {self.pid(kind)})" if self.pid(kind) else "未托管运行"))
        print(f"本机健康: {'正常' if local else '无响应'}")
        print(f"公网健康: {'正常' if public else '无响应'}")
        print(f"隧道目标: {'已核对为当前本机服务' if local and forwarded and local.get('pid') == forwarded.get('pid') else '未核对通过'}")
        if local and not self.loaded("serve"):
            print("提示：当前本机服务是手工启动，尚未由本脚本托管。")

    def pair(self) -> None:
        if not self.health():
            raise ServiceError("服务未运行，请先执行up。")
        print("配对邀请有效期约5分钟。")
        result = subprocess.run([find_node(), str(find_cli()), "pair", "--client", "--label", "Phone", "--public-url", PUBLIC_URL], cwd=WORKSPACE)
        if result.returncode:
            raise ServiceError("生成邀请失败。")


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenMausBot本机服务+SSH隧道用户级LaunchAgent管理")
    parser.add_argument("action", choices=["up", "down", "status", "restart", "pair", "render"])
    parser.add_argument("--directory", type=Path, help="render输出目录，不安装、不启动")
    args = parser.parse_args()
    try:
        manager = Manager()
        if args.action == "render":
            if not args.directory:
                parser.error("render需要--directory")
            manager.render(args.directory)
        else:
            getattr(manager, args.action)()
        return 0
    except (ServiceError, OSError, subprocess.SubprocessError, ValueError) as error:
        print(f"错误: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
