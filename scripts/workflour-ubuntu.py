#!/usr/bin/env python3
"""Seven-role Ubuntu desktop deployment; never imports accounts or sends model prompts."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = Path.home() / '.workflour/ubuntu'
spec = importlib.util.spec_from_file_location('workflour_ubuntu_shared', ROOT / 'scripts/xhs-ubuntu.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
LOCK = shared.LOCK
PLAYWRIGHT = '1.65.1'
ROLES = ('wf-manager', 'wf-plan-lead', 'wf-plan-review', 'wf-code-main',
         'wf-code-review', 'wf-code-helper', 'wf-assistant')
MARKER = '# Managed by workflour ubuntu v1'
SERVICE = 'workflour-workbench.service'
OBSERVER = 'workflour-observer.service'
DAILY = 'workflour-daily.service'
TIMERS = ('workflour-observer.timer', 'workflour-daily.timer')
UNITS = (SERVICE, OBSERVER, DAILY, *TIMERS)
run = shared.run
private_json = shared.private_json
require_ubuntu = shared.require_ubuntu
workbench = shared.workbench


def settings():
    path = BASE / 'settings.json'
    return json.loads(path.read_text()) if path.exists() else {}


def absolute(value, label):
    path = Path(value).expanduser()
    if not path.is_absolute() or any(c in str(path) for c in '\n\r\0'):
        raise ValueError(label + ' must be an absolute path without control characters')
    return str(path)


def environment():
    shared.BASE = BASE
    env = shared.environment()
    saved = settings()
    defaults = {
        'AGY_BIN': ('agy_bin', env['AGY_BIN']),
        'WORKFLOUR_TEAM_MANIFEST': ('team_manifest', str(Path.home() / '.workflour/team-v2/deployment.json')),
        'WORKFLOUR_OBSIDIAN_VAULT': ('obsidian_vault', str(Path.home() / 'Documents/Obsidian/Workflour')),
        'OMB_DATA_DIR': ('omb_data_dir', str(Path.home() / '.openmausbot')),
    }
    for key, (field, default) in defaults.items():
        env[key] = absolute(os.environ.get(key, saved.get(field, default)), key)
    env['DSH_HOME'] = absolute(env['DSH_HOME'], 'DSH_HOME')
    env['WORKFLOUR_ROOT'] = str(ROOT)
    env['WORKFLOUR_BROWSER_PYTHON'] = str(ROOT / '.tools/browser/bin/python')
    # DSH subprocesses and AGY inherit this environment from the workbench.
    env.pop('XHS_BROWSER_PYTHON', None)
    return env


def save_environment(env, **extra):
    data = settings()
    data.update(version=1, dsh_home=env['DSH_HOME'], source_profile=env['WORKFLOUR_DSH_SOURCE_PROFILE'],
                agy_bin=env['AGY_BIN'], team_manifest=env['WORKFLOUR_TEAM_MANIFEST'],
                obsidian_vault=env['WORKFLOUR_OBSIDIAN_VAULT'], omb_data_dir=env['OMB_DATA_DIR'])
    data.update(extra)
    private_json(BASE / 'settings.json', data)


def private_runtime():
    overlay = ROOT / 'integrations/openmausbot/workbench'
    digest = hashlib.sha256()
    for name in ('source-lock.json', 'workbench.css', 'workbench.js'):
        digest.update(name.encode()); digest.update((overlay / name).read_bytes())
    return BASE / ('workbench-' + LOCK['openmausbot'] + '-' + digest.hexdigest()[:16])


def prepare_ui(env):
    output = private_runtime()
    run([sys.executable, ROOT / 'scripts/prepare-workbench.py', '--source',
         BASE / 'runtime/node_modules/openmausbot', '--out', output], env=env)
    save_environment(env, workbench_dir=str(output))


def install(args):
    if workbench() is not None:
        raise ValueError('Port 8799 is occupied; wait until idle and stop its owner before installing')
    BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
    BASE.chmod(0o700)
    if args.system_deps:
        run(['sudo', 'apt-get', 'update'])
        run(['sudo', 'apt-get', 'install', '-y', 'python3-venv', 'ruby', 'curl', 'git', 'xz-utils',
             'build-essential', 'fonts-noto-cjk', 'fontconfig', 'libsecret-1-0', 'dbus-x11'])
    env = environment()
    shared.BASE = BASE
    save_environment(env, node_bin=shared.ensure_node())
    env = environment()
    package = BASE / 'runtime/package.json'
    manifest = json.loads(package.read_text()) if package.exists() else {'private': True}
    manifest.setdefault('allowScripts', {}).update({
        '@deepseek-ai/dsh-subprocess-local@0.2.1-rc.2': True, 'koffi@3.1.1': True,
        'node-pty@1.2.0-beta.15': True, 'protobufjs@7.6.6': True})
    private_json(package, manifest)
    run(['npm', 'install', '--prefix', BASE / 'runtime', '--no-audit', '--no-fund',
         '@deepseek-ai/dsh@' + LOCK['dsh'], 'pnpm@' + LOCK['pnpm'],
         'openmausbot@' + LOCK['openmausbot']], env=env)
    shared.ensure_workbuddy(env)
    browser = Path(env['WORKFLOUR_BROWSER_PYTHON'])
    if not browser.exists():
        run([sys.executable, '-m', 'venv', browser.parent.parent])
    run([browser, '-m', 'pip', 'install', 'playwright==' + PLAYWRIGHT], env=env)
    command = [browser, '-m', 'playwright', 'install']
    if args.system_deps:
        command.append('--with-deps')
    run(command + ['chromium'], env=env)
    if args.system_deps and not shutil.which('google-chrome', path=env['PATH']):
        # Role browser instructions use channel='chrome'; do not replace an
        # existing Chrome installation with Playwright's global installation.
        run([browser, '-m', 'playwright', 'install', 'chrome'], env=env)
    prepare_ui(env)
    print('工具已安装；账号与模型尚未验证。下一步 auth-workbuddy，安装官方 Antigravity CLI 后 auth-gemini。')


def auth_workbuddy():
    env = environment()
    save_environment(env)
    shared.ensure_workbuddy(env)
    print('在 Ubuntu 浏览器打开 http://127.0.0.1:3080，登录自己的 WorkBuddy 账号并保存模型/账号池；完成后 Ctrl-C。', flush=True)
    os.execvpe(env['DSH_BIN'], [env['DSH_BIN'], '--profile', env['WORKFLOUR_DSH_SOURCE_PROFILE'],
                              '--host', '127.0.0.1', '--port', '3080'], env)


def configure():
    if workbench() is not None:
        raise ValueError('Workbench is running; wait until idle, then down before configure')
    env = environment()
    # Fail before generating roles when either runtime or pool source is absent.
    run([env['AGY_BIN'], '--version'], env=env)
    run(['ruby', ROOT / 'scripts/workbuddy-pool-sync.rb', '--profile', 'omb-wf-manager', '--check'], env=env)
    save_environment(env)
    prepare_ui(env)
    run([sys.executable, ROOT / 'scripts/init-workflour-vault.py', '--vault', env['WORKFLOUR_OBSIDIAN_VAULT']], env=env)
    for role in ROLES:
        run(['bash', ROOT / 'integrations/openmausbot/setup.sh', '--only', role], env=env)
    run([sys.executable, ROOT / 'scripts/provision-team.py', 'prepare'], env=env)
    print('七角色配置完成。执行 up，再 connect；尚未创建业务任务或调用模型。')


def connect():
    env = environment()
    for action in ('create', 'activate', 'verify'):
        run([sys.executable, ROOT / 'scripts/provision-team.py', action], env=env)


def valid_manifest(path):
    """Reuse provisioning's readonly validation; never create IDs in doctor."""
    spec = importlib.util.spec_from_file_location('ubuntu_team_readback', ROOT / 'scripts/provision-team.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        module.manifest(path, create=False)
        return True
    except (ValueError, OSError, module.control.ControlError):
        return False


def unit_text(name, root=ROOT, python=sys.executable):
    if name not in UNITS:
        raise ValueError('Unknown managed unit')
    if any(c in str(root) + str(python) for c in '\n\r\0'):
        raise ValueError('Control characters are not supported in service paths')
    def quote(value, command=False):
        value = str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
        if command:
            value = value.replace('$', '$$')
        return '"' + value + '"'
    head = MARKER + '\n# Checkout: ' + str(root) + '\n[Unit]\nDescription=Workflour ' + name + '\n'
    if name in TIMERS:
        schedule = ('OnStartupSec=20s\nOnUnitInactiveSec=20s\nAccuracySec=1s\n' if name == TIMERS[0]
                    else 'OnCalendar=*-*-* 13:00:00 Asia/Shanghai\nPersistent=true\nAccuracySec=1s\n')
        return head + '[Timer]\n' + schedule + 'Unit=' + name.replace('.timer', '.service') + '\n[Install]\nWantedBy=timers.target\n'
    action = {SERVICE: 'serve', OBSERVER: 'observe', DAILY: 'daily'}[name]
    command = ' '.join((quote(python, True), quote(root / 'scripts/workflour-ubuntu.py', True), action))
    body = (head + 'After=network-online.target\n[Service]\nType=' + ('simple' if name == SERVICE else 'oneshot') + '\n'
            # WorkingDirectory is a single raw path, unlike ExecStart's words.
            'WorkingDirectory=' + str(root).replace('%', '%%') + '\nExecStart=' + command + '\nUMask=0077\n')
    if name == SERVICE:
        return body + 'Restart=on-failure\nRestartSec=10\n[Install]\nWantedBy=default.target\n'
    return body + 'TimeoutStartSec=' + ('600' if name == DAILY else '120') + '\n'


def owned_units(folder, must_exist=False):
    for name in UNITS:
        path = folder / name
        if path.is_symlink() or (path.exists() and not path.read_text().startswith(MARKER + '\n# Checkout: ' + str(ROOT) + '\n')):
            raise ValueError('Refuse service not owned by this checkout: ' + name)
        if must_exist and not path.exists():
            raise ValueError('Missing owned service; inspect the process you started: ' + name)


def services(action):
    folder = Path.home() / '.config/systemd/user'
    if action == 'up':
        if workbench() is not None:
            raise ValueError('Port 8799 already serves a workbench (possibly XHS); do not start another')
        owned_units(folder)
        folder.mkdir(parents=True, exist_ok=True)
        for name in UNITS:
            (folder / name).write_text(unit_text(name))
        run(['systemctl', '--user', 'daemon-reload'])
        # Enabling timers does not explicitly invoke their services. Persistent
        # daily timers may catch up a missed scheduled check after a later boot.
        run(['systemctl', '--user', 'enable', '--now', SERVICE, *TIMERS])
    elif action == 'down':
        bots = workbench()
        if bots and any(b.get('busy') or any(t.get('busy') for t in b.get('tasks', [])) for b in bots):
            raise ValueError('A Bot is busy; refusing to interrupt running work')
        owned_units(folder, must_exist=True)
        run(['systemctl', '--user', 'disable', '--now', *TIMERS, SERVICE])
        print('工作台与定时器已停止；已开始的只读观察或签到检查允许自行结束。')
    else:
        run(['systemctl', '--user', '--no-pager', 'status', SERVICE, *TIMERS])


def serve():
    env = environment()
    path = settings().get('workbench_dir')
    if not path or Path(path) != private_runtime():
        raise ValueError('Private UI missing or changed; run configure while workbench is stopped')
    run([sys.executable, ROOT / 'scripts/prepare-workbench.py', '--source',
         BASE / 'runtime/node_modules/openmausbot', '--out', path, '--verify'], env=env)
    node = shutil.which('node', path=env['PATH'])
    if not node:
        raise ValueError('Node runtime missing; run install')
    os.execvpe(node, [node, str(Path(path) / 'cli.js'), 'serve'], env)


def daily():
    env = environment()
    results = {}
    for label, script, flag in (
        ('checkin', 'integrations/openmausbot/workbuddy/checkin.mjs', '--daily-checkin'),
        ('fallback_restore_check', 'integrations/openmausbot/model-fallback/status.mjs', '--daily-check')):
        try:
            result = subprocess.run(['node', str(ROOT / script), flag], env=env, timeout=270)
            results[label] = {'exit_code': result.returncode}
        except (OSError, subprocess.TimeoutExpired):
            results[label] = {'exit_code': None, 'error': 'unavailable_or_timed_out'}
    print(json.dumps({'daily': results, 'timezone': 'Asia/Shanghai', 'model_prompts_sent': False}))
    return 0 if all(r['exit_code'] == 0 for r in results.values()) else 1


def doctor(offline=False):
    env = environment()
    checks = {}
    browser = env['WORKFLOUR_BROWSER_PYTHON']
    commands = {'dsh': [env['DSH_BIN'], '--version'], 'agy': [env['AGY_BIN'], '--version'],
                'node': ['node', '--version'], 'ruby': ['ruby', '--version'],
                'playwright': [browser, '-c', 'from importlib.metadata import version; assert version("playwright")=="' + PLAYWRIGHT + '"'],
                'browser': [browser, '-c', 'from playwright.sync_api import sync_playwright; '
                            'p=sync_playwright().start(); b=p.chromium.launch(channel="chrome"); b.close(); p.stop()'],
                'workbuddy_saved_configuration': ['ruby', str(ROOT / 'scripts/workbuddy-pool-sync.rb'),
                                                   '--profile', 'omb-wf-manager', '--check']}
    ui = settings().get('workbench_dir')
    if ui:
        commands['private_workbench'] = [sys.executable, str(ROOT / 'scripts/prepare-workbench.py'), '--verify',
                                        '--source', str(BASE / 'runtime/node_modules/openmausbot'), '--out', ui]
    else:
        checks['private_workbench'] = False
    for name, command in commands.items():
        try:
            checks[name] = subprocess.run(command, env=env, capture_output=True, timeout=30).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            checks[name] = False
    checks['team_manifest'] = valid_manifest(env['WORKFLOUR_TEAM_MANIFEST'])
    checks['vault_homepage'] = (Path(env['WORKFLOUR_OBSIDIAN_VAULT']) / '首页.md').is_file()
    if not offline:
        checks['workbench_running'] = workbench() is not None
    print(json.dumps({'checks': checks, 'ready_for_target_login_verification': all(checks.values()),
                      'account_authentication': 'not_probed', 'model_prompts_sent': False,
                      'note': '工具/配置检查不等于订阅、真实模型、图片能力或七角色业务验收；另需在目标机验证。'},
                     ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('install'); p.add_argument('--system-deps', action='store_true')
    p = sub.add_parser('doctor'); p.add_argument('--offline', action='store_true')
    for name in ('auth-workbuddy', 'auth-gemini', 'configure', 'connect', 'instructions', 'up', 'down', 'status', 'serve', 'observe', 'daily'):
        sub.add_parser(name)
    args = parser.parse_args()
    require_ubuntu()
    os.umask(0o077)
    if args.command == 'install': install(args)
    elif args.command == 'auth-workbuddy': auth_workbuddy()
    elif args.command == 'auth-gemini':
        env = environment(); save_environment(env); os.execvpe(env['AGY_BIN'], [env['AGY_BIN']], env)
    elif args.command == 'configure': configure()
    elif args.command == 'connect': connect()
    elif args.command == 'instructions': run([sys.executable, ROOT / 'scripts/provision-team.py', 'instructions'], env=environment())
    elif args.command in ('up', 'down', 'status'): services(args.command)
    elif args.command == 'serve': serve()
    elif args.command == 'observe': run([sys.executable, ROOT / 'scripts/workflow-observer.py', 'sync'], env=environment())
    elif args.command == 'daily': return daily()
    else: return doctor(args.offline)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit('workflour-ubuntu: ' + str(error)) from None
