"""Enforce requested X/YouTube scope before importing or contacting providers."""
import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import xhs_collection_limits as limits
spec = importlib.util.spec_from_file_location('limited_social', ROOT / 'scripts/xhs-source-collect.py')
social = importlib.util.module_from_spec(spec)
spec.loader.exec_module(social)


class CollectionLimitsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / '.xhs').mkdir()
        self.state = {'stage': 'collect', 'status': 'active', 'receipts': {}, 'artifacts': {}}
        limits.set_limits(self.root, self.state, 'all', 3, 2, 2)
        limits.set_limits(self.root, self.state, 'x', 1, 1, 1)
        self.save()

    def save(self):
        (self.root / '.xhs/state.json').write_text(json.dumps(self.state))

    def args(self, command='x-search', output='sources.x.json', **kwargs):
        return argparse.Namespace(command=command, output=str(self.root / output),
                                  query='test', keyword='test', limit=kwargs.pop('limit', 1), **kwargs)

    def test_excess_search_rejected_before_platform_dispatch(self):
        with patch.object(social, 'collect_x') as call:
            with self.assertRaisesRegex(ValueError, 'x.candidates'):
                social.run(self.args(limit=3))
            call.assert_not_called()
        self.assertFalse((self.root / '.xhs/social-usage.json').exists())
        self.assertFalse((self.root / 'sources.x.json').exists())

    def test_limited_search_reaches_adapter_and_new_filename_cannot_reset_it(self):
        async def fake(args, result):
            self.assertEqual(args.limit, 1)
            result['samples'].append({'source_url': 'https://x.com/i/status/123'})
        with patch.object(social, 'collect_x', side_effect=fake) as call, redirect_stdout(io.StringIO()):
            self.assertEqual(social.run(self.args()), 0)
            self.assertEqual(call.call_count, 1)
            with self.assertRaisesRegex(ValueError, 'remaining 0'):
                social.run(self.args(output='sources.x-second.json'))
            self.assertEqual(call.call_count, 1)
        result = json.loads((self.root / 'sources.x.json').read_text())
        self.assertEqual(result['collection_request']['candidates'], 1)

    def test_global_budget_is_shared_across_platforms(self):
        limits.reserve(self.root / 'x.json', 'x', candidates=1)
        limits.reserve(self.root / 'youtube.json', 'youtube', candidates=2)
        with self.assertRaisesRegex(ValueError, 'all.candidates'):
            limits.reserve(self.root / 'again.json', 'youtube', candidates=1)

    def test_detail_and_comment_bounds_checked_before_youtube(self):
        with patch.object(social, 'collect_youtube') as call:
            with self.assertRaisesRegex(ValueError, 'comments'):
                social.run(self.args('youtube-read', comments=3))
            call.assert_not_called()
        limits.reserve(self.root / 'y1.json', 'youtube', details=1, comments=2)
        limits.reserve(self.root / 'y2.json', 'youtube', details=1, comments=2)
        with self.assertRaisesRegex(ValueError, 'all.details'):
            limits.reserve(self.root / 'y3.json', 'youtube', details=1)

    def test_failed_attempt_consumes_budget_and_policy_cannot_be_reset(self):
        with patch.object(social, 'collect_x', side_effect=RuntimeError('provider failed')), redirect_stdout(io.StringIO()):
            self.assertEqual(social.run(self.args()), 3)
        with self.assertRaisesRegex(ValueError, 'remaining 0'):
            limits.reserve(self.root / 'retry.json', 'x', candidates=1)
        with self.assertRaisesRegex(ValueError, 'cannot be reset'):
            limits.set_limits(self.root, self.state, 'x', 3, 2, 2)

    def test_nested_output_finds_project_and_repeated_output_is_rejected(self):
        path = self.root / 'nested/sources.json'
        limits.reserve(path, 'x', candidates=1)
        with self.assertRaisesRegex(ValueError, 'already has an attempted'):
            limits.reserve(path, 'x', candidates=1)

    def test_dispatch_freezes_policy_and_closed_collection_rejects_requests(self):
        self.state['receipts']['collect'] = {'id': 'receipt'}
        with self.assertRaisesRegex(ValueError, 'before dispatch'):
            limits.set_limits(self.root, self.state, 'all', 5, 2, 1)
        self.state['stage'] = 'draft'
        self.save()
        with self.assertRaisesRegex(ValueError, 'closed'):
            limits.reserve(self.root / 'late.json', 'x', candidates=1)

    def test_legacy_project_without_policy_keeps_standalone_behavior(self):
        self.state.pop('social_limits')
        self.save()
        self.assertIsNone(limits.reserve(self.root / 'legacy.json', 'x', candidates=3))

    def test_real_cli_rejects_limit_before_provider_imports(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/xhs-source-collect.py'),
            'x-search', '--query', 'synthetic-boundary-check', '--limit', '3',
            '--output', str(self.root / 'cli.json')], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn('x.candidates', json.loads(result.stdout)['reason'])
        self.assertFalse((self.root / 'cli.json').exists())


if __name__ == '__main__':
    unittest.main()
