import importlib.util
from pathlib import Path
import unittest
import json
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location('coordinator_workflow', Path(__file__).resolve().parents[1] / 'scripts/coordinator-workflow.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class CoordinatorLedgerTests(unittest.TestCase):
    def setUp(self):
        self.state = {'phase': 'planning', 'assignments': {}}

    def test_restart_cannot_duplicate_uncertain_claim(self):
        module.apply(self.state, 'claim', 'planning', 'kimi')
        import json
        resumed = json.loads(json.dumps(self.state))
        with self.assertRaisesRegex(ValueError, 'Already claimed'):
            module.apply(resumed, 'claim', 'planning', 'kimi')
        module.apply(resumed, 'receipt', 'planning', 'kimi', 'native-id')
        with self.assertRaises(ValueError): module.apply(resumed, 'claim', 'planning', 'kimi')

    def test_stopped_result_cannot_advance_or_replay(self):
        module.apply(self.state, 'claim', 'planning', 'deepseek')
        module.apply(self.state, 'result', 'planning', 'deepseek', status='stopped')
        with self.assertRaises(ValueError): module.apply(self.state, 'advance', 'plan')
        with self.assertRaises(ValueError): module.apply(self.state, 'claim', 'planning', 'deepseek')

    def test_all_results_require_evidence_before_advance(self):
        for role in module.PHASES['planning']:
            module.apply(self.state, 'claim', 'planning', role)
            with self.assertRaises(ValueError): module.apply(self.state, 'result', 'planning', role, status='completed')
            with self.assertRaises(ValueError): module.apply(self.state, 'result', 'planning', role, status='completed', evidence='records/proposal.md')
            with self.assertRaises(ValueError): module.apply(self.state, 'receipt', 'planning', role, '')
            module.apply(self.state, 'receipt', 'planning', role, 'real-receipt-'+role)
            module.apply(self.state, 'result', 'planning', role, status='completed', evidence='records/proposal.md')
        module.apply(self.state, 'advance', 'plan')
        self.assertEqual(self.state['phase'], 'plan')

    def test_rework_preserves_receipts_uses_new_attempt_and_enforces_budget(self):
        self.state['phase'] = 'review'
        self.state['assignments']['implement/agy'] = {'status': 'completed', 'assignment_id': 'initial-code'}
        def settle_review():
            module.apply(self.state, 'claim', 'review', 'glm-review')
            module.apply(self.state, 'receipt', 'review', 'glm-review', 'review-'+str(self.state.get('repair_round', 0)))
            module.apply(self.state, 'result', 'review', 'glm-review', status='completed', evidence='review.md')
        settle_review()
        with self.assertRaises(ValueError): module.apply(self.state, 'rework', evidence='review.md')
        for attempt in (1, 2):
            module.apply(self.state, 'rework', evidence='review.md', reason='Pending filter includes completed tasks')
            self.assertEqual(self.state['repair_round'], attempt)
            with self.assertRaises(ValueError): module.apply(self.state, 'rework', evidence='review.md', reason='duplicate')
            for role in ('agy', 'deepseek'):
                module.apply(self.state, 'claim', 'implement', role)
                module.apply(self.state, 'receipt', 'implement', role, f'code-{role}-{attempt}')
                module.apply(self.state, 'result', 'implement', role, status='completed', evidence='fix.md')
            module.apply(self.state, 'advance', 'review')
            settle_review()
        with self.assertRaisesRegex(ValueError, 'exhausted'):
            module.apply(self.state, 'rework', evidence='review.md', reason='Still broken')
        self.assertEqual(self.state['assignments']['implement/agy']['assignment_id'], 'initial-code')
        self.assertEqual(len(self.state['rework_history']), 2)

    def test_new_task_archives_only_completed_verified_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); directory = root / '.workflour'; directory.mkdir()
            ledger = directory / 'coordination.json'
            ledger.write_text(json.dumps(self.state))
            before = ledger.read_bytes()
            argv = ['python3', str(spec.origin), '--actor', 'coordinator', '--project', tmp, 'init', 'NEXT', 'New explicit request', '--new-task']
            failed = subprocess.run(argv, capture_output=True)
            self.assertEqual(failed.returncode, 2)
            self.assertEqual(ledger.read_bytes(), before)
            prior = {'phase': 'verify', 'assignments': {'verify/coordinator': {'status': 'completed', 'assignment_id': 'local-test-receipt', 'evidence': 'verified.txt'}}}
            ledger.write_text(json.dumps(prior)); (root/'verified.txt').write_text('Actual test output')
            done = subprocess.run(argv, capture_output=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            archives = list((directory/'coordination-history').glob('*.json'))
            self.assertEqual(len(archives), 1)
            self.assertEqual(json.loads(archives[0].read_text()), prior)
            self.assertEqual(json.loads(ledger.read_text())['task_id'], 'NEXT')

    def test_concurrent_claim_has_one_winner_and_cannot_advance_forged_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); directory = root / '.workflour'; directory.mkdir()
            ledger = directory/'coordination.json'; ledger.write_text(json.dumps(self.state))
            argv = ['python3', str(spec.origin), '--actor', 'coordinator', '--project', tmp, 'claim', 'planning', 'kimi']
            children = [subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(8)]
            for child in children: child.communicate()
            codes = [child.returncode for child in children]
            self.assertEqual(codes.count(0), 1)
            self.assertEqual(codes.count(2), 7)
        forged = {'phase': 'planning', 'assignments': {f'planning/{role}': {'status': 'completed'} for role in module.PHASES['planning']}}
        with self.assertRaises(ValueError): module.apply(forged, 'advance', 'plan')
        for bad in (True, -1, 3, '1'):
            with self.subTest(round=bad), self.assertRaises(ValueError):
                module.apply({'phase': 'planning', 'repair_round': bad, 'assignments': {}}, 'claim', 'planning', 'kimi')

    def test_unmarked_worker_mutation_is_refused_without_ledger_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); directory = root/'.workflour'; directory.mkdir()
            ledger = directory/'coordination.json'; ledger.write_text(json.dumps(self.state))
            before = ledger.read_bytes()
            denied = subprocess.run(['python3', str(spec.origin), '--project', tmp, 'claim', 'planning', 'kimi'], capture_output=True)
            self.assertEqual(denied.returncode, 2)
            self.assertIn(b'return your result', denied.stderr)
            self.assertNotIn(b'--actor', denied.stderr)
            self.assertEqual(ledger.read_bytes(), before)
            read = subprocess.run(['python3', str(spec.origin), '--project', tmp, 'status'], capture_output=True)
            self.assertEqual(read.returncode, 0)
            self.assertEqual(ledger.read_bytes(), before)


if __name__ == '__main__': unittest.main()
