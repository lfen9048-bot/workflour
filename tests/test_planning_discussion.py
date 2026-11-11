import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('discussion_ledger', ROOT/'scripts/coordinator-workflow.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class DiscussionTests(unittest.TestCase):
    def setup_project(self, root):
        (root/'.workflour').mkdir()
        state = {'discussion_version': 1, 'phase': 'planning', 'assignments': {}}
        hashes = {}
        for role in m.PHASES['planning']:
            p = root/f'{role}.md'; p.write_text('Actual distinct proposal: '+role)
            hashes[role] = hashlib.sha256(p.read_bytes()).hexdigest()
            state['assignments']['planning/'+role] = {'status':'completed','assignment_id':'proposal-'+role,'evidence':p.name}
        return state, hashes

    def invoke(self, root, *args):
        return subprocess.run([sys.executable,str(spec.origin),'--actor','coordinator','--project',str(root),*args],capture_output=True,text=True)

    def test_new_flow_requires_cross_responses_and_rechecks_stale_proposals(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); state, hashes=self.setup_project(root)
            ledger=root/'.workflour/coordination.json';ledger.write_text(json.dumps(state))
            self.assertNotEqual(self.invoke(root,'advance','plan').returncode,0)
            self.assertEqual(self.invoke(root,'advance','discussion').returncode,0)
            self.assertNotEqual(self.invoke(root,'advance','plan').returncode,0)
            # Seed receipts as fixture data only, not real model/ACP evidence.
            state=json.loads(ledger.read_text())
            for role in m.PHASES['discussion']:
                response={'role':role,'round':2,'proposal_sha256':hashes,
                          'responses':[{'to':peer,'position':'agree','point':'Concrete '+peer+' point','reason':'Fits the stated requirement'} for peer in hashes if peer!=role]}
                p=root/(role+'.json');p.write_text(json.dumps(response))
                state['assignments']['discussion/'+role]={'status':'running','assignment_id':'reply-'+role}
            ledger.write_text(json.dumps(state))
            for role in hashes:
                result=self.invoke(root,'result','discussion',role,'completed','--evidence',role+'.json')
                self.assertEqual(result.returncode,0,result.stderr)
            original=(root/'kimi.md').read_bytes();(root/'kimi.md').write_text('Changed proposal')
            failed=self.invoke(root,'advance','plan');self.assertNotEqual(failed.returncode,0)
            self.assertIn('stale',failed.stderr)
            self.assertEqual(json.loads(ledger.read_text())['phase'],'discussion')
            (root/'kimi.md').write_bytes(original)
            self.assertEqual(self.invoke(root,'advance','plan').returncode,0)

    def test_missing_peer_forged_author_and_empty_reasons_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);state,hashes=self.setup_project(root)
            good={'role':'kimi','round':2,'proposal_sha256':hashes,'responses':[
                {'to':p,'position':'change','point':'Concrete point','reason':'Actual reason'} for p in ('deepseek','glm-plan')]}
            variants=[]
            bad=copy.deepcopy(good);bad['responses'].pop();variants.append(bad)
            bad=copy.deepcopy(good);bad['role']='deepseek';variants.append(bad)
            bad=copy.deepcopy(good);bad['responses'][1]['to']='deepseek';variants.append(bad)
            bad=copy.deepcopy(good);bad['responses'][1]['reason']=' ';variants.append(bad)
            for bad in variants:
                (root/'reply.json').write_text(json.dumps(bad))
                with self.assertRaises(ValueError):m.validate_discussion(root,state,'kimi','reply.json')

    def test_old_running_ledger_is_not_migrated(self):
        state={'phase':'planning','assignments':{f'planning/{r}':{'status':'completed','assignment_id':r,'evidence':r+'.md'} for r in m.PHASES['planning']}}
        m.apply(state,'advance','plan')
        self.assertEqual(state['phase'],'plan');self.assertNotIn('discussion_version',state)

    def test_fresh_init_enables_discussion(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'.workflour').mkdir()
            result=self.invoke(root,'init','TEST','Test requirement')
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['discussion_version'],1)


class ProjectCommandTests(unittest.TestCase):
    def test_project_cwd_and_exit_status_with_spaces_and_chinese(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'中文 project';(root/'.workflour').mkdir(parents=True)
            (root/'.workflour/project.json').write_text('{}')
            cmd=[sys.executable,str(ROOT/'scripts/project-exec.py'),'--project',str(root),'--',sys.executable,'-c',"import pathlib,sys; pathlib.Path('proof.txt').write_text(str(pathlib.Path.cwd()));sys.exit(7)"]
            result=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(result.returncode,7)
            self.assertEqual(Path((root/'proof.txt').read_text()),root.resolve())
            (root/'.workflour/project.json').unlink()
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,2)


class NativeMarkerTests(unittest.TestCase):
    def test_optional_colon_retains_exact_marker_and_rejects_unrelated_ids(self):
        from native_assignments import dispatch_tokens
        token='71ad76b9-5d92-4606-9ada-c3f5c0d58bde'
        for text in ('WF-DISPATCH:'+token,'【WF-DISPATCH '+token+'】','WF-DISPATCH: '+token):
            self.assertEqual(dispatch_tokens(text),[token])
        self.assertEqual(dispatch_tokens('Other '+token),[])
        self.assertEqual(dispatch_tokens('XWF-DISPATCH:'+token),[])
        self.assertEqual(dispatch_tokens('WF-DISPATCH:'+token+'f'),[])

    def test_token_repair_preserves_attempt_phase_and_rejects_wrong_owner(self):
        token='71ad76b9-5d92-4606-9ada-c3f5c0d58bde'
        state={'phase':'plan','assignments':{'discussion/kimi':{'status':'completed','assignment_id':'a','bot_id':'b','dispatch_token':None,'attempt':0}}}
        row={'id':'a','bot_id':'b','tokens':[token]}
        with self.assertRaises(ValueError):m.repair_token(copy.deepcopy(state),'discussion','kimi',[{**row,'bot_id':'wrong'}])
        with self.assertRaises(ValueError):m.repair_token(copy.deepcopy(state),'discussion','kimi',[{**row,'tokens':[token,'different']}])
        m.repair_token(state,'discussion','kimi',[row]);item=state['assignments']['discussion/kimi']
        self.assertEqual(item['dispatch_token'],token);self.assertEqual(item['status'],'completed')
        self.assertEqual(item['attempt'],0);self.assertEqual(state['phase'],'plan')
        self.assertEqual(len(state['token_recovery_history']),1)
        m.repair_token(state,'discussion','kimi',[row]);self.assertEqual(len(state['token_recovery_history']),1)
