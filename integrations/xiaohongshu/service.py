#!/usr/bin/env python3
"""Pinned local XHS MCP runtime; never publishes or copies browser cookies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import secrets
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
BASE = Path(os.environ.get('WORKFLOUR_XHS_HOME', Path.home() / '.workflour/xiaohongshu')).expanduser().resolve()
LABEL = 'local.workflour.xiaohongshu'
HOST = '127.0.0.1'
PORT = 18060


def prepare():
    BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
    BASE.chmod(0o700)
    for name in ('bin', 'logs', 'raw'):
        (BASE / name).mkdir(mode=0o700, exist_ok=True)
    token = BASE / 'auth-token'
    if not token.exists():
        fd = os.open(token, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write(secrets.token_urlsafe(32))
    token.chmod(0o600)


def current_binary(kind='server'):
    if kind not in ('server', 'login'):
        raise ValueError('Unknown pinned binary kind')
    lock = json.loads((HERE / 'release-lock.json').read_text())
    machine = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(platform.machine(), platform.machine())
    target = platform.system().lower() + '-' + machine
    if target not in lock['assets']:
        raise ValueError(f'Pinned upstream release does not support {target}; no unverified replacement installed')
    asset = lock['assets'][target][kind]
    return lock, target, asset, BASE / 'bin' / asset['name']


def install_binary(kind='server'):
    prepare()
    lock, target, asset, destination = current_binary(kind)
    valid = destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() == asset['sha256']
    if not valid:
        url = lock['repository'] + '/releases/download/' + lock['version'] + '/' + asset['name']
        request = urllib.request.Request(url, headers={'User-Agent': 'Workflour-XHS-Installer/1'})
        temporary = destination.with_suffix('.download')
        try:
            with urllib.request.urlopen(request, timeout=90) as response, temporary.open('wb') as handle:
                while chunk := response.read(1024 * 1024):
                    handle.write(chunk)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != asset['sha256']:
                raise ValueError('Downloaded binary SHA256 mismatch; it was not executed')
            temporary.chmod(0o700)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    destination.chmod(0o700)
    record = {'version': lock['version'], 'platform': target, 'sha256': asset['sha256'], 'binary': str(destination)}
    return record


def install():
    record = install_binary()
    (BASE / 'installation.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'installed': True, **record}))


def login():
    """Open only the pinned visible login browser and wait for user completion."""
    if platform.system() == 'Linux' and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        raise ValueError('Visible login needs a Linux desktop DISPLAY/WAYLAND_DISPLAY; use login-qr when headless')
    record = install_binary('login')
    env = os.environ.copy()
    env['COOKIES_PATH'] = str(BASE / 'cookies.json')
    env.pop('AUTH_TOKEN', None)  # The login binary does not need the MCP token.
    fd, log_path = tempfile.mkstemp(prefix='login-', suffix='.log', dir=BASE / 'logs')
    print(json.dumps({'status': 'waiting_for_manual_login', 'visible_browser': True,
                      'message': 'Complete login in the opened browser; this command waits for it to finish.'}), flush=True)
    with os.fdopen(fd, 'wb') as log:
        # Upstream writes progress details to stderr. Keep them in the private
        # log rather than accidentally returning identity/session data to chat.
        process = subprocess.run([record['binary']], cwd=BASE, env=env,
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                 umask=0o077)
    if process.returncode:
        raise ValueError('Visible login process failed; inspect its private log: ' + str(log_path))
    # A successful process exit alone is not a verified platform login.
    print(json.dumps({'status': 'login_window_closed', 'verification_required': True,
                      'verify_command': 'python3 scripts/xhs-collect.py status'}))


def run_server():
    prepare()
    _, _, asset, binary = current_binary()
    if not binary.exists() or hashlib.sha256(binary.read_bytes()).hexdigest() != asset['sha256']:
        raise ValueError('Run service.py install first; pinned binary is missing or changed')
    os.umask(0o077)
    os.chdir(BASE)
    env = os.environ.copy()
    env['COOKIES_PATH'] = str(BASE / 'cookies.json')
    env['AUTH_TOKEN'] = (BASE / 'auth-token').read_text().strip()
    os.execve(binary, [str(binary), '-port', f'{HOST}:{PORT}', '-headless=true'], env)


def health():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f'http://{HOST}:{PORT}/health', timeout=3) as response:
            value = json.load(response)
        return {'running': True, 'bind': f'{HOST}:{PORT}', 'health': value.get('status', value.get('success'))}
    except (OSError, ValueError):
        return {'running': False, 'bind': f'{HOST}:{PORT}'}


def up():
    prepare()
    if platform.system() != 'Darwin':
        raise ValueError('For Linux run service.py run under your user service manager; see README')
    loaded = subprocess.run(['launchctl', 'print', f'gui/{os.getuid()}/{LABEL}'], capture_output=True)
    if loaded.returncode == 0:
        print(json.dumps({'started': False, 'already_loaded': True, 'label': LABEL, **health()}))
        return
    if health()['running']:
        raise ValueError('Port already answers; refusing to replace an unknown running service')
    path = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {'Label': LABEL, 'ProgramArguments': [sys.executable, str(HERE / 'service.py'), 'run'],
            'WorkingDirectory': str(BASE), 'RunAtLoad': True, 'KeepAlive': {'SuccessfulExit': False},
            'ThrottleInterval': 30, 'StandardOutPath': str(BASE / 'logs/stdout.log'),
            'StandardErrorPath': str(BASE / 'logs/stderr.log'), 'Umask': 0o077,
            'EnvironmentVariables': {'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin',
                                     'WORKFLOUR_XHS_HOME': str(BASE)}}
    path.write_bytes(plistlib.dumps(data))
    path.chmod(0o600)
    result = subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(path)], capture_output=True)
    if result.returncode:
        raise ValueError('launchd bootstrap failed; inspect the service label before retrying')
    print(json.dumps({'started': True, 'label': LABEL, 'bind': f'{HOST}:{PORT}', 'logs': str(BASE / 'logs')}))


def down():
    if platform.system() != 'Darwin':
        raise ValueError('Stop the specific Linux user service or foreground process you started')
    result = subprocess.run(['launchctl', 'bootout', f'gui/{os.getuid()}/{LABEL}'], capture_output=True)
    path = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')
    if path.exists() and plistlib.loads(path.read_bytes()).get('Label') == LABEL:
        path.unlink()
    print(json.dumps({'unloaded': result.returncode == 0, 'label': LABEL}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'login', 'run', 'up', 'down', 'status'])
    args = parser.parse_args()
    {'install': install, 'login': login, 'run': run_server, 'up': up, 'down': down,
     'status': lambda: print(json.dumps(health()))}[args.action]()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, urllib.error.URLError) as error:
        # A small installer error is useful; never display token-bearing requests.
        print(json.dumps({'ok': False, 'error': type(error).__name__, 'message': str(error)[:180]}), file=sys.stderr)
        raise SystemExit(2)
