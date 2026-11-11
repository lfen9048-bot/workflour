import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('recovery',ROOT/'scripts/coordinator-workflow.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from native_assignments import read_assignments, sender_idle

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.state={'phase':'planning','assignments':{},'coordinator_thread':'chief'}
        m.apply(self.state,'claim','planning','kimi')
        self.item=self.state['assignments']['planning/kimi']
        self.row={'id':'native','bot_id':'bot','thread_id':'worker','status':'failed','outcome':'provider_error','tokens':[self.item['dispatch_token']]}
    def test_lost_receipt_reconciles_without_redispatch(self):
        self.row['status']='completed'
        m.recover(self.state,'reconcile','planning','kimi',[self.row])
        self.assertEqual(self.item['assignment_id'],'native')
        with self.assertRaisesRegex(ValueError,'live or completed'):
            m.recover(self.state,'retry','planning','kimi',[self.row],reason='test',evidence='proof')
        m.apply(self.state,'result','planning','kimi',status='completed',evidence='real.txt')
    def test_failure_retry_preserves_history_and_is_bounded(self):
        m.recover(self.state,'reconcile','planning','kimi',[self.row])
        token=self.item['dispatch_token']
        m.recover(self.state,'retry','planning','kimi',[self.row],reason='quota resolved',evidence='partial-files.md',snapshot={'code.py':'abc'})
        new=self.state['assignments']['planning/kimi']
        self.assertNotEqual(new['dispatch_token'],token)
        self.assertEqual(self.state['attempt_history'][0]['item']['assignment_id'],'native')
        with self.assertRaisesRegex(ValueError,'already bound'):
            m.apply(self.state,'receipt','planning','kimi','native')
        with self.assertRaisesRegex(ValueError,'One retry'):
            m.recover(self.state,'retry','planning','kimi',[],reason='again',evidence='proof')
    def test_stopped_needs_explicit_user_resume(self):
        self.row.update(status='cancelled',outcome='stopped')
        m.recover(self.state,'reconcile','planning','kimi',[self.row])
        before=copy.deepcopy(self.state)
        with self.assertRaisesRegex(ValueError,'authorization'):
            m.recover(self.state,'retry','planning','kimi',[self.row],reason='continue',evidence='proof')
        self.assertEqual(before,self.state)
        m.recover(self.state,'retry','planning','kimi',[self.row],reason='continue',evidence='proof',resume_authorization='User explicitly says continue')
    def test_live_and_approval_and_duplicate_matches_never_retry(self):
        for status in ('running','needs_input','waiting','queued','resume','completed'):
            with self.subTest(status=status):
                state=copy.deepcopy(self.state);row={**self.row,'status':status}
                m.recover(state,'reconcile','planning','kimi',[row])
                with self.assertRaises(ValueError):m.recover(state,'retry','planning','kimi',[row],reason='timeout',evidence='proof')
        with self.assertRaisesRegex(ValueError,'Multiple'):
            m.recover(self.state,'reconcile','planning','kimi',[self.row,{**self.row,'id':'another'}])
    def test_missing_bound_receipt_and_wrong_target_refused(self):
        self.item['assignment_id']='native'
        with self.assertRaisesRegex(ValueError,'missing'):m.recover(self.state,'reconcile','planning','kimi',[])
        self.item['bot_id']='other'
        with self.assertRaisesRegex(ValueError,'recipient'):m.recover(self.state,'reconcile','planning','kimi',[self.row])
    def test_readonly_native_adapter_scopes_owner_and_does_not_export_prompt(self):
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'runtime.db'
            c=sqlite3.connect(db);c.execute('CREATE TABLE assignments (json TEXT,requester_thread_id TEXT,assignee_thread_id TEXT,status TEXT)')
            row={'version':1,'id':'native','status':'failed','requester':{'threadId':'chief'},'assignee':{'botId':'bot','destination':{'threadId':'worker'}},'brief':'secret password and WF-DISPATCH:'+self.item['dispatch_token'],'createdAt':1,'executions':1}
            c.execute('INSERT INTO assignments VALUES (?,?,?,?)',(json.dumps(row),'chief','worker','failed'));c.commit();c.close()
            before=db.read_bytes();rows=read_assignments('chief',db)
            self.assertEqual(len(rows),1);self.assertNotIn('secret',json.dumps(rows));self.assertEqual(read_assignments('other',db),[])
            self.assertTrue(sender_idle('worker',db));self.assertEqual(before,db.read_bytes())

if __name__=='__main__':unittest.main()

class RecoveryCLITests(unittest.TestCase):
    def test_cancelled_receipt_cannot_retry_while_worker_has_direct_continuation(self):
        from unittest.mock import patch
        import contextlib,io,sys
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'.workflour').mkdir()
            (root/'.workflour/handoff.json').write_text('{"code_files":[]}')
            (root/'proof.md').write_text('Inspected files; user explicitly resumed')
            state={'phase':'planning','coordinator_thread':'chief','assignments':{}}
            m.apply(state,'claim','planning','kimi')
            row={'id':'old','bot_id':'bot','thread_id':'worker','status':'cancelled','outcome':'stopped','tokens':[state['assignments']['planning/kimi']['dispatch_token']]}
            m.recover(state,'reconcile','planning','kimi',[row])
            path=root/'.workflour/coordination.json';path.write_text(json.dumps(state));before=path.read_bytes()
            argv=['script','--actor','coordinator','--project',t,'retry','planning','kimi','--reason','resume','--evidence','proof.md','--resume-authorization','user continue']
            with patch.object(sys,'argv',argv),patch.object(m,'read_assignments',return_value=[row]),patch.object(m,'sender_idle',return_value=False) as idle,contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):m.main()
            idle.assert_called_once_with('worker')
            self.assertEqual(before,path.read_bytes())
    def test_release_requires_idle_sender_and_real_evidence(self):
        from unittest.mock import patch
        import contextlib,io,sys
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'.workflour').mkdir()
            (root/'.workflour/handoff.json').write_text('{"code_files":[]}')
            (root/'proof.md').write_text('Inspected partial files and original sender; explicit test recovery authorization')
            state={'phase':'planning','coordinator_thread':'chief','assignments':{}}
            m.apply(state,'claim','planning','kimi');m.recover(state,'reconcile','planning','kimi',[])
            path=root/'.workflour/coordination.json';path.write_text(json.dumps(state));before=path.read_bytes()
            argv=['script','--actor','coordinator','--project',t,'release-claim','planning','kimi','--reason','not sent','--evidence','proof.md','--resume-authorization','test instruction']
            with patch.object(sys,'argv',argv),patch.object(m,'read_assignments',return_value=[]),patch.object(m,'sender_idle',return_value=False),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):m.main()
            self.assertEqual(before,path.read_bytes())
            with patch.object(sys,'argv',argv),patch.object(m,'read_assignments',return_value=[]),patch.object(m,'sender_idle',return_value=True),contextlib.redirect_stdout(io.StringIO()):m.main()
            changed=json.loads(path.read_text());self.assertEqual(changed['assignments']['planning/kimi']['attempt'],1)
            self.assertEqual(len(changed['attempt_history']),1)
    def test_legacy_claim_without_searchable_token_never_infers_unsent(self):
        state={'phase':'planning','assignments':{'planning/kimi':{'status':'claimed'}}}
        with self.assertRaisesRegex(ValueError,'Legacy'):m.recover(state,'reconcile','planning','kimi',[])

class OriginAdoptionTests(unittest.TestCase):
    def test_only_idle_same_bot_can_adopt_and_old_receipts_remain_readable(self):
        state={'coordinator_thread':'old','assignments':{'planning/kimi':{'assignment_id':'previous'}}}
        args=dict(idle=True,rows=[{'status':'completed'}],old_owner='bot',new_owner='bot',reason='runtime changed',evidence='handoff.md',authorization='user resume')
        for change in ({'idle':False},{'rows':[{'status':'running'}]},{'new_owner':'other'},{'authorization':''}):
            before=copy.deepcopy(state)
            with self.assertRaises(ValueError):m.adopt_origin(state,'new',**{**args,**change})
            self.assertEqual(before,state)
        m.adopt_origin(state,'new',**args)
        self.assertEqual(m.workflow_threads(state),['new','old'])
        self.assertEqual(state['assignments']['planning/kimi']['assignment_id'],'previous')
