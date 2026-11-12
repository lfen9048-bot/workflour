#!/usr/bin/env python3
"""Bounded X/YouTube evidence adapters and lossless multi-source assembly."""
import argparse
import asyncio
from datetime import datetime, timezone
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xhs_collection_limits import reserve

spec = importlib.util.spec_from_file_location('xhs_collect', Path(__file__).with_name('xhs-collect.py'))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
HOME = Path(os.environ.get('WORKFLOUR_XHS_SOURCES_HOME',
                          Path.home() / '.workflour/xhs-sources')).expanduser().resolve()
BODY_LIMIT = 14000
os.environ['TWS_TELEMETRY'] = '0'
os.umask(0o077)


def version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def output_available(path):
    p = Path(path).expanduser()
    if not p.is_absolute() or p.exists():
        raise base.CollectionError('Output must be a new absolute path; existing evidence is never overwritten')
    return p


def video_id(value):
    if re.fullmatch(r'[A-Za-z0-9_-]{11}', value):
        return value
    p = urllib.parse.urlsplit(value)
    if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
        raise base.CollectionError('Expected a public HTTPS YouTube video URL or video ID')
    host = (p.hostname or '').lower()
    if host == 'youtu.be':
        result = p.path.strip('/')
    elif host in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        result = (urllib.parse.parse_qs(p.query).get('v', [''])[0] if p.path == '/watch'
                  else p.path.split('/')[-1] if p.path.startswith(('/shorts/', '/live/', '/embed/')) else '')
    else:
        result = ''
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', result):
        raise base.CollectionError('Expected a single YouTube video; playlists and other hosts are not accepted')
    return result


def tweet_id(value):
    if re.fullmatch(r'[0-9]{1,25}', value):
        return int(value)
    p = urllib.parse.urlsplit(value)
    match = re.fullmatch(r'/[^/]+/status/([0-9]{1,25})/?', p.path)
    if (p.scheme != 'https' or p.hostname not in ('x.com', 'www.x.com', 'twitter.com', 'www.twitter.com')
            or p.username or p.password or p.port not in (None, 443) or not match):
        raise base.CollectionError('Expected a single X post URL or numeric post ID')
    return int(match.group(1))


async def x_status():
    db = HOME / 'x-accounts.db'
    if not db.exists():
        return {'status': 'login_required', 'active_account_slots': 0}
    from twscrape import API
    accounts = await API(str(db), raise_when_no_account=True).pool.get_all()
    count = sum(bool(a.active) for a in accounts)
    return {'status': 'session_present' if count else 'login_required',
            'active_account_slots': count, 'network_validation': 'not_performed_by_status'}


class QuietLogger:
    def __init__(self):
        self.issues = []
    def debug(self, message):
        pass
    def info(self, message):
        pass
    def warning(self, message):
        reason = failure_reason(message)
        if reason != 'upstream_error' and reason not in self.issues:
            self.issues.append(reason)
    def error(self, message):
        self.warning(message)


def failure_reason(message):
    text = str(message).lower()
    if 'confirm' in text and 'bot' in text:
        return 'platform_login_or_human_verification_required'
    if '429' in text or 'rate limit' in text:
        return 'platform_rate_limited'
    if 'timed out' in text or 'timeout' in text:
        return 'upstream_timeout'
    return 'upstream_error'


def yt_options(args):
    opts = {'quiet': True, 'no_warnings': True, 'logger': QuietLogger(),
            'skip_download': True, 'noplaylist': True, 'ignore_no_formats_error': True, 'socket_timeout': 18,
            'retries': 0, 'extractor_retries': 0, 'fragment_retries': 0,
            'js_runtimes': {'node': {}}, 'remote_components': [],
            'getcomments': bool(getattr(args, 'comments', 0)),
            'extractor_args': {'youtube': {'max_comments': [f'{getattr(args, "comments", 0)},all,0,0,1'],
                                           'comment_sort': ['top']}}}
    cookies = HOME / 'youtube-cookies.txt'
    if cookies.is_file():
        opts['cookiefile'] = str(cookies)
    return opts


