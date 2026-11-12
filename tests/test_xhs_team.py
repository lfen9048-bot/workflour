"""Isolated native provisioning and selective setup; no model requests or real IDs."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('xhs_team', ROOT / 'scripts/provision-xhs-team.py')
team = importlib.util.module_from_spec(spec)
spec.loader.exec_module(team)


class NativeFixture:
    def __init__(self):
        self.bots = {'old-code': {'id': 'old-code', 'name': 'Existing code team',
                                 'soul': 'Keep existing instructions', 'cwd': '/existing/project',
                                 'modelSelection': {'instanceId': 'old-profile', 'model': 'manual'},
                                 'section': 'Code Team', 'approvalMode': 'full', 'tasks': []}}
        self.writes = []
        self.instances = [{'instanceId': role['instance'], 'models': {'options': [
            {'id': role['modelId'], 'variants': [{'id': role['thinking']}]}]}}
                          for role in team.declarations()]

    def call(self, method, path, body=None):
        if method == 'GET':
            return copy.deepcopy({'instances': self.instances} if path == '/api/instances'
                                 else {'bots': list(self.bots.values())})
        self.writes.append((method, path, copy.deepcopy(body)))
        if method == 'POST' and path == '/api/bots':
            self.bots[body['id']] = {'id': body['id'], **copy.deepcopy(body['settings']), 'tasks': []}
            return {'bot': copy.deepcopy(self.bots[body['id']])}
        if method == 'PATCH':
            bid = path.split('/')[3]
            self.bots[bid].update(copy.deepcopy(body))
            return {'bot': copy.deepcopy(self.bots[bid])}
        raise AssertionError('Unexpected API operation')


class XhsNativeProvisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'private' / 'deployment.json'
        self.deployment = team.manifest(self.path, create=True)
        self.client = NativeFixture()

    def test_three_new_bots_are_idempotent_and_preserve_manual_models_and_other_team(self):
        old = copy.deepcopy(self.client.bots['old-code'])
        result = team.provision(self.client, self.deployment, 'create')
        self.assertEqual(len(self.client.bots), 4)
        self.assertTrue(result['other_bots_configuration_matches_snapshot'])
        self.assertEqual(self.client.bots['old-code'], old)
        self.assertEqual(len([r for r in self.client.writes if r[0] == 'POST']), 3)
        planner = next(r for r in self.deployment['roles'] if r['key'] == 'xhs-planner')
        bot = self.client.bots[planner['botId']]
        bot['modelSelection'] = {'instanceId': 'manual-runtime', 'model': 'user-model'}
        self.client.writes.clear()
        again = team.provision(self.client, self.deployment, 'create')
        self.assertEqual(self.client.writes, [])
        self.assertEqual(len(self.client.bots), 4)
        self.assertEqual(bot['modelSelection']['model'], 'user-model')
        self.assertFalse(next(r for r in again['roles'] if r['role'] == 'xhs-planner')['initial_model_matches'])
        self.assertFalse(any('order' in path or 'messages' in path for _, path, _ in self.client.writes))

    def test_unknown_ownership_and_missing_catalog_fail_before_any_native_mutation(self):
        self.deployment['roles'][0]['botId'] = 'old-code'
        with self.assertRaisesRegex(team.control.ControlError, 'belongs to another'):
            team.provision(self.client, self.deployment, 'instructions')
        self.assertEqual(self.client.writes, [])
        self.deployment = team.manifest(self.path)
        self.client.instances[-1]['models']['options'] = []
        with self.assertRaises(team.control.ControlError):
            team.provision(self.client, self.deployment, 'create')
        self.assertEqual(self.client.writes, [])

    def test_instructions_check_all_targets_idle_before_first_patch(self):
        team.provision(self.client, self.deployment, 'create')
        self.client.bots[self.deployment['roles'][-1]['botId']]['tasks'] = [{'busy': True}]
        self.client.writes.clear()
        with self.assertRaisesRegex(team.control.ControlError, 'idle'):
            team.provision(self.client, self.deployment, 'instructions')
        self.assertEqual(self.client.writes, [])

    def test_instructions_render_current_root_without_overwriting_model(self):
        team.provision(self.client, self.deployment, 'create')
        manual = {'instanceId': 'custom', 'model': 'manual', 'variant': 'medium'}
        writer = self.deployment['roles'][-1]
        self.client.bots[writer['botId']]['modelSelection'] = manual
        self.client.writes.clear()
        team.provision(self.client, self.deployment, 'instructions')
        self.assertEqual(len(self.client.writes), 3)
        self.assertTrue(all(set(body) == {'soul'} for _, _, body in self.client.writes))
        self.assertEqual(self.client.bots[writer['botId']]['modelSelection'], manual)
        for role in self.deployment['roles']:
            soul = self.client.bots[role['botId']]['soul']
            self.assertNotIn('{{ROOT}}', soul)
            self.assertIn(str(ROOT), soul)
            for row in self.deployment['roles']:
                self.assertIn(row['botId'], soul)

    def test_machine_ids_are_private_and_portable_sources_remain_relative(self):
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        saved = json.loads(self.path.read_text())
        self.assertEqual(team.manifest(self.path)['roles'], saved['roles'])
        for role in team.declarations():
            self.assertFalse(Path(role['soulFile']).is_absolute())
            self.assertFalse(Path(role['skillsFile']).is_absolute())
            self.assertNotIn('botId', role)


class XhsSelectiveSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xhs setup ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'dsh'
        self.omb = self.base / 'omb'
        desktop = self.home / 'profiles/desktop'
        (desktop / 'node_modules').mkdir(parents=True)
        self.config = {'regions': {'cn': {'enabled': True, 'pool': {
            'enabled': True, 'memberAccountIds': ['1' * 24], 'orderAccountIds': ['1' * 24]}},
            'global': {'enabled': True, 'pool': {'enabled': False, 'memberAccountIds': [], 'orderAccountIds': []}}}}
        entry = '- id: dsh-connect-workbuddy\n  config: ' + json.dumps(self.config) + '\n'
        (desktop / 'cordis.patch.yml').write_text(entry)
        self.doc = self.home / 'profiles/omb-doc/cordis.patch.yml'
        self.doc.parent.mkdir()
        self.doc.write_text(entry)
        self.omb.mkdir()
        self.omb_config = self.omb / 'config.json'
        self.old = {'unrelated': True, 'instances': {'old-instance': {'driver': 'customAcp', 'config': {'cli': 'keep'}}}}
        self.omb_config.write_text(json.dumps(self.old))
        self.fake_dsh = self.base / 'dummy dsh'
        self.fake_dsh.write_text('#!/bin/sh\nprintf "fixture-dsh\\n"\n')
        self.fake_dsh.chmod(0o700)
        self.env = {**os.environ, 'DSH_BIN': str(self.fake_dsh), 'DSH_HOME': str(self.home), 'OMB_DATA_DIR': str(self.omb)}

    def run_setup(self, role):
        p = subprocess.run(['bash', str(ROOT / 'integrations/openmausbot/setup.sh'), '--only', role],
                           env=self.env, cwd=ROOT, text=True, capture_output=True, timeout=15)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def test_two_profiles_use_portable_templates_and_do_not_touch_other_instances(self):
        original = self.doc.read_bytes()
        for role in ('xhs-collector', 'xhs-planner'):
            self.run_setup(role)
            profile = self.home / f'profiles/omb-{role}'
            patch = (profile / 'cordis.patch.yml').read_text()
            self.assertIn(str(ROOT / 'agents' / role / 'skills'), patch)
            self.assertNotIn('@WORKSPACE_ROOT@', patch)
            self.assertEqual(patch.count('- id: dsh-connect-workbuddy'), 1)
            self.run_setup(role)
            self.assertEqual((profile / 'cordis.patch.yml').read_text(), patch)
        self.assertEqual(self.doc.read_bytes(), original)
        cfg = json.loads(self.omb_config.read_text())
        self.assertEqual(cfg['instances']['old-instance'], self.old['instances']['old-instance'])
        self.assertEqual(set(cfg['instances']), {'old-instance', 'omb-xhs-collector', 'omb-xhs-planner'})

    def test_writer_registers_only_agy_without_any_dsh_installation(self):
        empty_dsh = self.base / 'no-dsh'
        self.env.update(DSH_HOME=str(empty_dsh), DSH_BIN='/does-not-exist')
        self.run_setup('xhs-writer')
        self.assertFalse(empty_dsh.exists())
        cfg = json.loads(self.omb_config.read_text())
        self.assertEqual(set(cfg['instances']), {'old-instance', 'agy-gemini'})
        self.assertTrue(cfg['instances']['agy-gemini']['config']['cli'].endswith('/run-agy-agent.sh'))

    def test_new_roles_enable_private_pool_and_budget_layer_with_clean_protocol_stdout(self):
        fixture = self.base / 'launcher'
        (fixture / 'scripts').mkdir(parents=True)
        (fixture / 'integrations/openmausbot').mkdir(parents=True)
        shutil.copyfile(ROOT / 'run-acp-agent.sh', fixture / 'run-acp-agent.sh')
        shutil.copyfile(ROOT / 'scripts/workbuddy-pool-sync.rb', fixture / 'scripts/workbuddy-pool-sync.rb')
        (fixture / 'integrations/openmausbot/acp-resume-bridge.py').write_text(
            'import json,os,sys\nprint(json.dumps({"args":sys.argv[1:],"policy":os.environ.get("WORKFLOUR_QUOTA_POLICY")}))\n')
        source_before = (self.home / 'profiles/desktop/cordis.patch.yml').read_bytes()
        for role in ('xhs-collector', 'xhs-planner'):
            self.run_setup(role)
            p = subprocess.run(['bash', str(fixture / 'run-acp-agent.sh'), role], env=self.env,
                               text=True, capture_output=True, timeout=10)
            self.assertEqual(p.returncode, 0, p.stderr)
            parsed = json.loads(p.stdout)
            self.assertEqual(parsed['policy'], 'enabled')
            self.assertEqual(parsed['args'].count('--patch'), 3)
            self.assertIn('model-fallback/cordis.patch.yml', parsed['args'][-1])
        self.assertEqual((self.home / 'profiles/desktop/cordis.patch.yml').read_bytes(), source_before)

    def test_fresh_web_profile_needs_no_historical_mac_doc_profile(self):
        desktop = self.home / 'profiles/desktop'
        web = self.home / 'profiles/web'
        desktop.rename(web)
        self.doc.unlink()
        self.env['WORKFLOUR_DSH_SOURCE_PROFILE'] = 'web'
        original = (web / 'cordis.patch.yml').read_bytes()
        for role in ('xhs-collector', 'xhs-planner'):
            self.run_setup(role)
            profile = self.home / f'profiles/omb-{role}'
            self.assertEqual((profile / 'node_modules').resolve(), (web / 'node_modules').resolve())
            self.assertIn('dsh-connect-workbuddy', (profile / 'cordis.patch.yml').read_text())
        self.assertEqual((web / 'cordis.patch.yml').read_bytes(), original)

    def test_launcher_accepts_explicit_binary_and_linux_path_fallback(self):
        p = subprocess.run(['bash', str(ROOT / 'run-acp-agent.sh'), 'xhs-collector', '--version'],
                           env=self.env, text=True, capture_output=True, timeout=10)
        self.assertEqual((p.returncode, p.stdout), (0, 'fixture-dsh\n'))
        launcher = self.base / 'launcher.sh'
        launcher.write_text((ROOT / 'run-acp-agent.sh').read_text().replace(
            'DSH_BIN="/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh"',
            'DSH_BIN="/missing-Mac-installation"'))
        bin_dir = self.base / 'bin'
        bin_dir.mkdir()
        shutil.copyfile(self.fake_dsh, bin_dir / 'dsh')
        (bin_dir / 'dsh').chmod(0o700)
        env = {k: v for k, v in self.env.items() if k != 'DSH_BIN'}
        env['PATH'] = str(bin_dir) + os.pathsep + env['PATH']
        p = subprocess.run(['bash', str(launcher), 'xhs-planner', '--version'],
                           env=env, text=True, capture_output=True, timeout=10)
        self.assertEqual((p.returncode, p.stdout), (0, 'fixture-dsh\n'))


if __name__ == '__main__':
    unittest.main()
