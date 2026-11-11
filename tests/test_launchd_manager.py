"""Lifecycle safety checks without installing jobs or touching running services."""
import importlib.util
import plistlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / 'integrations/openmausbot/launchd/manage.py'
spec = importlib.util.spec_from_file_location('launchd_manager', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LaunchdManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manager = module.Manager(Path(self.temp.name) / 'Home with spaces', 8799)
        self.manager.require_domain = Mock()
        self.manager.port_busy = Mock(return_value=False)

    def test_collision_does_not_stop_or_overwrite_unmanaged_service(self):
        self.manager.loaded = Mock(return_value=False)
        self.manager.port_busy = Mock(return_value=True)
        self.manager.ctl = Mock()
        with self.assertRaisesRegex(module.ServiceError, '已有未托管服务'):
            self.manager.up()
        self.assertFalse(self.manager.agents.exists())
        self.manager.ctl.assert_not_called()

    def test_tunnel_detection_requires_ssh_exact_forward_and_host(self):
        text = '\n'.join([
            '12 1 /usr/bin/ssh -N -R 127.0.0.1:9001:127.0.0.1:8799 root@198.44.111.185',
            '13 1 /bin/bash -c "ssh -N -R 127.0.0.1:9001:127.0.0.1:8799 root@198.44.111.185"',
            '14 1 /usr/bin/ssh -N -R 127.0.0.1:9001:127.0.0.1:9999 root@198.44.111.185',
            '15 1 /usr/bin/ssh -N -R 127.0.0.1:9001:127.0.0.1:8799 another-host',
        ])
        self.assertEqual(module.Manager.matching_tunnels(text, self.manager.forward), [12])

    def test_foreign_same_label_plist_is_never_stopped_or_removed(self):
        path = self.manager.path('serve')
        module.Manager.write_plist(path, {'Label': module.LABELS['serve'], 'ProgramArguments': ['/bin/sleep', '100']})
        self.manager.loaded = Mock(return_value=False)
        self.manager.ctl = Mock()
        with self.assertRaisesRegex(module.ServiceError, '不是本脚本管理'):
            self.manager.down()
        self.assertTrue(path.exists())
        self.manager.ctl.assert_not_called()

    def test_down_boots_out_before_removing_owned_autostart_files(self):
        for kind, label in module.LABELS.items():
            module.Manager.write_plist(self.manager.path(kind), {'Label': label, 'Comment': module.OWNER})
        self.manager.loaded = Mock(return_value=True)
        self.manager.ctl = Mock(return_value=subprocess.CompletedProcess([], 0, '', ''))
        self.manager.down()
        self.assertEqual(self.manager.ctl.call_args_list[0].args, ('bootout', self.manager.target('tunnel')))
        self.assertEqual(self.manager.ctl.call_args_list[1].args, ('bootout', self.manager.target('serve')))
        self.assertFalse(any(self.manager.path(k).exists() for k in module.LABELS))

    def test_restart_refuses_busy_tasks_without_stopping(self):
        self.manager.health = Mock(return_value={'app': 'openmausbot'})
        self.manager.down = Mock()
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read = Mock(return_value=b'{"bots":[{"busy":false,"tasks":[{"busy":true}]}]}')
        self.manager.opener.open = Mock(return_value=response)
        with self.assertRaisesRegex(module.ServiceError, '仍有Bot任务运行'):
            self.manager.restart()
        self.manager.down.assert_not_called()

    def test_repeated_up_preserves_running_jobs_and_identical_files(self):
        self.manager.key.parent.mkdir(parents=True)
        self.manager.key.touch()
        self.manager.render(self.manager.agents)
        times = {kind: self.manager.path(kind).stat().st_mtime_ns for kind in module.LABELS}
        self.manager.loaded = Mock(return_value=True)
        self.manager.refuse_unmanaged = Mock()
        self.manager.pid = Mock(return_value=123)
        self.manager.health = Mock(side_effect=lambda public=False: {'app': 'openmausbot'} if public else {'app': 'openmausbot', 'pid': 123})
        self.manager.tunnel_health = Mock(return_value={'app': 'openmausbot', 'pid': 123})
        self.manager.ctl = Mock()
        self.manager.up()
        self.manager.ctl.assert_not_called()
        self.assertEqual(times, {kind: self.manager.path(kind).stat().st_mtime_ns for kind in module.LABELS})

    def test_failed_bootout_retains_autostart_definition(self):
        for kind, label in module.LABELS.items():
            module.Manager.write_plist(self.manager.path(kind), {'Label': label, 'Comment': module.OWNER})
        self.manager.loaded = Mock(return_value=True)
        self.manager.ctl = Mock(return_value=subprocess.CompletedProcess([], 1, '', 'permission denied'))
        with self.assertRaisesRegex(module.ServiceError, '停止tunnel失败'):
            self.manager.down()
        self.assertTrue(all(self.manager.path(kind).exists() for kind in module.LABELS))

    def test_real_renderer_preserves_spaces_and_explicit_public_origin(self):
        serve, tunnel = self.manager.plist('serve'), self.manager.plist('tunnel')
        # Round-trip through actual plist bytes, rather than testing an XML string.
        serve = plistlib.loads(plistlib.dumps(serve))
        self.assertEqual(serve['EnvironmentVariables']['HOME'], str(self.manager.home))
        self.assertIn('--public-url', serve['ProgramArguments'])
        self.assertIn(module.PUBLIC_URL, serve['ProgramArguments'])
        self.assertEqual(tunnel['ProgramArguments'][0], '/usr/bin/ssh')
        self.assertIn(self.manager.forward, tunnel['ProgramArguments'])
        self.assertTrue(serve['KeepAlive'] and tunnel['KeepAlive'])
        self.assertNotIn('NetworkState', str(tunnel))
        self.assertNotIn('nohup', str(serve))



class RuntimeSelectionTests(unittest.TestCase):
    def test_explicit_native_switch_does_not_load_private_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            config=Path(temp)/'runtime.json';config.write_text('{"mode":"native"}')
            self.assertIsNone(module.selected_cli(config))

    def test_broken_private_runtime_fails_instead_of_silent_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            config=Path(temp)/'runtime.json';config.write_text('{"mode":"workbench","cli":"/missing/cli.js"}')
            with self.assertRaisesRegex(module.ServiceError,'未静默回退'):
                module.selected_cli(config)

    def test_restart_preflights_private_runtime_before_stopping_healthy_service(self):
        manager=module.Manager()
        manager.health=Mock(return_value=None)
        manager.plist=Mock(side_effect=module.ServiceError('Invalid selected runtime'))
        manager.down=Mock();manager.up=Mock()
        with self.assertRaisesRegex(module.ServiceError,'Invalid selected runtime'):
            manager.restart()
        manager.down.assert_not_called();manager.up.assert_not_called()

if __name__ == '__main__':
    unittest.main()
