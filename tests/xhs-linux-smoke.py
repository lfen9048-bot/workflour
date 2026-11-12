#!/usr/bin/env python3
"""Real Linux runtime/render checks with synthetic content and no account login."""
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
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def check_server(command, url, env):
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(command, env=env, cwd=ROOT, stdout=log, stderr=log, start_new_session=True)
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    log.seek(0)
                    raise RuntimeError('Runtime exited: ' + log.read().decode(errors='replace')[-3000:])
                try:
                    with opener.open(url, timeout=2) as response:
                        assert response.status == 200
                        return {'health': 'passed', 'status': response.status}
                except OSError:
                    time.sleep(0.5)
            log.seek(0)
            raise RuntimeError('Runtime health timeout: ' + log.read().decode(errors='replace')[-5000:])
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=15)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('ubuntu_smoke', ROOT / 'scripts/xhs-ubuntu.py')
    ubuntu = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ubuntu)
    env = ubuntu.environment()
    # Installing then reopening auth must not mistake a caret range for the
    # pinned plugin version or reinstall a different plugin behind the user.
    ubuntu.ensure_workbuddy(env)
    results = {'platform': sys.platform, 'account_login': False, 'model_prompts_sent': False}
    for label, command, url in (
        ('workbench', [str(ubuntu.BASE / 'runtime/node_modules/.bin/openmausbot'), 'serve'],
         'http://127.0.0.1:8799/api/bots?messages=0'),
        ('collector', [sys.executable, str(ROOT / 'integrations/xiaohongshu/service.py'), 'run'],
         'http://127.0.0.1:18060/health')):
        print('Checking real runtime: ' + label, flush=True)
        results[label] = check_server(command, url, env)
    project = args.output / 'sample'
    project.mkdir()
    (project / 'cards.json').write_text(json.dumps({'series': 'Ubuntu 接入验证', 'as_of': '本地合成样本',
        'cards': [{'title': '小红书三 Agent 工作流', 'bullets': ['采集保存原始来源', '思考负责简短提纲', '写作交付图文草稿'],
                   'note': '此图仅用于验证中文字体与排版，不包含新闻事实。'},
                  {'title': '图文交付检查', 'body': '正文、来源与实际 PNG 均保存在独立内容项目。',
                   'source_label': '合成测试 · 未调用模型'}]}, ensure_ascii=False))
    subprocess.run([env['XHS_BROWSER_PYTHON'], str(ROOT / 'scripts/render-xhs-cards.py'),
                    '--project', str(project)], env=env, check=True)
    manifest = json.loads((project / 'output/render-manifest.json').read_text())
    for row in manifest['images']:
        data = (project / row['path']).read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n'
        assert struct.unpack('>II', data[16:24]) == (1080, 1440)
    results['render'] = {'images': 2, 'width': 1080, 'height': 1440, 'overflow': False}
    for component, name in zip(('omb', 'xhs'), ubuntu.UNITS):
        unit = args.output / name
        unit.write_text(ubuntu.unit_text(component))
        subprocess.run(['systemd-analyze', 'verify', str(unit)], check=True)
    results['systemd_units'] = 'syntax_verified'
    (args.output / 'verification.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results))


if __name__ == '__main__':
    main()
