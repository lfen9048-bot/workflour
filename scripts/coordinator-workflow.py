#!/usr/bin/env python3
"""Durable dispatch receipts for a Bot-owned workflow; never sends model messages."""
import argparse
import fcntl
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import uuid
import hashlib
import sqlite3
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_assignments import (read_assignments, matching, TERMINAL, sender_idle, workflow_threads, thread_owner,
                                validate_supplement, effective_status, require_completed, receipt_rows)

PHASES = {'planning': ['kimi', 'deepseek', 'glm-plan'],
          'discussion': ['kimi', 'deepseek', 'glm-plan'], 'plan': ['kimi'],
          'implement': ['agy', 'deepseek'], 'review': ['glm-review'], 'verify': ['coordinator']}


PLAN_CODE_PHASES = {
    'research': ['plan-lead'], 'plan-review': ['plan-review'], 'plan': ['plan-lead'],
    'implement': ['code-main'], 'review': ['code-review'],
    'experience': ['plan-review'], 'acceptance': [],
}
ALL_PHASES = tuple(dict.fromkeys((*PHASES, *PLAN_CODE_PHASES)))


def is_plan_code(state):
    return state.get('workflow') == 'plan-code'


def local_step(state, phase, role):
    return is_plan_code(state) and phase in ('research', 'plan') and role == 'plan-lead'


def settled(item, allow_local=False):
    return (item.get('status') == 'completed' and bool(item.get('evidence'))
            and (bool(item.get('assignment_id')) or (allow_local and item.get('execution') == 'local')))


def phases_for(state):
    if is_plan_code(state):
        phases = {key: list(roles) for key, roles in PLAN_CODE_PHASES.items()}
        if state.get('helper_subtask'):
            phases['implement'].append('code-helper')
        return phases
    # Existing running projects retain their original phase order.
    version = state.get('discussion_version', 0)
    if type(version) is not int or version not in (0, 1):
        raise ValueError('Unsupported discussion version')
    return {k: v for k, v in PHASES.items() if k != 'discussion' or version == 1}


def validate_discussion(root, state, role, evidence):
    """Check real peer-response artifacts against the exact proposal versions.

    This verifies attribution, coverage and freshness, not truth of reasoning.
    Native receipts still identify the separate authors; no synthetic replies.
    """
    roles = PHASES['discussion']
    if role not in roles:
        raise ValueError('Unknown discussion author')
    path = (root / evidence).resolve(strict=True)
    path.relative_to(root)
    response = json.loads(path.read_text(encoding='utf-8'))
    peers = set(roles) - {role}
    if not isinstance(response, dict):
        raise ValueError('Discussion evidence must be a JSON object')
    if response.get('role') != role or response.get('round') != 2:
        raise ValueError('Discussion must identify its author and round 2')
    expected = {}
    proposal_paths = set()
    for peer in roles:
        item = state['assignments'].get('planning/' + peer, {})
        proposal = (root / item.get('evidence', '')).resolve(strict=True)
        proposal.relative_to(root)
        if not proposal.is_file():
            raise ValueError('Missing peer proposal')
        proposal_paths.add(proposal)
        expected[peer] = hashlib.sha256(proposal.read_bytes()).hexdigest()
    if len(proposal_paths) != 3:
        raise ValueError('Three independently authored proposal files are required')
    if response.get('proposal_sha256') != expected:
        raise ValueError('Discussion references stale or missing proposal hashes')
    replies = response.get('responses')
    if not isinstance(replies, list) or len(replies) != 2:
        raise ValueError('Each author must respond to both other planners')
    if any(not isinstance(r, dict) for r in replies):
        raise ValueError('Invalid peer responses')
    if {r.get('to') for r in replies} != peers:
        raise ValueError('Peer responses must cover both other planners, not self')
    for reply in replies:
        if reply.get('position') not in ('agree', 'change', 'disagree'):
            raise ValueError('Response position must be agree/change/disagree')
        for field in ('point', 'reason'):
            if not isinstance(reply.get(field), str) or not reply[field].strip():
                raise ValueError('Peer response requires a concrete point and reason')
    return response


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.coordination-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def key_for(state, phase, role):
    repair = state.get('repair_round', 0)
    if type(repair) is not int or not 0 <= repair <= 2:
        raise ValueError('repair_round must be an integer from 0 to 2')
    attempt = state.get('repair_round', 0) if phase in ('implement', 'review', 'verify', 'experience') else 0
    return f'{phase}/{role}' + (f'@{attempt}' if attempt else '')


