#!/usr/bin/env python3
"""Linux-only real UI/browser and isolated seven-profile checks; no account/model login."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def check_server(command, env, payloads):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log, start_new_session=True)
        try:
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    log.seek(0); raise RuntimeError('Isolated workbench exited: ' + log.read().decode(errors='replace')[-3000:])
                try:
                    with opener.open('http://127.0.0.1:8799/api/bots?messages=0', timeout=2) as response:
                        assert response.status == 200
                    with opener.open('http://127.0.0.1:8799', timeout=2) as response:
                        html = response.read().decode()
                        assert '/workflour-workbench.js' in html and '/workflour-workbench.css' in html
                    contract = creation_contract(opener, payloads)
                    return {'health': 'passed', 'private_overlay': True, 'native_create_contract': contract}
                except OSError:
                    time.sleep(0.5)
            raise RuntimeError('Isolated workbench health timeout')
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM); process.wait(timeout=15)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)


def isolated_profiles(ubuntu, env, folder):
    dsh = folder / 'dsh'; source = dsh / 'profiles/web'; source.mkdir(parents=True)
    installed = Path(env['DSH_HOME']) / 'profiles' / env['WORKFLOUR_DSH_SOURCE_PROFILE'] / 'node_modules'
    assert installed.is_dir(), 'Pinned WorkBuddy package has not been installed'
    (source / 'node_modules').symlink_to(installed, target_is_directory=True)
    # No accounts, tokens or cookies: only a disabled pool and model IDs. The
    # real setup scripts must accept a clean Web source without legacy profiles.
    config = {'regions': {r: {'enabled': True, 'enabledModelIds': [], 'imageModelIds': [],
                             'pool': {'enabled': False, 'memberAccountIds': [], 'orderAccountIds': []}}
                          for r in ('cn', 'global')}}
    (source / 'cordis.patch.yml').write_text(json.dumps([{'id': 'dsh-connect-workbuddy', 'config': config}]))
    private = {**env, 'DSH_HOME': str(dsh), 'WORKFLOUR_DSH_SOURCE_PROFILE': 'web',
               'OMB_DATA_DIR': str(folder / 'omb'), 'WORKFLOUR_TEAM_MANIFEST': str(folder / 'team.json'),
               'WORKFLOUR_OBSIDIAN_VAULT': str(folder / 'vault')}
    # setup.sh expects a top-level YAML entry, not compact JSON, when extracting
    # the plugin block. Ruby uses its native safe serializer with no PyYAML dep.
    subprocess.run(['ruby', '-ryaml', '-rjson', '-e', 'p=ARGV[0];File.write(p,YAML.dump(JSON.parse(File.read(p))))',
                    str(source / 'cordis.patch.yml')], check=True)
    for _ in range(2):
        for role in ubuntu.ROLES:
            subprocess.run(['bash', str(ROOT / 'integrations/openmausbot/setup.sh'), '--only', role], env=private, check=True)
    actual = json.loads((folder / 'omb/config.json').read_text())['instances']
    expected = {'agy-gemini', *(f'omb-{r}' for r in ubuntu.ROLES if r != 'wf-code-main')}
    assert set(actual) == expected
    for role in ubuntu.ROLES:
        if role == 'wf-code-main': continue
        profile = dsh / 'profiles' / ('omb-' + role)
        assert (profile / 'node_modules').resolve() == installed.resolve()
        patch = (profile / 'cordis.patch.yml').read_text()
        assert '/Users/a1/' not in patch and str(ROOT) in patch
    subprocess.run([sys.executable, str(ROOT / 'scripts/provision-team.py'), 'prepare'], env=private, check=True)
    before = (folder / 'team.json').read_bytes()
    subprocess.run([sys.executable, str(ROOT / 'scripts/provision-team.py'), 'prepare'], env=private, check=True)
    assert (folder / 'team.json').read_bytes() == before
    manifest = json.loads(before)
    assert len(manifest['roles']) == 7 and len({r['botId'] for r in manifest['roles']}) == 7
    payloads = creation_payloads(private, folder / 'team.json')
    return ({'isolated_profiles': 6, 'instances': 7, 'repeat_setup': 'passed', 'manifest_stable': True,
             'real_bots_created': False, 'account_config_copied': False}, payloads)


def creation_payloads(env, manifest):
    """Capture actual provisioning payloads without native HTTP mutation.

    The in-memory transport does NOT advertise or validate real model access.
    No native HTTP mutation or model request is made by this contract check.
    """
    team = load('linux_team_schema', ROOT / 'scripts/provision-team.py')
    class MemoryClient:
        def __init__(self): self.bots, self.payloads = {}, []
        def call(self, method, path, body=None):
            if method == 'GET' and path.startswith('/api/bots'):
                return {'bots': list(self.bots.values())}
            if method == 'GET' and path == '/api/instances': return {'instances': []}
            if method == 'POST' and path == '/api/bots':
                self.payloads.append(body['settings'])
                bot = {'id': body['id'], 'memoryEnabled': True, **body['settings']}
                self.bots[bot['id']] = bot
                return {'bot': bot}
            if method == 'PATCH' and path.startswith('/api/bots/'):
                bot = self.bots[path.split('/')[-1]]; bot.update(body); return {'bot': bot}
            raise AssertionError('Unexpected fake transport operation: ' + method + ' ' + path)
    client = MemoryClient()
    with patch.dict(os.environ, env), patch.object(team.control, 'selection',
            side_effect=lambda instances, instance, model, effort: {'instanceId': instance, 'model': model, 'variant': effort}):
        result = team.provision('create', path=manifest, client=client)
    assert result['ok'] and len(client.payloads) == 7
    return client.payloads


def creation_contract(opener, payloads):
    """Real validation-only POST: native settings parsing must pass, then a
    deliberately absent instance stops execution before store.createBot.

    This is an API rejection contract, not authenticated model availability.
    Order checked against pinned routes/bots-create.js and index.js. No live
    user server is ever used: check_server starts/owns an empty data directory.
    """
    url = 'http://127.0.0.1:8799/api/bots'
    def ids():
        with opener.open(url + '?messages=0', timeout=5) as response:
            return sorted(row['id'] for row in json.load(response)['bots'])
    before = ids()
    expected = 'model instance "__workflour_ci_missing__" is unavailable'
    errors = []
    try:
        for settings in payloads:
            body = {'id': str(uuid.uuid4()), 'useDefaults': False, 'settings': settings,
                    'requireAvailableModel': True,
                    'modelSelection': {'instanceId': '__workflour_ci_missing__', 'model': '__no_model__'}}
            request = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST',
                                             headers={'Content-Type': 'application/json'})
            try:
                with opener.open(request, timeout=10) as response:
                    raise AssertionError('Validation-only creation unexpectedly succeeded: ' + str(response.status))
            except urllib.error.HTTPError as error:
                answer = json.load(error)
                assert error.code == 400 and answer.get('error') == expected, (error.code, answer)
                errors.append({'status': error.code, 'error': answer['error']})
    finally:
        assert ids() == before, 'Validation-only requests changed native Bot IDs'
    return {'validation_only_posts': len(errors), 'all_rejected_after_settings_parsing': True,
            'expected_error': expected, 'native_bot_ids_unchanged': True, 'model_requests': 0}


def render_browser(ubuntu, env, output):
    script = r'''
from playwright.sync_api import sync_playwright
from pathlib import Path
import sys
out = Path(sys.argv[1])
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome')
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    page = context.new_page()
    page.set_content('<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><style>body{font:24px sans-serif;max-width:50rem;margin:24px}button{font:inherit}</style><h1>Workflour 开发团队</h1><p>七角色 Ubuntu 浏览器验证</p><button onclick="document.querySelector(\'output\').textContent=\'操作成功\'">检查交互</button><output></output></html>')
    page.get_by_role('button', name='检查交互').click()
    assert page.locator('output').inner_text() == '操作成功'
    page.screenshot(path=str(out/'desktop.png'))
    page.set_viewport_size({'width':375,'height':812})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(out/'mobile.png'))
    context.close(); browser.close()
'''
    subprocess.run([env['WORKFLOUR_BROWSER_PYTHON'], '-c', script, str(output)], env=env, check=True)
    for name, size in [('desktop.png', (1280, 800)), ('mobile.png', (375, 812))]:
        data = (output / name).read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', data[16:24]) == size
    return {'chrome_channel': 'chrome', 'screenshots': ['desktop.png', 'mobile.png'],
            'button_interaction': 'passed', 'narrow_overflow': False, 'visual_judgment': 'not_claimed'}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    ubuntu = load('dev_ubuntu_smoke', ROOT / 'scripts/workflour-ubuntu.py')
    ubuntu.require_ubuntu()
    args.output.mkdir(parents=True, exist_ok=False)
    env = ubuntu.environment()
    if ubuntu.workbench() is not None: raise ValueError('Port 8799 occupied; smoke will not stop another service')
    results = {'platform': sys.platform, 'account_login': False, 'model_prompts_sent': False,
               'systemd_user_start': 'not_tested', 'agy_subscription': 'not_tested'}
    with tempfile.TemporaryDirectory(prefix='workflour Linux isolated ') as temp:
        folder = Path(temp)
        isolated = {**env, 'OMB_DATA_DIR': str(folder / 'runtime-omb')}
        ui = ubuntu.settings()['workbench_dir']
        results['profiles'], payloads = isolated_profiles(ubuntu, env, folder)
        results['workbench'] = check_server(['node', str(Path(ui) / 'cli.js'), 'serve'], isolated, payloads)
    results['browser'] = render_browser(ubuntu, env, args.output)
    for name in ubuntu.UNITS: (args.output / name).write_text(ubuntu.unit_text(name))
    subprocess.run(['systemd-analyze', 'verify', *[str(args.output / name) for name in ubuntu.UNITS]], check=True)
    # Exercise native path parsing, not only a Python string assertion. Python
    # accepts a nonexistent script argument, so verify checks unit path syntax
    # without needing another installed checkout or touching its services.
    unusual = args.output / 'path-syntax'; unusual.mkdir()
    weird_root = Path('/tmp/workflour space/%r/$D/"quoted')
    for name in ubuntu.UNITS: (unusual / name).write_text(ubuntu.unit_text(name, weird_root))
    subprocess.run(['systemd-analyze', 'verify', *[str(unusual / name) for name in ubuntu.UNITS]], check=True)
    subprocess.run(['systemd-analyze', 'calendar', '*-*-* 13:00:00 Asia/Shanghai'], check=True)
    results['systemd_syntax'] = {'normal_paths': 'verified', 'spaces_quotes_percent_dollar': 'verified'}
    (args.output / 'verification.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(results, ensure_ascii=False))


if __name__ == '__main__': main()
