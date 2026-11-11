"""Plan/Code regressions: real phase ownership, evidence freshness and bounded repair."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / file)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
ledger = load('plan_code_ledger', 'coordinator-workflow.py')
checker = load('plan_code_checker', 'workflow-check.py')
initializer = load('plan_code_initializer', 'new-project.py')
observer = load('plan_code_observer', 'workflow-observer.py')


class PlanCodeLedgerTests(unittest.TestCase):
    def setUp(self):
        self.state = {'workflow': 'plan-code', 'workflow_version': 2, 'phase': 'research',
                      'assignments': {}, 'coordinator_thread': 'lead-thread'}

    def finish(self, phase, role, suffix=''):
        ledger.apply(self.state, 'claim', phase, role)
        ledger.apply(self.state, 'receipt', phase, role, phase + role + suffix)
        ledger.apply(self.state, 'result', phase, role, status='completed', evidence=phase+'.md')

    def test_one_coder_default_real_peer_review_and_local_lead(self):
        self.assertEqual(ledger.phases_for(self.state)['implement'], ['code-main'])
        with self.assertRaisesRegex(ValueError, 'Use record'):
            ledger.apply(self.state, 'claim', 'research', 'plan-lead')
        ledger.apply(self.state, 'record', 'research', 'plan-lead', evidence='draft.md')
        self.assertNotIn('assignment_id', self.state['assignments']['research/plan-lead'])
        ledger.apply(self.state, 'advance', 'plan-review')
        with self.assertRaises(ValueError): ledger.apply(self.state, 'advance', 'plan')
        self.finish('plan-review', 'plan-review')
        ledger.apply(self.state, 'advance', 'plan')
        ledger.apply(self.state, 'record', 'plan', 'plan-lead', evidence='plan.md')
        ledger.apply(self.state, 'advance', 'implement')
        with self.assertRaises(ValueError): ledger.apply(self.state, 'claim', 'implement', 'code-helper')
        self.finish('implement', 'code-main')
        ledger.apply(self.state, 'advance', 'review')
        self.finish('review', 'code-review')
        ledger.apply(self.state, 'advance', 'experience')
        self.finish('experience', 'plan-review')
        ledger.apply(self.state, 'advance', 'acceptance')
        self.assertEqual(self.state['phase'], 'acceptance')
        with self.assertRaises(ValueError): ledger.apply(self.state, 'claim', 'acceptance', 'plan-lead')

    def test_technical_and_product_repairs_share_two_round_budget(self):
        self.state['phase'] = 'review'
        self.finish('review', 'code-review')
        ledger.apply(self.state, 'rework', evidence='review.md', reason='Technical issue')
        self.assertEqual(self.state['repair_round'], 1)
        self.finish('implement', 'code-main', '1')
        ledger.apply(self.state, 'advance', 'review')
        self.finish('review', 'code-review', '1')
        ledger.apply(self.state, 'advance', 'experience')
        self.finish('experience', 'plan-review', '1')
        ledger.apply(self.state, 'rework', evidence='experience.json', reason='Product issue')
        self.assertEqual(self.state['repair_round'], 2)
        self.assertIn('review/code-review', self.state['assignments'])
        self.assertIn('experience/plan-review@1', self.state['assignments'])
        self.finish('implement', 'code-main', '2')
        ledger.apply(self.state, 'advance', 'review')
        self.finish('review', 'code-review', '2')
        with self.assertRaisesRegex(ValueError, 'exhausted'):
            ledger.apply(self.state, 'rework', evidence='review.md', reason='Third issue')

    def test_local_record_flag_cannot_bypass_worker_or_legacy_receipts(self):
        for state in ({'phase':'planning','assignments':{}}, {'workflow':'plan-code','phase':'implement','assignments':{}}):
            phase = state['phase']
            for role in ledger.phases_for(state)[phase]:
                state['assignments'][phase+'/'+role] = {'status':'completed','evidence':'fake.md','execution':'local'}
            with self.assertRaises(ValueError):
                ledger.apply(state,'advance','plan' if phase == 'planning' else 'review')

    def test_stopped_new_role_retains_resume_and_duplicate_protection(self):
        self.state['phase'] = 'implement'
        ledger.apply(self.state, 'claim', 'implement', 'code-main')
        item = self.state['assignments']['implement/code-main']
        row = {'id':'dispatch', 'bot_id':'main', 'thread_id':'worker', 'status':'cancelled',
               'outcome':'stopped', 'tokens':[item['dispatch_token']]}
        ledger.recover(self.state, 'reconcile', 'implement', 'code-main', [row])
        with self.assertRaisesRegex(ValueError, 'authorization'):
            ledger.recover(self.state, 'retry', 'implement', 'code-main', [row], reason='recover', evidence='inspection.md')
        ledger.recover(self.state, 'retry', 'implement', 'code-main', [row], reason='recover',
                       evidence='inspection.md', resume_authorization='User says continue')
        with self.assertRaisesRegex(ValueError, 'Already claimed'):
            ledger.apply(self.state, 'claim', 'implement', 'code-main')
        self.assertEqual(self.state['attempt_history'][0]['item']['assignment_id'], 'dispatch')

    def test_local_steps_do_not_create_observer_missing_receipt_alert(self):
        ledger.apply(self.state, 'record', 'research', 'plan-lead', evidence='draft.md')
        with tempfile.TemporaryDirectory() as tmp:
            alerts, lines, threads = observer.collect(Path(tmp), self.state, {'code_files': []}, [])
        self.assertEqual(alerts, [])
        self.assertIn('负责人自身工作', ''.join(lines))
        self.assertEqual(threads['lead-thread'], 'plan-lead')
        self.assertIn('方案与体验评审', observer.role_label('plan-review/plan-review'))


class PlanCodeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = initializer.create_project(Path(self.temp.name)/'project', workflow='plan-code')
        (self.root/'app.py').write_text('value = 42\n')
        (self.root/'records').mkdir()
        self.state_path = self.root/'.workflour/handoff.json'
        state = json.loads(self.state_path.read_text())
        state.update(task_id='PC-001', original_request='Show the answer', requirements=[{'id':'R1','criterion':'Show 42'}],
                     code_files=['app.py'], baseline={'app.py':None},
                     work_items=[{'id':'C1','owner':'code-main','files':['app.py'],'status':'completed'}])
        for key in ('spec','plan','tasks','review','verification','acceptance'):
            name = 'records/'+key+'.md'; (self.root/name).write_text('# Actual '+key)
            state['artifacts'][key] = name
        for role in ('plan-lead','plan-review'):
            name = 'records/'+role+'.md'; (self.root/name).write_text('Independent '+role)
            state['planning']['contributions'].append({'owner':role,'record':name})
        state['planning'].update(status='settled', discussion_rounds=1,
            sources=[{'url':'https://docs.python.org/3/','title':'Python','decision':'Use the standard library'}])
        snapshot = {'app.py':checker.digest(self.root/'app.py')}
        state['review'].update(status='passed', snapshot=snapshot)
        self.state_path.write_text(json.dumps(state))
        self.project = checker.Project(self.root)
        with contextlib.redirect_stdout(io.StringIO()):
            self.project.run_test([sys.executable,'-c','print(42)'], detached=True)
        self.record = next((self.root/'.workflour/evidence').glob('*.json'))
        self.project.import_test(str(self.record.relative_to(self.root)))
        self.experience = {'status':'passed','reviewer':'plan-review','browser':'Test fixture browser',
            'url':'http://localhost:8000','at':'2026-11-11T12:00:00+08:00','snapshot':snapshot,
            'checks':[{'requirement':'R1','action':'Open page','observed':'42 is shown','passed':True}],
            'screenshots':[]}
        for name,width in (('desktop',1440),('mobile',390)):
            # Synthetic fixtures only; production requires actual screenshots.
            file = self.root/'records'/f'{name}.png'; file.write_bytes(b'\x89PNG\r\n\x1a\nfixture')
            self.experience['screenshots'].append({'path':str(file.relative_to(self.root)),
                'sha256':checker.digest(file),'viewport':{'width':width,'height':900}})
        log = self.root/'records/browser.json'; log.write_text('[{"action":"open","observed":"42"}]')
        self.experience['interaction_log'] = {'path':'records/browser.json','sha256':checker.digest(log)}
        self.project.state['artifacts']['experience'] = 'records/experience.json'
        self.save_experience()

    def save_experience(self):
        (self.root/'records/experience.json').write_text(json.dumps(self.experience))

    def test_plan_code_template_and_acceptance_are_pending(self):
        self.assertTrue(self.project.check('acceptance')['ok'])
        with self.assertRaisesRegex(checker.InvalidHandoff, 'Explicit user acceptance'):
            self.project.check('done')
        self.assertNotIn('Kimi', (self.root/'PROJECT-WORKFLOW.md').read_text())
        self.assertFalse((self.root/'.workflour/prompts/06-docs.md').exists())
        template = json.loads((self.root/'.workflour/templates/handoff.json').read_text())
        self.assertEqual(template['owner'], 'plan-lead')

    def test_browser_blocked_or_missing_mobile_cannot_be_acceptance(self):
        self.experience['status'] = 'blocked'; self.save_experience()
        with self.assertRaisesRegex(checker.InvalidHandoff, 'blocked'):
            self.project.check('acceptance')
        self.experience['status'] = 'passed'; self.experience['screenshots'].pop(); self.save_experience()
        with self.assertRaisesRegex(checker.InvalidHandoff, 'desktop and mobile'):
            self.project.check('acceptance')

    def test_cli_experience_is_explicit_and_cannot_replace_web_checks(self):
        self.experience.update(surface='cli', command=[sys.executable,'app.py'], exit_code=0)
        self.experience.pop('screenshots'); self.save_experience()
        with self.assertRaisesRegex(checker.InvalidHandoff,'surface must match'):
            self.project.check('acceptance')
        self.project.state['product_surface'] = 'cli'
        self.assertTrue(self.project.check('acceptance')['ok'])
        self.experience['exit_code'] = 1; self.save_experience()
        with self.assertRaisesRegex(checker.InvalidHandoff,'successful exit code'):
            self.project.check('acceptance')

    def test_experience_stale_or_modified_screenshot_is_rejected(self):
        self.experience['snapshot'] = {'app.py':'old'}; self.save_experience()
        with self.assertRaisesRegex(checker.InvalidHandoff, 'current snapshot'):
            self.project.check('acceptance')
        self.experience['snapshot'] = self.project.snapshot(); self.save_experience()
        (self.root/'records/mobile.png').write_bytes(b'changed')
        with self.assertRaisesRegex(checker.InvalidHandoff, 'changed'):
            self.project.check('acceptance')

    def test_omitted_user_goal_and_duplicate_test_import_are_rejected(self):
        self.project.state['requirements'].append({'id':'R2','criterion':'Keyboard interaction'})
        with self.assertRaisesRegex(checker.InvalidHandoff, 'every user'):
            self.project.check('acceptance')
        with self.assertRaisesRegex(checker.InvalidHandoff, 'already imported'):
            self.project.import_test(str(self.record.relative_to(self.root)))

    def test_worker_test_cli_keeps_shared_state_unchanged_and_import_checks_snapshot(self):
        self.project.save(); before = self.state_path.read_bytes()
        proc = subprocess.run([sys.executable,str(self.root/'.workflour/check.py'),'test','--',sys.executable,'-c','print(9)'],capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(before,self.state_path.read_bytes())
        self.assertIn('test_record',proc.stdout)
        (self.root/'app.py').write_text('value = 43')
        with self.assertRaisesRegex(checker.InvalidHandoff,'stale'):
            self.project.import_test(str(self.record.relative_to(self.root)))

    def test_first_worker_can_snapshot_actual_files_without_editing_handoff(self):
        self.project.state['code_files'] = []
        self.project.state['artifacts']['verification'] = ''
        self.project.save()
        before = self.state_path.read_bytes()
        proc = subprocess.run([sys.executable,str(self.root/'.workflour/check.py'),'test',
            '--files','app.py','--',sys.executable,'-c','print(17)'],capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(before,self.state_path.read_bytes())
        records = [json.loads(p.read_text()) for p in (self.root/'.workflour/evidence').glob('*.json')]
        actual = next(r for r in records if 'print(17)' in r['argv'])
        self.assertEqual(actual['snapshot'], {'app.py':checker.digest(self.root/'app.py')})

    def test_import_rejects_result_metadata_that_contradicts_captured_output(self):
        data = json.loads(self.record.read_text()); data['exit_code'] = 7
        self.record.write_text(json.dumps(data))
        with self.assertRaisesRegex(checker.InvalidHandoff,'metadata disagrees'):
            self.project.import_test(str(self.record.relative_to(self.root)))

    def test_worker_cannot_import_or_update_generated_handoff(self):
        before = self.state_path.read_bytes()
        for args in (['import-test',str(self.record.relative_to(self.root))], ['handoff']):
            proc = subprocess.run([sys.executable,str(self.root/'.workflour/check.py'),*args],capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0)
            self.assertIn('plan-lead',proc.stderr)
        self.assertEqual(before,self.state_path.read_bytes())



class PlanCodeCLITests(unittest.TestCase):
    def test_local_record_freshness_actor_and_no_self_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'.workflour').mkdir()
            (root/'.workflour/handoff.json').write_text(json.dumps({'workflow':{'kind':'plan-code'},'code_files':[]}))
            (root/'draft.md').write_text('Real research draft')
            base = [sys.executable,str(ROOT/'scripts/coordinator-workflow.py'),'--project',str(root)]
            def run(*args, actor='plan-lead'):
                return subprocess.run([*base,'--actor',actor,*args],capture_output=True,text=True)
            self.assertNotEqual(run('init','T1','Request','--workflow','plan-code').returncode,0)
            self.assertEqual(run('init','T1','Request','--workflow','plan-code','--thread-id','lead-thread').returncode,0)
            before = (root/'.workflour/coordination.json').read_bytes()
            self.assertNotEqual(run('record','research','--evidence','draft.md',actor='coordinator').returncode,0)
            self.assertEqual(before,(root/'.workflour/coordination.json').read_bytes())
            self.assertEqual(run('record','research','--evidence','draft.md').returncode,0)
            state = json.loads((root/'.workflour/coordination.json').read_text())
            record = state['assignments']['research/plan-lead']
            self.assertNotIn('assignment_id',record)
            self.assertEqual(record['evidence_sha256'],checker.digest(root/'draft.md'))
            (root/'draft.md').write_text('Changed after record')
            refused = run('advance','plan-review')
            self.assertNotEqual(refused.returncode,0)
            self.assertIn('evidence changed',refused.stderr)

if __name__ == '__main__': unittest.main()