def apply(state, action, phase=None, role=None, assignment_id=None, status=None, evidence=None, reason=None):
    if action == 'status':
        return state
    key_for(state, 'planning', 'kimi')  # Validate the round even for non-repair phases.
    if action == 'rework':
        rework_phases = ('review', 'experience') if is_plan_code(state) else ('review',)
        if state['phase'] not in rework_phases:
            raise ValueError('Rework requires the current review or experience phase')
        review_role = phases_for(state)[state['phase']][0]
        review = state['assignments'].get(key_for(state, state['phase'], review_role), {})
        if review.get('status') not in ('completed', 'failed') or not review.get('assignment_id'):
            raise ValueError('Rework requires a settled review and its dispatch receipt')
        if not evidence or not reason or not reason.strip():
            raise ValueError('Rework requires review evidence and a concrete reason')
        attempt = state.get('repair_round', 0)
        if attempt >= 2:
            raise ValueError('Two repair rounds exhausted; escalate to the user')
        state.setdefault('rework_history', []).append({'from_round': attempt, 'from_phase': state['phase'], 'reason': reason,
                                                      'evidence': evidence, 'at': now()})
        state['repair_round'] = attempt + 1
        state['phase'] = 'implement'
        state['updated_at'] = now()
        return state
    phases_map = phases_for(state)
    if phase not in phases_map:
        raise ValueError('Unknown phase')
    if action == 'advance':
        current = state['phase']
        phases = list(phases_map)
        if phases.index(phase) != phases.index(current) + 1:
            raise ValueError('Advance exactly one phase; preserve failed runs for explicit recovery')
        for owner in phases_map[current]:
            item = state['assignments'].get(key_for(state, current, owner), {})
            if not settled(item, allow_local=local_step(state, current, owner)):
                raise ValueError(f'{current}/{owner} is not completed')
        state['phase'] = phase
    else:
        if phase != state['phase'] or role not in phases_map[phase]:
            raise ValueError('Wrong active phase or role')
        key = key_for(state, phase, role)
        item = state['assignments'].get(key)
        if action == 'record':
            if not local_step(state, phase, role) or not evidence:
                raise ValueError('Only plan-lead research/plan steps use local evidence records')
            if item:
                raise ValueError('Local step already recorded; preserve its history')
            state['assignments'][key] = {'status': 'completed', 'execution': 'local',
                'evidence': evidence, 'thread_id': state.get('coordinator_thread'), 'settled_at': now()}
        elif action == 'claim':
            if local_step(state, phase, role):
                raise ValueError('Use record for the project lead own work; never invent a dispatch receipt')
            if item:
                raise ValueError('Already claimed: inspect receipt and native assignment before retry; no duplicate dispatch')
            state['assignments'][key] = {'status': 'claimed', 'claimed_at': now(), 'dispatch_token': str(uuid.uuid4()), 'attempt': 0}
        elif action == 'receipt':
            if not assignment_id or not assignment_id.strip():
                raise ValueError('A nonempty assignment receipt is required')
            if not item or item['status'] != 'claimed' or item.get('assignment_id'):
                raise ValueError('Receipt needs a previously claimed, unbound role')
            if any(row.get('assignment_id') == assignment_id for row in list(state['assignments'].values()) + [h['item'] for h in state.get('attempt_history', [])]):
                raise ValueError('Assignment receipt already bound')
            item.update(assignment_id=assignment_id, status='running')
        elif action == 'result':
            if status not in ('completed', 'failed', 'stopped'):
                raise ValueError('Unknown result status')
            if not item or item['status'] not in ('claimed', 'running'):
                raise ValueError('No active claim; settled results cannot be overwritten')
            if status == 'completed' and not evidence:
                raise ValueError('Completed results require a real evidence file')
            if status == 'completed' and (item['status'] != 'running' or not item.get('assignment_id')):
                raise ValueError('Completed results require a persisted dispatch receipt')
            item.update(status=status, evidence=evidence, settled_at=now())
            # Recovery advice describes a previous observation, not the settled
            # result. Do not leave "wait/settle" attached to completed work.
            if status == 'completed':
                item.pop('next_action', None)
    state['updated_at'] = now()
    return state


