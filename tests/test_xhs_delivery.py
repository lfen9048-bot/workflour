import copy
import json
from pathlib import Path
import signal
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import xhs_delivery as delivery


def png():
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1080, 1440, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + b'\x20\x30\x40' * 1080) * 1440)) + chunk(b'IEND', b''))


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / 'post'
        self.project.mkdir()
        self.wf = delivery.workflow
        state = self.wf.initialize(self.project, '流程测试', 'planner')
        (self.project / 'sources.json').write_text('{"samples": [{"source_url":"https://example.com"}]}')
        (self.project / 'draft.md').write_text('已有模型原稿，不覆盖。')
        (self.project / 'cards.json').write_text(json.dumps({'cards': [{'title': '流程测试'}]}))
        state.update(stage='draft', artifacts={k: self.wf.artifact(self.project, name)
                     for k, name in [('collect', 'sources.json'), ('brief', 'BRIEF.md')]},
                     image_policy={'max_requests': 1, 'useG1Credits': False})
        self.wf.write(self.project / '.xhs/state.json', state)
        self.state = state
        self.render = patch.object(delivery, 'run_renderer', side_effect=self.fake_render).start()
        self.addCleanup(patch.stopall)

    def fake_render(self, project, name):
        output = project / 'output'
        output.mkdir()
        (output / 'card-01.png').write_bytes(png())
        (output / 'preview.html').write_text('<html>真实测试像素</html>')
        value = {'images': [self.wf.artifact(project, 'output/card-01.png')]}
        self.wf.write(output / 'render-manifest.json', value)
        return value

    def evidence(self):
        folder = self.project / 'old-generation'
        folder.mkdir()
        self.wf.write(folder / 'image-evidence.json', {'status': 'blocked', 'images': [],
                      'reason': 'no_valid_new_native_image', 'finished_at': self.wf.now(),
                      'billing_override': {'useG1Credits': False}})
        return 'old-generation/image-evidence.json'

    def test_template_requires_visual_ack_and_duplicate_prepare_is_read_only(self):
        original_state = (self.project / '.xhs/state.json').read_bytes()
        first = delivery.prepare(self.project)
        self.assertEqual(first['status'], 'awaiting_visual_review')
        self.assertFalse((self.project / 'writing-report.json').exists())
        self.assertEqual(delivery.prepare(self.project), first)
        self.assertEqual(self.render.call_count, 1)
        with self.assertRaisesRegex(ValueError, 'every'):
            delivery.confirm(self.project, [])
        self.assertEqual(delivery.confirm(self.project, first['review_required'])['status'], 'ready')
        final = (self.project / 'writing-report.json').read_bytes()
        delivery.confirm(self.project, first['review_required'])
        self.assertEqual((self.project / 'writing-report.json').read_bytes(), final)
        self.assertEqual((self.project / '.xhs/state.json').read_bytes(), original_state)

    def test_reuse_blocked_evidence_delivers_partial_without_model_calls(self):
        evidence = self.evidence()
        before = (self.project / evidence).read_bytes()
        with patch.object(delivery.images, 'run_print') as native:
            prepared = delivery.prepare(self.project, existing_image_evidence=evidence)
            delivery.confirm(self.project, prepared['review_required'])
            native.assert_not_called()
        report = json.loads((self.project / 'writing-report.json').read_text())
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['image_generation']['status'], 'blocked')
        self.assertEqual((self.project / evidence).read_bytes(), before)

    def test_once_only_generation_falls_back_and_keeps_reservation(self):
        (self.project / 'prompt.txt').write_text('一个示意插图')
        def blocked(output, prompt, **kwargs):
            self.assertEqual(json.loads((self.project / 'delivery/receipt.json').read_text())['status'], 'preparing')
            self.wf.write(output / 'image-evidence.json', {'status': 'blocked', 'images': [],
                          'reason': 'quota', 'finished_at': self.wf.now()})
        with patch.object(delivery.images, 'run_print', side_effect=blocked) as native:
            prepared = delivery.prepare(self.project, image_prompt_file='prompt.txt')
            delivery.prepare(self.project, image_prompt_file='prompt.txt')
            self.assertEqual(native.call_count, 1)
        self.assertEqual(prepared['image_generation']['status'], 'blocked')
        with self.assertRaisesRegex(ValueError, 'original request'):
            delivery.prepare(self.project)

    def test_no_image_authorization_rejects_before_reserving(self):
        (self.project / 'prompt.txt').write_text('插图')
        self.state.pop('image_policy')
        self.wf.write(self.project / '.xhs/state.json', self.state)
        with self.assertRaisesRegex(ValueError, 'authorization'):
            delivery.prepare(self.project, image_prompt_file='prompt.txt')
        self.assertFalse((self.project / 'delivery/receipt.json').exists())

    def test_pending_crash_does_not_start_new_generation(self):
        folder = self.project / 'delivery'
        folder.mkdir()
        self.wf.write(folder / 'receipt.json', {'status': 'preparing', 'draft_token': self.state['dispatch_tokens']['draft'], 'request':
                      {'image_prompt_file': None, 'existing_image_evidence': None}})
        with patch.object(delivery.images, 'run_print') as native:
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                delivery.prepare(self.project)
            native.assert_not_called()

    def test_cancellation_preserves_failure_and_no_final_report(self):
        (self.project / 'prompt.txt').write_text('插图')
        with patch.object(delivery.images, 'run_print', side_effect=delivery.DeliveryCancelled):
            with self.assertRaises(delivery.DeliveryCancelled):
                delivery.prepare(self.project, image_prompt_file='prompt.txt')
        receipt = json.loads((self.project / 'delivery/receipt.json').read_text())
        self.assertEqual(receipt['status'], 'failed')
        self.assertFalse((self.project / 'writing-report.json').exists())

    def test_modified_original_or_image_rejects_visual_confirmation(self):
        prepared = delivery.prepare(self.project)
        (self.project / 'output/card-01.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            delivery.confirm(self.project, prepared['review_required'])

    def test_outside_evidence_and_symlink_directories_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'relative'):
            delivery.prepare(self.project, existing_image_evidence='/tmp/outside.json')
        (self.project / 'delivery/lock').unlink()
        (self.project / 'delivery').rmdir()
        (self.project / 'delivery').symlink_to(self.tmp.name, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            delivery.prepare(self.project)

    def test_render_failure_retains_image_receipt_and_prevents_regeneration(self):
        evidence = self.evidence()
        self.render.side_effect = ValueError('overflow')
        with self.assertRaisesRegex(ValueError, 'overflow'):
            delivery.prepare(self.project, existing_image_evidence=evidence)
        receipt = json.loads((self.project / 'delivery/receipt.json').read_text())
        self.assertEqual(receipt['status'], 'failed')
        self.assertEqual(receipt['image_generation']['status'], 'blocked')

    def test_recovery_and_prior_attempt_prevent_new_generation_before_reservation(self):
        (self.project / 'prompt.txt').write_text('插图')
        recovery = self.project / '.xhs/recovery'
        recovery.mkdir()
        (recovery / 'resume.json').write_text('{}')
        with patch.object(delivery.images, 'run_print') as native:
            with self.assertRaisesRegex(ValueError, 'Recovery'):
                delivery.prepare(self.project, image_prompt_file='prompt.txt')
            (recovery / 'resume.json').unlink()
            self.evidence()
            with self.assertRaisesRegex(ValueError, 'Prior image'):
                delivery.prepare(self.project, image_prompt_file='prompt.txt')
            native.assert_not_called()

    def test_confirm_recovers_after_report_write_before_ready_receipt(self):
        prepared = delivery.prepare(self.project)
        save = delivery.save_receipt
        def interrupt(directory, receipt, status, **fields):
            if status == 'ready':
                raise OSError('interrupted ready write')
            return save(directory, receipt, status, **fields)
        with patch.object(delivery, 'save_receipt', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'interrupted'):
                delivery.confirm(self.project, prepared['review_required'])
        report = (self.project / 'writing-report.json').read_bytes()
        self.assertEqual(delivery.confirm(self.project, prepared['review_required'])['status'], 'ready')
        self.assertEqual((self.project / 'writing-report.json').read_bytes(), report)

    def test_revise_refuses_running_or_uncertain_delivery(self):
        with delivery.delivery_lock(self.project):
            with self.assertRaisesRegex(ValueError, 'already running'):
                self.wf.revise(self.project, self.state, '修复排版', 'review.md')
        self.wf.write(self.project / 'delivery/receipt.json', {'status': 'preparing'})
        with self.assertRaisesRegex(ValueError, 'preparing'):
            self.wf.revise(self.project, self.state, '修复排版', 'review.md')

    def test_revision_archives_delivery_and_allows_fresh_template_prepare(self):
        prepared = delivery.prepare(self.project)
        delivery.confirm(self.project, prepared['review_required'])
        state = copy.deepcopy(self.state)
        state['artifacts']['draft'] = self.wf.artifact(self.project, 'draft.md')
        primary = {'id': 'writer-receipt', 'status': 'completed', 'bot_id': 'writer',
                   'thread_id': 'writer-thread', 'created_at': 1}
        state['receipts']['draft'] = primary
        self.wf.finish(self.project, state)
        (self.project / 'review.md').write_text('只调整卡片排版，不重采集或生图。')
        with patch.object(self.wf, 'native_receipt', return_value=primary):
            self.wf.revise(self.project, state, '局部排版', 'review.md')
        self.wf.write(self.project / '.xhs/state.json', state)
        self.assertTrue((self.project / 'history/revision-0/delivery/receipt.json').is_file())
        self.assertFalse((self.project / 'delivery').exists())
        self.assertEqual(delivery.prepare(self.project)['status'], 'awaiting_visual_review')
        self.wf.verify_artifacts(self.project, state)

    def test_finish_checks_synchronous_receipt_and_locks_failed_image_evidence(self):
        evidence = self.evidence()
        prepared = delivery.prepare(self.project, existing_image_evidence=evidence)
        delivery.confirm(self.project, prepared['review_required'])
        state = copy.deepcopy(self.state)
        state['artifacts']['draft'] = self.wf.artifact(self.project, 'draft.md')
        self.wf.finish(self.project, state)
        self.assertEqual(state['status'], 'pending_user_review')
        self.assertIn(evidence, [a['path'] for a in state['artifacts'].values()])
        (self.project / evidence).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.wf.verify_artifacts(self.project, state)

    def test_successful_original_is_validated_and_must_also_be_viewed(self):
        folder = self.project / 'prior'
        folder.mkdir()
        (folder / 'image.png').write_bytes(png())
        saved = self.wf.artifact(self.project, 'prior/image.png')
        self.wf.write(folder / 'image-evidence.json', {'status': 'generated_pending_visual_review',
                      'native_status': 'SUCCESS', 'exit_code': 0, 'prompt_sent': True,
                      'finished_at': self.wf.now(), 'images': [{'file': 'image.png', 'sha256': saved['sha256']}]})
        prepared = delivery.prepare(self.project, existing_image_evidence='prior/image-evidence.json')
        self.assertEqual(prepared['review_required'], ['prior/image.png', 'output/card-01.png'])
        with self.assertRaisesRegex(ValueError, 'every'):
            delivery.confirm(self.project, ['output/card-01.png'])
        delivery.confirm(self.project, prepared['review_required'])
        state = copy.deepcopy(self.state)
        state['artifacts']['draft'] = self.wf.artifact(self.project, 'draft.md')
        self.wf.finish(self.project, state)
        self.assertEqual(state['delivery_status'], 'ready')

    def test_new_contract_cannot_finish_after_removing_delivery_receipt(self):
        prepared = delivery.prepare(self.project)
        delivery.confirm(self.project, prepared['review_required'])
        state = copy.deepcopy(self.state)
        state['delivery_contract'] = 'synchronous-v1'
        state['artifacts']['draft'] = self.wf.artifact(self.project, 'draft.md')
        (self.project / 'delivery/receipt.json').unlink()
        with self.assertRaisesRegex(ValueError, 'requires a completed'):
            self.wf.finish(self.project, state)


if __name__ == '__main__':
    unittest.main()
