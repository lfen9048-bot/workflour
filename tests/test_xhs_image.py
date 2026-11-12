import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
import zlib


SPEC = importlib.util.spec_from_file_location('xhs_image', Path(__file__).resolve().parents[1] / 'scripts/xhs-image.py')
image = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(image)


def png(path, width=2, height=3):
    def chunk(kind, content):
        return struct.pack('>I', len(content)) + kind + content + struct.pack('>I', zlib.crc32(kind + content) & 0xffffffff)
    data = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\x00' + b'\x20\x40\x60' * width) * height)) + chunk(b'IEND', b''))
    path.write_bytes(data)
    return data


class XhsImageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / 'output'
        self.output.mkdir()
        self.brain = self.root / 'brain'
        self.brain.mkdir()
        self.roots = patch.object(image, 'default_artifact_roots', return_value=(self.brain,))
        self.roots.start()
        self.addCleanup(self.roots.stop)

    def receipt(self, response, status='SUCCESS'):
        return json.dumps({'status': status, 'response': response, 'duration_seconds': 2,
                           'num_turns': 3, 'usage': {'input_tokens': 7, 'secret': 'DO_NOT_SAVE'},
                           'thoughts': 'HIDDEN_THOUGHTS', 'tool_args': {'secret': 'DO_NOT_SAVE'}})

    def test_full_success_waits_for_cli_and_copies_real_artifact(self):
        artifact = self.brain / 'native.png'
        png(artifact)
        response = 'I launched the specialist and am waiting.\n' + str(artifact)
        with patch.object(image, 'execute_print', return_value=(0, self.receipt(response), False)) as execute:
            report = image.run_print(self.output, 'One editorial illustration.', 40)
        self.assertEqual(report['status'], 'generated_pending_visual_review')
        self.assertEqual(report['images'][0]['dimensions'], [2, 3])
        self.assertEqual(report['images'][0]['file'], 'image-01.png')
        self.assertEqual(report['image_model'], 'unverified')
        self.assertFalse(report['native_image_tool_observed'])
        self.assertTrue(artifact.exists(), 'native artifact must be copied, not moved')
        command = execute.call_args.args[0]
        self.assertIn('--print', command)
        self.assertIn(image.PRINT_MODEL, command)
        self.assertIn('{"useG1Credits":false}', command)
        self.assertNotIn('--agent', command)
        self.assertNotIn('--dangerously-skip-permissions', command)
        saved = (self.output / 'image-evidence.json').read_text()
        self.assertNotIn('HIDDEN_THOUGHTS', saved)
        self.assertNotIn('DO_NOT_SAVE', saved)
        self.assertEqual(report['usage'], {'input_tokens': 7})
        self.assertEqual(execute.call_count, 1)

    def test_partial_or_non_success_response_is_never_success(self):
        artifact = self.brain / 'native.png'
        png(artifact)
        with patch.object(image, 'execute_print', return_value=(0, self.receipt(str(artifact), 'RUNNING'), False)):
            report = image.run_print(self.output, 'brief', 30)
        self.assertEqual(report['status'], 'blocked')
        self.assertEqual(report['reason'], 'native_print_not_complete')
        self.assertEqual(report['images'], [])

    def test_success_with_waiting_text_discovers_only_exact_conversation_artifact(self):
        conversation = '00000000-0000-0000-0000-000000000001'
        unrelated = self.brain / '00000000-0000-0000-0000-000000000002'
        unrelated.mkdir()
        png(unrelated / 'do-not-collect.png', width=9)
        directory = self.brain / conversation
        directory.mkdir()
        png(directory / 'native.png', width=4)
        outside = self.root / 'outside.png'
        png(outside, width=8)
        (directory / 'escaped.png').symlink_to(outside)
        receipt = json.loads(self.receipt('I launched the image specialist; awaiting its final artifact.'))
        receipt['conversation_id'] = conversation
        with patch.object(image, 'execute_print', return_value=(0, json.dumps(receipt), False)):
            report = image.run_print(self.output, 'brief', 30)
        self.assertEqual(report['status'], 'generated_pending_visual_review')
        self.assertEqual(report['images'][0]['dimensions'], [4, 3])
        self.assertEqual(len(report['images']), 1)

    def test_private_cwd_output_is_copied_before_temporary_workspace_is_removed(self):
        seen_workspace = []
        def execute(command, workspace, timeout):
            seen_workspace.append(workspace)
            self.assertFalse(image.within(workspace, image.ROOT))
            self.assertNotIn(str(self.output), command[-1])
            png(workspace / 'cover.png', width=5)
            return 0, self.receipt('Complete.'), False
        with patch.object(image, 'execute_print', side_effect=execute):
            report = image.run_print(self.output, 'brief', 30)
        self.assertEqual(report['status'], 'generated_pending_visual_review')
        self.assertEqual(report['images'][0]['dimensions'], [5, 3])
        self.assertFalse(seen_workspace[0].exists())
        self.assertTrue((self.output / report['images'][0]['file']).is_file())

    def test_conversation_discovery_retains_freshness_and_symlink_checks(self):
        conversation = '00000000-0000-0000-0000-000000000001'
        directory = self.brain / conversation
        directory.mkdir()
        old = directory / 'old.png'
        png(old)
        os.utime(old, (1, 1))
        images, rejected = image.collect_images(self.output, '', time.time(), conversation=conversation)
        self.assertEqual(images, [])
        self.assertEqual(rejected, 1)
        self.assertEqual(image.conversation_artifacts('../outside'), [])

    def test_waiting_text_or_path_without_file_is_blocked(self):
        with patch.object(image, 'execute_print', return_value=(0, self.receipt('Waiting.\n' + str(self.brain / 'missing.png')), False)):
            report = image.run_print(self.output, 'brief', 30)
        self.assertEqual(report['reason'], 'no_valid_new_native_image')
        self.assertEqual(report['images'], [])

    def test_unknown_absolute_and_symlink_escaped_artifacts_are_rejected(self):
        outside = self.root / 'private.png'
        png(outside)
        link = self.brain / 'escaped.png'
        link.symlink_to(outside)
        images, rejected = image.collect_images(self.output, f'{outside}\n{link}', time.time())
        self.assertEqual(images, [])
        self.assertGreaterEqual(rejected, 1)

    def test_existing_native_artifact_is_not_attributed_to_new_run(self):
        artifact = self.brain / 'old.png'
        png(artifact)
        os.utime(artifact, (1, 1))
        images, rejected = image.collect_images(self.output, str(artifact), time.time())
        self.assertEqual(images, [])
        self.assertEqual(rejected, 1)

    def test_copy_does_not_overwrite_an_agent_created_file(self):
        artifact = self.brain / 'native.png'
        png(artifact)
        destination = self.output / 'image-01.png'
        destination.write_bytes(b'keep existing contents')
        images, _ = image.collect_images(self.output, str(artifact), time.time())
        self.assertEqual(destination.read_bytes(), b'keep existing contents')
        self.assertEqual(images, [])

    def test_only_one_image_is_collected(self):
        paths = [self.brain / name for name in ('one.png', 'two.png')]
        for path in paths:
            png(path)
        images, _ = image.collect_images(self.output, '\n'.join(map(str, paths)), time.time())
        self.assertEqual(len(images), 1)

    def test_malformed_raster_is_not_success(self):
        fake = self.output / 'fake.png'
        fake.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 40)
        self.assertIsNone(image.image_info(fake))
        valid = self.output / 'valid.jpg'
        png(valid)  # Actual media type comes from bytes, not the extension.
        self.assertEqual(image.image_info(valid)['media_type'], 'image/png')

    def test_print_does_not_consult_old_acp_block_cache(self):
        legacy = self.root / 'capability.json'
        legacy.write_text(json.dumps({'status': 'blocked', 'reason': 'IMAGE_TOOL_UNAVAILABLE'}))
        with patch.object(image, 'CAPABILITY', legacy), patch.object(image, 'execute_print', return_value=(0, self.receipt('Waiting.'), False)) as execute:
            report = image.run_print(self.output, 'brief', 30)
        self.assertTrue(report['prompt_sent'])
        self.assertEqual(execute.call_count, 1)

    def test_timeout_stops_own_process_group_without_retry(self):
        process = Mock(pid=43210, returncode=-15)
        process.communicate.side_effect = [subprocess.TimeoutExpired('agy', 35), ('discarded', 'discarded')]
        with patch.object(image.subprocess, 'Popen', return_value=process) as popen, patch.object(image.os, 'killpg') as kill:
            code, stdout, timed_out = image.execute_print(['agy', '--print', 'brief'], self.output, 30)
        self.assertTrue(timed_out)
        self.assertEqual(stdout, '')
        self.assertEqual(code, -15)
        self.assertEqual(popen.call_count, 1)
        self.assertTrue(popen.call_args.kwargs['start_new_session'])
        self.assertEqual([call.args for call in kill.call_args_list],
                         [(43210, image.signal.SIGTERM), (43210, image.signal.SIGKILL)])

    def test_api_environment_is_child_only_and_credits_override_is_not_persistent(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-value', 'GOOGLE_APPLICATION_CREDENTIALS': '/unused', 'KEEP_ME': 'yes'}):
            environment = image.subscription_environment()
            self.assertNotIn('GEMINI_API_KEY', environment)
            self.assertNotIn('GOOGLE_APPLICATION_CREDENTIALS', environment)
            self.assertEqual(environment['KEEP_ME'], 'yes')
            self.assertEqual(os.environ['GEMINI_API_KEY'], 'test-value')

    def test_tool_metadata_parser_ignores_thoughts_and_raw_args(self):
        conversation = '00000000-0000-0000-0000-000000000001'
        transcript = self.brain / conversation / '.system_generated/logs/transcript.jsonl'
        transcript.parent.mkdir(parents=True)
        transcript.write_text(json.dumps({'type': 'PLANNER_RESPONSE', 'content': 'hidden',
            'tool_calls': [{'name': 'invoke_subagent', 'args': {'Prompt': 'hidden'}}]}) + '\n')
        self.assertEqual(image.native_tool_names(conversation), ['invoke_subagent'])
        self.assertEqual(image.native_tool_names('../../outside'), [])

    def test_tool_metadata_symlink_cannot_escape_conversation(self):
        conversation = '00000000-0000-0000-0000-000000000001'
        outside = self.root / 'elsewhere'
        log = outside / '.system_generated/logs/transcript.jsonl'
        log.parent.mkdir(parents=True)
        log.write_text(json.dumps({'tool_calls': [{'name': 'should_not_read'}]}) + '\n')
        (self.brain / conversation).symlink_to(outside, target_is_directory=True)
        self.assertEqual(image.native_tool_names(conversation), [])

    def test_cli_refuses_existing_output_and_multiple_images_without_calling_model(self):
        (self.output / 'keep.txt').write_text('keep')
        with patch.object(image.sys, 'argv', ['xhs-image.py', 'generate', '--output-dir', str(self.output), '--prompt-file', '/brief.txt']), patch.object(image, 'run_print') as run:
            with self.assertRaises(SystemExit):
                image.main()
        run.assert_not_called()
        with patch.object(image.sys, 'argv', ['xhs-image.py', 'generate', '--output-dir', str(self.output), '--max-images', '2']):
            with self.assertRaises(SystemExit):
                image.main()


if __name__ == '__main__':
    unittest.main()