def validate_experience_evidence(root, evidence):
    import importlib.util
    spec = importlib.util.spec_from_file_location('plan_code_checks', Path(__file__).with_name('workflow-check.py'))
    checks = importlib.util.module_from_spec(spec); spec.loader.exec_module(checks)
    handoff = json.loads((root / '.workflour/handoff.json').read_text())
    record = json.loads((root / evidence).read_text())
    return checks.validate_experience(root, record, code_snapshot(root),
                                     [r['id'] for r in handoff.get('requirements', [])], handoff.get('product_surface', 'web'))


def code_snapshot(root):
    handoff = json.loads((root / '.workflour/handoff.json').read_text())
    result = {}
    for name in handoff.get('code_files', []):
        path = (root / name).resolve()
        path.relative_to(root)
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return result


def project_checks(root):
    import importlib.util
    spec = importlib.util.spec_from_file_location('coordinator_project_checks', Path(__file__).with_name('workflow-check.py'))
    checks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checks)
    return checks.Project(root)


def recover(state, action, phase, role, rows, *, reason=None, evidence=None,
            snapshot=None, resume_authorization=None):
    if state['phase'] != phase or role not in phases_for(state).get(phase, []):
        raise ValueError('Recovery requires the active phase and role')
    key = key_for(state, phase, role)
    item = state['assignments'].get(key)
    if not item:
        raise ValueError('No claim to reconcile')
    native = matching(state, item, rows)
    status = effective_status(native) if native else None
    if action == 'reconcile':
        if native:
            if item.get('assignment_id') and item['assignment_id'] != native['id']:
                raise ValueError('Receipt conflict')
            item.update(assignment_id=native['id'], bot_id=native['bot_id'], thread_id=native['thread_id'])
            item['native_observation'] = {**native, 'checked_at': now()}
            if status in ('failed', 'cancelled'):
                if item['status'] == 'completed':
                    raise ValueError('Completed ledger conflicts with native failure; inspect evidence')
                item.update(status='stopped' if status == 'cancelled' or native.get('outcome') in ('stopped', 'interrupted') else 'failed', settled_at=now())
                if item.get('supplements'):
                    item['next_action'] = 'A primary/supplement failed or stopped; preserve all receipts, inspect bounded recovery; never replay completed primary work'
            elif status == 'completed':
                # Native completion is not product success; evidence must still be reviewed.
                if item['status'] != 'completed':
                    item['status'] = 'running'
                item['next_action'] = 'Read worker result and files; settle with real evidence, do not redispatch'
            else:
                if item['status'] in ('failed', 'stopped', 'completed'):
                    raise ValueError('Settled ledger conflicts with live native assignment; wait, never retry')
                item['status'] = 'running'
                item['next_action'] = 'Wait for native assignment / approval; do not redispatch'
        else:
            if not item.get('dispatch_token') and not item.get('assignment_id'):
                raise ValueError('Legacy unbound claim has no dispatch token; identify and bind real receipt manually')
            if item.get('assignment_id'):
                raise ValueError('Bound native receipt missing; cannot infer failure or safe retry')
            item['native_observation'] = {'status': 'not_found', 'checked_at': now()}
            item['next_action'] = 'Uncertain dispatch: explicitly confirm the original sending turn is stopped before retry'
    elif action == 'retry':
        if item.get('supplements'):
            raise ValueError('Supplemented work cannot retry the primary; preserve receipts and inspect only the failed addition')
        if not reason or not reason.strip() or not evidence:
            raise ValueError('Retry requires reason and inspected side-effect evidence')
        if item.get('attempt', 0) >= 1:
            raise ValueError('One retry exhausted; escalate to user, preserve history')
        if native:
            if native['status'] not in ('failed', 'cancelled'):
                raise ValueError('Native work is live or completed; cannot retry')
            if item['status'] not in ('failed', 'stopped'):
                raise ValueError('Run reconcile before retry')
        elif item.get('assignment_id'):
            raise ValueError('Missing bound native assignment; cannot retry')
        else:
            # Absence is not proof a stale sending turn cannot dispatch later.
            if item.get('native_observation', {}).get('status') != 'not_found':
                raise ValueError('Reconcile uncertain claim first')
        if (not native or item['status'] == 'stopped' or native.get('outcome') in ('stopped', 'interrupted', 'denied')) and not resume_authorization:
            raise ValueError('Stopped/uncertain work requires explicit user resume authorization')
        previous = json.loads(json.dumps(item))
        state.setdefault('attempt_history', []).append({'key': key, 'item': previous,
            'reason': reason, 'evidence': evidence, 'snapshot': snapshot,
            'resume_authorization': resume_authorization, 'at': now()})
        state['assignments'][key] = {'status': 'claimed', 'claimed_at': now(),
            'dispatch_token': str(uuid.uuid4()), 'attempt': item.get('attempt', 0) + 1,
            'bot_id': item.get('bot_id'), 'retry_of': item.get('assignment_id'),
            'recovery_evidence': evidence, 'recovery_snapshot': snapshot}
    state['updated_at'] = now()
    return state