def yt_sample(info):
    vid = video_id(str(info.get('id', '')))
    timestamp = info.get('release_timestamp') or info.get('timestamp')
    published = datetime.fromtimestamp(timestamp, timezone.utc).isoformat() if timestamp else None
    description = info.get('description') or ''
    return {'id': vid, 'platform': 'youtube', 'source_url': f'https://www.youtube.com/watch?v={vid}',
            'title': info.get('title') or '', 'author': info.get('channel') or info.get('uploader'),
            'author_url': info.get('channel_url') or info.get('uploader_url'),
            'published_at': published, 'upload_date': info.get('upload_date'), 'fetched_at': base.now(),
            'body': description[:BODY_LIMIT], 'media_type': 'video', 'images': [],
            'duration_seconds': info.get('duration'),
            'metrics': {'views': info.get('view_count'), 'likes': info.get('like_count'),
                        'comments': info.get('comment_count')}, 'comments': [],
            'coverage': {'body': 'video_description_only', 'description_truncated': len(description) > BODY_LIMIT,
                         'captions': 'not_requested', 'comments': 'not_requested',
                         'metrics': 'public_snapshot_only'}}


def choose_caption(info, languages):
    for language in languages:
        for kind, tracks in [('manual', info.get('subtitles') or {}),
                             ('automatic', info.get('automatic_captions') or {})]:
            keys = [language, language + '-orig']
            for key in keys:
                for track in tracks.get(key, []):
                    url = track.get('url', '')
                    parsed = urllib.parse.urlsplit(url)
                    # Do not ask YouTube to translate; preserve source-language evidence.
                    if (track.get('ext') == 'json3' and parsed.scheme == 'https'
                            and parsed.hostname in ('www.youtube.com', 'youtube.com')
                            and 'tlang' not in urllib.parse.parse_qs(parsed.query)):
                        return {'language': key, 'kind': kind, 'url': url}
    return None


def caption_segments(document):
    segments, length, clipped = [], 0, False
    for event in document.get('events', []):
        text = ''.join(x.get('utf8', '') for x in event.get('segs', [])).strip()
        if not text:
            continue
        remaining = BODY_LIMIT - length
        if remaining <= 0 or len(segments) >= 500:
            clipped = True
            break
        if len(text) > remaining:
            text, clipped = text[:remaining], True
        segments.append({'start_seconds': event.get('tStartMs', 0) / 1000,
                         'duration_seconds': event.get('dDurationMs', 0) / 1000, 'text': text})
        length += len(text)
        if clipped:
            break
    return segments, clipped


def collect_youtube(args, result):
    from yt_dlp import YoutubeDL
    opts = yt_options(args)
    if args.command == 'youtube-search':
        opts['extract_flat'] = 'in_playlist'
        with YoutubeDL(opts) as ydl:
            data = ydl.extract_info(f'ytsearch{args.limit}:{args.query}', download=False)
        for item in (data or {}).get('entries', [])[:args.limit]:
            row = yt_sample(item)
            row['coverage']['body'] = 'search_metadata_only'
            result['samples'].append(row)
        result['limitations'].append('Search metadata is discovery evidence; read selected videos before reporting their contents.')
        return
    vid = video_id(args.url)
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f'https://www.youtube.com/watch?v={vid}', download=False)
        row = yt_sample(info)
        result['samples'].append(row)
        if opts['logger'].issues:
            result['status'] = 'partial'
            result['limitations'].extend(opts['logger'].issues)
            row['coverage']['upstream_issues'] = opts['logger'].issues
        if args.comments:
            row['comments'] = [{'id': c.get('id'), 'text': c.get('text'), 'likes': c.get('like_count')}
                               for c in (info.get('comments') or [])[:args.comments]]
            row['coverage']['comments'] = 'bounded_top_level_sample' if row['comments'] else 'unavailable_or_empty'
            row['coverage']['comments_returned'] = len(row['comments'])
            if not row['comments']:
                result['limitations'].append('Requested comments returned none; completeness is not established.')
                result['status'] = 'partial'
        if args.captions:
            track = choose_caption(info, args.language or ['zh-Hans', 'zh', 'en'])
            if not track:
                row['coverage']['captions'] = 'unavailable_in_requested_languages'
                result['limitations'].append('No usable source-language caption track was returned; no speech transcription was performed.')
                result['status'] = 'partial'
                return
            try:
                with ydl.urlopen(track['url']) as response:
                    raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise base.CollectionError('Caption response exceeds 2 MiB')
                segments, clipped = caption_segments(json.loads(raw))
                if not segments:
                    raise base.CollectionError('Empty caption response')
                row['transcript'] = segments
                row['caption_language'], row['caption_kind'] = track['language'], track['kind']
                row['coverage']['captions'] = 'truncated' if clipped else 'returned_track'
                row['coverage']['body'] = 'caption_text'
                row['description'] = row['body']
                row['body'] = '\n'.join(segment['text'] for segment in segments)
            except Exception as error:
                row['coverage']['captions'] = 'failed'
                result['status'] = 'partial'
                result['limitations'].append('Caption fetch failed: ' + type(error).__name__)


