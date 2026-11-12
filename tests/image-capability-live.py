#!/usr/bin/env python3
"""Opt-in real read_image probe; one fresh isolated DSH session, no Bot mutation.

Generates a random PNG with no text metadata. Expected digits are never in the
prompt, filename or readable fixture text. Only the image tool is permitted.
Evidence is append-only; this runner does not register a capability by itself.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import secrets
import struct
import sys
import tempfile
import time
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('skill_probe', ROOT / 'tests/skills-specialization-live.py')
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)


def png_digits(digits):
    glyphs = ('111101101101111', '010110010010111', '111001111100111',
              '111001111001111', '101101111001001', '111100111001111',
              '111100111101111', '111001001001001', '111101111101111', '111101111001111')
    scale, margin = 20, 40
    width, height = len(digits) * 4 * scale + 2 * margin, 5 * scale + 2 * margin
    rows = [bytearray([255] * (width * 3)) for _ in range(height)]
    for offset, digit in enumerate(digits):
        glyph = glyphs[int(digit)]
        for y in range(5):
            for x in range(3):
                if glyph[y * 3 + x] == '1':
                    for yy in range(margin + y * scale, margin + (y + 1) * scale):
                        start = (margin + (offset * 4 + x) * scale) * 3
                        rows[yy][start:start + scale * 3] = bytes([15, 25, 35]) * scale
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b''.join(b'\0' + row for row in rows))) + chunk(b'IEND', b''))


class ImageProcess(live.EvidenceProcess):
    def allow_permission(self, params):
        tool = params.get('toolCall') or {}
        paths = live.tool_file_paths(tool, self.fixture)
        permitted = (params.get('sessionId') in (None, self.session)
                     and live.tool_operation(tool) == 'read_image'
                     and paths == [self.fixture / 'input.png'])
        return permitted, 'only_generated_image_allowed' if permitted else 'outside_probe_scope'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not args.output.is_absolute() or args.output.exists():
        parser.error('output must be a new absolute path')
    report = {'schema_version': 1, 'started_at': datetime.now(timezone.utc).isoformat(),
              'public_answer': '', 'tools': [], 'permissions': [], 'config_confirmations': [],
              'usage_events': [], 'status': 'starting', 'role': 'wf-assistant'}
    source_profile = os.environ.get('WORKFLOUR_DSH_SOURCE_PROFILE', 'desktop' if sys.platform == 'darwin' else 'web')
    plugin_package = Path(os.environ.get('DSH_HOME', str(Path.home() / '.dsh'))) / 'profiles' / source_profile / 'node_modules/dsh-connect-workbuddy/package.json'
    report['workbuddy_version'] = json.loads(plugin_package.read_text())['version']
    proc = None
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='wf-image-probe-') as folder:
        fixture = Path(folder).resolve()
        expected = ''.join(str(secrets.randbelow(10)) for _ in range(8))
        image = png_digits(expected)
        (fixture / 'input.png').write_bytes(image)
        report['image_sha256'] = hashlib.sha256(image).hexdigest()
        report['expected_sha256'] = hashlib.sha256(expected.encode()).hexdigest()
        report['nonce_in_prompt'] = False
        try:
            proc = ImageProcess('wf-assistant', fixture, [], report)
            proc.call('initialize', {'protocolVersion': 1, 'clientCapabilities': {},
                'clientInfo': {'name': 'workflour-image-probe', 'version': '1'}}, 60)
            new = proc.call('session/new', {'cwd': str(fixture), 'mcpServers': []}, 45)
            proc.session = new['sessionId']
            report['session_id'] = proc.session
            report['initial_config'] = live.selection(new)
            chosen = proc.call('session/set_config_option', {'sessionId': proc.session,
                'configId': 'reasoning_effort', 'value': 'low'}, 30)
            report['effort_ack'] = live.selection(chosen)
            print(json.dumps({'stage': 'image_prompt', 'session': proc.session}), flush=True)
            completed = proc.call('session/prompt', {'sessionId': proc.session, 'prompt': [{
                'type': 'text', 'text': '这是已授权的隔离图片能力验证。仅调用一次 read_image 读取 '
                + str(fixture / 'input.png') + '，识别图片内全部八位数字，只回复八位数字。'
                '不要调用其他工具，不加载技能，不读其他文件，不改任何文件或配置，不委派。'
                '如果实际读图失败，请如实说明，不能猜测。'}]}, 240)
            report['stop_reason'] = completed.get('stopReason')
            state = json.loads((Path.home() / '.dsh/workflour-fallback' / (proc.session + '.json')).read_text())
            report['fallback'] = live.fallback_metadata(proc.session)
            billing = state.get('billing') or {}
            report['billing'] = {k: billing[k] for k in ('nativeProvider', 'region', 'model', 'reason', 'cost', 'tier') if k in billing}
            # Internal provider IDs include account IDs; keep only the native provider.
            for route in (report['fallback'] or {}).values():
                if isinstance(route, dict) and str(route.get('provider', '')).startswith('workflour-wb-'):
                    route['provider'] = billing.get('nativeProvider') or 'workbuddy-account-adapter'
            answer = '\n'.join(line for line in report['public_answer'].splitlines()
                               if not line.startswith('【系统·模型状态】')).strip()
            report['model_answer'] = answer
            report['exact_match'] = answer == expected
            reads = [t for t in report['tools'] if t.get('title') == 'read_image']
            completed_ids = {t.get('id') for t in report['tools'] if t.get('status') == 'completed'}
            report['image_tool_requested'] = bool(reads)
            report['image_tool_completed'] = any(t.get('id') in completed_ids for t in reads)
            calls = [t for t in report['tools'] if t.get('event') == 'tool_call']
            report['actual_tool_scope'] = 'one_read_image' if len(calls) == 1 and calls[0].get('title') == 'read_image' else 'unexpected_tools'
            report['passed'] = (report['exact_match'] and re.fullmatch(r'[0-9]{8}', answer) is not None
                                and report['actual_tool_scope'] == 'one_read_image'
                                and report['image_tool_completed'] and bool(state.get('confirmed_at'))
                                and billing.get('nativeProvider') == 'workbuddy-global'
                                and state.get('active', {}).get('model') == 'deepseek-v4.1-flash-sg'
                                and completed.get('stopReason') == 'end_turn')
            report['status'] = 'passed' if report['passed'] else 'failed'
        except Exception as error:
            report['status'], report['error_type'] = 'failed', type(error).__name__
        finally:
            if proc:
                if proc.session and proc.proc.poll() is None:
                    try:
                        proc.call('session/close', {'sessionId': proc.session}, 10)
                    except Exception:
                        pass
                proc.close_stdin()
                proc.terminate()
                report['protocol_error_count'] = len(proc.protocol_errors)
            report['seconds'] = round(time.monotonic() - started, 2)
            report['finished_at'] = datetime.now(timezone.utc).isoformat()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x') as file:
                file.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            print(json.dumps({'status': report['status'], 'answer': report['public_answer'],
                              'billing': report.get('billing'), 'output': str(args.output)}, ensure_ascii=False))
    return 0 if report.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
