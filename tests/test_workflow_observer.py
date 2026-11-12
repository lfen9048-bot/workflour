import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('observer',ROOT/'scripts/workflow-observer.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ObserverTests(unittest.TestCase):
    def prepare(self,t):
        root=Path(t)/'project';(root/'.workflour').mkdir(parents=True)
        vault=Path(t)/'vault';vault.mkdir();(vault/'手写.md').write_text('keep')
        (root/'.workflour/handoff.json').write_text(json.dumps({'stage':'plan','owner':'项目总控','next_action':'test','artifacts':{},'code_files':[]}))
        ledger={'coordinator_thread':'chief','phase':'planning','assignments':{'planning/kimi':{'status':'running','assignment_id':'a'}}}
        (root/'.workflour/coordination.json').write_text(json.dumps(ledger))
        row=m.register(root,vault,Path(t)/'registry')
        native=[{'id':'a','status':'needs_input','bot_id':'b','thread_id':'worker','tokens':[]}]
        return root,vault,row,native
    def test_scoped_export_redacts_secrets_and_preserves_handwritten_notes(self):
        with tempfile.TemporaryDirectory() as t:
            root,vault,row,native=self.prepare(t);seen=[]
            def read(tid):
                seen.append(tid)
                return [{'id':'message','role':'bot','kind':'text','text':'password=abc123'}, {'id':'hidden','role':'bot','kind':'text','channel':'analysis','text':'hidden reasoning'}]
            s=m.sync_project(row,lambda _:native,read)
            self.assertTrue(s['ok']);self.assertEqual(set(seen),{'chief','worker'})
            content=(Path(s['output'])/'记录/worker.md').read_text()
            self.assertNotIn('abc123',content);self.assertNotIn('hidden reasoning',content)
            self.assertIn('等待审批',str(s['alerts']));self.assertEqual((vault/'手写.md').read_text(),'keep')
    def test_export_failure_retains_prior_record_and_recovers(self):
        with tempfile.TemporaryDirectory() as t:
            root,vault,row,native=self.prepare(t)
            m.sync_project(row,lambda _:native,lambda _:[])
            file=vault/'07-自动记录'/row['slug']/'记录/worker.md';before=file.read_bytes()
            def fail(_):raise ConnectionError()
            s=m.sync_project(row,lambda _:native,fail)
            self.assertFalse(s['ok']);self.assertEqual(file.read_bytes(),before)
            self.assertIn('同步失败',(file.parent.parent/'异常.md').read_text())
            self.assertTrue(m.sync_project(row,lambda _:native,lambda _:[])['ok'])
    def test_native_unavailable_never_inferred_as_success(self):
        with tempfile.TemporaryDirectory() as t:
            root,vault,row,native=self.prepare(t)
            def fail(_):raise OSError()
            s=m.sync_project(row,fail,lambda _:[])
            self.assertFalse(s['ok']);self.assertIn('不据此重发',str(s['errors']))
    def test_vault_symlink_escape_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root,vault,row,native=self.prepare(t)
            other=Path(t)/'other';other.mkdir();(vault/'07-自动记录').symlink_to(other)
            with self.assertRaises(ValueError):m.sync_project(row,lambda _:native,lambda _:[])

    def test_local_verification_does_not_report_a_missing_worker_dispatch(self):
        with tempfile.TemporaryDirectory() as t:
            root,vault,row,native=self.prepare(t)
            path=root/'.workflour/coordination.json';ledger=json.loads(path.read_text())
            ledger['assignments']={'verify/coordinator@1':{'status':'claimed'},
                                   'implement/deepseek@1':{'status':'claimed'}}
            path.write_text(json.dumps(ledger))
            result=m.sync_project(row,lambda _:[],lambda _:[])
            self.assertFalse(any('verify/coordinator' in a for a in result['alerts']))
            self.assertTrue(any('implement/deepseek' in a and '回执未绑定' in a for a in result['alerts']))
            progress=(Path(result['output'])/'进度.md').read_text()
            self.assertIn('等待测试证据',progress)

if __name__=='__main__':unittest.main()


class ApprovalVisibilityTests(unittest.TestCase):
    prepare = ObserverTests.prepare
    def test_open_permission_is_visible_but_not_exported_and_answer_clears_it(self):
        with tempfile.TemporaryDirectory() as t:
            root,vault,row,native=self.prepare(t)
            card={'kind':'options','role':'bot','card':{'requestId':'private-id','requestType':'permission','title':'do not export card detail'}}
            native[0]['status']='running'
            s=m.sync_project(row,lambda _:native,lambda _:[card])
            self.assertTrue(any('等待审批' in a for a in s['alerts']))
            content=(Path(s['output'])/'记录/worker.md').read_text()
            self.assertNotIn('private-id',content);self.assertNotIn('card detail',content)
            card['card']['answered']='allow'
            s=m.sync_project(row,lambda _:native,lambda _:[card])
            self.assertFalse(any('等待审批' in a for a in s['alerts']))


class SuspendedRegistryTests(unittest.TestCase):
    prepare = ObserverTests.prepare
    def test_suspend_preserves_records_and_resume_reenables_export(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as t:
            root,vault,row,native=self.prepare(t);base=Path(t)/'registry'
            m.sync_project(row,lambda _:native,lambda _:[])
            record=vault/'07-自动记录'/row['slug']/'记录/worker.md';before=record.read_bytes()
            m.set_suspended(root,'Confirmed missing old conversation',base=base)
            with patch.object(m,'sync_project',side_effect=AssertionError('Must not export suspended project')):
                status=m.run_all(base)
            self.assertTrue(status['ok']);self.assertTrue(status['projects'][0]['suspended'])
            self.assertIn('已暂停',(vault/'07-自动记录/首页.md').read_text())
            self.assertEqual(record.read_bytes(),before)
            self.assertTrue(list(base.glob('registry-backup-*.json')))
            m.set_suspended(root,resume=True,base=base)
            with patch.object(m,'sync_project',return_value={'ok':True,'alerts':[]}) as sync:
                m.run_all(base);sync.assert_called_once()

    def test_404_is_explicit_without_auto_rebinding_or_removing_history(self):
        from urllib.error import HTTPError
        with tempfile.TemporaryDirectory() as t:
            root,vault,row,native=self.prepare(t)
            ledger=(root/'.workflour/coordination.json').read_bytes()
            def missing(_):raise HTTPError('http://127.0.0.1',404,'not found',{},None)
            result=m.sync_project(row,lambda _:native,missing)
            self.assertFalse(result['ok']);self.assertIn('HTTP 404',str(result['errors']))
            self.assertEqual((root/'.workflour/coordination.json').read_bytes(),ledger)


class CurrentNextStepTests(unittest.TestCase):
    prepare = ObserverTests.prepare

    def setup_plan_code(self, temporary, *, settled=True):
        root, vault, row, native = self.prepare(temporary)
        ledger = {'workflow': 'plan-code', 'coordinator_thread': 'chief', 'phase': 'implement',
                  'assignments': {'implement/code-main': {'status': 'completed' if settled else 'running',
                                                         'assignment_id': 'a'}}}
        handoff = {'task_id': 'PC-1', 'stage': 'implement', 'owner': 'plan-lead',
                   'next_owner': 'code-main', 'next_action': '等待主单与补充单回传后复核',
                   'artifacts': {}, 'code_files': [], 'acceptance': {'status': 'pending'}}
        native[0]['status'] = 'completed'
        (root / '.workflour/coordination.json').write_text(json.dumps(ledger))
        (root / '.workflour/handoff.json').write_text(json.dumps(handoff))
        return root, vault, row, native, ledger, handoff

    def test_completed_work_shows_observed_next_step_without_mutating_shared_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, _, row, native, _, _ = self.setup_plan_code(temporary)
            readable = root / 'HANDOFF.md'
            readable.write_text('Keep this existing handoff')
            files = [root / '.workflour/coordination.json', root / '.workflour/handoff.json', readable]
            before = {file: file.read_bytes() for file in files}
            result = m.sync_project(row, lambda _: native, lambda _: [])
            progress = (Path(result['output']) / '进度.md').read_text()
            self.assertIn('当前阶段结果已登记完成', progress)
            self.assertIn('推进独立技术审核', progress)
            self.assertIn('负责人记录（可能滞后）', progress)
            self.assertTrue(any('仍在等待回传' in alert for alert in result['alerts']))
            self.assertEqual(before, {file: file.read_bytes() for file in files})

    def test_returned_receipt_is_not_mislabelled_as_settled(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, native, ledger, handoff = self.setup_plan_code(temporary, settled=False)
            next_step = m.observed_next_step(ledger, handoff, native)
            self.assertEqual(next_step['status'], 'returned')
            self.assertIn('核对实际产物和测试', next_step['text'])
            self.assertNotIn('登记完成', next_step['text'])

    def test_missing_running_failed_receipts_never_offer_stage_advance(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, native, ledger, handoff = self.setup_plan_code(temporary)
            for status, expected in (('running', 'running'), ('needs_input', 'waiting'),
                                     ('failed', 'blocked'), ('cancelled', 'blocked')):
                with self.subTest(status=status):
                    native[0]['status'] = status
                    result = m.observed_next_step(ledger, handoff, native)
                    self.assertEqual(result['status'], expected)
                    self.assertNotIn('推进', result['text'])
            self.assertEqual(m.observed_next_step(ledger, handoff, [])['status'], 'unknown')

    def test_valid_wait_for_review_is_not_flagged_as_old_worker_wait(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, native, ledger, handoff = self.setup_plan_code(temporary)
            handoff['next_action'] = '等待负责人推进独立技术审核'
            self.assertEqual(m.observed_next_step(ledger, handoff, native)['alerts'], [])

    def test_other_receipt_with_same_token_cannot_replace_primary(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, native, ledger, handoff = self.setup_plan_code(temporary)
            ledger['assignments']['implement/code-main']['dispatch_token'] = 'marker'
            native[0].update(id='different-primary', tokens=['marker'])
            self.assertEqual(m.observed_next_step(ledger, handoff, native)['status'], 'unknown')

    def test_stale_generated_handoff_and_phase_difference_are_visible(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, _, _, _, ledger, handoff = self.setup_plan_code(temporary)
            (root / 'HANDOFF.md').write_text(
                'Regenerated from .workflour/handoff.json.\n' +
                '\n'.join(f'- {key}: {value}' for key, value in handoff.items() if key in
                          ('task_id', 'stage', 'owner', 'next_owner', 'next_action')))
            self.assertEqual(m.handoff_consistency_alerts(root, ledger, handoff), [])
            handoff.update(stage='review', next_action='新的交接')
            alerts = m.handoff_consistency_alerts(root, ledger, handoff)
            self.assertTrue(any('派单阶段与项目阶段不一致' in alert for alert in alerts))
            self.assertTrue(any('HANDOFF.md 与 handoff.json 不一致' in alert for alert in alerts))

    def test_acceptance_stays_a_user_action(self):
        result = m.observed_next_step({'workflow': 'plan-code', 'phase': 'acceptance'},
                                     {'acceptance': {'status': 'pending'}}, [])
        self.assertEqual(result['status'], 'acceptance')
        self.assertIn('等待用户验收', result['text'])
