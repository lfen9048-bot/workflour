"""Prepared, single-send native dispatches; no model requests or native DB writes.

The CLI prepares exact coordinate_bots arguments. A DSH before-execute guard
checks them, then a journal changes prepared -> sending before the native call.
An interrupted/ambiguous send is never made prepared again automatically.
"""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import uuid

from native_assignments import DB, TERMINAL, dispatch_tokens, read_assignments, thread_owner

NATIVE_DB = Path(os.environ.get('WORKFLOUR_NATIVE_DB', str(DB)))

UUID = re.compile(r'^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$')
INTENT = re.compile(r'(?<![A-Za-z0-9_-])WF-INTENT:([a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})(?![a-f0-9-])')
PHASES = {'plan-review': ['plan-review'], 'implement': ['code-main', 'code-helper'],
          'review': ['code-review'], 'experience': ['plan-review']}
BASIS_KEYS = ('phase', 'role', 'assignment_key', 'primary_token', 'requester', 'target',
              'message', 'title', 'done_when', 'supplement', 'reason', 'evidence',
              'evidence_sha256', 'required_capabilities', 'primary_assignment_id')


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sealed_message(token, ident, request_hash, brief):
    return f'WF-DISPATCH:{token}\nWF-INTENT:{ident}\nWF-CONTRACT:{request_hash}\n{brief}'


def native_length(value):
    """The native JS schema counts UTF-16 code units, including emoji pairs."""
    return len(value.encode('utf-16-le', errors='surrogatepass')) // 2


def index_dir(value=None):
    return Path(value or os.environ.get('WORKFLOUR_DISPATCH_HOME', Path.home() / '.workflour/dispatch-intents')).expanduser()


def read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError('Missing, unsafe or oversized dispatch record')
    return json.loads(path.read_text(encoding='utf-8'))


