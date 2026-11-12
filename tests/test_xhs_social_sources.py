import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('social_sources', ROOT / 'scripts/xhs-source-collect.py')
social = importlib.util.module_from_spec(spec)
spec.loader.exec_module(social)


class SocialSourcesTests(unittest.TestCase):
    def test_only_platform_video_urls(self):
        vid = '0vZ_UVLhSQQ'
        for url in [vid, 'https://youtu.be/' + vid, 'https://www.youtube.com/watch?v=' + vid]:
            self.assertEqual(social.video_id(url), vid)
        for url in ['http://youtube.com/watch?v=' + vid, 'https://youtube.com.evil.test/watch?v=' + vid,
                    'https://user:pass@youtube.com/watch?v=' + vid, 'https://127.0.0.1/' + vid,
                    'https://www.youtube.com/playlist?list=ABC', 'https://youtube.com:8000/watch?v=' + vid]:
            with self.assertRaises(social.base.CollectionError):
                social.video_id(url)

    def test_only_platform_post_urls(self):
        self.assertEqual(social.tweet_id('https://x.com/i/status/123'), 123)
        self.assertEqual(social.tweet_id('123'), 123)
        for url in ['https://x.com.evil.test/i/status/123', 'https://user:pass@x.com/i/status/123', 'file:///123']:
            with self.assertRaises(social.base.CollectionError):
                social.tweet_id(url)

    def test_captions_prefer_manual_and_reject_translation(self):
        good = {'ext': 'json3', 'url': 'https://www.youtube.com/api/timedtext?lang=en'}
        translated = {'ext': 'json3', 'url': 'https://www.youtube.com/api/timedtext?lang=ja&tlang=en'}
        self.assertEqual(social.choose_caption({'subtitles': {'en': [good]},
                          'automatic_captions': {'en': [good]}}, ['en'])['kind'], 'manual')
        self.assertIsNone(social.choose_caption({'automatic_captions': {'en': [translated]}}, ['en']))
        self.assertIsNone(social.choose_caption({'subtitles': {'en': [dict(good, url='http://localhost/sub')]}}, ['en']))

    def test_timestamps_and_caption_bounds(self):
        rows, clipped = social.caption_segments({'events': [
            {'tStartMs': 1250, 'dDurationMs': 2500, 'segs': [{'utf8': 'Hello '}, {'utf8': 'world'}]},
            {'tStartMs': 4000, 'segs': [{'utf8': 'x' * 15000}]}]})
        self.assertEqual(rows[0], {'start_seconds': 1.25, 'duration_seconds': 2.5, 'text': 'Hello world'})
        self.assertTrue(clipped)
        self.assertEqual(sum(len(r['text']) for r in rows), social.BODY_LIMIT)

    def test_output_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'sources.json'; p.write_text('original')
            with self.assertRaises(social.base.CollectionError):
                social.output_available(str(p))
            with self.assertRaises(FileExistsError):
                social.base.save_json(p, {'wrong': True})
            self.assertEqual(p.read_text(), 'original')
        with self.assertRaises(social.base.CollectionError):
            social.output_available('relative.json')

    def test_merge_retains_partial_and_prefers_detail_without_losing_original(self):
        with tempfile.TemporaryDirectory() as d:
            files = []
            for index, (status, row) in enumerate([
                ('collected', {'source_url': 'https://www.youtube.com/watch?v=0vZ_UVLhSQQ', 'body': '',
                               'coverage': {'body': 'search_metadata_only'}}),
                ('partial', {'source_url': 'https://www.youtube.com/watch?v=0vZ_UVLhSQQ', 'body': 'real detail',
                             'coverage': {'body': 'video_description_only'}})]):
                p = Path(d) / f'{index}.json'
                data = social.base.pack('test', 'live_youtube')
                data.update(status=status, samples=[row], limitations=['missing captions'] if status == 'partial' else [])
                p.write_text(json.dumps(data)); files.append(str(p))
            result = social.merge(argparse.Namespace(keyword='test', input=files))
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(len(result['samples']), 1)
            self.assertEqual(result['samples'][0]['body'], 'real detail')
            self.assertEqual(result['samples'][0]['source_mode'], 'live_youtube')
            self.assertEqual(result['samples'][0]['alternate_observations'][0]['body'], '')
            self.assertIn('missing captions', result['limitations'])

    def test_empty_merge_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'blocked.json'
            data = social.base.pack('test', 'live_x'); data['status'] = 'blocked'
            p.write_text(json.dumps(data))
            self.assertEqual(social.merge(argparse.Namespace(keyword='test', input=[str(p)]))['status'], 'blocked')

    def test_merge_preserves_collection_times_for_duplicate_observations(self):
        with tempfile.TemporaryDirectory() as d:
            files = []
            times = ['2026-11-10T10:00:00+00:00', '2026-11-11T12:00:00+00:00']
            for index, time in enumerate(times):
                data = social.base.pack('test', 'live_xiaohongshu')
                data.update(collected_at=time, samples=[{
                    'source_url': 'https://www.xiaohongshu.com/explore/sample',
                    'body': '' if index == 0 else 'detail',
                    'metrics': {'likes': index + 1},
                    'coverage': {'body': 'list_only' if index == 0 else 'detail'},
                }])
                p = Path(d) / f'{index}.json'
                p.write_text(json.dumps(data)); files.append(str(p))
            for inputs in (files, files[::-1]):
                with self.subTest(inputs=inputs):
                    result = social.merge(argparse.Namespace(keyword='test', input=inputs))
                    self.assertEqual({i['path']: i['collected_at'] for i in result['inputs']}, dict(zip(files, times)))
                    sample = result['samples'][0]
                    self.assertEqual(sample['source_collected_at'], times[1])
                    self.assertEqual(sample['metrics']['likes'], 2)
                    older = sample['alternate_observations'][0]
                    self.assertEqual(older['source_collected_at'], times[0])
                    self.assertEqual(older['metrics']['likes'], 1)
                    self.assertNotIn('fetched_at', sample)
                    self.assertNotIn(result['collected_at'], times)
            merged = Path(d) / 'merged.json'
            merged.write_text(json.dumps(result))
            again = social.merge(argparse.Namespace(keyword='test', input=[str(merged)]))
            self.assertEqual(again['samples'], result['samples'])

    def test_merge_keeps_sample_fetch_time_and_does_not_invent_missing_collection_time(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'source.json'
            data = social.base.pack('test', 'live_x')
            data.pop('collected_at')
            data['samples'] = [{'source_url': 'https://x.com/i/status/123',
                                'fetched_at': '2026-11-10T12:00:00+00:00'}]
            p.write_text(json.dumps(data))
            result = social.merge(argparse.Namespace(keyword='test', input=[str(p)]))
            self.assertIsNone(result['inputs'][0]['collected_at'])
            self.assertIsNone(result['samples'][0]['source_collected_at'])
            self.assertEqual(result['samples'][0]['fetched_at'], data['samples'][0]['fetched_at'])

    def test_remerging_a_richer_bundle_keeps_all_observation_times(self):
        with tempfile.TemporaryDirectory() as d:
            files, times = [], ['2026-11-10', '2026-11-11', '2026-11-12']
            for index, time in enumerate(times):
                p = Path(d) / f'{index}.json'
                data = social.base.pack('test', 'live_xiaohongshu')
                data.update(collected_at=time, samples=[{
                    'source_url': 'https://www.xiaohongshu.com/explore/sample',
                    'body': 'detail' if index == 1 else '',
                    'coverage': {'body': 'detail' if index == 1 else 'list_only'},
                }])
                p.write_text(json.dumps(data)); files.append(str(p))
            merged = Path(d) / 'merged.json'
            merged.write_text(json.dumps(social.merge(argparse.Namespace(keyword='test', input=files[:2]))))
            def observation_times(sample):
                return [sample['source_collected_at']] + [time
                    for other in sample.get('alternate_observations', []) for time in observation_times(other)]
            for inputs in ([files[2], str(merged)], [str(merged), files[2]]):
                with self.subTest(inputs=inputs):
                    result = social.merge(argparse.Namespace(keyword='test', input=inputs))
                    self.assertCountEqual(observation_times(result['samples'][0]), times)

    def test_legacy_merged_bundle_does_not_supply_original_collection_time(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'legacy-merged.json'
            data = social.base.pack('test', 'mixed_public_sources')
            data.update(collected_at='2026-11-12T12:00:00+00:00', samples=[
                {'source_url': 'https://www.xiaohongshu.com/explore/old', 'metrics': {'likes': 10}},
                {'source_url': 'https://x.com/i/status/123', 'fetched_at': '2026-11-10T10:00:00+00:00'},
            ])
            p.write_text(json.dumps(data))
            result = social.merge(argparse.Namespace(keyword='test', input=[str(p)]))
            self.assertTrue(all(s['source_collected_at'] is None for s in result['samples']))
            self.assertEqual(result['samples'][1]['fetched_at'], data['samples'][1]['fetched_at'])
            self.assertEqual(result['inputs'][0]['collected_at'], data['collected_at'])

    def test_platform_errors_do_not_echo_credentials(self):
        logger = social.QuietLogger()
        logger.warning('Sign in to confirm you are not a bot. cookie=secret')
        self.assertEqual(logger.issues, ['platform_login_or_human_verification_required'])
        self.assertNotIn('secret', str(logger.issues))


if __name__ == '__main__':
    unittest.main()
