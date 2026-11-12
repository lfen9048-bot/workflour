"""Native task identity is acknowledged separately from manual model controls."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('bindings_bridge', Path(__file__).resolve().parents[1] / 'integrations/openmausbot/acp-resume-bridge.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def params(bot='bot-one', thread='thread-one', http=True):
    env = {'OMB_BOT_ID': bot, 'OMB_THREAD_ID': thread, 'SECRET': 'never-persist'}
    server = {'name': 'agents'}
    if http:
        server.update(type='http', url='http://localhost/mcp', headers=[
            {'name': 'authorization', 'value': 'never-persist'},
            {'name': 'x-omb-agents-env', 'value': base64.urlsafe_b64encode(json.dumps(env).encode()).decode().rstrip('=')}])
    else:
        server.update(command='unused', env=[{'name': key, 'value': value} for key, value in env.items()])
    return {'mcpServers': [server]}


class BindingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {'DSH_HOME': self.tmp.name})
        env.start(); self.addCleanup(env.stop)
        self.bridge = M.ResumeBridge(controls=M.ModelControls(), bindings=M.SessionBindings())
        self.path = Path(self.tmp.name) / 'workflour-session-bindings/native-one.json'

    def exchange(self, method, parameters, success=True):
        request = M.encode({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': parameters})
        result = self.bridge.client(request)
        if result[0][0] == 'client':
            return json.loads(result[0][1])
        response = {'jsonrpc': '2.0', 'id': 1}
        response.update({'result': {'sessionId': 'native-one'}} if success else {'error': {'code': -1}})
        return json.loads(self.bridge.child(M.encode(response))[0][1])

    def test_http_and_stdio_keep_only_identity_after_success(self):
        for http in (True, False):
            self.exchange('session/new', params(http=http))
            value = json.loads(self.path.read_text())
            self.assertEqual(value, {'schema_version': 1, 'session_id': 'native-one', 'bot_id': 'bot-one', 'thread_id': 'thread-one'})
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('never-persist', self.path.read_text())
            self.assertFalse((Path(self.tmp.name) / 'workflour-fallback-controls/native-one.json').exists())

    def test_failed_new_or_resume_never_rebinds(self):
        self.exchange('session/new', params(), success=False)
        self.assertFalse(self.path.exists())
        self.exchange('session/new', params())
        before = self.path.read_text()
        self.exchange('session/resume', {**params(thread='thread-two'), 'sessionId': 'native-one'}, success=False)
        self.assertEqual(self.path.read_text(), before)

    def test_successful_resume_updates_binding_without_control_revision(self):
        self.exchange('session/new', params())
        controls = M.ModelControls()
        controls.write('native-one', {'model': 'manual'}, changed=True)
        before = controls.read('native-one')
        self.exchange('session/resume', {**params(thread='thread-two'), 'sessionId': 'native-one'})
        self.assertEqual(json.loads(self.path.read_text())['thread_id'], 'thread-two')
        self.assertEqual(controls.read('native-one'), before)

    def test_non_omb_session_explicitly_replaces_old_identity_after_acknowledgement(self):
        self.exchange('session/new', params())
        self.exchange('session/resume', {'sessionId': 'native-one', 'mcpServers': []})
        self.assertEqual(json.loads(self.path.read_text()),
                         {'schema_version': 1, 'session_id': 'native-one', 'scope': 'non_omb'})
        self.assertNotIn('error', self.exchange('session/prompt', {'sessionId': 'native-one', 'prompt': []}))

    def test_prompt_checks_record_loss_corruption_and_identity_change(self):
        for failure in ('missing', 'corrupt', 'changed', 'non_omb'):
            with self.subTest(failure=failure):
                self.exchange('session/new', params())
                if failure == 'missing': self.path.unlink()
                elif failure == 'corrupt': self.path.write_text('broken')
                else:
                    value = json.loads(self.path.read_text())
                    if failure == 'changed': value['thread_id'] = 'another-thread'
                    else: value = {'schema_version': 1, 'session_id': 'native-one', 'scope': 'non_omb'}
                    self.path.write_text(json.dumps(value))
                self.assertIn('error', self.exchange('session/prompt', {'sessionId': 'native-one', 'prompt': []}))
                self.exchange('session/resume', {**params(), 'sessionId': 'native-one'})
                self.assertNotIn('error', self.exchange('session/prompt', {'sessionId': 'native-one', 'prompt': []}))

    def test_restart_requires_acknowledged_resume_before_prompt(self):
        self.exchange('session/new', params())
        self.bridge = M.ResumeBridge(controls=M.ModelControls(), bindings=M.SessionBindings())
        self.assertIn('error', self.exchange('session/prompt', {'sessionId': 'native-one', 'prompt': []}))
        self.exchange('session/resume', {**params(), 'sessionId': 'native-one'})
        self.assertNotIn('error', self.exchange('session/prompt', {'sessionId': 'native-one', 'prompt': []}))

    def test_conflicting_or_incomplete_identity_fails_without_forwarding(self):
        conflicted=params(); conflicted['mcpServers'] += params(thread='thread-two', http=False)['mcpServers']
        for value in (conflicted, params(thread='../../invalid'), {'mcpServers':[{'env':[{'name':'OMB_BOT_ID','value':'only-one'}]}]}):
            self.assertIn('error', self.exchange('session/new', value))
        self.assertFalse(self.path.exists())

    def test_write_failure_is_not_reported_as_success(self):
        with patch.object(self.bridge.bindings, 'write', side_effect=OSError('disk full')):
            self.assertIn('error', self.exchange('session/new', params()))
        self.assertIn('error', self.exchange('session/prompt', {'sessionId': 'native-one', 'prompt': []}))
        self.exchange('session/resume', {**params(), 'sessionId': 'native-one'})
        self.assertNotIn('error', self.exchange('session/prompt', {'sessionId': 'native-one', 'prompt': []}))


if __name__ == '__main__':
    unittest.main()