def ensure_directory(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refuse dispatch directory symlink')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir():
        raise ValueError('Expected dispatch directory')
    return path


def atomic_write(path, value):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refuse dispatch record symlink')
    ensure_directory(path.parent)
    fd, tmp = tempfile.mkstemp(prefix='.dispatch-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
            output.write('\n'); output.flush(); os.fsync(output.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


@contextmanager
def lock(path):
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def project_files(project):
    root = Path(project).resolve(strict=True)
    wf = root / '.workflour'
    if wf.is_symlink() or not wf.is_dir():
        raise ValueError('Expected initialized project with a real .workflour directory')
    return root, wf


def assignment_key(state, phase, role):
    repair = state.get('repair_round', 0)
    if type(repair) is not int or not 0 <= repair <= 2:
        raise ValueError('Invalid repair round')
    return phase + '/' + role + (f'@{repair}' if repair and phase in ('implement', 'review', 'experience') else '')


def active_item(state, phase, role):
    if state.get('workflow') != 'plan-code' or state.get('phase') != phase or role not in PHASES.get(phase, []):
        raise ValueError('Dispatch requires the active Plan/Code phase and role')
    if role == 'code-helper' and not state.get('helper_subtask'):
        raise ValueError('Helper has not been enabled for this project')
    key = assignment_key(state, phase, role)
    item = state.get('assignments', {}).get(key)
    if not item or not UUID.fullmatch(str(item.get('dispatch_token', ''))):
        raise ValueError('Claim the role with a real target Bot before preparing dispatch')
    if not UUID.fullmatch(str(item.get('bot_id', ''))):
        raise ValueError('Claim must identify the exact target Bot')
    return key, item


def scoped_evidence(root, name):
    if not name or Path(name).is_absolute():
        raise ValueError('Supplement scope evidence must be project-relative')
    path = (root / name).resolve(strict=True)
    path.relative_to(root)
    if not path.is_file() or not path.read_text(encoding='utf-8').strip():
        raise ValueError('Supplement needs nonempty scope evidence')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_identity(binding):
    if not isinstance(binding, dict) or any(not UUID.fullmatch(str(binding.get(k, ''))) for k in ('bot_id', 'thread_id')):
        raise ValueError('A confirmed native Bot/thread binding is required')
    return {k: binding[k] for k in ('bot_id', 'thread_id')}


def prepare(project, phase, role, message, *, title=None, done_when=None, supplement=False,
            reason=None, evidence=None, require_image=False, db=NATIVE_DB, index_home=None):
    """Prepare exact native arguments from an existing claim; never dispatch.

    Repeating the exact preparation returns its existing prepared/sent intent.
    A different preparation cannot replace an unresolved or sent primary.
    """
    root, wf = project_files(project)
    if not isinstance(message, str) or not message.strip() or any(tag in message for tag in ('WF-DISPATCH', 'WF-INTENT', 'WF-CONTRACT')):
        raise ValueError('Supply a nonempty brief without handwritten dispatch/intent markers')
    if title is not None and (not isinstance(title, str) or native_length(title) > 80
            or any(ord(c) < 0x20 or 0x7f <= ord(c) <= 0x9f or ord(c) in (0x2028, 0x2029) for c in title)):
        raise ValueError('Title must fit on one line and use at most 80 native UTF-16 units')
    if done_when is not None and (not isinstance(done_when, str) or native_length(done_when) > 1000):
        raise ValueError('done_when must use at most 1000 native UTF-16 units')
    with lock(wf / 'coordination.lock'):
        state = read_json(wf / 'coordination.json')
        key, item = active_item(state, phase, role)
        owner_thread = state.get('coordinator_thread')
        owner = validate_identity({'thread_id': owner_thread, 'bot_id': thread_owner(owner_thread, db=db)})
        target_thread = 'new'
        primary = None
        scope_hash = None
        if supplement:
            if item.get('status') != 'running' or not item.get('assignment_id'):
                raise ValueError('Supplement requires an active bound primary; do not claim again')
            if not reason or not reason.strip():
                raise ValueError('Supplement requires a concrete reason')
            scope_hash = scoped_evidence(root, evidence)
            rows = read_assignments(owner_thread, db=db)
            primary = next((r for r in rows if r['id'] == item['assignment_id']), None)
            if (not primary or primary['bot_id'] != item['bot_id'] or primary['thread_id'] != item.get('thread_id')
                    or item['dispatch_token'] not in primary['tokens'] or primary.get('mode') != 'work'):
                raise ValueError('Primary native receipt differs from the claimed role')
            target_thread = primary['thread_id']
        elif item.get('status') != 'claimed' or item.get('assignment_id'):
            raise ValueError('Primary dispatch requires an unbound claim; inspect existing receipts')
        surface = read_json(wf / 'handoff.json').get('product_surface', 'web')
        capabilities = ['image'] if require_image or (phase == 'experience' and surface == 'web') else []
        basis = {'phase': phase, 'role': role, 'assignment_key': key, 'primary_token': item['dispatch_token'],
                 'requester': owner, 'target': {'bot_id': item['bot_id'], 'thread': target_thread},
                 'message': message.strip(), 'title': title, 'done_when': done_when, 'supplement': bool(supplement),
                 'reason': reason, 'evidence': evidence, 'evidence_sha256': scope_hash,
                 'required_capabilities': capabilities, 'primary_assignment_id': item.get('assignment_id')}
        request_hash = digest(basis)
        folder = ensure_directory(wf / 'dispatch-intents')
        previous = [read_json(p) for p in folder.glob('*.json')]
        for old in previous:
            if old.get('request_sha256') == request_hash:
                if old.get('state') in ('sending', 'uncertain'):
                    raise ValueError('Previous send is uncertain; reconcile native receipts, never resend')
                publish_index(old, index_home)
                return old
        for old in previous:
            if old.get('assignment_key') != key or old.get('primary_token') != item['dispatch_token']:
                continue
            if old.get('state') in ('prepared', 'sending', 'uncertain') or not supplement:
                raise ValueError('An intent already owns this dispatch; inspect it instead of preparing another')
            if old.get('supplement'):
                registered = [s.get('assignment_id') for s in item.get('supplements', [])]
                if old.get('assignment_id') not in registered:
                    raise ValueError('Register the previous supplement receipt before preparing more work')
        ident = str(uuid.uuid4())
        args = {'bot_ids': [item['bot_id']], 'message': sealed_message(item['dispatch_token'], ident, request_hash, message.strip()),
                'thread': target_thread, 'in_my_folder': True, 'reply': 'resume'}
        if native_length(args['message']) > 4000:
            raise ValueError('Brief plus dispatch markers exceeds native 4000-character limit')
        if title is not None: args['title'] = title
        if done_when is not None: args['done_when'] = done_when
        # Plan review and final experience use the same Bot in one parent task.
        # Native OMB refuses a later assignment to a completed same-Bot child
        # without rework even when thread:new; experience is new authorized work.
        if supplement or phase == 'experience' or state.get('repair_round', 0): args['rework'] = True
        value = {**basis, 'schema_version': 1, 'id': ident, 'project': str(root), 'state': 'prepared',
                 'native_arguments': args, 'payload_sha256': digest(args), 'request_sha256': request_hash,
                 'created_at': timestamp()}
        atomic_write(folder / (ident + '.json'), value)
        publish_index(value, index_home)
        return value


def publish_index(intent, index_home=None):
    folder = ensure_directory(index_dir(index_home))
    pointer = {'schema_version': 1, 'id': intent['id'], 'project': intent['project']}
    path = folder / (intent['id'] + '.json')
    if path.exists() and read_json(path) != pointer:
        raise ValueError('Dispatch index collision; refusing to replace an existing project')
    atomic_write(path, pointer)


def locate(ident, index_home=None):
    if not isinstance(ident, str) or not UUID.fullmatch(ident):
        raise ValueError('Invalid intent identity')
    folder = index_dir(index_home)
    if folder.is_symlink(): raise ValueError('Refuse dispatch index symlink')
    pointer = read_json(folder / (ident + '.json'))
    if pointer.get('schema_version') != 1 or pointer.get('id') != ident:
        raise ValueError('Invalid dispatch index')
    root, wf = project_files(pointer['project'])
    folder = wf / 'dispatch-intents'
    if folder.is_symlink() or not folder.is_dir(): raise ValueError('Unsafe dispatch intent directory')
    value = read_json(folder / (ident + '.json'))
    if value.get('schema_version') != 1 or value.get('id') != ident or value.get('project') != str(root):
        raise ValueError('Dispatch intent identity mismatch')
    if digest(value.get('native_arguments')) != value.get('payload_sha256'):
        raise ValueError('Prepared dispatch payload changed')
    if digest({key: value[key] for key in BASIS_KEYS}) != value.get('request_sha256'):
        raise ValueError('Dispatch contract changed; capability and scope declarations must remain intact')
    expected = sealed_message(value['primary_token'], ident, value['request_sha256'], value['message'])
    if value['native_arguments'].get('message') != expected:
        raise ValueError('Dispatch brief is not bound to the original capability contract')
    return root, wf, value


def intent_id(args):
    if not isinstance(args, dict) or not isinstance(args.get('message'), str):
        raise ValueError('Native dispatch must have prepared arguments')
    found = INTENT.findall(args['message'])
    if len(found) != 1:
        raise ValueError('Missing or ambiguous WF-INTENT; run prepare-dispatch, do not send directly')
    return found[0]


def validate(project, intent, args, binding, *, allowed=('prepared',)):
    if intent.get('state') not in allowed:
        raise ValueError('Dispatch already sent or outcome uncertain; inspect native receipts, never resend')
    if digest(args) != intent['payload_sha256'] or args != intent['native_arguments']:
        raise ValueError('Arguments differ from the prepared dispatch; no native call was made')
    if validate_identity(binding) != intent['requester']:
        raise ValueError('Prepared dispatch belongs to another native Bot/thread')
    if dispatch_tokens(args['message']) != [intent['primary_token']]:
        raise ValueError('Dispatch marker differs from its original claim')
    state = read_json(project / '.workflour/coordination.json')
    key, item = active_item(state, intent['phase'], intent['role'])
    if (key != intent['assignment_key'] or item['dispatch_token'] != intent['primary_token']
            or item['bot_id'] != intent['target']['bot_id'] or state.get('coordinator_thread') != binding['thread_id']):
        raise ValueError('Claim or coordinator changed since dispatch preparation')
    if intent['supplement']:
        if (item.get('status') != 'running' or item.get('assignment_id') != intent['primary_assignment_id']
                or item.get('thread_id') != intent['target']['thread']):
            raise ValueError('Supplement no longer belongs to the active primary')
        if scoped_evidence(project, intent['evidence']) != intent['evidence_sha256']:
            raise ValueError('Supplement scope changed after preparation')
    elif item.get('status') != 'claimed' or item.get('assignment_id'):
        raise ValueError('Primary already bound or settled; inspect instead of resending')


def preflight(args, binding, *, index_home=None):
    root, _, value = locate(intent_id(args), index_home)
    validate(root, value, args, binding)
    return {'ok': True, 'intent_id': value['id']}


def begin(args, binding, *, index_home=None):
    ident = intent_id(args)
    root, wf, _ = locate(ident, index_home)
    with lock(wf / 'coordination.lock'):
        _, _, value = locate(ident, index_home)
        validate(root, value, args, binding)
        value.update(state='sending', sending_at=timestamp())
        atomic_write(wf / 'dispatch-intents' / (ident + '.json'), value)
    return {'ok': True, 'intent_id': ident}


def native_rows(binding, db=NATIVE_DB, incoming=False):
    binding = validate_identity(binding)
    field = 'assignee_thread_id' if incoming else 'requester_thread_id'
    with closing(sqlite3.connect(Path(db).resolve(strict=True).as_uri() + '?mode=ro', uri=True, timeout=5)) as connection:
        connection.execute('PRAGMA query_only=ON')
        return [json.loads(row[0]) for row in connection.execute(f'SELECT json FROM assignments WHERE {field}=?', (binding['thread_id'],))]


def row_matches(value, row):
    recipient = row.get('assignee', {})
    target_thread = recipient.get('destination', {}).get('threadId')
    return (row.get('version') == 1 and row.get('mode') == 'work'
            and bool(UUID.fullmatch(str(row.get('id'))))
            and row.get('requester', {}).get('botId') == value['requester']['bot_id']
            and row.get('requester', {}).get('threadId') == value['requester']['thread_id']
            and recipient.get('botId') == value['target']['bot_id']
            and (value['target']['thread'] == 'new' or target_thread == value['target']['thread'])
            and bool(UUID.fullmatch(str(target_thread)))
            and row.get('brief') == value['native_arguments']['message']
            and INTENT.findall(row.get('brief', '')) == [value['id']]
            and dispatch_tokens(row.get('brief', '')) == [value['primary_token']])


def finish(ident, binding, *, db=NATIVE_DB, index_home=None):
    """Read real native rows after the call; a tool's claimed receipt is not proof."""
    _, wf, _ = locate(ident, index_home)
    with lock(wf / 'coordination.lock'):
        _, _, value = locate(ident, index_home)
        if validate_identity(binding) != value['requester']:
            raise ValueError('Only the bound native requester can reconcile this dispatch')
        if value['state'] not in ('sending', 'uncertain', 'sent'):
            raise ValueError('No native call was started for this intent')
        rows = native_rows(binding, db=db)
        candidates = [row for row in rows if ident in INTENT.findall(row.get('brief', ''))]
        if len(candidates) == 1 and row_matches(value, candidates[0]):
            row = candidates[0]
            if value.get('assignment_id') and value['assignment_id'] != row['id']:
                raise ValueError('Native receipt identity changed')
            value.update(state='sent', assignment_id=row['id'], thread_id=row['assignee']['destination']['threadId'],
                         native_status=row['status'], reconciled_at=timestamp())
            value.pop('uncertainty', None)
        else:
            value.update(state='uncertain', reconciled_at=timestamp(),
                         uncertainty='native_receipt_missing' if not candidates else 'native_receipt_conflict')
        atomic_write(wf / 'dispatch-intents' / (ident + '.json'), value)
    return {'ok': value['state'] == 'sent', 'intent_id': ident, 'state': value['state'],
            **{k: value[k] for k in ('assignment_id', 'thread_id', 'native_status', 'uncertainty') if k in value}}


def requirements_for_binding(binding, *, db=NATIVE_DB, index_home=None):
    """Resolve requirements from native work ownership, never prompt keywords.

    Native receipt may be committed before the sender's result hook runs, hence
    sending is valid here. A confirmed uncertain send stays blocked until an
    explicit reconciliation makes its outcome authoritative.
    """
    binding = validate_identity(binding)
    requirements, intents = set(), []
    for row in native_rows(binding, db=db, incoming=True):
        if row.get('status') in TERMINAL:
            continue
        if (row.get('assignee', {}).get('botId') != binding['bot_id']
                or row.get('assignee', {}).get('destination', {}).get('threadId') != binding['thread_id']):
            raise ValueError('Native receiver identity mismatch')
        ids = INTENT.findall(row.get('brief', ''))
        if not ids: continue  # Historical/direct work has no new capability contract.
        if len(ids) != 1: raise ValueError('Ambiguous native intent identity')
        _, _, value = locate(ids[0], index_home)
        if value['state'] not in ('sending', 'sent') or not row_matches(value, row):
            raise ValueError('Dispatch capabilities are unconfirmed; reconcile before continuing')
        if value.get('assignment_id') not in (None, row['id']) or value.get('thread_id') not in (None, binding['thread_id']):
            raise ValueError('Native task differs from its capability receipt')
        caps = value.get('required_capabilities')
        if not isinstance(caps, list) or any(cap != 'image' for cap in caps):
            raise ValueError('Unsupported task capability declaration')
        requirements.update(caps); intents.append(value['id'])
    return {'required_capabilities': sorted(requirements), 'intents': sorted(set(intents))}
