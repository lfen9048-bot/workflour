"""Side-effect-free tests for selecting and invoking the visible login tool."""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('xhs_service', Path(__file__).with_name('service.py'))
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class VisibleLoginTests(unittest.TestCase):
    def test_selects_exact_pinned_login_asset_for_each_supported_platform(self):
        for system, machine, expected in [('Darwin', 'arm64', 'xiaohongshu-login-darwin-arm64'),
                                          ('Linux', 'x86_64', 'xiaohongshu-login-linux-amd64')]:
            with self.subTest(system=system), patch.object(service.platform, 'system', return_value=system), \
                    patch.object(service.platform, 'machine', return_value=machine):
                _, _, asset, binary = service.current_binary('login')
                self.assertEqual(asset['name'], expected)
                self.assertEqual(binary.name, expected)
                self.assertEqual(len(asset['sha256']), 64)

    def test_linux_arm64_remains_explicitly_unsupported(self):
        with patch.object(service.platform, 'system', return_value='Linux'), \
                patch.object(service.platform, 'machine', return_value='aarch64'), self.assertRaises(ValueError):
            service.current_binary('login')

    def test_valid_local_login_binary_is_hash_checked_without_download(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'bin').mkdir()
            binary = base / 'bin/login'
            binary.write_bytes(b'pinned login test bytes')
            asset = {'name': 'login', 'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}
            with patch.object(service, 'BASE', base), patch.object(service, 'prepare'), \
                    patch.object(service, 'current_binary', return_value=({'version': 'test'}, 'linux-amd64', asset, binary)), \
                    patch.object(service.urllib.request, 'urlopen') as fetch:
                record = service.install_binary('login')
            fetch.assert_not_called()
            self.assertEqual(record['sha256'], asset['sha256'])
            self.assertEqual(binary.stat().st_mode & 0o777, 0o700)

    def test_visible_login_shares_cookie_path_without_starting_server_or_leaking_child_output(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'logs').mkdir()
            output = io.StringIO()

            def child(args, **kwargs):
                self.assertEqual(args, ['/pinned/login'])
                self.assertEqual(kwargs['cwd'], base)
                self.assertEqual(kwargs['env']['COOKIES_PATH'], str(base / 'cookies.json'))
                self.assertNotIn('AUTH_TOKEN', kwargs['env'])
                self.assertEqual(kwargs['umask'], 0o077)
                kwargs['stdout'].write(b'private upstream detail')
                return types.SimpleNamespace(returncode=0)

            with patch.object(service, 'BASE', base), patch.object(service.platform, 'system', return_value='Darwin'), \
                    patch.object(service, 'install_binary', return_value={'binary': '/pinned/login'}) as installer, \
                    patch.object(service.subprocess, 'run', side_effect=child), \
                    patch.object(service, 'run_server') as server, \
                    patch.dict(os.environ, {'AUTH_TOKEN': 'never_echo_this'}), redirect_stdout(output):
                service.login()
            installer.assert_called_once_with('login')
            server.assert_not_called()
            self.assertNotIn('never_echo_this', output.getvalue())
            self.assertNotIn('private upstream detail', output.getvalue())
            messages = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertTrue(messages[-1]['verification_required'])
            self.assertEqual(list((base / 'logs').iterdir())[0].stat().st_mode & 0o777, 0o600)

    def test_linux_without_desktop_does_not_start_login(self):
        with patch.object(service.platform, 'system', return_value='Linux'), \
                patch.dict(os.environ, {}, clear=True), patch.object(service, 'install_binary') as install, \
                self.assertRaisesRegex(ValueError, 'desktop'):
            service.login()
        install.assert_not_called()


if __name__ == '__main__':
    unittest.main()
