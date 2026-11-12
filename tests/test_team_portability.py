"""Isolated relocation checks; fake CLI/bridge only, no accounts or model calls."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ROLES = ('wf-manager', 'wf-plan-lead', 'wf-plan-review',
         'wf-code-review', 'wf-code-helper', 'wf-assistant')


def read_yaml(path):
    result = subprocess.run(['/usr/bin/ruby', '-r', 'yaml', '-r', 'json', '-e',
        'puts JSON.generate(YAML.safe_load(File.read(ARGV[0]), aliases: false))', str(path)],
        text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


class TeamPortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        # YAML-significant punctuation, whitespace and a backslash must remain
        # literal. Nothing is executed from the developer's real home/profile.
        self.repo = self.base / 'checkout : # "quoted" \\team'
        integration = self.repo / 'integrations/openmausbot'
        integration.mkdir(parents=True)
        (self.repo / 'scripts').mkdir()
        shutil.copyfile(ROOT / 'integrations/openmausbot/setup.sh', integration / 'setup.sh')
        shutil.copytree(ROOT / 'integrations/openmausbot/profiles', integration / 'profiles')
        shutil.copytree(ROOT / 'agents', self.repo / 'agents', symlinks=True)
        # Only declarative XHS choices are needed to check the shared setup path.
        (integration / 'team-xhs').mkdir()
        shutil.copyfile(ROOT / 'integrations/openmausbot/team-xhs/models.json', integration / 'team-xhs/models.json')
        shutil.copyfile(ROOT / 'run-acp-agent.sh', self.repo / 'run-acp-agent.sh')
        shutil.copyfile(ROOT / 'scripts/workbuddy-pool-sync.rb', self.repo / 'scripts/workbuddy-pool-sync.rb')
        for component in ('session-title', 'model-fallback'):
            folder = integration / component
            folder.mkdir()
            shutil.copyfile(ROOT / 'integrations/openmausbot' / component / 'cordis.patch.yml', folder / 'cordis.patch.yml')
            (folder / 'plugin.mjs').write_text('// fixture; never imported or executed\n')
        (integration / 'acp-resume-bridge.py').write_text(
            'import json,os,sys\nprint(json.dumps({"argv":sys.argv[1:],'
            '"policy":os.environ.get("WORKFLOUR_QUOTA_POLICY")}))\n')
        self.home = self.base / 'private home'
        self.dsh = self.home / '.dsh'
        self.omb = self.home / '.openmausbot'
        self.source = self.dsh / 'profiles/web'
        (self.source / 'node_modules').mkdir(parents=True)
        self.account = {'marker': 'fresh-web-fixture', 'regions': {
            region: {'pool': {'enabled': False, 'memberAccountIds': [], 'orderAccountIds': []}}
            for region in ('cn', 'global')}}
        self.source_patch = self.source / 'cordis.patch.yml'
        self.source_patch.write_text('- id: dsh-connect-workbuddy\n  config: ' + json.dumps(self.account) + '\n')
        self.omb.mkdir(parents=True)
        self.config = self.omb / 'config.json'
        self.original_config = {'other': True, 'instances': {'unrelated': {'driver': 'keep'}}}
        self.config.write_text(json.dumps(self.original_config))
        self.cli_log = self.base / 'fake-cli.log'
        self.cli = self.base / 'fake dsh'
        self.cli.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$FAKE_DSH_LOG"\n'
                            'if [ "$1" = "--version" ]; then printf "fixture\\n"; exit 0; fi\nexit 93\n')
        self.cli.chmod(0o700)
        self.env = {**os.environ, 'HOME': str(self.home), 'DSH_HOME': str(self.dsh),
                    'OMB_DATA_DIR': str(self.omb), 'DSH_BIN': str(self.cli),
                    'WORKFLOUR_DSH_SOURCE_PROFILE': 'web', 'FAKE_DSH_LOG': str(self.cli_log)}

    def setup_role(self, role, success=True):
        result = subprocess.run(['bash', str(self.repo / 'integrations/openmausbot/setup.sh'), '--only', role],
                                env=self.env, text=True, capture_output=True, timeout=15)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def launch(self, role, success=True):
        result = subprocess.run(['bash', str(self.repo / 'run-acp-agent.sh'), role],
                                env=self.env, text=True, capture_output=True, timeout=15)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        return result

    def test_all_six_dsh_roles_use_web_without_historical_profiles_and_resolve_skills(self):
        original = self.source_patch.read_bytes()
        for role in ROLES:
            with self.subTest(role=role):
                self.setup_role(role)
                profile = self.dsh / 'profiles' / ('omb-' + role)
                data = {row['id']: row for row in read_yaml(profile / 'cordis.patch.yml')}
                declared = {row['id']: row for row in read_yaml(
                    self.repo / 'integrations/openmausbot/profiles' / (role + '.patch.yml'))}
                self.assertEqual(data['acp'], declared['acp'], 'Relocation must not change the declared model')
                skill_dir = self.repo / 'agents' / role / 'skills'
                self.assertEqual(data['skill-filesystem']['config']['customSkillDirs'], [str(skill_dir)])
                self.assertTrue(skill_dir.is_dir())
                self.assertTrue((skill_dir / (role + '-role') / 'SKILL.md').is_file())
                persona = data['system-prompt']['config']['personaPrefix']
                for name in ('SOUL.md', 'SKILLS.md'):
                    self.assertIn(str(self.repo / 'agents' / role / name), persona)
                    self.assertTrue((self.repo / 'agents' / role / name).is_file())
                self.assertEqual(data['dsh-connect-workbuddy']['config'], self.account)
                self.assertEqual((profile / 'node_modules').resolve(), (self.source / 'node_modules').resolve())
                self.assertEqual((profile / 'cordis.patch.yml').stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.source_patch.read_bytes(), original)
        self.assertFalse((self.dsh / 'profiles/omb-doc').exists())
        self.assertFalse((self.dsh / 'profiles/agent-doc').exists())
        self.assertFalse(self.cli_log.exists(), 'No native CLI call should be needed for saved Web config')
        self.assertEqual(json.loads(self.config.read_text())['instances']['unrelated'], {'driver': 'keep'})

    def test_seventh_role_registers_agy_without_dsh_and_preserves_other_instances(self):
        self.env.update(DSH_HOME=str(self.base / 'absent dsh'), DSH_BIN='/missing-dsh')
        self.setup_role('wf-code-main')
        self.assertFalse(Path(self.env['DSH_HOME']).exists())
        instances = json.loads(self.config.read_text())['instances']
        self.assertEqual(set(instances), {'unrelated', 'agy-gemini'})
        self.assertEqual(instances['unrelated'], {'driver': 'keep'})
        self.assertIn(str(self.repo / 'run-agy-agent.sh'), instances['agy-gemini']['config']['cli'])

    def test_existing_target_account_state_is_preserved_on_rerun(self):
        self.setup_role('wf-manager')
        patch = self.dsh / 'profiles/omb-wf-manager/cordis.patch.yml'
        patch.write_text(patch.read_text().replace('fresh-web-fixture', 'target-updated'))
        self.setup_role('wf-manager')
        data = {row['id']: row for row in read_yaml(patch)}
        self.assertEqual(data['dsh-connect-workbuddy']['config']['marker'], 'target-updated')
        self.assertIn('fresh-web-fixture', self.source_patch.read_text())

    def test_xhs_and_root_placeholder_remain_supported(self):
        self.setup_role('xhs-planner')
        patch = self.dsh / 'profiles/omb-xhs-planner/cordis.patch.yml'
        data = {row['id']: row for row in read_yaml(patch)}
        self.assertEqual(data['skill-filesystem']['config']['customSkillDirs'],
                         [str(self.repo / 'agents/xhs-planner/skills')])
        template = self.repo / 'integrations/openmausbot/profiles/wf-manager.patch.yml'
        text = template.read_text().replace('/Users/a1/Documents/a/workflour', '{{ROOT}}')
        # Curly-brace placeholders must themselves be valid YAML strings.
        text = text.replace('- {{ROOT}}/agents/wf-manager/skills', '- "{{ROOT}}/agents/wf-manager/skills"')
        template.write_text(text)
        self.setup_role('wf-manager')
        data = {row['id']: row for row in read_yaml(self.dsh / 'profiles/omb-wf-manager/cordis.patch.yml')}
        self.assertEqual(data['skill-filesystem']['config']['customSkillDirs'],
                         [str(self.repo / 'agents/wf-manager/skills')])

    def test_missing_role_skill_directory_does_not_replace_existing_patch(self):
        self.setup_role('wf-manager')
        patch = self.dsh / 'profiles/omb-wf-manager/cordis.patch.yml'
        before = patch.read_bytes()
        shutil.rmtree(self.repo / 'agents/wf-manager/skills')
        self.setup_role('wf-manager', success=False)
        self.assertEqual(patch.read_bytes(), before)

    def test_private_plugins_resolve_checkout_and_keep_original_templates_and_stdout(self):
        self.setup_role('wf-manager')
        originals = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in (self.repo / 'integrations/openmausbot').glob('*/cordis.patch.yml')}
        result = self.launch('wf-manager')
        self.assertEqual(result['policy'], 'enabled')
        self.assertEqual(result['argv'].count('--patch'), 3)
        for component, arg in (('session-title', result['argv'][-3]), ('model-fallback', result['argv'][-1])):
            path = Path(arg)
            self.assertTrue(path.is_relative_to(self.dsh))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            row = read_yaml(path)[0]['insert'][0]
            self.assertEqual(row['name'], str((self.repo / 'integrations/openmausbot' / component / 'plugin.mjs').resolve()))
            self.assertEqual(row['id'], 'workflour-' + component)
        repeated = self.launch('wf-manager')
        self.assertEqual(repeated['argv'][-4:], result['argv'][-4:])
        self.assertEqual(originals, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in originals})
        self.assertFalse(self.cli_log.exists())
        # Legacy roles keep two plugin layers and do not acquire quota policy.
        (self.dsh / 'profiles/omb-coder').mkdir()
        self.env['WORKFLOUR_QUOTA_POLICY'] = 'enabled'
        legacy = self.launch('coder')
        self.assertIsNone(legacy['policy'])
        self.assertEqual(legacy['argv'].count('--patch'), 2)

    def test_missing_plugin_fails_before_bridge_or_cli_and_version_probe_still_works(self):
        self.setup_role('wf-manager')
        (self.repo / 'integrations/openmausbot/model-fallback/plugin.mjs').unlink()
        result = self.launch('wf-manager', success=False)
        self.assertIn('refusing to start', result.stderr)
        self.assertFalse(self.cli_log.exists())
        version = subprocess.run(['bash', str(self.repo / 'run-acp-agent.sh'), 'wf-manager', '--version'],
                                 env=self.env, text=True, capture_output=True, timeout=10)
        self.assertEqual((version.returncode, version.stdout), (0, 'fixture\n'))


if __name__ == '__main__':
    unittest.main()
