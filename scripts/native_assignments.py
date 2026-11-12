"""Read-only, version-checked OpenMausBot 0.1.143 assignment adapter.

No capability tokens, prompts, results or database writes leave this adapter.
The public HTTP assignment endpoint requires a live Bot capability; maintenance
uses a read-only SQLite snapshot instead of borrowing that capability.
"""
import json
from pathlib import Path
import sqlite3
import re
import hashlib
from contextlib import closing

DB = Path.home() / '.openmausbot/runtime.db'
TERMINAL = {'completed', 'failed', 'cancelled'}


def dispatch_tokens(brief):
    # Accept a missing separator colon, not a changed/missing UUID or other tag.
    uuid = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    return list(dict.fromkeys(re.findall(r'(?<![A-Za-z0-9_-])WF-DISPATCH(?:\s*:\s*|\s+)(' + uuid + r')(?![0-9a-f-])', brief)))


def read_assignments(thread_id, db=DB):
    if not thread_id:
        raise ValueError('No coordinator thread bound; use bind-origin before recovery')
    uri = Path(db).resolve(strict=True).as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as connection:
        connection.execute('PRAGMA query_only=ON')
        rows = connection.execute('SELECT json FROM assignments WHERE requester_thread_id=?', (thread_id,)).fetchall()
    result = []
    for (raw,) in rows:
        row = json.loads(raw)
        if row.get('version') != 1 or row.get('requester', {}).get('threadId') != thread_id:
            raise ValueError('Unsupported native assignment schema or owner mismatch')
        dest = row['assignee']['destination']
        result.append({
            'id': row['id'], 'status': row['status'], 'outcome': row.get('outcome'),
            'bot_id': row['assignee']['botId'], 'thread_id': dest['threadId'],
            'created_at': row['createdAt'], 'executions': row['executions'],
            'requester_bot_id': row['requester'].get('botId'), 'requester_thread_id': thread_id,
            'mode': row.get('mode'), 'parent_id': row.get('parentId'), 'root_id': row.get('rootId'),
            'brief_sha256': hashlib.sha256(row['brief'].encode()).hexdigest(),
            # Only UUID markers are retained from the brief.
            'tokens': dispatch_tokens(row['brief']),
        })
    return result


def matching(state, item, rows):
    token = item.get('dispatch_token')
    receipt = item.get('assignment_id')
    supplements = item.get('supplements', [])
    if not isinstance(supplements, list):
        raise ValueError('Invalid supplement registry')
    ids = [s.get('assignment_id') for s in supplements if isinstance(s, dict)]
    if len(ids) != len(supplements) or any(not sid or sid == receipt for sid in ids) or len(ids) != len(set(ids)):
        raise ValueError('Invalid or duplicate supplement receipt')
    candidates = [r for r in rows if r['id'] == receipt or r['id'] in ids or (token and token in r['tokens'])]
    if any(item.get('bot_id') and r['bot_id'] != item['bot_id'] for r in candidates):
        raise ValueError('Native recipient differs from claimed Bot')
    if not supplements and len(candidates) > 1:
        raise ValueError('Multiple native assignments match; reconcile manually, never retry')
    if not supplements:
        return candidates[0] if candidates else None
    by_id = {r['id']: r for r in candidates}
    if len(candidates) != len(by_id) or set(by_id) != {receipt, *ids}:
        raise ValueError('Unknown same-token assignment or registered supplement missing; explicitly inspect receipts')
    primary = by_id[receipt]
    for saved in supplements:
        row = by_id[saved['assignment_id']]
        validate_supplement(primary, row, item)
        fields = ('requester_bot_id', 'requester_thread_id', 'bot_id', 'thread_id', 'created_at', 'brief_sha256')
        if any(saved.get(field) != row.get(field) for field in fields) or not saved.get('reason') or not saved.get('evidence') or not saved.get('evidence_sha256'):
            raise ValueError('Supplement identity/evidence metadata changed; inspect instead of deduplicating')
    # status/id remain the primary's real native values. Derived bundle state is
    # separate so neither native receipt nor original result is fabricated.
    return {**primary, 'supplements': [by_id[sid] for sid in ids]}


def validate_supplement(primary, row, item):
    if primary['id'] == row['id']:
        raise ValueError('A primary receipt is not a supplement')
    for field in ('requester_bot_id', 'requester_thread_id', 'bot_id', 'thread_id'):
        if not primary.get(field) or row.get(field) != primary[field]:
            raise ValueError('Supplement must have the same sender and worker Bot/thread')
    if item.get('bot_id') != primary['bot_id'] or item.get('thread_id') != primary['thread_id']:
        raise ValueError('Primary identity differs from bound ledger receipt')
    if type(primary.get('created_at')) is not int or type(row.get('created_at')) is not int or row['created_at'] <= primary['created_at']:
        raise ValueError('Supplement must be created after the primary receipt')
    if primary.get('mode') != 'work' or row.get('mode') != 'work':
        raise ValueError('Only concrete work may supplement a work receipt')
    token = item.get('dispatch_token')
    if not token or token not in primary['tokens'] or token not in row['tokens']:
        raise ValueError('Supplement must retain the primary dispatch marker')
    if not primary.get('brief_sha256') or not row.get('brief_sha256') or row['brief_sha256'] == primary['brief_sha256']:
        raise ValueError('Identical/unknown work brief is not a bounded supplement')


def receipt_rows(native):
    return [native, *native.get('supplements', [])] if native else []


def effective_status(native):
    rows = receipt_rows(native)
    for state in ('failed', 'cancelled'):
        if any(r['status'] == state for r in rows):
            return state
    pending = [r['status'] for r in rows if r['status'] != 'completed']
    return pending[0] if pending else 'completed'


def require_completed(state, item, rows):
    native = matching(state, item, rows)
    if native and (native['id'] != item.get('assignment_id') or
                   (item.get('thread_id') and native['thread_id'] != item['thread_id'])):
        raise ValueError('Bound primary receipt/thread differs; a token match cannot replace its identity')
    if not native or any(r['status'] != 'completed' for r in receipt_rows(native)):
        detail = ', '.join(r['id'] + '=' + r['status'] for r in receipt_rows(native)) or 'receipt missing'
        raise ValueError('Primary and every supplement must be completed before result/advance: ' + detail)
    return native


def sender_idle(thread_id, db=DB):
    with closing(sqlite3.connect(Path(db).resolve(strict=True).as_uri() + '?mode=ro', uri=True, timeout=5)) as connection:
        connection.execute('PRAGMA query_only=ON')
        count = connection.execute("SELECT count(*) FROM assignments WHERE assignee_thread_id=? AND status NOT IN ('completed','failed','cancelled')", (thread_id,)).fetchone()[0]
    return count == 0


def workflow_threads(state):
    return list(dict.fromkeys(t for t in [state.get('coordinator_thread')] +
                             [h['thread'] for h in state.get('origin_history', [])] if t))


def thread_owner(thread_id, db=DB):
    with closing(sqlite3.connect(Path(db).resolve(strict=True).as_uri() + '?mode=ro', uri=True, timeout=5)) as connection:
        connection.execute('PRAGMA query_only=ON')
        owners = connection.execute('SELECT DISTINCT assignee_bot_id FROM assignments WHERE assignee_thread_id=?', (thread_id,)).fetchall()
    if len(owners) != 1:
        raise ValueError('Cannot confirm a unique native owner of this conversation')
    return owners[0][0]