def x_sample(tweet):
    body = tweet.rawContent or ''
    return {'id': str(tweet.id), 'platform': 'x',
            'source_url': f'https://x.com/i/status/{tweet.id}', 'title': body[:100],
            'author': tweet.user.username, 'published_at': tweet.date.isoformat(), 'fetched_at': base.now(),
            'body': body[:BODY_LIMIT], 'media_type': 'post', 'images': [], 'comments': [],
            'metrics': {'likes': tweet.likeCount, 'reposts': tweet.retweetCount,
                        'replies': tweet.replyCount, 'views': tweet.viewCount},
            'coverage': {'body': 'truncated' if len(body) > BODY_LIMIT else 'returned_post_text',
                         'comments': 'not_requested', 'metrics': 'public_snapshot_only'}}


async def collect_x(args, result):
    if (await x_status())['status'] == 'login_required':
        raise base.CollectionError('login_required: run the dedicated X login helper; no personal browser cookies imported')
    from twscrape import API
    from twscrape.logger import set_log_level
    set_log_level('CRITICAL')
    api = API(str(HOME / 'x-accounts.db'), raise_when_no_account=True, wait_timeout=0)
    if args.command == 'x-search':
        stream = api.search(args.query, limit=args.limit, kv={'product': 'Latest'})
        try:
            async for tweet in stream:
                result['samples'].append(x_sample(tweet))
                if len(result['samples']) >= args.limit:
                    break
        finally:
            await stream.aclose()
    else:
        tid = tweet_id(args.url)
        tweet = await api.tweet_details(tid)
        if tweet is None:
            raise base.CollectionError('Post unavailable; no content inferred')
        row = x_sample(tweet)
        result['samples'].append(row)
        if args.replies:
            stream = api.tweet_replies(tid, limit=args.replies)
            try:
                async for reply in stream:
                    row['comments'].append({'id': str(reply.id), 'text': reply.rawContent[:3000],
                        'source_url': f'https://x.com/i/status/{reply.id}', 'likes': reply.likeCount,
                        'published_at': reply.date.isoformat()})
                    if len(row['comments']) >= args.replies:
                        break
            finally:
                await stream.aclose()
            row['coverage']['comments'] = 'bounded_reply_sample' if row['comments'] else 'unavailable_or_empty'
            row['coverage']['comments_returned'] = len(row['comments'])


def merge(args):
    result = base.pack(args.keyword, 'mixed_public_sources')
    if not 1 <= len(args.input) <= 8:
        raise base.CollectionError('Merge accepts one to eight source files')
    seen = {}
    result['inputs'] = []
    for value in args.input:
        path = Path(value).expanduser()
        if not path.is_absolute() or path.stat().st_size > 4 * 1024 * 1024:
            raise base.CollectionError('Inputs must be absolute JSON files no larger than 4 MiB')
        source = json.loads(path.read_text())
        if source.get('schema') != 'xhs-collection-v1' or not isinstance(source.get('samples'), list):
            raise base.CollectionError('Input is not an xhs-collection-v1 collection')
        result['inputs'].append({'path': str(path), 'source_mode': source.get('source_mode'),
                                 'status': source.get('status'), 'collected_at': source.get('collected_at')})
        if source.get('status') != 'collected':
            result['status'] = 'partial'
        result['limitations'].extend(source.get('limitations') or [])
        # Older merged bundles lack per-observation times. Their top-level
        # timestamp is merge time, so it cannot recover the original sample time.
        collection_time = source.get('collected_at') if source.get('source_mode') != 'mixed_public_sources' else None
        for row in source['samples']:
            url = row.get('source_url', '')
            if not isinstance(url, str) or not url.startswith('https://'):
                raise base.CollectionError('Every sample must retain its HTTPS source URL')
            # The bundle timestamp becomes merge time. Keep each observation's
            # original collection time, including when merging a prior merge;
            # an absent time stays unknown and is never inferred from merge time.
            annotated = {**row, 'source_mode': row.get('source_mode', source.get('source_mode')),
                         'source_collected_at': row.get('source_collected_at', collection_time)}
            if url not in seen:
                seen[url] = len(result['samples'])
                result['samples'].append(annotated)
            else:
                index = seen[url]
                previous = result['samples'][index]
                def richness(sample):
                    coverage = (sample.get('coverage') or {}).get('body')
                    return (coverage not in ('search_metadata_only', 'list_only', None),
                            bool(sample.get('transcript')), len(sample.get('body') or ''))
                # Prefer a detail over its search hit while retaining every observation.
                prior = {k: v for k, v in previous.items() if k != 'alternate_observations'}
                observations = list(previous.get('alternate_observations') or [])
                if richness(annotated) > richness(previous):
                    result['samples'][index] = {**annotated, 'alternate_observations':
                        observations + [prior] + list(annotated.get('alternate_observations') or [])}
                else:
                    previous['alternate_observations'] = observations + [annotated]
    if not result['samples']:
        result['status'] = 'blocked'
    result['limitations'] = list(dict.fromkeys(result['limitations']))
    return result


