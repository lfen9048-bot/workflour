import importlib.util
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('xhs_agy_bridge', ROOT / 'scripts/xhs-agy-mcp-bridge.py')
BRIDGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BRIDGE)


class XhsAgyBridgeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / 'scripts').mkdir()
        self.script = self.root / 'scripts/xhs-delivery-mcp.py'
        self.script.write_text('# bounded test fixture')
        self.manifest = self.root / 'deployment.json'
        self.manifest.write_text(json.dumps({'roles': [
            {'key': 'xhs-writer', 'botId': 'writer-fixture'},
            {'key': 'xhs-planner', 'botId': 'planner-fixture'}]}))
        self.config = self.root / '.agents/mcp_config.json'
        self.config.parent.mkdir()
        self.server = {'command': sys.executable, 'args': [str(self.script)],
                       'timeoutSeconds': 600, 'tools': {
                           name: {'background': 'off', 'eager': True}
                           for name in ('prepare_delivery', 'confirm_delivery')}}
        self.save_config(self.server)

    def save_config(self, server):
        self.config.write_text(json.dumps({'mcpServers': {
            BRIDGE.SERVER_NAME: server, 'unrelated': {'command': 'never-import-this'}}}))

    def frame(self, method='session/new', bot='writer-fixture', **kwargs):
        return {'jsonrpc': '2.0', 'id': 3, 'method': method, 'params': {
            'cwd': str(self.root), 'mcpServers': [{'name': 'agents', 'command': 'unchanged',
                'args': ['same'], 'env': [{'name': 'OMB_BOT_ID', 'value': bot},
                                        {'name': 'PRIVATE_FIXTURE', 'value': 'never-copy-or-log'}]}], **kwargs}}

    def encode(self, message):
        # Formatting intentionally differs from the bridge's rewritten JSON.
        return (json.dumps(message, indent=None, separators=(', ', ': ')) + '\r\n').encode()

    def rewrite(self, message):
        return BRIDGE.rewrite(self.encode(message), self.root, self.manifest)

    def test_injects_only_standard_stdio_fields_with_bounded_env(self):
        for method in ('session/new', 'session/load', 'session/resume'):
            message = self.frame(method, sessionId='native-fixture')
            output, error = self.rewrite(message)
            self.assertIsNone(error)
            changed = json.loads(output)
            self.assertEqual(changed['params']['mcpServers'][0], message['params']['mcpServers'][0])
            server = changed['params']['mcpServers'][1]
            self.assertEqual(set(server), {'name', 'command', 'args', 'env'})
            self.assertEqual(server['name'], BRIDGE.SERVER_NAME)
            self.assertEqual(server['command'], sys.executable)
            self.assertEqual(server['args'], [str(self.script)])
            self.assertEqual(server['env'], [{'name': 'WORKFLOUR_XHS_ACP_BOUNDED', 'value': '1'}])
            self.assertNotIn('never-copy-or-log', json.dumps(server))
            self.assertNotIn('unrelated', json.dumps(server))
            self.assertEqual(changed['params']['sessionId'], 'native-fixture')

    def test_unrelated_methods_bots_cwds_and_missing_identity_are_byte_exact(self):
        cases = [self.frame('session/prompt'), self.frame('initialize'),
                 self.frame(bot='planner-fixture'), self.frame(bot='unknown'),
                 self.frame(cwd=str(self.root / 'scripts')),
                 self.frame(mcpServers=[]), self.frame(mcpServers=None),
                 self.frame(cwd='.'), self.frame(mcpServers=[{'name': 'agents', 'env': {}}])]
        self.config.unlink()  # Non-targets must not depend on workspace config.
        for message in cases:
            with self.subTest(message=message):
                raw = self.encode(message)
                self.assertEqual(BRIDGE.rewrite(raw, self.root, self.manifest), (raw, None))
        for raw in (b'not json\n', b'[]\n', b'{"id":1,"id":2}\n', b'{"n":NaN}\n'):
            self.assertEqual(BRIDGE.rewrite(raw, self.root, self.manifest), (raw, None))

    def test_identity_conflicts_duplicate_env_and_unknown_manifest_do_not_inject(self):
        message = self.frame()
        message['params']['mcpServers'].append(self.frame(bot='planner-fixture')['params']['mcpServers'][0])
        duplicate = self.frame()
        duplicate['params']['mcpServers'][0]['env'].append({'name': 'OMB_BOT_ID', 'value': 'writer-fixture'})
        for message in (message, duplicate):
            raw = self.encode(message)
            self.assertEqual(BRIDGE.rewrite(raw, self.root, self.manifest), (raw, None))
        self.manifest.unlink()
        raw = self.encode(self.frame())
        self.assertEqual(BRIDGE.rewrite(raw, self.root, self.manifest), (raw, None))

    def test_target_missing_or_conflicting_config_returns_sanitized_error(self):
        for server in ({}, {'command': '/bin/sh', 'args': [str(self.script)]},
                       {**self.server, 'args': [str(self.script), '--extra']},
                       {**self.server, 'disabled': True},
                       {**self.server, 'enabledTools': ['prepare_delivery']},
                       {**self.server, 'disabledTools': ['confirm_delivery']}):
            with self.subTest(server=server):
                self.save_config(server)
                upstream, error = self.rewrite(self.frame())
                self.assertIsNone(upstream)
                response = json.loads(error)
                self.assertEqual(response['id'], 3)
                self.assertEqual(response['error']['code'], -32602)
                self.assertNotIn('never-copy-or-log', error.decode())
        self.config.unlink()
        upstream, error = self.rewrite(self.frame())
        self.assertIsNone(upstream)
        self.assertIn('configure-xhs-delivery.py', json.loads(error)['error']['message'])

    def test_workspace_symlink_and_damaged_config_are_rejected(self):
        self.config.write_text('{broken')
        self.assertIsNotNone(self.rewrite(self.frame())[1])
        self.config.unlink()
        target = self.root / 'outside-config.json'
        target.write_text(json.dumps({'mcpServers': {BRIDGE.SERVER_NAME: self.server}}))
        self.config.symlink_to(target)
        self.assertIsNotNone(self.rewrite(self.frame())[1])
        self.config.unlink()
        self.config.parent.rmdir()
        directory = self.root / 'outside-agents'
        directory.mkdir()
        self.config.parent.symlink_to(directory, target_is_directory=True)
        self.assertIsNotNone(self.rewrite(self.frame())[1])

    def test_existing_exact_registration_is_idempotent_and_conflict_is_error(self):
        message = self.frame()
        message['params']['mcpServers'].append(BRIDGE.approved_server(self.root))
        raw = self.encode(message)
        self.assertEqual(BRIDGE.rewrite(raw, self.root, self.manifest), (raw, None))
        message['params']['mcpServers'][1]['env'] = []
        upstream, error = self.rewrite(message)
        self.assertIsNone(upstream)
        self.assertIn('Conflicting', json.loads(error)['error']['message'])

    def test_native_roundtrip_preserves_bytes_and_injects_target_only(self):
        bridge = self.root / 'scripts/xhs-agy-mcp-bridge.py'
        shutil.copyfile(ROOT / 'scripts/xhs-agy-mcp-bridge.py', bridge)
        shutil.copyfile(ROOT / 'scripts/xhs_paths.py', self.root / 'scripts/xhs_paths.py')
        child = self.root / 'echo.py'
        child.write_text('import sys\nfor line in sys.stdin.buffer:\n sys.stdout.buffer.write(line); sys.stdout.buffer.flush()\n')
        env = {**os.environ, 'XHS_DEPLOYMENT_MANIFEST': str(self.manifest)}
        process = subprocess.Popen([sys.executable, str(bridge), sys.executable, str(child)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        try:
            raw = self.encode(self.frame(bot='planner-fixture'))
            process.stdin.write(raw)
            process.stdin.flush()
            self.assertTrue(select.select([process.stdout], [], [], 3)[0])
            self.assertEqual(process.stdout.readline(), raw)
            process.stdin.write(self.encode(self.frame()))
            process.stdin.flush()
            self.assertTrue(select.select([process.stdout], [], [], 3)[0])
            response = json.loads(process.stdout.readline())
            self.assertEqual(response['params']['mcpServers'][-1]['name'], BRIDGE.SERVER_NAME)
            self.config.unlink()
            process.stdin.write(self.encode(self.frame()))
            process.stdin.flush()
            self.assertTrue(select.select([process.stdout], [], [], 3)[0])
            self.assertEqual(json.loads(process.stdout.readline())['error']['code'], -32602)
            process.stdin.close()
            self.assertEqual(process.wait(timeout=10), 0)
            self.assertEqual(process.stderr.read(), b'')
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            for stream in (process.stdin, process.stdout, process.stderr):
                if not stream.closed:
                    stream.close()

    def test_delivery_timeout_defaults_and_acp_bound(self):
        for value, expected in (('', 560), ('1', 170), ('true', 560)):
            with self.subTest(value=value), patch.dict(os.environ, {'WORKFLOUR_XHS_ACP_BOUNDED': value}):
                spec = importlib.util.spec_from_file_location('bounded_delivery_mcp', ROOT / 'scripts/xhs-delivery-mcp.py')
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.assertEqual(module.CALL_TIMEOUT, expected)


if __name__ == '__main__':
    unittest.main()
