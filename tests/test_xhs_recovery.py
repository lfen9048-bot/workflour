import copy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import xhs_recovery as recovery

wf = recovery.workflow()


class Client:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []
        self.bots = [
            {'id': 'planner', 'description': 'Workflour 小红书图文 · xhs-planner',
             'modelSelection': {'model': 'default'},
             'tasks': [{'threadId': 'planner-thread', 'busy': False,
                        'modelSelection': {'model': 'manually-selected', 'variant': 'high'}}]},
            {'id': 'collector', 'tasks': [{'threadId': 'collect-thread', 'busy': False}]},
            {'id': 'writer', 'tasks': [{'threadId': 'draft-thread', 'busy': False}]},
        ]

    def call(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == 'GET' and path == '/api/bots?messages=0':
            return {'bots': self.bots}
        if method == 'POST' and path == '/api/bots/planner/messages':
            if self.fail:
                raise TimeoutError('Uncertain response after native acceptance')
            return {'ok': True}
        raise AssertionError('Unexpected model/task/service action: ' + method + ' ' + path)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'draft'
        self.project.mkdir()
        (self.project / '.xhs').mkdir()
        self.team = {'roles': [{'key': 'xhs-' + key, 'botId': key} for key in ('planner', 'collector', 'writer')]}
        self.manifest = Path(self.temp.name) / 'deployment.json'
        self.manifest.write_text(json.dumps(self.team))
        self.native = Path(self.temp.name) / 'native'
        self.native.mkdir()
        (self.native / 'bots.json').write_text(json.dumps(Client().bots))
        (self.native / 'config.json').write_text(json.dumps({'automaticRecovery': {'enabled': False}}))
        native_dir = patch.object(recovery, 'NATIVE_DATA', self.native)
        native_dir.start()
        self.addCleanup(native_dir.stop)
        env = patch.dict(os.environ, {'XHS_DEPLOYMENT_MANIFEST': str(self.manifest)})
        env.start()
        self.addCleanup(env.stop)
        self.state = wf.initialize(self.project, '已授权的旧稿恢复', 'planner-thread')
        created = int(datetime.fromisoformat(self.state['created_at']).timestamp() * 1000) + 1
        self.rows = [{'id': 'root', 'root_id': 'root', 'parent_id': None, 'status': 'failed',
                      'outcome': 'provider_error', 'bot_id': 'planner', 'requester_bot_id': 'planner',
                      'thread_id': 'planner-thread', 'requester_thread_id': 'planner-thread',
                      'created_at': created, 'mode': 'work', 'tokens': [], 'brief_sha256': 'a' * 64}]
        for stage, bot in (('collect', 'collector'), ('draft', 'writer')):
            self.rows.append({'id': stage, 'root_id': 'root', 'parent_id': 'root', 'status': 'completed',
                              'outcome': 'done', 'bot_id': bot, 'requester_bot_id': 'planner',
                              'thread_id': stage + '-thread', 'requester_thread_id': 'planner-thread',
                              'created_at': created + 1, 'mode': 'work',
                              'tokens': [self.state['dispatch_tokens'][stage]], 'brief_sha256': 'b' * 64})
        wf.write(self.project / 'sources.json', {'status': 'ready', 'samples': [{'source_url': 'https://example.org/official'}]})
        wf.record(self.project, self.state, 'collect', 'sources.json', 'collect', rows=self.rows)
        wf.record(self.project, self.state, 'brief', 'BRIEF.md')
        wf.write(self.project / 'draft.md', '# 原稿\n\n只做已有事实的机械交付。')
        wf.write(self.project / '.xhs/social-usage.json', {'requests': [{'source': 'x', 'candidates': 1, 'details': 0, 'comments': 0}]})
        wf.write(self.project / 'generated-images/run1/image-evidence.json',
                 {'status': 'blocked', 'reason': 'no_valid_new_native_image', 'images': [],
                  'finished_at': '2026-11-12T06:53:33Z', 'public_answer': '429 RESOURCE_EXHAUSTED'})
        self.save()

    def save(self):
        wf.write(self.project / '.xhs/state.json', self.state)

    def files(self):
        return {str(p.relative_to(self.project)): p.read_bytes() for p in self.project.rglob('*') if p.is_file()}

    def send(self, client=None, **kwargs):
        # Exercise the underlying journal protocol with an isolated fake safe
        # transport. Production has no override and its native guard refuses.
        with patch.object(recovery, 'native_takeover_guard', return_value={'send_allowed': True}):
            return recovery.send(client or Client(), self.team, self.project, '修复后继续已授权机械交付', rows=self.rows, idle=lambda _: True, **kwargs)

    def deliver(self):
        def chunk(kind, value):
            return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value) & 0xffffffff)
        image = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
                 + chunk(b'IDAT', zlib.compress(b'\0\x10\x20\x30')) + chunk(b'IEND', b''))
        (self.project / 'output').mkdir(exist_ok=True)
        (self.project / 'output/card-01.png').write_bytes(image)
        wf.write(self.project / 'cards.json', {'cards': [{'title': '原稿'}]})
        wf.write(self.project / 'output/preview.html', '<html>预览</html>')
        wf.write(self.project / 'writing-report.json', {'status': 'partial', 'images': ['output/card-01.png'],
                 'image_generation': {'status': 'blocked', 'reason': 'no_valid_new_native_image'}})

    def test_reconcile_binds_lost_receipt_without_completing_or_replaying_work(self):
        before = copy.deepcopy(self.state)
        files = self.files()
        observation = recovery.reconcile(self.project, self.state, self.rows)
        self.assertEqual(self.state['receipts']['draft']['id'], 'draft')
        self.assertEqual(observation['planner_status'], 'provider_failure')
        self.assertEqual(observation['status'], 'incomplete_deliverable')
        self.assertIn('writing-report.json', observation['deliverable']['missing'])
        for key in ('status', 'stage', 'artifacts', 'dispatch_tokens', 'social_limits', 'revision_count'):
            self.assertEqual(self.state[key], before[key])
        self.assertEqual(self.files(), files)

    def test_duplicate_or_wrong_recipient_fails_atomically(self):
        for change in ('duplicate', 'wrong_bot', 'missing_bound'):
            state = copy.deepcopy(self.state)
            rows = copy.deepcopy(self.rows)
            if change == 'duplicate':
                rows.append({**rows[-1], 'id': 'duplicate'})
            elif change == 'wrong_bot':
                rows[-1]['bot_id'] = 'wrong'
            else:
                state['receipts']['draft'] = {k: rows[-1][k] for k in ('id', 'status', 'bot_id', 'thread_id', 'created_at')}
                rows.pop()
            before = copy.deepcopy(state)
            with self.subTest(change=change), self.assertRaises(ValueError):
                recovery.reconcile(self.project, state, rows)
            self.assertEqual(state, before)

    def test_active_native_work_blocks_even_if_files_exist(self):
        self.deliver()
        self.rows[-1]['status'] = 'running'
        result = recovery.preview(self.project, rows=self.rows)
        self.assertEqual(result['observation']['status'], 'waiting_native')
        self.assertFalse(result['resume']['workflow_eligible'])
        with self.assertRaises(ValueError):
            self.send()
        self.assertFalse((self.project / recovery.JOURNAL).exists())

    def test_unfinished_image_and_preparing_delivery_are_pending_tools(self):
        original = self.project / 'generated-images/run1/image-evidence.json'
        original.unlink()
        result = recovery.preview(self.project, rows=self.rows)
        self.assertEqual(result['observation']['status'], 'pending_tool')
        self.assertFalse(result['resume']['workflow_eligible'])
        wf.write(original, {'status': 'blocked', 'finished_at': 'now'})
        wf.write(self.project / 'delivery/receipt.json', {'status': 'preparing'})
        result = recovery.preview(self.project, rows=self.rows)
        self.assertEqual(result['observation']['status'], 'pending_tool')
        self.assertFalse(result['resume']['workflow_eligible'])

    def test_waiting_visual_review_is_distinct_and_may_resume_original_planner(self):
        wf.write(self.project / 'delivery/receipt.json', {'status': 'awaiting_visual_review'})
        result = recovery.preview(self.project, rows=self.rows)
        self.assertEqual(result['observation']['status'], 'awaiting_visual_review')
        self.assertTrue(result['resume']['workflow_eligible'])
        self.assertIn('实际读每张图', result['prompt'])

    def test_real_deliverables_validate_only_on_copy_and_bad_png_is_rejected(self):
        self.deliver()
        before = self.files()
        result = recovery.preview(self.project, rows=self.rows)
        self.assertEqual(result['observation']['status'], 'ready_for_review')
        self.assertEqual(self.files(), before)
        self.assertNotIn('draft', json.loads((self.project / '.xhs/state.json').read_text())['artifacts'])
        (self.project / 'output/card-01.png').write_text('not an image')
        result = recovery.preview(self.project, rows=self.rows)
        self.assertEqual(result['observation']['status'], 'incomplete_deliverable')
        self.assertIn('PNG', result['observation']['deliverable']['validation_error'])

    def test_preview_is_local_read_only_and_does_not_consume_attempt(self):
        before = self.files()
        with patch.object(recovery, 'read_assignments', return_value=self.rows) as read:
            result = recovery.preview(self.project)
        read.assert_called_once_with('planner-thread')
        self.assertTrue(result['resume']['workflow_eligible'])
        self.assertFalse(result['sent'])
        self.assertEqual(self.files(), before)
        self.assertNotIn('RESOURCE_EXHAUSTED', json.dumps(result))

    def test_explicit_send_once_same_thread_preserves_model_evidence_and_limits(self):
        before = self.files()
        client = Client()
        result = self.send(client)
        self.assertEqual(result['status'], 'sent')
        self.assertEqual([(c[0], c[1]) for c in client.calls], [('GET', '/api/bots?messages=0'), ('POST', '/api/bots/planner/messages')])
        body = client.calls[-1][2]
        self.assertEqual(body['threadId'], 'planner-thread')
        saved = json.loads((self.project / recovery.JOURNAL).read_text())
        self.assertEqual(saved['send_id'], body['sendId'])
        self.assertEqual(saved['prompt_sha256'], hashlib.sha256(body['text'].encode()).hexdigest())
        self.assertEqual(saved['model_selection'], {'model': 'manually-selected', 'variant': 'high'})
        self.assertIn('禁止 coordinate_bots', body['text'])
        self.assertIn('prepare 不得传 image_prompt', body['text'])
        self.assertIn('generated-images/run1/image-evidence.json', body['text'])
        state = json.loads((self.project / '.xhs/state.json').read_text())
        for key in ('dispatch_tokens', 'social_limits', 'artifacts', 'revision_count', 'status', 'stage'):
            self.assertEqual(state[key], self.state[key])
        for name in before:
            if name not in ('.xhs/state.json', 'HANDOFF.md'):
                self.assertEqual((self.project / name).read_bytes(), before[name], name)
        with self.assertRaisesRegex(ValueError, 'already reserved'):
            self.send(client)
        self.assertEqual(sum(c[0] == 'POST' for c in client.calls), 1)

    def test_uncertain_send_retains_failure_and_never_resends(self):
        client = Client(fail=True)
        with self.assertRaises(TimeoutError):
            self.send(client)
        saved = json.loads((self.project / recovery.JOURNAL).read_text())
        self.assertEqual(saved['status'], 'delivery_unknown')
        self.assertEqual(saved['source_root']['status'], 'failed')
        with self.assertRaisesRegex(ValueError, 'already reserved'):
            self.send(client)
        self.assertEqual(sum(c[0] == 'POST' for c in client.calls), 1)

    def test_native_or_runtime_busy_cannot_send(self):
        client = Client()
        client.bots[-1]['tasks'][0]['busy'] = True
        with self.assertRaisesRegex(ValueError, 'worker runtime'):
            self.send(client)
        self.assertFalse((self.project / recovery.JOURNAL).exists())
        client.bots[-1]['tasks'][0]['busy'] = False
        with patch.object(recovery, 'native_takeover_guard', return_value={'send_allowed': True}), self.assertRaisesRegex(ValueError, 'planner must be confirmed idle'):
            recovery.send(client, self.team, self.project, '已授权恢复', rows=self.rows, idle=lambda _: False)
        self.assertEqual(sum(c[0] == 'POST' for c in client.calls), 0)

    def test_missing_ambiguous_cancelled_or_new_root_blocks_recovery(self):
        for variant in ('missing', 'ambiguous', 'cancelled', 'completed'):
            rows = copy.deepcopy(self.rows)
            if variant == 'missing':
                rows.pop(0)
            elif variant == 'ambiguous':
                rows.append({**rows[0], 'id': 'another-root', 'root_id': 'another-root'})
            else:
                rows[0]['status'] = variant
                rows[0]['outcome'] = 'stopped' if variant == 'cancelled' else 'done'
            with self.subTest(variant=variant):
                self.assertFalse(recovery.preview(self.project, rows=rows)['resume']['workflow_eligible'])

    def test_missing_draft_or_already_delivered_never_sends(self):
        (self.project / 'draft.md').unlink()
        self.assertFalse(recovery.preview(self.project, rows=self.rows)['resume']['workflow_eligible'])
        wf.write(self.project / 'draft.md', '原稿')
        self.state['status'] = 'pending_user_review'
        self.save()
        result = recovery.preview(self.project, rows=self.rows)
        self.assertEqual(result['observation']['status'], 'pending_user_review')
        self.assertFalse(result['resume']['workflow_eligible'])

    def test_changed_locked_artifact_and_escaping_evidence_refuse_before_send(self):
        old = (self.project / 'sources.json').read_bytes()
        (self.project / 'sources.json').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Recorded artifact changed'):
            self.send()
        (self.project / 'sources.json').write_bytes(old)
        evidence = self.project / 'generated-images/run1/image-evidence.json'
        evidence.unlink()
        evidence.symlink_to(self.manifest)
        with self.assertRaises(ValueError):
            self.send()
        self.assertFalse((self.project / recovery.JOURNAL).exists())

    def test_recovery_directory_symlink_cannot_redirect_journal(self):
        target = Path(self.temp.name) / 'outside'
        target.mkdir()
        (self.project / '.xhs/recovery').symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'cannot be a symlink'):
            self.send()
        self.assertEqual(list(target.iterdir()), [])

    def test_nested_image_versions_do_not_invent_pending_parent_attempt(self):
        parent = self.project / 'generated-images/versions'
        parent.mkdir()
        (self.project / 'generated-images/run1').rename(parent / 'run1')
        (parent / 'run1/assets').mkdir()
        result = recovery.preview(self.project, rows=self.rows)
        self.assertTrue(result['resume']['workflow_eligible'])
        self.assertEqual(len(result['observation']['image_attempts']), 1)
        (parent / 'run2').mkdir()
        result = recovery.preview(self.project, rows=self.rows)
        self.assertEqual(result['observation']['status'], 'pending_tool')

    def test_original_root_may_initialize_ledger_after_its_own_turn_started(self):
        self.rows[0]['created_at'] -= 60_000
        result = recovery.preview(self.project, rows=self.rows)
        self.assertTrue(result['resume']['workflow_eligible'])
        self.assertEqual(result['observation']['source_root']['id'], 'root')

    def test_protected_failure_evidence_cannot_be_changed_after_recovery(self):
        self.send()
        evidence = self.project / 'generated-images/run1/image-evidence.json'
        value = json.loads(evidence.read_text())
        value['reason'] = 'rewritten'
        wf.write(evidence, value)
        with self.assertRaisesRegex(ValueError, 'protected evidence changed'):
            recovery.preview(self.project, rows=self.rows)

    def test_interrupted_prepared_journal_reserves_the_only_attempt(self):
        wf.write(self.project / recovery.JOURNAL, {'status': 'prepared'})
        client = Client()
        with self.assertRaisesRegex(ValueError, 'already reserved'):
            self.send(client)
        self.assertEqual(client.calls, [])

    def test_authorized_revision_reads_protected_original_from_archive(self):
        self.send()
        self.deliver()
        state = json.loads((self.project / '.xhs/state.json').read_text())
        wf.record(self.project, state, 'draft', 'draft.md', rows=self.rows)
        wf.finish(self.project, state)
        wf.write(self.project / 'review.md', '用户授权修改一个明确事实。')
        wf.revise(self.project, state, '用户授权的局部修订', 'review.md', rows=self.rows)
        wf.write(self.project / '.xhs/state.json', state)
        wf.write(self.project / 'draft.md', '新的授权修订稿。')
        result = recovery.preview(self.project, rows=self.rows)
        self.assertFalse(result['resume']['workflow_eligible'])
        self.assertTrue((self.project / 'history/revision-0/draft.md').is_file())

    def test_native_takeover_guard_refuses_before_any_request_or_journal(self):
        client = Client()
        before = self.files()
        # This variable belongs to the client process, not the running server;
        # disabled automaticRecovery/empty fallbacks cannot prove safety either.
        with patch.dict(os.environ, {'OMB_QUOTA_SWITCH': '0'}):
            with self.assertRaisesRegex(ValueError, 'Native automatic quota takeover'):
                recovery.send(client, self.team, self.project, '已授权恢复', rows=self.rows, idle=lambda _: True)
        self.assertEqual(client.calls, [])
        self.assertEqual(self.files(), before)
        self.assertFalse((self.project / recovery.JOURNAL).exists())

    def test_workflow_ready_preview_still_reports_native_send_unavailable(self):
        before = self.files()
        result = recovery.preview(self.project, rows=self.rows)
        self.assertTrue(result['resume']['workflow_eligible'])
        self.assertFalse(result['resume']['allowed'])
        self.assertEqual(result['status'], 'native_takeover_uncontrolled')
        self.assertFalse(result['native_takeover_guard']['scoped_opt_out_available'])
        self.assertIn('not a native no-takeover guarantee', result['model_policy'])
        self.assertEqual(self.files(), before)

    def test_status_reports_task_drift_without_restoring_or_exposing_other_fields(self):
        self.send()
        bots = Client().bots
        bots[0]['tasks'][0]['modelSelection'] = {'instanceId': 'omb-coder', 'model': 'agent-default'}
        bots[0]['capabilityToken'] = 'must-not-appear'
        bots[0]['soul'] = 'private prompt must-not-appear'
        (self.native / 'bots.json').write_text(json.dumps(bots))
        (self.native / 'config.json').write_text(json.dumps({'automaticRecovery': {'enabled': False}, 'apiKey': 'must-not-appear'}))
        before = self.files()
        result = recovery.preview(self.project, rows=self.rows)
        self.assertEqual(result['status'], 'runtime_drift')
        self.assertEqual(result['runtime']['current_selection'], {'instanceId': 'omb-coder', 'model': 'agent-default'})
        self.assertEqual(result['runtime']['expected_selection'], {'model': 'manually-selected', 'variant': 'high'})
        self.assertFalse(result['runtime']['automatic_restore'])
        self.assertFalse(result['resume']['allowed'])
        self.assertNotIn('must-not-appear', json.dumps(result))
        self.assertEqual(self.files(), before)
        self.assertEqual(json.loads((self.native / 'bots.json').read_text()), bots)

    def test_matching_selection_does_not_imply_native_takeover_disabled(self):
        self.send()
        result = recovery.preview(self.project, rows=self.rows)
        self.assertEqual(result['runtime']['status'], 'matches_send_snapshot')
        self.assertFalse(result['runtime']['global_automatic_recovery_enabled'])
        self.assertEqual(result['runtime']['bot_fallback_count'], 0)
        self.assertFalse(result['native_takeover_guard']['send_allowed'])
        self.assertFalse(result['resume']['allowed'])

    def test_missing_native_registry_is_unknown_and_never_permission_to_send(self):
        (self.native / 'bots.json').unlink()
        result = recovery.preview(self.project, rows=self.rows)
        self.assertEqual(result['runtime']['status'], 'unavailable')
        self.assertIn('read_error', result['runtime'])
        self.assertFalse(result['resume']['allowed'])


if __name__ == '__main__':
    unittest.main()
