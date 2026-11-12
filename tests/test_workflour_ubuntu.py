"""Isolated deployment boundaries; no installer, service, account or model requests."""
import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dev_ubuntu_test', ROOT / 'scripts/workflour-ubuntu.py')
ubuntu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ubuntu)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ubuntu deployment ')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.base = self.home / 'runtime'
        for context in (patch.object(ubuntu, 'BASE', self.base),
                        patch.object(Path, 'home', return_value=self.home),
                        patch.dict(os.environ, {'PATH': '/usr/bin:/bin'}, clear=True)):
            context.start(); self.addCleanup(context.stop)

    def test_default_source_is_web_and_saved_nonsecret_paths_survive_service_environment(self):
        env = ubuntu.environment()
        self.assertEqual(env['WORKFLOUR_DSH_SOURCE_PROFILE'], 'web')
        self.assertEqual(env['WORKFLOUR_TEAM_MANIFEST'], str(self.home / '.workflour/team-v2/deployment.json'))
        self.assertEqual(env['WORKFLOUR_ROOT'], str(ROOT))
        self.assertNotIn('XHS_BROWSER_PYTHON', env)
        fields = {'DSH_HOME': 'custom dsh', 'AGY_BIN': 'bin/agy', 'WORKFLOUR_TEAM_MANIFEST': 'team.json',
                  'WORKFLOUR_OBSIDIAN_VAULT': 'vault', 'OMB_DATA_DIR': 'omb'}
        for key, rel in fields.items(): env[key] = str(self.home / rel)
        env['WORKFLOUR_DSH_SOURCE_PROFILE'] = 'web-alt'
        ubuntu.save_environment(env, node_bin=str(self.home / 'node/bin'))
        restored = ubuntu.environment()
        for key in fields: self.assertEqual(restored[key], env[key])
        self.assertEqual(restored['WORKFLOUR_DSH_SOURCE_PROFILE'], 'web-alt')
        self.assertIn(str(self.home / 'node/bin'), restored['PATH'])
        self.assertEqual((self.base / 'settings.json').stat().st_mode & 0o777, 0o600)

    def test_path_and_source_traversal_fail_before_writing(self):
        for key, bad in [('DSH_HOME', 'relative'), ('AGY_BIN', '/bad\npath'),
                         ('WORKFLOUR_DSH_SOURCE_PROFILE', '../desktop')]:
            with self.subTest(key=key), patch.dict(os.environ, {key: bad}):
                with self.assertRaises(ValueError): ubuntu.environment()
        self.assertFalse(self.base.exists())

    def test_mac_rejected_before_dispatch(self):
        with patch.object(ubuntu.shared.platform, 'system', return_value='Darwin'), \
             patch.object(ubuntu, 'install') as install, patch('sys.argv', ['entry', 'install']):
            with self.assertRaises(ValueError): ubuntu.main()
            install.assert_not_called()

    def test_busy_task_blocks_down(self):
        with patch.object(ubuntu, 'workbench', return_value=[{'tasks': [{'busy': True}]}]), \
             patch.object(ubuntu, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'busy'): ubuntu.services('down')
            run.assert_not_called()

    def test_same_port_xhs_not_replaced(self):
        with patch.object(ubuntu, 'workbench', return_value=[]), patch.object(ubuntu, 'run') as run:
            with self.assertRaisesRegex(ValueError, '8799'): ubuntu.services('up')
            with self.assertRaises(ValueError): ubuntu.configure()
            with self.assertRaises(ValueError): ubuntu.install(argparse.Namespace(system_deps=False))
            run.assert_not_called()

    def test_ownership_preflight_prevents_partial_replacement(self):
        folder = self.home / '.config/systemd/user'; folder.mkdir(parents=True)
        target = folder / ubuntu.UNITS[-1]; target.write_text('another installer')
        with patch.object(ubuntu, 'workbench', return_value=None), patch.object(ubuntu, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'not owned'): ubuntu.services('up')
            run.assert_not_called()
        self.assertEqual(list(folder.iterdir()), [target])
        self.assertEqual(target.read_text(), 'another installer')

    def test_owned_units_from_other_checkout_refused(self):
        folder = self.home / 'units'; folder.mkdir()
        (folder / ubuntu.SERVICE).write_text(ubuntu.unit_text(ubuntu.SERVICE, Path('/other')))
        with self.assertRaisesRegex(ValueError, 'not owned'): ubuntu.owned_units(folder)

    def test_up_installs_timers_without_explicit_daily_execution(self):
        with patch.object(ubuntu, 'workbench', return_value=None), patch.object(ubuntu, 'run') as run:
            ubuntu.services('up')
            first = [p.read_text() for p in (self.home / '.config/systemd/user').iterdir()]
            ubuntu.services('up')
            self.assertEqual(first, [p.read_text() for p in (self.home / '.config/systemd/user').iterdir()])
            calls = [c.args[0] for c in run.call_args_list]
            self.assertEqual(calls[1], ['systemctl', '--user', 'enable', '--now', ubuntu.SERVICE, *ubuntu.TIMERS])
            self.assertFalse(any(ubuntu.DAILY in cmd for cmd in calls))

    def test_systemd_paths_and_timers(self):
        text = ubuntu.unit_text(ubuntu.SERVICE, Path('/a b/%r/$S/"x'))
        self.assertIn('WorkingDirectory=/a b/%%r/$S/"x\n', text)
        self.assertIn('$$S', text.split('ExecStart=')[1])
        self.assertIn('UMask=0077', text)
        self.assertIn('OnCalendar=*-*-* 13:00:00 Asia/Shanghai', ubuntu.unit_text(ubuntu.TIMERS[1]))
        self.assertIn('Persistent=true', ubuntu.unit_text(ubuntu.TIMERS[1]))
        self.assertIn('OnUnitInactiveSec=20s', ubuntu.unit_text(ubuntu.TIMERS[0]))
        with self.assertRaises(ValueError): ubuntu.unit_text(ubuntu.SERVICE, Path('/bad\npath'))

    def test_daily_failure_still_checks_fallback_and_returns_failure(self):
        with patch.object(ubuntu.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 7),
                                                              subprocess.CompletedProcess([], 0)]) as run, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ubuntu.daily(), 1)
            self.assertEqual(run.call_args_list[0].args[0][-1], '--daily-checkin')
            self.assertEqual(run.call_args_list[1].args[0][-1], '--daily-check')

    def test_daily_timeout_is_not_success_and_does_not_prevent_second_check(self):
        with patch.object(ubuntu.subprocess, 'run', side_effect=[subprocess.TimeoutExpired('node', 270),
                                                               subprocess.CompletedProcess([], 0)]) as run, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(ubuntu.daily(), 1)
            self.assertEqual(run.call_count, 2)
            self.assertIsNone(json.loads(output.getvalue())['daily']['checkin']['exit_code'])

    def test_connect_only_provisions_no_business_send(self):
        with patch.object(ubuntu, 'run') as run:
            ubuntu.connect()
            self.assertEqual([c.args[0][-1] for c in run.call_args_list], ['create', 'activate', 'verify'])

    def test_doctor_manifest_validation_does_not_create_or_accept_empty_file(self):
        path = self.home / 'team.json'
        self.assertFalse(ubuntu.valid_manifest(path))
        self.assertFalse(path.exists())
        path.write_text('{}')
        self.assertFalse(ubuntu.valid_manifest(path))
        self.assertEqual(path.read_text(), '{}')

    def test_install_uses_own_runtime_and_browser_without_xhs_components(self):
        def venv_effect(command, **kwargs):
            if command[1:3] == ['-m', 'venv']:
                browser = Path(command[3]) / 'bin/python'
                browser.parent.mkdir(parents=True); browser.touch()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(ubuntu, 'ROOT', root), patch.object(ubuntu, 'workbench', return_value=None), \
                 patch.object(ubuntu.shared, 'ensure_node', return_value='/usr/bin'), \
                 patch.object(ubuntu.shared, 'ensure_workbuddy') as wb, patch.object(ubuntu, 'prepare_ui') as ui, \
                 patch.object(ubuntu, 'run', side_effect=venv_effect) as run, contextlib.redirect_stdout(io.StringIO()):
                ubuntu.install(argparse.Namespace(system_deps=False))
                calls = [c.args[0] for c in run.call_args_list]
                self.assertTrue(any('playwright==' + ubuntu.PLAYWRIGHT in c for c in calls))
                self.assertFalse(any('xhs' in str(c) or 'xiaohongshu' in str(c) for c in calls))
                wb.assert_called_once(); ui.assert_called_once()
                self.assertEqual(wb.call_args.args[0]['WORKFLOUR_DSH_SOURCE_PROFILE'], 'web')

    def test_configure_generates_all_seven_and_local_vault(self):
        with patch.object(ubuntu, 'workbench', return_value=None), patch.object(ubuntu, 'prepare_ui'), \
             patch.object(ubuntu, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
            ubuntu.configure()
            commands = [c.args[0] for c in run.call_args_list]
            roles = [c[-1] for c in commands if '--only' in c]
            self.assertEqual(roles, list(ubuntu.ROLES))
            self.assertTrue(any('init-workflour-vault.py' in str(c[1]) for c in commands))
            self.assertEqual(commands[-1][-1], 'prepare')

    def test_private_runtime_changes_with_overlay_without_replacing_old_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); overlay = root / 'integrations/openmausbot/workbench'; overlay.mkdir(parents=True)
            for name in ('source-lock.json', 'workbench.css', 'workbench.js'): (overlay / name).write_text('v1')
            with patch.object(ubuntu, 'ROOT', root):
                before = ubuntu.private_runtime(); before.mkdir(parents=True)
                (overlay / 'workbench.js').write_text('v2')
                self.assertNotEqual(before, ubuntu.private_runtime())
                self.assertTrue(before.exists())

    def test_missing_or_stale_private_ui_cannot_start_upstream_silently(self):
        with patch.object(ubuntu.os, 'execvpe') as execute:
            with self.assertRaisesRegex(ValueError, 'Private UI'): ubuntu.serve()
            execute.assert_not_called()

    def test_doctor_reports_authentication_not_probed(self):
        with patch.object(ubuntu.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(ubuntu.doctor(offline=True), 3)
        result = json.loads(output.getvalue())
        self.assertFalse(result['model_prompts_sent'])
        self.assertEqual(result['account_authentication'], 'not_probed')


if __name__ == '__main__': unittest.main()