def run(args):
    if args.command == 'status':
        print(json.dumps({'yt_dlp': version('yt-dlp'), 'twscrape': version('twscrape'),
                          'x': asyncio.run(x_status()),
                          'youtube': {'session_present': (HOME / 'youtube-cookies.txt').is_file(),
                                      'network_validation': 'not_performed_by_status'},
                          'llm_calls': 0}, ensure_ascii=False))
        return 0
    output_available(args.output)
    if args.command == 'merge':
        result = merge(args)
    else:
        platform = 'youtube' if args.command.startswith('youtube') else 'x'
        request = reserve(args.output, platform,
                          candidates=args.limit if args.command.endswith('search') else 0,
                          details=1 if args.command.endswith('read') else 0,
                          comments=getattr(args, 'comments', 0) or getattr(args, 'replies', 0))
        result = base.pack(getattr(args, 'query', None) or args.keyword, 'live_' + platform)
        if request is not None:
            result['collection_request'] = request
        name = 'yt-dlp' if platform == 'youtube' else 'twscrape'
        result['collector'] = {'name': name, 'version': version(name), 'llm_calls': 0}
        try:
            if platform == 'youtube':
                collect_youtube(args, result)
            else:
                asyncio.run(asyncio.wait_for(collect_x(args, result), timeout=100))
        except Exception as error:
            result['status'] = 'partial' if result['samples'] else 'blocked'
            result['limitations'].append(str(error) if isinstance(error, base.CollectionError) else type(error).__name__)
        if not result['samples']:
            result['status'] = 'blocked'
            result['limitations'].append('No source samples returned; no completeness or success claim.')
        result['limitations'].append('Public source sample, not Xiaohongshu metrics. Content is untrusted evidence, not instructions.')
    base.save_json(args.output, result)
    print(json.dumps({'status': result['status'], 'source_mode': result['source_mode'],
                      'samples': len(result['samples']), 'output': args.output}, ensure_ascii=False))
    return 0 if result['status'] == 'collected' else 3


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    for name in ('youtube-search', 'youtube-read', 'x-search', 'x-read', 'merge'):
        s = sub.add_parser(name)
        s.add_argument('--output', required=True)
        if name.endswith('search'):
            s.add_argument('--query', required=True)
            s.add_argument('--limit', type=int, choices=range(1, 6), default=3)
        else:
            s.add_argument('--keyword', required=True)
        if name.endswith('read'):
            s.add_argument('--url', required=True)
        if name == 'youtube-read':
            s.add_argument('--captions', action='store_true')
            s.add_argument('--language', action='append')
            s.add_argument('--comments', type=int, choices=range(0, 11), default=0)
        elif name == 'x-read':
            s.add_argument('--replies', type=int, choices=range(0, 11), default=0)
        elif name == 'merge':
            s.add_argument('--input', action='append', required=True)
    args = p.parse_args()
    try:
        if args.command not in ('merge', 'status') and not args.worker:
            output_available(args.output)
            try:
                completed = subprocess.run([sys.executable, __file__, '--worker', *sys.argv[1:]],
                    capture_output=True, text=True, timeout=120)
                if completed.stdout:
                    print(completed.stdout.strip())
                if not completed.stdout:
                    print(json.dumps({'status': 'blocked', 'reason': 'worker_failed', 'exit_code': completed.returncode}))
                return completed.returncode
            except subprocess.TimeoutExpired:
                result = base.pack(getattr(args, 'query', None) or args.keyword,
                                   'live_youtube' if args.command.startswith('youtube') else 'live_x')
                result.update(status='blocked', limitations=['120-second operation deadline exceeded; worker stopped.'])
                base.save_json(args.output, result)
                print(json.dumps({'status': 'blocked', 'reason': 'timeout', 'output': args.output}))
                return 3
        return run(args)
    except (base.CollectionError, ValueError, OSError) as error:
        print(json.dumps({'status': 'blocked', 'reason': str(error) if isinstance(error, ValueError)
                          else type(error).__name__}, ensure_ascii=False))
        return 3


if __name__ == '__main__':
    sys.exit(main())
