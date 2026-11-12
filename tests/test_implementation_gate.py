"""Implementation cannot settle or enter review on missing/stale test evidence."""
import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('implementation_gate_fixtures', ROOT / 'tests/test_plan_code_freshness.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class ImplementationGateTests(unittest.TestCase):
    def prepare(self, action, repair=0):
        case = fixtures.FreshnessTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.lock_plan()
        case.state.update(phase='implement', repair_round=repair)
        suffix = f'@{repair}' if repair else ''
        row = case.completed('implement', 'code-main', 'records/tasks.md', suffix)
        item = case.state['assignments']['implement/code-main' + suffix]
        item['next_action'] = 'Wait for the supplement and settle the result'
        if action == 'result':
            item['status'] = 'running'
        case.write_ledger()
        # This gate precedes independent review, so review must not be required.
        case.project.state['review'].update(status='pending', snapshot={})
        case.project.save()
        return case, row, item

    def invoke(self, case, row, action, failure=None):
        command = (['result', 'implement', 'code-main', 'completed', '--evidence', 'records/tasks.md']
                   if action == 'result' else ['advance', 'review'])
        case.invoke(*command, rows=[row], failure=failure)

    def test_both_entries_reject_invalid_evidence_without_changing_ledger(self):
        cases = {'work_items': 'Assign work_items', 'no_tests': 'missing or failing test',
                 'failure': 'has not passed verification', 'stale': 'has not passed verification',
                 'changed_output': 'evidence is missing or has changed',
                 'changed_source_during_test': 'missing or failing test'}
        for action in ('result', 'advance'):
            for invalid, message in cases.items():
                with self.subTest(action=action, invalid=invalid):
                    case, row, _ = self.prepare(action)
                    project = case.project
                    if invalid == 'work_items':
                        project.state['work_items'] = []
                    elif invalid == 'no_tests':
                        project.state['tests'] = []
                    elif invalid == 'failure':
                        with contextlib.redirect_stdout(io.StringIO()):
                            project.run_test([sys.executable, '-c', 'raise SystemExit(7)'])
                    elif invalid == 'stale':
                        (case.root / 'app.py').write_text('value = 43\n')
                    elif invalid == 'changed_output':
                        project.path(project.state['tests'][0]['evidence']).write_text('replaced output')
                    else:
                        project.state['tests'][-1]['source_changed_during_test'] = True
                    project.save()
                    handoff_before = project.state_path.read_bytes()
                    self.invoke(case, row, action, failure=message)
                    self.assertEqual(project.state_path.read_bytes(), handoff_before)

    def test_completed_receipt_without_imported_tests_is_not_enough(self):
        case, row, _ = self.prepare('result')
        case.project.state['tests'] = []
        case.project.state['verification']['status'] = 'pending'
        case.project.save()
        with contextlib.redirect_stdout(io.StringIO()):
            case.project.run_test([sys.executable, '-c', 'print(42)'], detached=True)
        self.invoke(case, row, 'result', failure='has not passed verification')

    def test_first_implementation_passes_before_review_and_clears_old_advice(self):
        case, row, _ = self.prepare('result')
        self.invoke(case, row, 'result')
        item = case.state['assignments']['implement/code-main']
        self.assertEqual(item['status'], 'completed')
        self.assertNotIn('next_action', item)
        self.invoke(case, row, 'advance')
        self.assertEqual(case.state['phase'], 'review')

    def test_repair_needs_new_tests_then_can_complete(self):
        case, row, _ = self.prepare('result', repair=1)
        (case.root / 'app.py').write_text('value = 43\n')
        self.invoke(case, row, 'result', failure='has not passed verification')
        with contextlib.redirect_stdout(io.StringIO()):
            case.project.run_test([sys.executable, '-c', 'print(43)'])
        self.invoke(case, row, 'result')
        self.invoke(case, row, 'advance')
        self.assertEqual(case.state['phase'], 'review')
        self.assertEqual(case.state['repair_round'], 1)

    def test_successful_same_command_rerun_preserves_failed_evidence(self):
        case, row, _ = self.prepare('result')
        flag = case.root / 'fail.flag'
        command = [sys.executable, '-c', "from pathlib import Path; raise SystemExit(7 if Path('fail.flag').exists() else 0)"]
        flag.write_text('fail')
        with contextlib.redirect_stdout(io.StringIO()):
            case.project.run_test(command)
        failed = case.project.state['tests'][-1]
        failed_bytes = case.project.path(failed['evidence']).read_bytes()
        self.invoke(case, row, 'result', failure='has not passed verification')
        flag.unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            case.project.run_test(command)
        self.invoke(case, row, 'result')
        self.invoke(case, row, 'advance')
        self.assertEqual(case.project.path(failed['evidence']).read_bytes(), failed_bytes)
        self.assertEqual(failed['exit_code'], 7)


if __name__ == '__main__':
    unittest.main()