def register_supplement(state, phase, role, assignment_id, rows, *, reason, evidence, evidence_sha256):
    """Explicitly attach a verified native serial addition; never dispatch work."""
    if state['phase'] != phase or role not in phases_for(state).get(phase, []):
        raise ValueError('Supplement requires the active phase and role')
    item = state['assignments'].get(key_for(state, phase, role))
    if not item or item.get('status') != 'running' or not item.get('assignment_id'):
        raise ValueError('Supplement requires an active bound primary; cannot rewrite settled results')
    if not reason or not reason.strip() or not evidence or not evidence_sha256:
        raise ValueError('Supplement requires reason and evidence of its source and bounded scope')
    entries = list(state['assignments'].values()) + [h['item'] for h in state.get('attempt_history', [])]
    used = {entry.get('assignment_id') for entry in entries}
    used.update(s.get('assignment_id') for entry in entries for s in entry.get('supplements', []))
    if not assignment_id or assignment_id in used:
        raise ValueError('Receipt already bound; never duplicate or replace a primary')
    primary = [r for r in rows if r['id'] == item['assignment_id']]
    extra = [r for r in rows if r['id'] == assignment_id]
    if len(primary) != 1 or len(extra) != 1:
        raise ValueError('Need exactly one owned primary and one real supplement receipt')
    primary, extra = primary[0], extra[0]
    validate_supplement(primary, extra, item)
    if primary['requester_thread_id'] not in workflow_threads(state):
        raise ValueError('Supplement sender is not a bound workflow owner')
    fields = ('requester_bot_id', 'requester_thread_id', 'bot_id', 'thread_id', 'created_at', 'brief_sha256')
    item.setdefault('supplements', []).append({'assignment_id': assignment_id,
        **{field: extra[field] for field in fields}, 'reason': reason.strip(), 'evidence': evidence,
        'evidence_sha256': evidence_sha256, 'registered_at': now()})
    item['next_action'] = 'Wait for the primary and every supplement, inspect the latest result and snapshot; do not redispatch'
    state['updated_at'] = now()
    return state


def validate_completion(root, state, item, rows):
    root = Path(root).resolve(strict=True)
    native = require_completed(state, item, rows)
    for supplement in item.get('supplements', []):
        proof = (root / supplement['evidence']).resolve(strict=True)
        proof.relative_to(root)
        if not proof.is_file() or hashlib.sha256(proof.read_bytes()).hexdigest() != supplement['evidence_sha256']:
            raise ValueError('Supplement source/scope evidence changed after registration')
    if not sender_idle(native['thread_id']):
        raise ValueError('Worker has another active continuation; wait before result/advance')
    return native


def repair_token(state, phase, role, rows):
    """Recover a missing marker from an already-bound owned native receipt.

    Never redispatch or change the receipt, author, phase, status or attempt.
    """
    key = key_for(state, phase, role)
    item = state['assignments'].get(key)
    if not item or not item.get('assignment_id') or not item.get('bot_id'):
        raise ValueError('Token repair requires an existing receipt and target Bot')
    candidates = [r for r in rows if r['id'] == item['assignment_id'] and r['bot_id'] == item['bot_id']]
    if len(candidates) != 1 or len(candidates[0]['tokens']) != 1:
        raise ValueError('Need one owned native receipt carrying exactly one dispatch token')
    token = candidates[0]['tokens'][0]
    if item.get('dispatch_token') == token:
        return state
    if item.get('dispatch_token'):
        raise ValueError('Conflicting existing token; do not overwrite')
    state.setdefault('token_recovery_history', []).append({'key':key,'previous':item.get('dispatch_token'),
        'restored':token,'assignment_id':item['assignment_id'],'source':'owned native brief','at':now()})
    item['dispatch_token'] = token
    state['updated_at'] = now()
    return state


