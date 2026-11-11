"""Account preference propagation, isolated from credentials and model calls."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import shutil


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'scripts/workbuddy-pool-sync.rb'
DSH = Path('/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh')
ROLE = 'omb-wf-manager'
A, B, C = '1' * 24, '2' * 24, '3' * 24


def read_yaml(path):
    result = subprocess.run(['/usr/bin/ruby', '-ryaml', '-rjson', '-e',
                             'puts JSON.generate(YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], permitted_symbols: [], aliases: false))',
                             str(path)], text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


class PoolSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='pool prefs ')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.desktop = self.home / 'profiles/desktop/cordis.patch.yml'
        self.target = self.home / f'profiles/{ROLE}/cordis.patch.yml'
        self.desktop.parent.mkdir(parents=True)
        self.target.parent.mkdir(parents=True)
        self.source_config = {
            'accounts': {'cn': {'accountId': C}},
            'regions': {
                'cn': {'enabled': True, 'lastCatalog': [{'id': 'source-model'}],
                       'pool': {'enabled': True, 'memberAccountIds': [A, B], 'orderAccountIds': [B, A], 'targetModelId': 'source-probe'}},
                'global': {'enabled': True, 'pool': {'enabled': False, 'memberAccountIds': [], 'orderAccountIds': []}},
            },
        }
        self.target_config = {
            'accounts': {'cn': {'accountId': A}},
            'regions': {
                'cn': {'enabled': True, 'lastCatalog': [{'id': 'target-model', 'maxTokens': 4096}],
                       'pool': {'enabled': False, 'memberAccountIds': [C], 'orderAccountIds': [], 'targetModelId': 'target-probe', 'probeInputTokens': 0}},
                'global': {'enabled': True, 'pool': {'enabled': False, 'memberAccountIds': [], 'orderAccountIds': []}},
            },
            'imageToolEnabled': False,
        }
        self.write_configs()

    def write_configs(self):
        # JSON is a valid YAML subset and avoids a test-only YAML dependency.
        self.desktop.write_text(json.dumps([{'id': 'dsh-connect-workbuddy', 'config': self.source_config}]))
        self.target.write_text(json.dumps([{'id': 'dsh-connect-workbuddy', 'name': 'dsh-connect-workbuddy', 'config': self.target_config}]))

    def run_helper(self, mode='--prepare', *, profile=ROLE, good=True):
        result = subprocess.run(['/usr/bin/ruby', str(HELPER), '--home', str(self.home),
                                 '--profile', profile, mode, '--owner-pid', str(os.getpid())],
                                cwd=ROOT, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode == 0, good, result.stderr)
        return result

    def test_overlay_changes_only_three_pool_fields_and_keeps_target_configuration(self):
        original = {p: p.read_bytes() for p in (self.desktop, self.target)}
        result = self.run_helper()
        overlay = Path(result.stdout.strip())
        self.assertTrue(overlay.is_file())
        composed = read_yaml(overlay)[0]['config']
        expected = json.loads(json.dumps(self.target_config))
        for region in ('cn', 'global'):
            for key in ('enabled', 'memberAccountIds', 'orderAccountIds'):
                expected['regions'][region]['pool'][key] = self.source_config['regions'][region]['pool'][key]
        self.assertEqual(composed, expected)
        self.assertNotIn('source-model', overlay.read_text())
        self.assertEqual(composed['accounts'], self.target_config['accounts'])
        for path, before in original.items():
            self.assertEqual(path.read_bytes(), before)
        self.assertEqual(overlay.stat().st_mode & 0o777, 0o600)
        self.assertEqual(overlay.parent.stat().st_mode & 0o777, 0o700)
        self.assertNotIn(A, result.stderr)
        self.assertNotIn(B, result.stderr)
        self.assertNotIn(C, result.stderr)
        meta = json.loads(Path(str(overlay) + '.meta.json').read_text())
        self.assertEqual(meta['regions']['cn'], {'enabled': True, 'members': 2, 'ordered': 2})

    def test_desktop_edit_is_loaded_on_next_start_without_changing_first_overlay(self):
        first = Path(self.run_helper().stdout.strip())
        original = first.read_bytes()
        self.source_config['regions']['cn']['pool'].update(enabled=False, memberAccountIds=[B], orderAccountIds=[])
        self.write_configs()
        second = Path(self.run_helper().stdout.strip())
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), original)
        self.assertEqual(read_yaml(second)[0]['config']['regions']['cn']['pool']['memberAccountIds'], [B])
        self.assertFalse(read_yaml(second)[0]['config']['regions']['cn']['pool']['enabled'])

    def test_check_is_nonmutating_and_works_before_new_profile_exists(self):
        self.target.unlink()
        result = self.run_helper('--check')
        self.assertTrue(json.loads(result.stdout)['source_valid'])
        self.assertFalse((self.home / 'workflour-pool-overlays').exists())
        self.assertFalse(self.target.exists())

    def test_only_current_six_workflow_profiles_are_allowed(self):
        for role in ('omb-coder', 'agent-doc', 'omb-manager', 'omb-wf-code-main', '../desktop'):
            with self.subTest(role=role):
                self.run_helper('--check', profile=role, good=False)
        self.assertFalse((self.home / 'workflour-pool-overlays').exists())

    def test_malformed_source_or_missing_pool_fails_without_old_settings_fallback(self):
        original = self.target.read_bytes()
        self.desktop.write_text('- id: dsh-connect-workbuddy\n  config: [broken\n')
        result = self.run_helper(good=False)
        self.assertIn('refusing to start', result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertNotIn('[broken', result.stderr)
        self.assertEqual(self.target.read_bytes(), original)
        self.write_configs()
        del self.source_config['regions']['cn']['pool']
        self.write_configs()
        self.run_helper(good=False)
        self.assertFalse((self.home / 'workflour-pool-overlays').exists())

    def test_no_empty_enabled_pool_unchecked_order_or_invalid_member_is_accepted(self):
        for pool in (
            {'enabled': True, 'memberAccountIds': [], 'orderAccountIds': []},
            {'enabled': True, 'memberAccountIds': [A], 'orderAccountIds': [C]},
            {'enabled': 'true', 'memberAccountIds': [A], 'orderAccountIds': []},
            {'enabled': True, 'memberAccountIds': [A, A], 'orderAccountIds': []},
            {'enabled': True, 'memberAccountIds': ['secret-account-value'], 'orderAccountIds': []},
        ):
            with self.subTest(pool=pool):
                self.source_config['regions']['cn']['pool'] = pool
                self.write_configs()
                result = self.run_helper(good=False)
                self.assertNotIn('secret-account-value', result.stderr)

    def test_inline_target_secrets_are_rejected_without_copying_or_printing_them(self):
        self.target_config['accounts']['cn']['accessToken'] = 'unprintable-secret-value'
        self.write_configs()
        result = self.run_helper(good=False)
        self.assertNotIn('unprintable-secret-value', result.stdout + result.stderr)
        self.assertFalse((self.home / 'workflour-pool-overlays').exists())

    def test_stale_own_overlays_are_removed_but_live_and_unrelated_files_remain(self):
        first = Path(self.run_helper().stdout.strip())
        stale = first.parent / 'pool-99999999-aaaaaaaaaaaaaaaa.yml'
        stale.write_text('stale')
        unrelated = first.parent / 'not-ours.yml'
        unrelated.write_text('keep')
        target = first.parent / 'user-target.txt'
        target.write_text('untouched')
        link = first.parent / 'pool-99999999-bbbbbbbbbbbbbbbb.yml'
        link.symlink_to(target)
        self.run_helper()
        self.assertFalse(stale.exists())
        self.assertTrue(first.exists())
        self.assertEqual(unrelated.read_text(), 'keep')
        self.assertTrue(link.is_symlink())
        self.assertEqual(target.read_text(), 'untouched')

    def test_launcher_keeps_protocol_stdout_clean_and_limits_sync_to_new_roles(self):
        launcher_root = self.home / 'launcher'
        (launcher_root / 'scripts').mkdir(parents=True)
        integration = launcher_root / 'integrations/openmausbot'
        integration.mkdir(parents=True)
        shutil.copyfile(HELPER, launcher_root / 'scripts/workbuddy-pool-sync.rb')
        (integration / 'acp-resume-bridge.py').write_text(
            'import os,sys,json\nprint(json.dumps({"argv":sys.argv[1:],"policy":os.environ.get("WORKFLOUR_QUOTA_POLICY")}))\n')
        fake_dsh = self.home / 'dummy dsh'
        fake_dsh.write_text('#!/bin/sh\nexit 93\n')
        fake_dsh.chmod(0o700)
        launcher = launcher_root / 'run-acp-agent.sh'
        original = (ROOT / 'run-acp-agent.sh').read_text()
        original = original.replace(f'DSH_BIN="{DSH}"', f'DSH_BIN="{fake_dsh}"')
        launcher.write_text(original)
        env = {**os.environ, 'DSH_HOME': str(self.home), 'WORKFLOUR_QUOTA_POLICY': 'enabled'}
        (self.home / 'profiles/omb-coder').mkdir()
        for role, overlay_count, policy in [('coder', 2, None), ('wf-manager', 3, 'enabled')]:
            with self.subTest(role=role):
                result = subprocess.run(['/bin/bash', str(launcher), role], env=env,
                                        text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                # One bridge JSON line only, no helper diagnostics on ACP stdout.
                answer = json.loads(result.stdout)
                self.assertEqual(answer['policy'], policy)
                self.assertEqual(answer['argv'].count('--patch'), overlay_count)
                self.assertIn('session-title/cordis.patch.yml', answer['argv'][-3])
                self.assertIn('model-fallback/cordis.patch.yml', answer['argv'][-1])
        self.desktop.unlink()
        failed = subprocess.run(['/bin/bash', str(launcher), 'wf-manager'], env=env,
                                text=True, capture_output=True, timeout=10)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(failed.stdout, '')
        self.assertIn('refusing to start', failed.stderr)

    @unittest.skipUnless(DSH.is_file(), 'local Harness CLI unavailable')
    def test_native_cordis_composition_preserves_full_target_and_following_plugins(self):
        patch = Path(self.run_helper().stdout.strip())
        profile = self.target.parent
        (profile / 'package.json').write_text(json.dumps({'name': 'fixture', 'dsh': {'profile': {'bundles': []}}}))
        (profile / 'cordis.yml').write_text('[]\n')
        # Native Cordis inserts the test entry, then the generated overlay updates
        # its full config. --dump-config composes only; no plugin/model is mounted.
        self.target.write_text(json.dumps([{'insert': [
            {'id': 'dsh-connect-workbuddy', 'name': 'fake-workbuddy', 'config': self.target_config},
            {'id': 'llm-defaults', 'name': 'fake-default', 'config': {'provider': 'workbuddy', 'model': 'keep-model'}},
        ]}]))
        extras = self.home / 'following.yml'
        extras.write_text(json.dumps([{'insert': [
            {'id': 'workflour-session-title', 'name': 'not-mounted-title'},
            {'id': 'workflour-model-fallback', 'name': 'not-mounted-fallback'},
        ]}]))
        result = subprocess.run([str(DSH), '--profile', ROLE, '--patch', str(patch), '--patch', str(extras), '--dump-config'],
                                env={**os.environ, 'DSH_HOME': str(self.home)}, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('not found', result.stderr)
        composed_path = self.home / 'composed.yml'
        composed_path.write_text(result.stdout)
        entries = {entry['id']: entry for entry in read_yaml(composed_path)}
        config = entries['dsh-connect-workbuddy']['config']
        self.assertTrue(config['regions']['cn']['pool']['enabled'])
        self.assertEqual(config['regions']['cn']['pool']['memberAccountIds'], [A, B])
        self.assertEqual(config['regions']['cn']['pool']['targetModelId'], 'target-probe')
        self.assertEqual(config['regions']['cn']['lastCatalog'], self.target_config['regions']['cn']['lastCatalog'])
        self.assertEqual(config['accounts'], self.target_config['accounts'])
        self.assertEqual(entries['llm-defaults']['config']['model'], 'keep-model')
        self.assertIn('workflour-session-title', entries)
        self.assertIn('workflour-model-fallback', entries)


if __name__ == '__main__':
    unittest.main()
