"""Portable intake and Ubuntu service boundaries; no real accounts or model calls."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


entry = load('start_xhs_test', 'start-xhs.py')
ubuntu = load('xhs_ubuntu_test', 'xhs-ubuntu.py')


class NativeClient:
    def __init__(self, role, fail_send=False):
        self.role = role
        self.fail_send = fail_send
        self.busy = False
        self.writes = []

    def call(self, method, path, body=None):
        if method == 'GET':
            return {'bots': [{'id': self.role['botId'], 'description':
                'Workflour 小红书图文 · xhs-planner', 'tasks': [{'busy': self.busy}]}]}
        self.writes.append((method, path, copy.deepcopy(body)))
        if path.endswith('/tasks'):
            return {'task': {'threadId': 'actual-workbench-thread'}}
        if self.fail_send:
            raise TimeoutError('Native send response lost')
        return {'ok': True}


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.team = entry.team_tool.manifest(self.base / 'deployment.json', create=True)
        self.role = next(r for r in self.team['roles'] if r['key'] == 'xhs-planner')

    def test_binds_actual_workbench_id_before_sending_and_preserves_native_permission_defaults(self):
        client = NativeClient(self.role)
        project = self.base / 'new draft'
        result = entry.start(client, self.team, project, 'Claude消息')
        state = json.loads((project / '.xhs/state.json').read_text())
        self.assertEqual(state['planner_thread'], 'actual-workbench-thread')
        self.assertEqual(result['status'], 'sent')
        self.assertEqual(len(client.writes), 2)
        self.assertEqual(set(client.writes[0][2]), {'title', 'select'})
        message = client.writes[1][2]
        self.assertIn('actual-workbench-thread', message['text'])
        self.assertIn('template_only', message['text'])
        self.assertEqual(json.loads((project / '.xhs/launch.json').read_text())['send_id'], message['sendId'])
        with self.assertRaises(ValueError):
            entry.start(client, self.team, project, 'Claude消息')
        self.assertEqual(len(client.writes), 2)

    def test_uncertain_send_is_recorded_without_automatic_retry(self):
        client = NativeClient(self.role, fail_send=True)
        project = self.base / 'uncertain'
        with self.assertRaises(TimeoutError):
            entry.start(client, self.team, project, 'Claude', image=True)
        journal = json.loads((project / '.xhs/launch.json').read_text())
        self.assertEqual(journal['status'], 'delivery_unknown')
        self.assertEqual(len(client.writes), 2)
        self.assertIn('至多1次', client.writes[-1][2]['text'])
        with self.assertRaises(ValueError):
            entry.start(client, self.team, project, 'Claude')

    def test_busy_planner_does_not_create_project_or_native_task(self):
        client = NativeClient(self.role)
        client.busy = True
        project = self.base / 'busy'
        with self.assertRaisesRegex(ValueError, 'busy'):
            entry.start(client, self.team, project, 'Claude')
        self.assertFalse(project.exists())
        self.assertEqual(client.writes, [])


class UbuntuServicesTests(unittest.TestCase):
    def test_service_paths_escape_spaces_quotes_percent_and_dollar(self):
        text = ubuntu.unit_text('omb', Path('/a b/%r/$S/"x'), '/usr/bin/python3')
        self.assertIn('WorkingDirectory="/a b/%%r/$S/\\"x"', text)
        self.assertIn('$$S', text.split('ExecStart=')[1])
        self.assertIn('UMask=0077', text)
        with self.assertRaises(ValueError):
            ubuntu.unit_text('omb', Path('/bad\npath'))

    def test_busy_native_task_blocks_service_shutdown(self):
        with patch.object(ubuntu, 'workbench', return_value=[{'tasks': [{'busy': True}]}]), \
             patch.object(ubuntu, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'busy'):
                ubuntu.services('down')
            run.assert_not_called()

    def test_unknown_service_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            folder = home / '.config/systemd/user'
            folder.mkdir(parents=True)
            target = folder / ubuntu.UNITS[0]
            target.write_text('someone else\n')
            with patch.object(Path, 'home', return_value=home), \
                 patch.object(ubuntu, 'workbench', return_value=None), patch.object(ubuntu, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'not owned'):
                    ubuntu.services('up')
                self.assertEqual(target.read_text(), 'someone else\n')
                run.assert_not_called()

    def test_profile_path_traversal_rejected(self):
        for value in ('../desktop', 'web/x', '', 'web\n'):
            with self.assertRaises(ValueError):
                ubuntu.source_profile(value)
        self.assertEqual(ubuntu.source_profile('web'), 'web')

    def test_mac_install_rejected_before_mutations(self):
        with patch.object(ubuntu.platform, 'system', return_value='Darwin'):
            with self.assertRaisesRegex(ValueError, 'inside your Ubuntu VM'):
                ubuntu.require_ubuntu()


if __name__ == '__main__':
    unittest.main()
