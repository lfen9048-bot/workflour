"""Native serial additions stay explicit; duplicates and early completion fail closed."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import native_assignments as native


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


ledger = module('supplement_ledger', 'coordinator-workflow.py')
observer = module('supplement_observer', 'workflow-observer.py')


class Supplements(unittest.TestCase):
    def setUp(self):
        self.state = {'workflow': 'plan-code', 'phase': 'implement', 'coordinator_thread': 'lead-thread',
                      'assignments': {'implement/code-main': {'status': 'running', 'assignment_id': 'primary',
                          'dispatch_token': 'marker', 'bot_id': 'worker', 'thread_id': 'work-thread'}}}
        self.item = self.state['assignments']['implement/code-main']
        self.primary = {'id': 'primary', 'status': 'running', 'outcome': None, 'tokens': ['marker'],
            'bot_id': 'worker', 'thread_id': 'work-thread', 'requester_bot_id': 'lead',
            'requester_thread_id': 'lead-thread', 'created_at': 100, 'executions': 1,
            'mode': 'work', 'brief_sha256': 'primary-hash', 'root_id': 'original-root'}
        self.extra = {**self.primary, 'id': 'extra', 'status': 'queued', 'created_at': 200, 'executions': 0,
                      'brief_sha256': 'addition-hash', 'root_id': 'later-owner-turn-root'}
        self.rows = [self.primary, self.extra]

    def register(self, **kwargs):
        return ledger.register_supplement(self.state, 'implement', 'code-main', 'extra', self.rows,
            reason='User clarified existing requirement', evidence='supplement.md', evidence_sha256='proof-hash', **kwargs)

    def test_legacy_single_receipt_unchanged_and_duplicates_not_inferred(self):
        self.assertEqual(native.matching(self.state, self.item, [self.primary]), self.primary)
        with self.assertRaisesRegex(ValueError, 'Multiple'):
            native.matching(self.state, self.item, self.rows)

    def test_explicit_registration_keeps_primary_and_accepts_different_parent_root(self):
        self.register()
        actual = native.matching(self.state, self.item, self.rows)
        self.assertEqual(self.item['assignment_id'], 'primary')
        self.assertEqual(self.item['dispatch_token'], 'marker')
        self.assertEqual(actual['id'], 'primary')
        self.assertEqual(actual['status'], 'running')
        self.assertEqual(actual['supplements'][0]['id'], 'extra')
        with self.assertRaisesRegex(ValueError, 'already bound'):
            self.register()

    def test_registration_refuses_wrong_identity_older_duplicate_or_unmarked_work(self):
        for key, value in [('requester_bot_id', 'other'), ('requester_thread_id', 'other'),
                           ('bot_id', 'other'), ('thread_id', 'other'), ('created_at', 100),
                           ('mode', 'notify'), ('tokens', ['different']), ('brief_sha256', 'primary-hash')]:
            with self.subTest(key=key):
                old = self.extra[key]
                self.extra[key] = value
                with self.assertRaises(ValueError):
                    self.register()
                self.extra[key] = old
        self.assertNotIn('supplements', self.item)

    def test_unregistered_third_receipt_and_missing_registered_receipt_still_fail(self):
        self.register()
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            native.matching(self.state, self.item, self.rows + [{**self.extra, 'id': 'unknown'}])
        with self.assertRaisesRegex(ValueError, 'missing'):
            native.matching(self.state, self.item, [self.primary])
        self.extra['requester_bot_id'] = 'changed'
        with self.assertRaises(ValueError):
            native.matching(self.state, self.item, self.rows)

    def test_primary_completed_does_not_complete_queued_addition(self):
        self.register()
        self.primary['status'] = 'completed'
        actual = native.matching(self.state, self.item, self.rows)
        self.assertEqual(actual['status'], 'completed')  # Real primary state preserved.
        self.assertEqual(native.effective_status(actual), 'queued')
        with self.assertRaisesRegex(ValueError, 'every supplement'):
            native.require_completed(self.state, self.item, self.rows)
        self.extra['status'] = 'completed'
        native.require_completed(self.state, self.item, self.rows)

    def test_missing_primary_cannot_be_replaced_by_one_other_token_match(self):
        self.extra['status'] = 'completed'
        with self.assertRaisesRegex(ValueError, 'cannot replace'):
            native.require_completed(self.state, self.item, [self.extra])

    def test_supplement_failure_blocks_without_retrying_successful_primary(self):
        self.register()
        self.primary['status'] = 'completed'
        self.extra['status'] = 'failed'
        ledger.recover(self.state, 'reconcile', 'implement', 'code-main', self.rows)
        self.assertEqual(self.item['status'], 'failed')
        self.assertEqual(self.item['assignment_id'], 'primary')
        self.assertEqual(self.item['native_observation']['status'], 'completed')
        self.assertIn('never replay', self.item['next_action'])
        with self.assertRaisesRegex(ValueError, 'cannot retry the primary'):
            ledger.recover(self.state, 'retry', 'implement', 'code-main', self.rows,
                           reason='retry', evidence='proof.md', resume_authorization='Continue addition')
        self.assertNotIn('attempt_history', self.state)

    def test_settled_primary_cannot_be_rewritten_with_supplement(self):
        self.item['status'] = 'completed'
        with self.assertRaisesRegex(ValueError, 'settled'):
            self.register()

    def test_completion_checks_registration_evidence_and_other_active_turns(self):
        self.register()
        self.primary['status'] = self.extra['status'] = 'completed'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / 'supplement.md').write_text('Exact source/scope')
            with patch.object(ledger, 'sender_idle', return_value=True):
                with self.assertRaisesRegex(ValueError, 'evidence changed'):
                    ledger.validate_completion(root, self.state, self.item, self.rows)
                self.item['supplements'][0]['evidence_sha256'] = hashlib.sha256((root / 'supplement.md').read_bytes()).hexdigest()
                ledger.validate_completion(root, self.state, self.item, self.rows)
            with patch.object(ledger, 'sender_idle', return_value=False):
                with self.assertRaisesRegex(ValueError, 'continuation'):
                    ledger.validate_completion(root, self.state, self.item, self.rows)

    def test_observer_shows_added_receipt_or_explicit_collision_without_losing_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            alerts, lines, threads = observer.collect(Path(temporary), self.state, {'code_files': []}, self.rows)
            self.assertIn('回执核对冲突', str(alerts))
            self.assertIn('work-thread', threads)
            self.register(); self.primary['status'] = 'completed'
            alerts, lines, _ = observer.collect(Path(temporary), self.state, {'code_files': []}, self.rows)
            self.assertIn('已登记补充', str(lines)); self.assertIn('extra', str(lines))
            self.assertIn('排队', str(alerts))
            self.assertEqual(observer.observed_next_step(self.state, {}, self.rows)['status'], 'running')
            self.extra['status'] = 'completed'
            self.assertEqual(observer.observed_next_step(self.state, {}, self.rows)['status'], 'returned')
            self.item['status'] = 'completed'
            self.assertEqual(observer.observed_next_step(self.state, {}, self.rows)['status'], 'settled')

    def test_cli_registration_and_result_advance_require_all_real_receipts(self):
        with contextlib.ExitStack() as stack:
            # A successful implementation now also needs a real initialized
            # project and imported passing test evidence, not just receipts.
            spec = importlib.util.spec_from_file_location('supplement_evidence_fixture', ROOT / 'tests/test_plan_code_workflow.py')
            fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)
            fixture = fixtures.PlanCodeEvidenceTests(); fixture.setUp()
            stack.callback(fixture.doCleanups)
            fixture.project.save()
            root = fixture.root
            path = root / '.workflour/coordination.json'; path.write_text(json.dumps(self.state))
            (root / 'supplement.md').write_text('Source user quote; bounded copy fix; primary/extra receipts; same worker thread.')
            (root / 'result.md').write_text('Latest implementation and tests')
            def invoke(args, success=True):
                with patch.object(sys, 'argv', ['coordinator-workflow.py', '--project', str(root), '--actor', 'plan-lead', *args]), \
                     patch.object(ledger, 'workflow_rows', return_value=self.rows), patch.object(ledger, 'sender_idle', return_value=True), \
                     contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    if success:
                        ledger.main()
                    else:
                        before = path.read_bytes()
                        with self.assertRaises(SystemExit) as error:
                            ledger.main()
                        self.assertEqual(error.exception.code, 2)
                        self.assertEqual(before, path.read_bytes())
            invoke(['supplement', 'implement', 'code-main', 'extra', '--reason', 'Copy clarification', '--evidence', 'supplement.md'])
            self.primary['status'] = 'completed'
            invoke(['result', 'implement', 'code-main', 'completed', '--evidence', 'result.md'], False)
            self.extra['status'] = 'completed'
            invoke(['result', 'implement', 'code-main', 'completed', '--evidence', 'result.md'])
            self.rows.append({**self.extra, 'id': 'unknown-late-receipt'})
            invoke(['advance', 'review'], False)
            self.rows.pop()
            invoke(['advance', 'review'])
            self.assertEqual(json.loads(path.read_text())['phase'], 'review')

    def test_native_reader_extracts_binding_metadata_without_exposing_brief(self):
        with tempfile.TemporaryDirectory() as temporary:
            db = Path(temporary) / 'native.db'
            row = {'version': 1, 'id': 'id', 'status': 'queued', 'requester': {'botId': 'lead', 'threadId': 'lead-thread'},
                   'assignee': {'botId': 'worker', 'destination': {'threadId': 'work-thread'}},
                   'createdAt': 123, 'executions': 0, 'mode': 'work', 'brief': 'private task', 'rootId': 'root'}
            with sqlite3.connect(db) as connection:
                connection.execute('CREATE TABLE assignments (requester_thread_id TEXT,json TEXT)')
                connection.execute('INSERT INTO assignments VALUES (?,?)', ('lead-thread', json.dumps(row)))
            result = native.read_assignments('lead-thread', db)[0]
            self.assertEqual(result['requester_bot_id'], 'lead')
            self.assertEqual(result['brief_sha256'], hashlib.sha256(b'private task').hexdigest())
            self.assertNotIn('private task', str(result))


if __name__ == '__main__':
    unittest.main()
