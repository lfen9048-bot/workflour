import importlib.util
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import struct
import zlib
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('xhs_workflow', Path(__file__).resolve().parents[1] / 'scripts/xhs-workflow.py')
xhs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xhs)


class XhsWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'post'
        self.root.mkdir()
        self.state = xhs.initialize(self.root, 'Claude 更新', 'planner-thread')
        self.manifest = Path(self.temp.name) / 'deployment.json'
        self.manifest.write_text(json.dumps({'roles': [{'key': 'xhs-collector', 'botId': 'collector'}, {'key': 'xhs-writer', 'botId': 'writer'}, {'key': 'xhs-planner', 'botId': 'planner'}]}))
        self.env = patch.dict(os.environ, {'XHS_DEPLOYMENT_MANIFEST': str(self.manifest)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def rows(self, stage='collect', status='completed'):
        return [{'id': stage + '-receipt', 'status': status, 'bot_id': 'collector' if stage == 'collect' else 'writer',
                 'thread_id': stage + '-thread', 'requester_thread_id': 'planner-thread', 'created_at': 9999999999999,
                 'requester_bot_id': 'planner', 'mode': 'work', 'tokens': [self.state['dispatch_tokens'][stage]]}]

    def collect(self):
        (self.root / 'sources.json').write_text(json.dumps({'status': 'ready', 'source_mode': 'official_web', 'samples': [{'source_url': 'https://www.anthropic.com/news'}], 'limitations': ['非小红书样本']}))
        xhs.record(self.root, self.state, 'collect', 'sources.json', 'collect-receipt', rows=self.rows())

    def first_draft(self, acceptance=True, recorded=True):
        self.collect()
        xhs.record(self.root, self.state, 'brief', 'BRIEF.md')
        (self.root / 'draft.md').write_text('# Claude 首稿\n\n具体事实与来源。\n#Claude')
        (self.root / 'cards.json').write_text(json.dumps({'cards': [{'title': '首稿'}]}))
        output = self.root / 'output'
        output.mkdir()
        def chunk(kind, payload):
            return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)
        image = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b'\x00\x10\x20\x30')) + chunk(b'IEND', b'')
        (output / 'card-01.png').write_bytes(image)
        (output / 'render-manifest.json').write_text(json.dumps({'image': 'card-01.png'}))
        (output / 'preview.html').write_text('<html>首稿预览</html>')
        (self.root / 'writing-report.json').write_text(json.dumps({'status': 'partial', 'images': ['output/card-01.png'],
            'limitations': ['原生生图未接通'], 'image_generation': {'status': 'blocked', 'reason': 'IMAGE_TOOL_UNAVAILABLE'}}))
        if recorded:
            xhs.record(self.root, self.state, 'draft', 'draft.md', 'draft-receipt', rows=self.rows('draft'))
        if acceptance and recorded:
            xhs.finish(self.root, self.state)
        (self.root / 'review.md').write_text('# 局部退稿\n\n移除无来源的全员开放表述，保留真实URL。')

    def amendment_rows(self, status='running', token=False):
        primary = self.rows('draft')[0]
        primary['brief_sha256'] = 'a' * 64
        followup = {**primary, 'id': 'amendment-receipt', 'status': status,
                    'created_at': primary['created_at'] + 1, 'brief_sha256': 'b' * 64,
                    'tokens': [self.state['dispatch_tokens']['draft']] if token else []}
        return [primary, followup]

    def test_existing_tokenless_followup_requires_explicit_exception_and_both_receipts_complete(self):
        self.first_draft(recorded=False)
        xhs.bind_receipt(self.state, 'draft', 'draft-receipt', self.rows('draft', 'running'))
        token = self.state['dispatch_tokens']['draft']
        rows = self.amendment_rows()
        with self.assertRaisesRegex(ValueError, 'explicit maintenance'):
            xhs.amend_receipt(self.root, self.state, 'amendment-receipt', '已有一次局部改稿补充', 'review.md', rows=rows)
        self.assertNotIn('draft_amendment', self.state)
        xhs.amend_receipt(self.root, self.state, 'amendment-receipt', '只修无依据的范围和缺失链接', 'review.md', True, rows)
        self.assertEqual(self.state['receipts']['draft']['id'], 'draft-receipt')
        self.assertEqual(self.state['receipts']['draft']['status'], 'completed')
        self.assertEqual(self.state['dispatch_tokens']['draft'], token)
        self.assertTrue(self.state['draft_amendment']['token_missing'])
        self.assertEqual(self.state['draft_amendment']['maintenance_exception'], 'missing_dispatch_token')
        self.assertEqual(self.state['draft_amendment']['status'], 'running')
        with self.assertRaisesRegex(ValueError, 'both be completed'):
            xhs.record(self.root, self.state, 'draft', 'draft.md', rows=rows)
        self.assertNotIn('draft', self.state['artifacts'])
        rows[1]['status'] = 'completed'
        (self.root / 'draft.md').write_text('# 最新修订稿\n\n仅保留已经核实的范围，含来源URL。')
        xhs.record(self.root, self.state, 'draft', 'draft.md', rows=rows)
        xhs.finish(self.root, self.state)
        self.assertEqual(self.state['status'], 'pending_user_review')
        self.assertEqual(self.state['draft_amendment']['status'], 'completed')
        self.assertEqual(self.state['revision_count'], 1)
        with self.assertRaisesRegex(ValueError, 'Only one'):
            xhs.revise(self.root, self.state, '不能再派一轮', 'review.md', rows=rows)

    def test_amendment_rejects_other_work_duplicate_briefs_and_a_second_registration(self):
        self.first_draft(recorded=False)
        xhs.bind_receipt(self.state, 'draft', 'draft-receipt', self.rows('draft'))
        for field, value in [('requester_bot_id', 'other-planner'), ('thread_id', 'other-thread'),
                             ('bot_id', 'other-writer'), ('mode', 'consult'),
                             ('created_at', 0), ('brief_sha256', 'a' * 64),
                             ('tokens', ['another-project-token'])]:
            rows = self.amendment_rows()
            rows[1][field] = value
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    xhs.amend_receipt(self.root, self.state, 'amendment-receipt', '局部改稿', 'review.md', True, rows)
                self.assertNotIn('draft_amendment', self.state)
        rows = self.amendment_rows(token=True)
        xhs.amend_receipt(self.root, self.state, 'amendment-receipt', '局部改稿', 'review.md', rows=rows)
        self.assertFalse(self.state['draft_amendment']['token_missing'])
        with self.assertRaisesRegex(ValueError, 'Only one'):
            xhs.amend_receipt(self.root, self.state, 'amendment-receipt', '重复登记', 'review.md', rows=rows)

    def test_amendment_scope_and_native_brief_identity_cannot_change_after_registration(self):
        self.first_draft(recorded=False)
        xhs.bind_receipt(self.state, 'draft', 'draft-receipt', self.rows('draft'))
        rows = self.amendment_rows('completed')
        xhs.amend_receipt(self.root, self.state, 'amendment-receipt', '限定一次具体补充', 'review.md', True, rows)
        scope = (self.root / 'review.md').read_text()
        (self.root / 'review.md').write_text('换成另一整个任务')
        with self.assertRaisesRegex(ValueError, 'scope evidence changed'):
            xhs.record(self.root, self.state, 'draft', 'draft.md', rows=rows)
        (self.root / 'review.md').write_text(scope)
        rows[1]['brief_sha256'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'identity or brief changed'):
            xhs.record(self.root, self.state, 'draft', 'draft.md', rows=rows)

    def test_one_revision_archives_first_draft_and_keeps_source_and_brief_locked(self):
        self.first_draft()
        initial = copy.deepcopy(self.state)
        original_files = {name: (self.root / name).read_bytes() for name in ('draft.md', 'cards.json',
            'writing-report.json', 'output/card-01.png', 'output/render-manifest.json', 'output/preview.html')}
        # The native status is authoritative even if the saved receipt lagged.
        self.state['receipts']['draft']['status'] = 'running'
        xhs.revise(self.root, self.state, '限定事实范围', 'review.md', rows=self.rows('draft'))
        self.assertEqual((self.state['revision_count'], self.state['stage'], self.state['status']), (1, 'draft', 'active'))
        self.assertEqual(self.state['artifacts'], {k: initial['artifacts'][k] for k in ('collect', 'brief')})
        self.assertEqual(self.state['receipts'], {'collect': initial['receipts']['collect']})
        self.assertEqual(self.state['dispatch_tokens']['collect'], initial['dispatch_tokens']['collect'])
        self.assertNotEqual(self.state['dispatch_tokens']['draft'], initial['dispatch_tokens']['draft'])
        archive = self.root / 'history/revision-0'
        for name, content in original_files.items():
            self.assertEqual((archive / name).read_bytes(), content)
            self.assertEqual((self.root / name).read_bytes(), content)
        manifest = json.loads((archive / 'manifest.json').read_text())
        self.assertEqual(manifest['artifacts'], initial['artifacts'])
        self.assertEqual(manifest['draft_receipt']['status'], 'completed')
        self.assertEqual(manifest['draft_token'], initial['dispatch_tokens']['draft'])
        self.assertEqual((archive / '_revision-review.md').read_bytes(), (self.root / 'review.md').read_bytes())
        (self.root / 'draft.md').write_text('# 修订稿\n\n保留有来源事实。')
        xhs.verify_artifacts(self.root, self.state)
        (self.root / 'sources.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            xhs.verify_artifacts(self.root, self.state)

    def test_revised_work_needs_new_receipt_and_cannot_be_revised_twice(self):
        self.first_draft(acceptance=False)
        old_rows = self.rows('draft')
        xhs.revise(self.root, self.state, '只改无证据的范围表述', 'review.md', rows=old_rows)
        with self.assertRaisesRegex(ValueError, 'Retired draft receipt'):
            xhs.bind_receipt(self.state, 'draft', 'draft-receipt', old_rows)
        (self.root / 'draft.md').write_text('# 修订稿\n\n范围已注明来源。')
        new_rows = self.rows('draft')
        new_rows[0]['id'] = 'revised-receipt'
        new_rows[0]['thread_id'] = 'revised-thread'
        xhs.record(self.root, self.state, 'draft', 'draft.md', 'revised-receipt', rows=new_rows)
        xhs.finish(self.root, self.state)
        self.assertEqual(self.state['status'], 'pending_user_review')
        with self.assertRaisesRegex(ValueError, 'Only one'):
            xhs.revise(self.root, self.state, '还想再改', 'review.md', rows=new_rows)

    def test_revision_checks_live_completion_and_snapshot_before_archiving(self):
        with self.assertRaisesRegex(ValueError, 'Record a completed draft'):
            xhs.revise(self.root, self.state, '改稿', 'review.md', rows=[])
        self.first_draft()
        before = copy.deepcopy(self.state)
        with self.assertRaisesRegex(ValueError, 'must be completed'):
            xhs.revise(self.root, self.state, '改稿', 'review.md', rows=self.rows('draft', 'running'))
        self.assertEqual(self.state, before)
        self.assertFalse((self.root / 'history').exists())
        (self.root / 'draft.md').write_text('changed after record')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            xhs.revise(self.root, self.state, '改稿', 'review.md', rows=self.rows('draft'))
        self.assertFalse((self.root / 'history').exists())

    def test_revision_archive_and_review_are_immutable(self):
        self.first_draft()
        xhs.revise(self.root, self.state, '限定事实范围', 'review.md', rows=self.rows('draft'))
        archived = self.root / 'history/revision-0/draft.md'
        original = archived.read_bytes()
        archived.write_text('replace history')
        with self.assertRaisesRegex(ValueError, 'history artifact changed'):
            xhs.verify_artifacts(self.root, self.state)
        archived.write_bytes(original)
        added = archived.parent / 'extra.txt'
        added.write_text('new history entry')
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            xhs.verify_artifacts(self.root, self.state)
        added.unlink()
        (self.root / 'review.md').write_text('silently replace requested scope')
        with self.assertRaisesRegex(ValueError, 'Revision evidence changed'):
            xhs.verify_artifacts(self.root, self.state)

    def test_revision_never_overwrites_existing_history_or_uses_source_as_review(self):
        self.first_draft()
        with self.assertRaisesRegex(ValueError, 'separate review'):
            xhs.revise(self.root, self.state, '改稿', 'draft.md', rows=self.rows('draft'))
        with self.assertRaisesRegex(ValueError, 'project-relative Markdown'):
            xhs.revise(self.root, self.state, '改稿', str(self.root / 'review.md'), rows=self.rows('draft'))
        archive = self.root / 'history/revision-0'
        archive.mkdir(parents=True)
        (archive / 'keep.txt').write_text('original')
        with self.assertRaisesRegex(ValueError, 'must not be overwritten'):
            xhs.revise(self.root, self.state, '改稿', 'review.md', rows=self.rows('draft'))
        self.assertEqual((archive / 'keep.txt').read_text(), 'original')

    def test_source_mode_and_limitations_are_preserved(self):
        self.collect()
        self.assertEqual(self.state['source_mode'], 'official_web')
        self.assertEqual(self.state['source_limitations'], ['非小红书样本'])

    def test_source_must_exist_and_worker_must_complete(self):
        (self.root / 'sources.json').write_text(json.dumps({'status': 'ready', 'samples': []}))
        with self.assertRaisesRegex(ValueError, 'not completed'):
            xhs.record(self.root, self.state, 'collect', 'sources.json', 'collect-receipt', rows=self.rows(status='running'))
        with self.assertRaisesRegex(ValueError, 'blocked/empty'):
            xhs.record(self.root, self.state, 'collect', 'sources.json', 'collect-receipt', rows=self.rows())

    def test_wrong_recipient_and_old_receipt_are_rejected(self):
        rows = self.rows()
        rows[0]['bot_id'] = 'unrelated'
        with self.assertRaisesRegex(ValueError, 'different recipient'):
            xhs.bind_receipt(self.state, 'collect', 'collect-receipt', rows)
        rows = self.rows()
        rows[0]['created_at'] = 0
        with self.assertRaisesRegex(ValueError, 'predates'):
            xhs.bind_receipt(self.state, 'collect', 'collect-receipt', rows)

    def test_a_second_receipt_cannot_replace_the_first(self):
        xhs.bind_receipt(self.state, 'collect', 'collect-receipt', self.rows())
        with self.assertRaisesRegex(ValueError, 'already has a receipt'):
            xhs.bind_receipt(self.state, 'collect', 'new-receipt', [])

    def test_unregistered_same_stage_assignments_block_binding_and_completion(self):
        (self.root / 'sources.json').write_text(json.dumps({
            'status': 'collected', 'samples': [{'source_url': 'https://www.anthropic.com/news'}]}))
        for status in ('running', 'completed', 'failed', 'cancelled'):
            rows = self.rows()
            rows.append({**rows[0], 'id': 'duplicate-receipt', 'status': status})
            before = copy.deepcopy(self.state)
            with self.subTest(status=status):
                with self.assertRaisesRegex(ValueError, 'Unregistered.*assignment'):
                    xhs.bind_receipt(self.state, 'collect', 'collect-receipt', rows)
                with self.assertRaisesRegex(ValueError, 'Unregistered.*assignment'):
                    xhs.record(self.root, self.state, 'collect', 'sources.json', 'collect-receipt', rows=rows)
                self.assertEqual(self.state, before)

    def test_duplicate_added_after_binding_is_caught_before_record(self):
        xhs.bind_receipt(self.state, 'collect', 'collect-receipt', self.rows())
        rows = self.rows()
        rows.append({**rows[0], 'id': 'late-duplicate', 'status': 'running'})
        (self.root / 'sources.json').write_text(json.dumps({
            'status': 'collected', 'samples': [{'source_url': 'https://www.anthropic.com/news'}]}))
        before = copy.deepcopy(self.state)
        with self.assertRaisesRegex(ValueError, 'Unregistered.*assignment'):
            xhs.record(self.root, self.state, 'collect', 'sources.json', rows=rows)
        self.assertEqual(self.state, before)

    def test_other_stage_tokens_do_not_block_the_selected_receipt(self):
        rows = self.rows() + self.rows('draft', 'running')
        xhs.bind_receipt(self.state, 'collect', 'collect-receipt', rows)
        self.assertEqual(self.state['receipts']['collect']['status'], 'completed')

    def test_registered_same_token_amendment_waits_for_both_workers(self):
        self.first_draft(recorded=False)
        xhs.bind_receipt(self.state, 'draft', 'draft-receipt', self.rows('draft'))
        rows = self.amendment_rows(token=True)
        xhs.amend_receipt(self.root, self.state, 'amendment-receipt', '一次局部补充', 'review.md', rows=rows)
        with self.assertRaisesRegex(ValueError, 'both be completed'):
            xhs.record(self.root, self.state, 'draft', 'draft.md', rows=rows)
        rows[1]['status'] = 'completed'
        rows[0]['status'] = 'running'
        with self.assertRaisesRegex(ValueError, 'not completed'):
            xhs.record(self.root, self.state, 'draft', 'draft.md', rows=rows)
        rows[0]['status'] = 'completed'
        xhs.record(self.root, self.state, 'draft', 'draft.md', rows=rows)
        self.assertEqual(self.state['stage'], 'review')

    def test_amendment_registration_and_record_reject_an_extra_assignment(self):
        self.first_draft(recorded=False)
        xhs.bind_receipt(self.state, 'draft', 'draft-receipt', self.rows('draft'))
        rows = self.amendment_rows('completed', token=True)
        extra = {**rows[1], 'id': 'unregistered-third', 'status': 'running'}
        before = copy.deepcopy(self.state)
        with self.assertRaisesRegex(ValueError, 'Unregistered.*assignment'):
            xhs.amend_receipt(self.root, self.state, 'amendment-receipt', '一次局部补充', 'review.md', rows=rows + [extra])
        self.assertEqual(self.state, before)
        xhs.amend_receipt(self.root, self.state, 'amendment-receipt', '一次局部补充', 'review.md', rows=rows)
        before = copy.deepcopy(self.state)
        with self.assertRaisesRegex(ValueError, 'Unregistered.*assignment'):
            xhs.record(self.root, self.state, 'draft', 'draft.md', rows=rows + [extra])
        self.assertEqual(self.state, before)

    def test_legacy_manifest_variable_binds_the_correct_deployment(self):
        with patch.dict(os.environ, {'WORKFLOUR_XHS_DEPLOYMENT': str(self.manifest)}, clear=True), \
                patch.object(Path, 'home', return_value=Path(self.temp.name)):
            xhs.bind_receipt(self.state, 'collect', 'collect-receipt', self.rows())
        self.assertEqual(self.state['receipts']['collect']['bot_id'], 'collector')

    def test_manifest_resolution_matches_provisioner_and_primary_variable_wins(self):
        environments = [
            ({}, Path.home() / '.workflour/xhs/deployment.json'),
            ({'WORKFLOUR_XHS_DEPLOYMENT': str(self.manifest)}, self.manifest),
            ({'XHS_DEPLOYMENT_MANIFEST': str(self.manifest),
              'WORKFLOUR_XHS_DEPLOYMENT': '/unused/legacy.json'}, self.manifest),
            ({'WORKFLOUR_XHS_DEPLOYMENT': '~/custom-xhs/deployment.json'},
             Path.home() / 'custom-xhs/deployment.json'),
        ]
        for env, expected in environments:
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True):
                spec = importlib.util.spec_from_file_location('xhs_provision_paths',
                    Path(xhs.__file__).with_name('provision-xhs-team.py'))
                provision = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(provision)
                self.assertEqual(xhs.deployment_path(), expected)
                self.assertEqual(provision.DEFAULT_MANIFEST, expected)

    def test_cannot_skip_collection(self):
        with self.assertRaisesRegex(ValueError, 'Complete stages'):
            xhs.record(self.root, self.state, 'brief', 'BRIEF.md')

    def test_changed_source_invalidates_next_stage(self):
        self.collect()
        (self.root / 'sources.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            xhs.record(self.root, self.state, 'brief', 'BRIEF.md')

    def test_artifact_cannot_escape_through_symlink(self):
        secret = Path(self.temp.name) / 'outside.txt'
        secret.write_text('outside')
        (self.root / 'outside.txt').symlink_to(secret)
        with self.assertRaises(ValueError):
            xhs.artifact(self.root, 'outside.txt')

    def test_existing_project_is_never_reinitialized(self):
        (self.root / 'unrelated.txt').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'new/empty'):
            xhs.initialize(self.root, 'different topic')
        self.assertEqual((self.root / 'unrelated.txt').read_text(), 'keep')

    def test_finish_needs_actual_images_and_keeps_user_review_pending(self):
        self.collect()
        xhs.record(self.root, self.state, 'brief', 'BRIEF.md')
        (self.root / 'draft.md').write_text('# Claude 新消息\n\n正文和标签。')
        xhs.record(self.root, self.state, 'draft', 'draft.md', 'draft-receipt', rows=self.rows('draft'))
        (self.root / 'writing-report.json').write_text(json.dumps({'status': 'ready', 'images': [], 'image_generation': {'status': 'template_only'}}))
        with self.assertRaisesRegex(ValueError, 'Actual image'):
            xhs.finish(self.root, self.state)
        (self.root / 'fake.png').write_text('a prompt is not an image')
        (self.root / 'writing-report.json').write_text(json.dumps({'status': 'partial', 'images': ['fake.png'], 'image_generation': {'status': 'blocked'}}))
        with self.assertRaisesRegex(ValueError, 'PNG'):
            xhs.finish(self.root, self.state)

    def test_consult_or_unrelated_stage_marker_is_rejected(self):
        rows = self.rows()
        rows[0].update(mode='consult', requester_bot_id='wrong', tokens=[])
        with self.assertRaisesRegex(ValueError, 'project stage marker'):
            xhs.bind_receipt(self.state, 'collect', 'collect-receipt', rows)

    def test_png_validation_rejects_header_only_and_accepts_decodable_image(self):
        with self.assertRaises(ValueError):
            xhs.png_dimensions(b'\x89PNG\r\n\x1a\nnot-an-image')
        def chunk(kind, payload):
            return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)
        data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b'\x00\x10\x20\x30')) + chunk(b'IEND', b'')
        self.assertEqual(xhs.png_dimensions(data), (1, 1))

    def test_attributed_review_preserves_the_original_draft_and_freezes_the_new_version(self):
        self.first_draft(acceptance=False)
        original = copy.deepcopy(self.state['artifacts']['draft'])
        (self.root / 'draft.reviewed.md').write_text('# 编辑版\n\n清楚说明开放范围。')
        report_path = self.root / 'writing-report.json'
        report = json.loads(report_path.read_text())
        report['draft_file'] = 'draft.reviewed.md'
        report_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'author and original draft hash'):
            xhs.finish(self.root, self.state)
        report['maintenance_review'] = {'author': 'maintenance', 'base_draft_sha256': original['sha256']}
        report_path.write_text(json.dumps(report))
        xhs.finish(self.root, self.state)
        self.assertEqual(self.state['artifacts']['draft'], original)
        self.assertEqual(self.state['artifacts']['reviewed_draft']['path'], 'draft.reviewed.md')
        self.assertEqual(self.state['status'], 'pending_user_review')
        (self.root / 'draft.reviewed.md').write_text('changed after review')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            xhs.verify_artifacts(self.root, self.state)

    def native_image_evidence(self):
        directory = self.root / 'image-generation'
        directory.mkdir()
        source = directory / 'original.png'
        source.write_bytes((self.root / 'output/card-01.png').read_bytes())
        evidence = {'version': 2, 'status': 'generated_pending_visual_review',
                    'native_status': 'SUCCESS', 'exit_code': 0, 'prompt_sent': True,
                    'finished_at': '2026-11-12T05:00:00Z',
                    'images': [{'file': 'original.png',
                                'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}]}
        path = directory / 'image-evidence.json'
        path.write_text(json.dumps(evidence))
        return path, source, evidence

    def writing_generation(self, generation):
        path = self.root / 'writing-report.json'
        report = json.loads(path.read_text())
        report.update(status='ready', image_generation=generation)
        path.write_text(json.dumps(report))
        return report

    def test_generated_images_require_completed_native_evidence_without_mutating_state(self):
        self.first_draft(acceptance=False)
        evidence_path, source, valid = self.native_image_evidence()
        before = copy.deepcopy(self.state)
        for generation in ({'status': 'passed'}, {'status': 'reused'},
                           {'status': 'passed', 'evidence': 'image-generation/missing.json'}):
            with self.subTest(generation=generation):
                self.writing_generation(generation)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    xhs.finish(self.root, self.state)
                self.assertEqual(self.state, before)
        for field, value in [('status', 'checking'), ('status', 'blocked'),
                             ('native_status', 'RUNNING'), ('exit_code', 1),
                             ('exit_code', False), ('prompt_sent', False),
                             ('finished_at', None), ('images', [])]:
            with self.subTest(field=field, value=value):
                evidence_path.write_text(json.dumps({**valid, field: value}))
                self.writing_generation({'status': 'passed', 'evidence': str(evidence_path)})
                with self.assertRaises(ValueError):
                    xhs.finish(self.root, self.state)
                self.assertEqual(self.state, before)

    def test_native_evidence_aliases_and_project_paths_freeze_receipts_and_originals(self):
        self.first_draft(acceptance=False)
        evidence_path, source, evidence = self.native_image_evidence()
        for status, key, absolute in [('passed', 'evidence', False), ('reused', 'source_evidence', True)]:
            with self.subTest(status=status):
                state = copy.deepcopy(self.state)
                generation = {'status': status, key: str(evidence_path if absolute else evidence_path.relative_to(self.root))}
                if status == 'reused':
                    generation.update(reused_image_path=str(source), reused_image_sha256=evidence['images'][0]['sha256'])
                self.writing_generation(generation)
                xhs.finish(self.root, state)
                self.assertEqual(state['status'], 'pending_user_review')
                self.assertEqual(state['artifacts']['image_evidence_1'], xhs.artifact(self.root, str(evidence_path)))
                self.assertEqual(state['artifacts']['image_original_1'], xhs.artifact(self.root, str(source)))
                for path in (evidence_path, source):
                    original = path.read_bytes()
                    path.write_bytes(original + b'changed')
                    with self.assertRaisesRegex(ValueError, 'artifact changed'):
                        xhs.verify_artifacts(self.root, state)
                    path.write_bytes(original)

    def test_generation_evidence_rejects_missing_changed_invalid_or_unrelated_originals(self):
        self.first_draft(acceptance=False)
        evidence_path, source, evidence = self.native_image_evidence()
        before = copy.deepcopy(self.state)
        cases = [({'file': 'missing.png', 'sha256': evidence['images'][0]['sha256']}, None),
                 ({'file': 'original.png', 'sha256': '0' * 64}, None),
                 ({'file': 'original.png', 'sha256': hashlib.sha256(b'not a raster').hexdigest()}, b'not a raster'),
                 ({'file': '../output/card-01.png', 'sha256': evidence['images'][0]['sha256']}, None)]
        original = source.read_bytes()
        for row, data in cases:
            with self.subTest(row=row):
                source.write_bytes(original if data is None else data)
                evidence_path.write_text(json.dumps({**evidence, 'images': [row]}))
                self.writing_generation({'status': 'passed', 'evidence': str(evidence_path)})
                with self.assertRaises((ValueError, FileNotFoundError)):
                    xhs.finish(self.root, self.state)
                self.assertEqual(self.state, before)
        source.write_bytes(original)
        evidence_path.write_text(json.dumps(evidence))
        self.writing_generation({'status': 'reused', 'source_evidence': str(evidence_path),
                                 'reused_image_path': 'output/card-01.png',
                                 'reused_image_sha256': evidence['images'][0]['sha256']})
        with self.assertRaisesRegex(ValueError, 'must match an original'):
            xhs.finish(self.root, self.state)
        self.assertEqual(self.state, before)

    def test_generation_evidence_and_originals_cannot_escape_the_project(self):
        self.first_draft(acceptance=False)
        evidence_path, source, evidence = self.native_image_evidence()
        before = copy.deepcopy(self.state)
        outside = Path(self.temp.name) / 'outside.json'
        outside.write_text(json.dumps(evidence))
        link = self.root / 'evidence-link.json'
        link.symlink_to(outside)
        for name in (str(outside), str(link)):
            self.writing_generation({'status': 'passed', 'evidence': name})
            with self.assertRaises(ValueError):
                xhs.finish(self.root, self.state)
            self.assertEqual(self.state, before)
        outside_image = Path(self.temp.name) / 'outside.png'
        outside_image.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(outside_image)
        self.writing_generation({'status': 'passed', 'evidence': str(evidence_path)})
        with self.assertRaises(ValueError):
            xhs.finish(self.root, self.state)
        self.assertEqual(self.state, before)

    def test_explicit_non_ai_reuse_freezes_provided_image_without_claiming_generation(self):
        self.first_draft(acceptance=False)
        source = self.root / 'provided.png'
        source.write_bytes((self.root / 'output/card-01.png').read_bytes())
        generation = {'status': 'reused', 'ai_generated': False,
                      'reused_image_path': 'provided.png',
                      'reused_image_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        before = copy.deepcopy(self.state)
        for invalid in ({**generation, 'status': 'passed'},
                        {**generation, 'source_evidence': 'irrelevant.json'},
                        {**generation, 'reused_image_sha256': '0' * 64}):
            self.writing_generation(invalid)
            with self.assertRaises(ValueError):
                xhs.finish(self.root, self.state)
            self.assertEqual(self.state, before)
        self.writing_generation(generation)
        xhs.finish(self.root, self.state)
        self.assertIn('image_original_1', self.state['artifacts'])
        self.assertNotIn('image_evidence_1', self.state['artifacts'])
        source.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            xhs.verify_artifacts(self.root, self.state)

    def test_finish_late_failure_never_partially_records_images_or_reviewed_draft(self):
        self.first_draft(acceptance=False)
        (self.root / 'draft.reviewed.md').write_text('A separate attributed edit')
        report_path = self.root / 'writing-report.json'
        report = json.loads(report_path.read_text())
        report.update(draft_file='draft.reviewed.md',
                      maintenance_review={'author': 'maintenance', 'base_draft_sha256': self.state['artifacts']['draft']['sha256']})
        report['images'].append('output/missing.png')
        report_path.write_text(json.dumps(report))
        before = copy.deepcopy(self.state)
        with self.assertRaises(FileNotFoundError):
            xhs.finish(self.root, self.state)
        self.assertEqual(self.state, before)

    def test_multiple_native_evidence_files_remain_in_revision_archive(self):
        self.first_draft(acceptance=False)
        first, source, evidence = self.native_image_evidence()
        second = source.parent / 'second-evidence.json'
        second.write_text(json.dumps(evidence))
        self.writing_generation({'status': 'passed', 'evidence': [str(first), str(second)],
                                 'source_evidence': str(first)})
        xhs.finish(self.root, self.state)
        self.assertIn('image_evidence_2', self.state['artifacts'])
        self.assertNotIn('image_evidence_3', self.state['artifacts'])
        xhs.revise(self.root, self.state, 'One bounded edit', 'review.md', rows=self.rows('draft'))
        archive = self.root / 'history/revision-0'
        for path in (first, second, source):
            self.assertEqual((archive / path.relative_to(self.root)).read_bytes(), path.read_bytes())


if __name__ == '__main__':
    unittest.main()
