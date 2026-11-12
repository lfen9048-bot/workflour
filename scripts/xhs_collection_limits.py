"""Project-scoped X/YouTube request limits; reserve before any platform call."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile

FIELDS = ('candidates', 'details', 'comments')


def set_limits(project, state, source, candidates, details, comments):
    """Called by the planner under the workflow lock, before collection starts."""
    values = dict(zip(FIELDS, (candidates, details, comments)))
    if source not in ('all', 'x', 'youtube') or any(type(v) is not int or not 0 <= v <= 10 for v in values.values()):
        raise ValueError('Social limits must be integers from 0 to 10 for all/x/youtube')
    if state.get('receipts', {}).get('collect') or 'collect' in state.get('artifacts', {}) or (project / '.xhs/social-usage.json').exists():
        raise ValueError('Set social limits before dispatch or collection; existing requests cannot be reset')
    state.setdefault('social_limits', {})[source] = values


def locate(output):
    path = Path(output).expanduser().resolve()
    for parent in path.parents:
        if (parent / '.xhs/state.json').is_file():
            return parent
    return None


@contextmanager
def project_lock(project):
    with (project / '.xhs/lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def reserve(output, source, *, candidates=0, details=0, comments=0):
    """Count attempted requests, including failures, across new output filenames.

    This limits requested candidates, not undocumented upstream page prefetch.
    Legacy standalone tools without a project policy keep their existing limits.
    """
    project = locate(output)
    if project is None:
        return None
    with project_lock(project):
        state = json.loads((project / '.xhs/state.json').read_text())
        limits = state.get('social_limits', {})
        if not limits:
            return None
        if state.get('stage') != 'collect' or state.get('status') != 'active':
            raise ValueError('Collection is closed for this project')
        usage_path = project / '.xhs/social-usage.json'
        if usage_path.is_symlink():
            raise ValueError('Refuse symlink collection usage')
        usage = json.loads(usage_path.read_text()) if usage_path.exists() else {'requests': []}
        requested = {'source': source, 'candidates': candidates, 'details': details, 'comments': comments,
                     'output': str(Path(output).expanduser().resolve().relative_to(project))}
        if source not in ('x', 'youtube') or any(type(requested[k]) is not int or requested[k] < 0 for k in FIELDS):
            raise ValueError('Invalid social collection request')
        if any(row['output'] == requested['output'] for row in usage['requests']):
            raise ValueError('This collection output already has an attempted request; do not resend')
        for scope in ('all', source):
            cap = limits.get(scope)
            if cap is None:
                continue
            rows = [row for row in usage['requests'] if scope == 'all' or row['source'] == scope]
            for key in ('candidates', 'details'):
                used = sum(row[key] for row in rows)
                if used + requested[key] > cap[key]:
                    raise ValueError(f'Social collection limit exceeded: {scope}.{key} requested {requested[key]}, remaining {cap[key] - used}; no request sent')
            if comments > cap['comments']:
                raise ValueError(f'Social collection limit exceeded: {scope}.comments per detail is {cap["comments"]}; no request sent')
        usage['requests'].append(requested)
        fd, name = tempfile.mkstemp(prefix='.social-usage-', dir=usage_path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(usage, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, usage_path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return requested
