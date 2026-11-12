import importlib.util
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('configure_xhs_delivery', ROOT / 'scripts/configure-xhs-delivery.py')
CONFIG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONFIG)

STUB = '''import json, os, subprocess, sys, time
from pathlib import Path

def prepare(project, image_prompt_file=None, existing_image_evidence=None):
    control = json.loads((project / 'control.json').read_text())
    print('helper log belongs on stderr', flush=True)
    (project / 'started').write_text(str(os.getpid()))
    if control.get('child'):
        code = "import os,time;from pathlib import Path;Path(" + repr(str(project / 'child-started')) + ").write_text(str(os.getpid()));time.sleep(30)"
        subprocess.Popen([sys.executable, '-c', code])
    time.sleep(control.get('delay', 0))
    if control.get('fail'):
        raise ValueError('fixture failure')
    return {'status': 'awaiting_visual_review', 'image_prompt_file': image_prompt_file,
            'existing_image_evidence': existing_image_evidence}

def confirm(project, reviewed_images):
    return {'status': 'ready', 'reviewed_images': reviewed_images}
'''


class Peer:
    def __init__(self, script):
        self.stderr = tempfile.TemporaryFile()
        self.proc = subprocess.Popen([sys.executable, str(script)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.stderr)
        self.buffer = b''

    def send(self, message):
        self.raw(json.dumps(message).encode() + b'\n')

    def raw(self, value):
        self.proc.stdin.write(value)
        self.proc.stdin.flush()

    def request(self, request_id, method, params=None):
        self.send({'jsonrpc': '2.0', 'id': request_id, 'method': method,
                   'params': {} if params is None else params})

    def read(self, timeout=3):
        deadline = time.monotonic() + timeout
        while b'\n' not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.proc.stdout], [], [], remaining)[0]:
                raise TimeoutError('No MCP response')
            chunk = os.read(self.proc.stdout.fileno(), 65536)
            if not chunk:
                raise EOFError('MCP server closed stdout')
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b'\n', 1)
        return json.loads(line)

    def initialize(self):
        self.request(1, 'initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                                      'clientInfo': {'name': 'test', 'version': '1'}})
        response = self.read()
        self.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        return response

    def close(self):
        if self.proc.stdin and not self.proc.stdin.closed:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=12)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.proc.stdout.close()
        self.stderr.close()


class XhsDeliveryMcpTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        scripts = self.root / 'scripts'
        scripts.mkdir()
        self.script = scripts / 'xhs-delivery-mcp.py'
        shutil.copyfile(ROOT / 'scripts/xhs-delivery-mcp.py', self.script)
        (scripts / 'xhs_delivery.py').write_text(STUB)
        self.project = self.root / 'post'
        (self.project / '.xhs').mkdir(parents=True)
        (self.project / '.xhs/state.json').write_text(json.dumps({'workflow': 'xhs-three', 'version': 1}))
        self.control()
        (self.project / 'prompt.md').write_text('fixture prompt')
        (self.project / 'card.png').write_bytes(b'fixture; helper validates real images')
        self.peer = Peer(self.script)
        self.addCleanup(self.peer.close)

    def control(self, **kwargs):
        (self.project / 'control.json').write_text(json.dumps(kwargs))

    def call(self, request_id=2, name='prepare_delivery', **arguments):
        self.peer.request(request_id, 'tools/call', {'name': name,
                          'arguments': {'project': str(self.project), **arguments}})

    def wait_file(self, path):
        deadline = time.monotonic() + 3
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(path.exists(), str(path))
        return int(path.read_text())

    def assert_stopped(self, pid):
        # A dead orphan can briefly remain a zombie until the OS reaps it.
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            linux_status = Path('/proc') / str(pid) / 'stat'
            if linux_status.exists() and linux_status.read_text().split(') ', 1)[1].startswith('Z'):
                return
            time.sleep(0.03)
        self.fail('Delivery process remains active: ' + str(pid))

    def test_initialize_and_only_two_tools(self):
        response = self.peer.initialize()
        self.assertEqual(response['result']['protocolVersion'], '2024-11-05')
        self.peer.request(2, 'tools/list')
        tools = self.peer.read()['result']['tools']
        self.assertEqual([row['name'] for row in tools], ['prepare_delivery', 'confirm_delivery'])
        self.assertTrue(all(row['inputSchema']['additionalProperties'] is False for row in tools))
        self.assertEqual(tools[1]['inputSchema']['properties']['reviewed_images']['maxItems'], 7)

    def test_protocol_errors_and_notifications(self):
        for raw, code in [(b'{bad\n', -32700), (b'[]\n', -32600),
                          (b'{"jsonrpc":"2.0","id":true,"method":"ping"}\n', -32600),
                          (b'{"jsonrpc":"2.0","id":1,"id":2,"method":"ping"}\n', -32700)]:
            self.peer.raw(raw)
            self.assertEqual(self.peer.read()['error']['code'], code)
        self.peer.request(3, 'tools/list')
        self.assertEqual(self.peer.read()['error']['code'], -32000)
        self.peer.initialize()
        self.peer.request(4, 'missing')
        self.assertEqual(self.peer.read()['error']['code'], -32601)
        self.peer.request(5, 'tools/list', [])
        self.assertEqual(self.peer.read()['error']['code'], -32602)
        self.peer.send({'jsonrpc': '2.0', 'method': 'unknown/notification'})
        self.peer.request(6, 'ping')
        self.assertEqual(self.peer.read(), {'jsonrpc': '2.0', 'id': 6, 'result': {}})

    def test_tool_validation_and_xhs_project_boundary(self):
        self.peer.initialize()
        cases = [('prepare_delivery', {'unexpected': True}),
                 ('prepare_delivery', {'image_prompt_file': '../escape.md'}),
                 ('prepare_delivery', {'image_prompt_file': str(self.project / 'prompt.md')}),
                 ('prepare_delivery', {'image_prompt_file': 7}),
                 ('prepare_delivery', {'image_prompt_file': 'prompt.md', 'existing_image_evidence': 'prompt.md'}),
                 ('confirm_delivery', {'reviewed_images': []}),
                 ('confirm_delivery', {'reviewed_images': ['card.png', './card.png']}),
                 ('confirm_delivery', {'reviewed_images': [False]}),
                 ('shell', {})]
        for number, (name, arguments) in enumerate(cases, 2):
            with self.subTest(name=name, arguments=arguments):
                self.call(number, name, **arguments)
                self.assertTrue(self.peer.read()['result']['isError'])
        (self.project / '.xhs/state.json').write_text('{"workflow":"plan-code","version":1}')
        self.call(20)
        self.assertTrue(self.peer.read()['result']['isError'])
        self.assertFalse((self.project / 'started').exists())

    def test_project_file_symlinks_are_rejected_before_helper(self):
        self.peer.initialize()
        (self.project / 'alias.md').symlink_to(self.project / 'prompt.md')
        (self.project / 'alias-dir').symlink_to(self.project, target_is_directory=True)
        for number, filename in enumerate(('alias.md', 'alias-dir/prompt.md'), 2):
            self.call(number, image_prompt_file=filename)
            self.assertTrue(self.peer.read()['result']['isError'])
        self.assertFalse((self.project / 'started').exists())

    def test_long_call_waits_and_keeps_ping_responsive(self):
        self.control(delay=0.7)
        self.peer.initialize()
        self.call(image_prompt_file='prompt.md')
        with self.assertRaises(TimeoutError):
            self.peer.read(0.15)
        self.peer.request(3, 'ping')
        self.assertEqual(self.peer.read()['id'], 3)
        result = self.peer.read()['result']
        self.assertFalse(result['isError'])
        self.assertEqual(json.loads(result['content'][0]['text'])['image_prompt_file'], 'prompt.md')
        self.peer.stderr.seek(0)
        self.assertIn(b'helper log belongs on stderr', self.peer.stderr.read())

    def test_helper_failure_is_tool_error_and_confirm_succeeds(self):
        self.control(fail=True)
        self.peer.initialize()
        self.call()
        result = self.peer.read()['result']
        self.assertTrue(result['isError'])
        self.assertIn('fixture failure', result['content'][0]['text'])
        self.call(3, 'confirm_delivery', reviewed_images=['card.png'])
        result = self.peer.read()['result']
        self.assertFalse(result['isError'])
        self.assertEqual(json.loads(result['content'][0]['text'])['status'], 'ready')

    def test_busy_call_rejected_without_starting_another_worker(self):
        self.control(delay=0.5)
        self.peer.initialize()
        self.call()
        self.wait_file(self.project / 'started')
        self.call(3)
        result = self.peer.read()
        self.assertEqual(result['id'], 3)
        self.assertTrue(result['result']['isError'])
        self.assertEqual(self.peer.read()['id'], 2)

    def test_cancellation_stops_worker_and_child_without_late_success(self):
        self.control(delay=30, child=True)
        self.peer.initialize()
        self.call()
        pid = self.wait_file(self.project / 'started')
        child = self.wait_file(self.project / 'child-started')
        self.peer.send({'jsonrpc': '2.0', 'method': 'notifications/cancelled', 'params': {'requestId': 2}})
        self.peer.request(3, 'ping')
        self.assertEqual(self.peer.read()['id'], 3)
        self.assert_stopped(pid)
        self.assert_stopped(child)
        with self.assertRaises(TimeoutError):
            self.peer.read(0.15)

    def test_eof_stops_worker_and_child(self):
        self.control(delay=30, child=True)
        self.peer.initialize()
        self.call()
        pid = self.wait_file(self.project / 'started')
        child = self.wait_file(self.project / 'child-started')
        self.peer.proc.stdin.close()
        self.assertEqual(self.peer.proc.wait(timeout=12), 0)
        self.assert_stopped(pid)
        self.assert_stopped(child)
        self.assertEqual(self.peer.proc.stdout.read(), b'')

    def test_deadline_returns_error_and_stops_worker(self):
        self.peer.close()
        self.script.write_text(self.script.read_text().replace('CALL_TIMEOUT = ', 'CALL_TIMEOUT = 0.3 # ', 1))
        self.peer = Peer(self.script)
        self.addCleanup(self.peer.close)
        self.control(delay=30)
        self.peer.initialize()
        self.call()
        pid = self.wait_file(self.project / 'started')
        result = self.peer.read()['result']
        self.assertTrue(result['isError'])
        self.assertIn('deadline', result['content'][0]['text'])
        self.assert_stopped(pid)


class ConfigureXhsDeliveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts/xhs-delivery-mcp.py').write_text('# fixture')
        self.path = self.root / '.agents/mcp_config.json'

    def existing(self, value):
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(value if isinstance(value, str) else json.dumps(value))
        return self.path.read_bytes()

    def test_creates_workspace_config_and_is_idempotent(self):
        self.assertTrue(CONFIG.configure(self.root)['changed'])
        raw = self.path.read_bytes()
        config = json.loads(raw)['mcpServers'][CONFIG.SERVER_KEY]
        self.assertTrue(Path(config['command']).is_absolute())
        self.assertEqual(config['args'], [str(self.root.resolve() / 'scripts/xhs-delivery-mcp.py')])
        self.assertEqual(config['timeoutSeconds'], 600)
        self.assertEqual(config['tools'], {name: {'background': 'off', 'eager': True}
                                         for name in ('prepare_delivery', 'confirm_delivery')})
        self.assertFalse(CONFIG.configure(self.root)['changed'])
        self.assertEqual(self.path.read_bytes(), raw)

    def test_preserves_other_servers_and_top_level_settings(self):
        other = {'mcpServers': {'other': {'command': 'existing', 'env': {'KEEP': 'private fixture'}}},
                 'userSetting': ['keep', 7]}
        self.existing(other)
        CONFIG.configure(self.root)
        updated = json.loads(self.path.read_text())
        self.assertEqual(updated['mcpServers']['other'], other['mcpServers']['other'])
        self.assertEqual(updated['userSetting'], other['userSetting'])

    def test_conflict_is_not_overwritten(self):
        raw = self.existing({'mcpServers': {CONFIG.SERVER_KEY: {'command': 'different'}}})
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            CONFIG.configure(self.root)
        self.assertEqual(self.path.read_bytes(), raw)

    def test_malformed_config_is_not_overwritten(self):
        for value in ('{broken', '[]', '{"mcpServers":null}', '{"a":1,"a":2}', '{"a":NaN}'):
            with self.subTest(value=value):
                raw = self.existing(value)
                with self.assertRaises(ValueError):
                    CONFIG.configure(self.root)
                self.assertEqual(self.path.read_bytes(), raw)

    def test_config_file_and_agents_directory_symlinks_are_rejected(self):
        target = self.root / 'other.json'
        target.write_text('{}')
        self.path.parent.mkdir()
        self.path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            CONFIG.configure(self.root)
        self.assertEqual(target.read_text(), '{}')
        self.path.unlink()
        self.path.parent.rmdir()
        directory = self.root / 'elsewhere'
        directory.mkdir()
        self.path.parent.symlink_to(directory, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            CONFIG.configure(self.root)
        self.assertEqual(list(directory.iterdir()), [])

    def test_concurrent_config_change_is_not_overwritten(self):
        self.existing({'mcpServers': {}})
        original = CONFIG.read_config
        calls = []

        def changed(path):
            calls.append(path)
            if len(calls) == 2:
                path.write_text('{"mcpServers":{"concurrent":{}}}')
            return original(path)

        with patch.object(CONFIG, 'read_config', changed):
            with self.assertRaisesRegex(ValueError, 'changed during'):
                CONFIG.configure(self.root)
        self.assertIn('concurrent', json.loads(self.path.read_text())['mcpServers'])
        self.assertEqual(list(self.path.parent.glob('.xhs-mcp-*')), [])


if __name__ == '__main__':
    unittest.main()
