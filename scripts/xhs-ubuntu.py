#!/usr/bin/env python3
"""Ubuntu desktop quick entry. Installs tools, never copies Mac accounts or sends test prompts."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = Path.home() / '.workflour/xhs-ubuntu'
LOCK = json.loads((ROOT / 'integrations/ubuntu/versions.json').read_text())
UNITS = ('workflour-xhs-workbench.service', 'workflour-xhs-collector.service')
MARKER = '# Managed by workflour xhs-ubuntu v1'


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def require_ubuntu():
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise ValueError('This installer targets Ubuntu x86_64; it must run inside your Ubuntu VM')
    info = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if info.get('ID', '').strip('"') != 'ubuntu':
        raise ValueError('Ubuntu is required; other Linux distributions are not validated')
    if sys.version_info < (3, 10):
        raise ValueError('Python 3.10+ required; Ubuntu 24.04 is recommended')
    if os.geteuid() == 0:
        raise ValueError('Run as your desktop user, not sudo/root; only OS dependency installation uses sudo')


def source_profile(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ValueError('Invalid WorkBuddy source profile name')
    return value


def environment():
    saved = json.loads((BASE / 'settings.json').read_text()) if (BASE / 'settings.json').exists() else {}
    env = os.environ.copy()
    env.setdefault('DSH_HOME', saved.get('dsh_home', str(Path.home() / '.dsh')))
    env.setdefault('WORKFLOUR_DSH_SOURCE_PROFILE', saved.get('source_profile', 'web'))
    source_profile(env['WORKFLOUR_DSH_SOURCE_PROFILE'])
    runtime_bin = BASE / 'runtime/node_modules/.bin'
    node_bin = saved.get('node_bin', '')
    env['PATH'] = os.pathsep.join([str(runtime_bin), node_bin, str(Path.home() / '.local/bin'), env.get('PATH', '')])
    env.setdefault('DSH_BIN', str(runtime_bin / 'dsh'))
    env.setdefault('AGY_BIN', shutil.which('agy', path=env['PATH']) or str(Path.home() / '.local/bin/agy'))
    env.setdefault('XHS_BROWSER_PYTHON', str(Path.home() / '.workflour/xhs-sources/venv/bin/python'))
    env.setdefault('TWS_TELEMETRY', '0')
    env.setdefault('OMB_DATA_DIR', str(Path.home() / '.openmausbot'))
    return env


def private_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def ensure_node():
    binary = shutil.which('node')
    if binary:
        version = subprocess.check_output([binary, '--version'], text=True).strip()
        if int(version.lstrip('v').split('.')[0]) >= 24 and shutil.which('npm'):
            return str(Path(binary).parent)
    name = 'node-v' + LOCK['node'] + '-linux-x64'
    destination = BASE / name
    if not (destination / 'bin/node').exists():
        with tempfile.TemporaryDirectory(dir=BASE) as tmp:
            archive = Path(tmp) / (name + '.tar.xz')
            urllib.request.urlretrieve('https://nodejs.org/dist/v' + LOCK['node'] + '/' + archive.name, archive)
            if hashlib.sha256(archive.read_bytes()).hexdigest() != LOCK['node_linux_x64_sha256']:
                raise ValueError('Node archive checksum mismatch; archive was not executed')
            run(['tar', '-xJf', archive, '-C', tmp])
            (Path(tmp) / name).replace(destination)
    return str(destination / 'bin')


def install(args):
    BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
    BASE.chmod(0o700)
    if args.system_deps:
        run(['sudo', 'apt-get', 'update'])
        run(['sudo', 'apt-get', 'install', '-y', 'python3-venv', 'ruby', 'curl', 'git', 'xz-utils',
             'build-essential', 'fonts-noto-cjk', 'fontconfig', 'libsecret-1-0', 'dbus-x11'])
    env = environment()
    settings = {'version': 1, 'dsh_home': env['DSH_HOME'],
                'source_profile': env['WORKFLOUR_DSH_SOURCE_PROFILE']}
    if not args.tools_only:
        settings['node_bin'] = ensure_node()
    elif (BASE / 'settings.json').exists():
        settings['node_bin'] = json.loads((BASE / 'settings.json').read_text()).get('node_bin', '')
    private_json(BASE / 'settings.json', settings)
    env = environment()
    if not args.tools_only:
        # Recent npm versions skip unapproved native builds. Keep the policy
        # local to this runtime and permit the known dependency versions only.
        package = BASE / 'runtime/package.json'
        manifest = json.loads(package.read_text()) if package.exists() else {'private': True}
        manifest.setdefault('allowScripts', {}).update({
            '@deepseek-ai/dsh-subprocess-local@0.2.1-rc.2': True,
            'koffi@3.1.1': True, 'node-pty@1.2.0-beta.15': True, 'protobufjs@7.6.6': True,
        })
        private_json(package, manifest)
        run(['npm', 'install', '--prefix', BASE / 'runtime', '--no-audit', '--no-fund',
             '@deepseek-ai/dsh@' + LOCK['dsh'], 'pnpm@' + LOCK['pnpm'],
             'openmausbot@' + LOCK['openmausbot']], env=env)
        ensure_workbuddy(env)
    for folder in ('xhs-sources', 'xhs-crawler'):
        venv = Path.home() / '.workflour' / folder / 'venv'
        if not (venv / 'bin/python').exists():
            run([sys.executable, '-m', 'venv', venv])
        run([venv / 'bin/python', '-m', 'pip', 'install', '-r', ROOT / 'integrations' / folder / 'requirements.txt'])
    browser = Path(env['XHS_BROWSER_PYTHON'])
    command = [browser, '-m', 'playwright', 'install']
    if args.system_deps:
        command.append('--with-deps')
    run(command + ['chromium'])
    if args.system_deps and not any(shutil.which(x) for x in ('google-chrome', 'chromium', 'chromium-browser')):
        run([browser, '-m', 'playwright', 'install', 'chrome'])
    if not args.skip_xhs:
        run([sys.executable, ROOT / 'integrations/xiaohongshu/service.py', 'install'], env=env)
    print('工具安装完成；尚未验证账号。下一步 auth-workbuddy，然后安装/登录 Antigravity。')


def ensure_workbuddy(env):
    profile = env['WORKFLOUR_DSH_SOURCE_PROFILE']
    package = Path(env['DSH_HOME']) / 'profiles' / profile / 'package.json'
    deps = json.loads(package.read_text()).get('dependencies', {}) if package.exists() else {}
    wanted = deps.get('dsh-connect-workbuddy')
    if wanted and wanted != LOCK['workbuddy']:
        raise ValueError('Existing WorkBuddy version differs; no automatic downgrade. Use a separate source profile')
    if not wanted:
        run([env['DSH_BIN'], 'plugin', '--profile', profile, 'add', '--save-exact',
             'dsh-connect-workbuddy@' + LOCK['workbuddy']], env=env)


def auth_workbuddy():
    env = environment()
    ensure_workbuddy(env)
    profile = env['WORKFLOUR_DSH_SOURCE_PROFILE']
    print('在 DSH Web 的 WorkBuddy 设置登录，保存账号池与模型选择；完成后 Ctrl-C 返回。', flush=True)
    os.execvpe(env['DSH_BIN'], [env['DSH_BIN'], '--profile', profile, '--host', '127.0.0.1', '--port', '3080'], env)


def team_module():
    spec = importlib.util.spec_from_file_location('ubuntu_xhs_team', ROOT / 'scripts/provision-xhs-team.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def workbench():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open('http://127.0.0.1:8799/api/bots?messages=0', timeout=3) as response:
            return json.load(response)['bots']
    except urllib.error.URLError as e:
        if isinstance(e.reason, ConnectionRefusedError):
            return None
        raise ValueError('Workbench status is unknown; do not replace or stop it') from None


def configure():
    if workbench() is not None:
        raise ValueError('Workbench is running. Wait until idle, run down, then configure; it will not be restarted automatically')
    env = environment()
    run([env['AGY_BIN'], '--version'], env=env)
    run(['ruby', ROOT / 'scripts/workbuddy-pool-sync.rb', '--profile', 'omb-xhs-collector', '--check'], env=env)
    for role in ('xhs-collector', 'xhs-planner', 'xhs-writer'):
        run(['bash', ROOT / 'integrations/openmausbot/setup.sh', '--only', role], env=env)
    run([sys.executable, ROOT / 'scripts/configure-xhs-delivery.py', '--root', ROOT], env=env)
    run([sys.executable, ROOT / 'scripts/provision-xhs-team.py', 'prepare'], env=env)
    print('配置完成。执行 up 启动服务，再执行 connect 创建三个 Bot。')


def unit_text(component, root=ROOT, python=sys.executable):
    def quote(value, command=False):
        # systemd expands percent specifiers even inside double quotes.
        value = str(value).replace('%', '%%').replace('\\', '\\\\').replace('"', '\\"')
        if command:
            value = value.replace('$', '$$')
        return '"' + value + '"'
    if any(c in str(root) + str(python) for c in '\n\r'):
        raise ValueError('Newlines are not supported in service paths')
    return (MARKER + '\n[Unit]\nDescription=Workflour XHS ' + component + '\nAfter=network-online.target\n'
            '[Service]\nType=simple\nWorkingDirectory=' + str(root).replace('%', '%%') + '\nExecStart=' + quote(python, True) + ' '
            + quote(root / 'scripts/xhs-ubuntu.py', True) + ' serve --component ' + component + '\n'
            'Restart=on-failure\nRestartSec=10\nUMask=0077\n'
            '[Install]\nWantedBy=default.target\n')


def services(action):
    folder = Path.home() / '.config/systemd/user'
    if action == 'up':
        if workbench() is not None:
            raise ValueError('Port 8799 already serves a workbench; inspect it instead of starting another')
        folder.mkdir(parents=True, exist_ok=True)
        for name in UNITS:
            path = folder / name
            if path.exists() and not path.read_text().startswith(MARKER):
                raise ValueError('Refuse to replace a service not owned by this installer: ' + name)
        for name, component in zip(UNITS, ('omb', 'xhs')):
            (folder / name).write_text(unit_text(component))
        run(['systemctl', '--user', 'daemon-reload'])
        run(['systemctl', '--user', 'enable', '--now', *UNITS])
    elif action == 'down':
        bots = workbench()
        if bots and any(b.get('busy') or any(t.get('busy') for t in b.get('tasks', [])) for b in bots):
            raise ValueError('A Bot is busy; refusing to interrupt running work')
        for name in UNITS:
            path = folder / name
            if not path.exists() or not path.read_text().startswith(MARKER):
                raise ValueError('Missing owned service; manage the foreground process you started')
        run(['systemctl', '--user', 'disable', '--now', *UNITS])
    else:
        run(['systemctl', '--user', '--no-pager', 'status', *UNITS])


def serve(component):
    env = environment()
    if component == 'omb':
        binary = str(BASE / 'runtime/node_modules/.bin/openmausbot')
        args = [binary, 'serve']
    else:
        binary = sys.executable
        args = [binary, str(ROOT / 'integrations/xiaohongshu/service.py'), 'run']
    os.execvpe(binary, args, env)


def doctor(offline=False):
    env = environment()
    checks = {}
    commands = {'dsh': [env['DSH_BIN'], '--version'], 'agy': [env['AGY_BIN'], '--version'],
                'node': ['node', '--version'], 'ruby': ['ruby', '--version'],
                'sources': [env['XHS_BROWSER_PYTHON'], '-c', 'import twscrape, yt_dlp, playwright'],
                'crawler': [str(Path.home() / '.workflour/xhs-crawler/venv/bin/python'), '-c', 'import scrapling'],
                'chromium': [env['XHS_BROWSER_PYTHON'], '-c',
                    'from playwright.sync_api import sync_playwright; from pathlib import Path; '
                    'p=sync_playwright().start(); assert Path(p.chromium.executable_path).is_file(); p.stop()']}
    for name, command in commands.items():
        try:
            result = subprocess.run(command, env=env, capture_output=True, timeout=30)
            checks[name] = result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            checks[name] = False
    checks['login_browser'] = bool(os.environ.get('XHS_CHROME_BIN') or any(
        shutil.which(x) for x in ('google-chrome', 'chromium', 'chromium-browser')))
    try:
        result = subprocess.run(['ruby', str(ROOT / 'scripts/workbuddy-pool-sync.rb'), '--profile',
                                 'omb-xhs-collector', '--check'], env=env, capture_output=True, timeout=10)
        checks['workbuddy_saved_configuration'] = result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        checks['workbuddy_saved_configuration'] = False
    if not offline:
        checks['workbench_running'] = workbench() is not None
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open('http://127.0.0.1:18060/health', timeout=3) as response:
                checks['xhs_collector_running'] = response.status == 200
        except OSError:
            checks['xhs_collector_running'] = False
    print(json.dumps({'checks': checks, 'ready_for_target_login_verification': all(checks.values()),
                      'model_prompts_sent': False, 'account_authentication': 'not_probed',
                      'note': 'Missing agy: use the official Linux installer, then auth-gemini. Login/model/image acceptance is separate.'}, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('install')
    p.add_argument('--system-deps', action='store_true')
    p.add_argument('--tools-only', action='store_true', help='CI/tool-only install; omit Node/DSH/workbench')
    p.add_argument('--skip-xhs', action='store_true', help='Omit the optional XHS binary download')
    p = sub.add_parser('doctor'); p.add_argument('--offline', action='store_true')
    p = sub.add_parser('serve'); p.add_argument('--component', choices=('omb', 'xhs'), default='omb')
    p = sub.add_parser('start'); p.add_argument('--topic', required=True); p.add_argument('--project', required=True)
    p.add_argument('--image', action='store_true')
    for name in ('auth-workbuddy', 'auth-gemini', 'configure', 'connect', 'up', 'down', 'status', 'login-x', 'login-youtube', 'login-xhs'):
        sub.add_parser(name)
    args = parser.parse_args()
    require_ubuntu()
    os.umask(0o077)
    if args.command == 'install': install(args)
    elif args.command == 'doctor': return doctor(args.offline)
    elif args.command == 'auth-workbuddy': auth_workbuddy()
    elif args.command == 'auth-gemini':
        env = environment(); os.execvpe(env['AGY_BIN'], [env['AGY_BIN']], env)
    elif args.command == 'configure': configure()
    elif args.command in ('up', 'down', 'status'): services(args.command)
    elif args.command == 'serve': serve(args.component)
    elif args.command == 'connect':
        for action in ('create', 'verify'):
            run([sys.executable, ROOT / 'scripts/provision-xhs-team.py', action], env=environment())
    elif args.command == 'start':
        command = [sys.executable, ROOT / 'scripts/start-xhs.py', '--project', args.project, '--topic', args.topic]
        run(command + (['--image'] if args.image else []), env=environment())
    elif args.command == 'login-xhs':
        run([sys.executable, ROOT / 'integrations/xiaohongshu/service.py', 'login'], env=environment())
    else:
        env = environment()
        run([env['XHS_BROWSER_PYTHON'], ROOT / 'integrations/xhs-sources/login.py', '--platform', args.command[6:]], env=env)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit('xhs-ubuntu: ' + str(error)) from None