def workflow_rows(state):
    threads=workflow_threads(state)
    if not threads: raise ValueError('Bind the native coordinator conversation first')
    return [row for thread in threads for row in read_assignments(thread)]


def adopt_origin(state, new_thread, *, idle, rows, old_owner, new_owner, reason, evidence, authorization):
    old=state.get('coordinator_thread')
    if not old or not new_thread or old == new_thread:
        raise ValueError('Adoption requires a different confirmed coordinator conversation')
    if not idle or any(row['status'] not in TERMINAL for row in rows):
        raise ValueError('Stop the original coordinator and settle its native assignments before adoption')
    if not old_owner or old_owner != new_owner:
        raise ValueError('Origin adoption must stay on the same Bot')
    if not all((reason,evidence,authorization)):
        raise ValueError('Adoption needs inspection evidence and explicit resume authorization')
    state.setdefault('origin_history',[]).append({'thread':old,'reason':reason,'evidence':evidence,
        'resume_authorization':authorization,'at':now()})
    state['coordinator_thread']=new_thread
    state['updated_at']=now()
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--actor', help='Explicit shared-state writer mode; not authentication or a filesystem sandbox')
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('init'); p.add_argument('task_id'); p.add_argument('request')
    p.add_argument('--thread-id', help='Native coordinator workbench thread owning dispatches')
    p.add_argument('--workflow', choices=('code-team', 'plan-code'), help='Defaults to the initialized project workflow')
    p.add_argument('--new-task', action='store_true', help='Explicitly archive a completed verified run before a new task')
    sub.add_parser('status')
    p = sub.add_parser('prepare-dispatch', help='Prepare checked native arguments; never sends a Bot message')
    p.add_argument('phase', choices=ALL_PHASES); p.add_argument('role')
    p.add_argument('--message-file', type=Path, required=True)
    p.add_argument('--title'); p.add_argument('--done-when')
    p.add_argument('--supplement', action='store_true')
    p.add_argument('--reason'); p.add_argument('--evidence')
    p.add_argument('--require-image', action='store_true')
    p = sub.add_parser('repair-token'); p.add_argument('phase', choices=ALL_PHASES); p.add_argument('role')
    p = sub.add_parser('bind-origin'); p.add_argument('--thread-id', required=True)
    p = sub.add_parser('adopt-origin'); p.add_argument('--thread-id', required=True)
    p.add_argument('--reason', required=True); p.add_argument('--evidence', required=True)
    p.add_argument('--resume-authorization', required=True)
    for recovery in ('reconcile', 'retry', 'release-claim'):
        p = sub.add_parser(recovery); p.add_argument('phase', choices=ALL_PHASES); p.add_argument('role')
        if recovery in ('retry', 'release-claim'):
            p.add_argument('--reason', required=True); p.add_argument('--evidence', required=True)
            p.add_argument('--resume-authorization', help='Quote/source of explicit user resume; not identity authentication')
    p = sub.add_parser('record'); p.add_argument('phase', choices=('research', 'plan')); p.add_argument('--evidence', required=True)
    p = sub.add_parser('enable-helper'); p.add_argument('--reason', required=True); p.add_argument('--evidence', required=True)
    p = sub.add_parser('rework')
    p.add_argument('--reason', required=True)
    p.add_argument('--evidence', required=True)
    p = sub.add_parser('supplement'); p.add_argument('phase', choices=ALL_PHASES); p.add_argument('role')
    p.add_argument('assignment_id'); p.add_argument('--reason', required=True); p.add_argument('--evidence', required=True)
    for action in ('claim', 'receipt', 'result', 'advance'):
        p = sub.add_parser(action); p.add_argument('phase', choices=ALL_PHASES)
        if action != 'advance': p.add_argument('role')
        if action == 'claim': p.add_argument('--bot-id')
        if action == 'receipt': p.add_argument('assignment_id')
        if action == 'result':
            p.add_argument('status', choices=['completed', 'failed', 'stopped'])
            p.add_argument('--evidence')
    args = parser.parse_args()
    lock = None
    try:
        if args.action == 'prepare-dispatch':
            if args.actor != 'plan-lead':
                raise ValueError('Shared-state updates belong to plan-lead')
            # The helper owns coordination.lock. Do not acquire it twice.
            import dispatch_intents
            value = dispatch_intents.prepare(args.project, args.phase, args.role, args.message_file.read_text(),
                title=args.title, done_when=args.done_when, supplement=args.supplement,
                reason=args.reason, evidence=args.evidence, require_image=args.require_image)
            print(json.dumps({k: value[k] for k in ('id', 'state', 'native_arguments', 'required_capabilities')}, ensure_ascii=False))
            return 0
        root = args.project.resolve(strict=True)
        path = root / '.workflour' / 'coordination.json'
        if path.parent.is_symlink() or not path.parent.is_dir():
            raise ValueError('Choose an initialized project with a real .workflour directory')
        fd = os.open(path.parent / 'coordination.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        lock = os.fdopen(fd, 'r+')
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.is_symlink(): raise ValueError('Refuse symlink ledger')
        if args.action == 'init':
            metadata_path = root / '.workflour/project.json'
            metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
            workflow = args.workflow or metadata.get('workflow', 'code-team')
            if workflow not in ('code-team', 'plan-code'):
                raise ValueError('Choose --workflow code-team or plan-code for a dispatch ledger')
            expected_actor = 'plan-lead' if workflow == 'plan-code' else 'coordinator'
            if args.actor != expected_actor:
                raise ValueError('Shared-state updates belong to ' + expected_actor + '; return your result to it')
            if workflow == 'plan-code' and not args.thread_id:
                raise ValueError('plan-code requires the native plan-lead thread ID')
            if path.exists():
                if not args.new_task:
                    raise ValueError('Ledger exists; inspect/resume it instead of resetting')
                prior = json.loads(path.read_text())
                verified = prior.get('assignments', {}).get(key_for(prior, 'verify', 'coordinator'), {})
                if is_plan_code(prior):
                    verified = prior.get('assignments', {}).get(key_for(prior, 'experience', 'plan-review'), {})
                    handoff = json.loads((root / '.workflour/handoff.json').read_text())
                    if prior.get('phase') != 'acceptance' or not settled(verified) or handoff.get('acceptance', {}).get('status') != 'accepted':
                        raise ValueError('Keep the pending acceptance project; start a new project for another task')
                elif prior.get('phase') != 'verify' or not settled(verified):
                    raise ValueError('Only a completed verified run can be archived for a new task')
                proof = (root / verified['evidence']).resolve(strict=True)
                proof.relative_to(root)
                if not proof.is_file() or not proof.stat().st_size:
                    raise ValueError('Previous verification evidence is missing or empty')
                archive = path.parent / 'coordination-history' / (uuid.uuid4().hex + '.json')
                save(archive, prior)
            state = {'schema_version': 1, 'task_id': args.task_id, 'request': args.request,
                     'phase': 'planning', 'discussion_version': 1,
                     'assignments': {}, 'created_at': now(),
                     'coordinator_thread': args.thread_id}
            if workflow == 'plan-code':
                state.update(workflow='plan-code', workflow_version=3, freshness_version=1, phase='research',
                             shared_state_owner='plan-lead', acceptance='pending')
                state.pop('discussion_version', None)
        else:
            state = json.loads(path.read_text())
            expected_actor = 'plan-lead' if is_plan_code(state) else 'coordinator'
            if args.action != 'status' and args.actor != expected_actor:
                raise ValueError('Shared-state updates belong to ' + expected_actor + '; return your result to it')
            if args.action == 'advance':
                if is_plan_code(state):
                    project_checks(root).check_freshness(state,
                        require_contract=args.phase in ('implement', 'review', 'experience', 'acceptance'))
                    if args.phase == 'review':
                        project_checks(root).check_implementation_ready()
                if is_plan_code(state) and args.phase == 'acceptance':
                    project_checks(root).check('acceptance')
                for owner in phases_for(state).get(state.get('phase'), []):
                    completed = state.get('assignments', {}).get(key_for(state, state['phase'], owner), {})
                    proof_name = completed.get('evidence')
                    if not proof_name: raise ValueError('Completed dependency has no evidence')
                    proof = (root / proof_name).resolve(strict=True)
                    proof.relative_to(root)
                    if not proof.is_file() or not proof.stat().st_size:
                        raise ValueError('Completed dependency evidence missing or empty')
                    if is_plan_code(state):
                        if completed.get('evidence_sha256') != hashlib.sha256(proof.read_bytes()).hexdigest():
                            raise ValueError('Completed evidence changed after recording; inspect instead of advancing')
                        if completed.get('snapshot') != code_snapshot(root):
                            raise ValueError('Code changed after phase completion; repeat the relevant checks')
                    if (is_plan_code(state) and not local_step(state, state['phase'], owner)) or completed.get('supplements'):
                        validate_completion(root, state, completed, workflow_rows(state))
                    if is_plan_code(state) and state['phase'] == 'experience':
                        validate_experience_evidence(root, proof_name)
                    if state['phase'] == 'discussion':
                        validate_discussion(root, state, owner, proof_name)
            evidence = getattr(args, 'evidence', None)
            if evidence:
                file = (root / evidence).resolve(strict=True)
                file.relative_to(root)
                if not file.is_file() or not file.stat().st_size: raise ValueError('Empty evidence file')
            if args.action == 'result' and args.status == 'completed':
                item = state['assignments'].get(key_for(state, args.phase, args.role), {})
                if is_plan_code(state) or item.get('supplements'):
                    validate_completion(root, state, item, workflow_rows(state))
                if is_plan_code(state) and args.phase == 'implement':
                    project_checks(root).check_implementation_ready()
            if args.action == 'result' and is_plan_code(state) and args.phase == 'experience' and args.status == 'completed':
                if not evidence:
                    raise ValueError('Experience requires actual browser evidence JSON')
                validate_experience_evidence(root, evidence)
            if args.action == 'result' and args.phase == 'discussion' and args.status == 'completed':
                if not evidence:
                    raise ValueError('Discussion requires peer response JSON')
                validate_discussion(root, state, args.role, evidence)
            if args.action == 'record':
                contract = None
                if is_plan_code(state) and args.phase == 'plan':
                    project = project_checks(root)
                    freshness = project.check_freshness(state)
                    if freshness['mode'] == 'versioned':
                        contract = project.requirements_snapshot()
                state = apply(state, 'record', args.phase, 'plan-lead', evidence=evidence)
                state['assignments'][key_for(state, args.phase, 'plan-lead')].update(
                    snapshot=code_snapshot(root), evidence_sha256=hashlib.sha256((root / evidence).read_bytes()).hexdigest())
                if contract is not None:
                    state['requirements_snapshot'] = contract
            elif args.action == 'enable-helper':
                if not is_plan_code(state) or state['phase'] not in ('research', 'plan-review', 'plan') or state.get('helper_subtask'):
                    raise ValueError('Enable a helper once before implementation, for an explicit independent subtask')
                if not args.reason.strip():
                    raise ValueError('Describe the independent subtask and its file ownership')
                state['helper_subtask'] = {'reason': args.reason, 'evidence': evidence, 'at': now()}
            elif args.action == 'repair-token':
                state = repair_token(state, args.phase, args.role, workflow_rows(state))
            elif args.action == 'bind-origin':
                if state.get('coordinator_thread') and state['coordinator_thread'] != args.thread_id:
                    raise ValueError('Cannot replace the owning conversation')
                rows = read_assignments(args.thread_id)
                ids = {row['id'] for row in rows}
                for item in state['assignments'].values():
                    receipt = item.get('assignment_id')
                    if not receipt and not matching(state, item, rows):
                        raise ValueError('Cannot infer origin of an unbound claim; identify native dispatch first')
                    if receipt and not receipt.startswith('local-test:') and receipt not in ids:
                        raise ValueError('Existing receipt does not belong to this conversation')
                state['coordinator_thread'] = args.thread_id
            elif args.action == 'adopt-origin':
                old=state.get('coordinator_thread')
                if not old: raise ValueError('Bind the original conversation before adoption')
                state=adopt_origin(state,args.thread_id,idle=sender_idle(old),rows=workflow_rows(state),
                    old_owner=thread_owner(old),new_owner=thread_owner(args.thread_id),
                    reason=args.reason,evidence=evidence,authorization=args.resume_authorization)
            elif args.action == 'supplement':
                state = register_supplement(state, args.phase, args.role, args.assignment_id, workflow_rows(state),
                    reason=args.reason, evidence=evidence, evidence_sha256=hashlib.sha256((root / evidence).read_bytes()).hexdigest())
            elif args.action in ('reconcile', 'retry', 'release-claim'):
                rows = workflow_rows(state)
                # Recovery cannot race a still-running old sender. A new chief
                # turn may be active; native rows are terminal and token-scoped.
                if args.action in ('retry', 'release-claim'):
                    item = state['assignments'][key_for(state, args.phase, args.role)]
                    if args.action == 'release-claim':
                        if item.get('assignment_id') or matching(state, item, rows):
                            raise ValueError('A native assignment exists; reconcile it, do not release')
                        if not sender_idle(state['coordinator_thread']):
                            raise ValueError('Original coordinator conversation is still active; stop it first')
                    elif not item.get('assignment_id'):
                        raise ValueError('Unbound claim: bind a real receipt or use release-claim after stopping sender')
                    else:
                        native = matching(state, item, rows)
                        recipient = native.get('thread_id') if native else item.get('thread_id')
                        if recipient and not sender_idle(recipient):
                            raise ValueError('Worker conversation has active continuation or approval; wait, never retry')
                state = recover(state, 'retry' if args.action == 'release-claim' else args.action, args.phase, args.role, rows,
                    reason=getattr(args, 'reason', None), evidence=evidence,
                    snapshot=code_snapshot(root), resume_authorization=getattr(args, 'resume_authorization', None))
            else:
                if args.action == 'receipt' and state.get('coordinator_thread') and args.role != 'coordinator':
                    rows = workflow_rows(state)
                    item = state['assignments'][key_for(state, args.phase, args.role)]
                    if (state.get('discussion_version') == 1 or is_plan_code(state)) and not item.get('dispatch_token'):
                        raise ValueError('Missing dispatch token: never clear it to bypass receipt ownership')
                    row = next((r for r in rows if r['id'] == args.assignment_id), None)
                    if not row or (item.get('bot_id') and item['bot_id'] != row['bot_id']) or (item.get('dispatch_token') and item['dispatch_token'] not in row['tokens']):
                        raise ValueError('Native receipt not owned by this coordinator or target Bot')
                    item.update(bot_id=row['bot_id'], thread_id=row['thread_id'])
                state = apply(state, args.action, getattr(args, 'phase', None), getattr(args, 'role', None),
                              getattr(args, 'assignment_id', None), getattr(args, 'status', None), evidence,
                              getattr(args, 'reason', None))
                if is_plan_code(state) and args.action == 'result' and args.status == 'completed':
                    completed = state['assignments'][key_for(state, args.phase, args.role)]
                    completed.update(snapshot=code_snapshot(root), evidence_sha256=hashlib.sha256((root / evidence).read_bytes()).hexdigest())
                if args.action == 'claim' and args.bot_id:
                    state['assignments'][key_for(state, args.phase, args.role)]['bot_id'] = args.bot_id
        if args.action != 'status':
            save(path, state)
        if args.action == 'init' and (root / '.workflour/project.json').exists():
            # Registration is recoverable and separate from committed dispatch
            # state. Never tell callers to repeat init after a sync failure.
            import importlib.util
            observer_spec = importlib.util.spec_from_file_location('workflow_observer', Path(__file__).with_name('workflow-observer.py'))
            observer = importlib.util.module_from_spec(observer_spec); observer_spec.loader.exec_module(observer)
            try:
                observer.register(root)
            except (ValueError, OSError) as exc:
                save(root / '.workflour/observer-status.json', {'ok': False, 'errors': [type(exc).__name__], 'next_action': 'Run workflow-observer.py register again; ledger init already committed'})
                print('Ledger saved; Obsidian registration failed. Retry observer register, NOT init.', file=sys.stderr)
        print(json.dumps(state, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, sqlite3.Error) as exc:
        parser.exit(2, f'Coordinator ledger: {exc}\n')
    finally:
        if lock is not None:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()


if __name__ == '__main__': main()
