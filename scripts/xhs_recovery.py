"""Reconcile XHS evidence and guard any proposed original-planner resume.

Observation is local/read-only. The installed native runtime cannot guarantee a
scoped no-takeover send, so sending is disabled before any journal reservation.
"""
import copy
from datetime import datetime
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import uuid

from native_assignments import read_assignments, sender_idle, TERMINAL

ROOT = Path(__file__).resolve().parents[1]
JOURNAL = '.xhs/recovery/resume.json'
NATIVE_DATA = Path.home() / '.openmausbot'


def native_takeover_guard():
    """Fail closed: 0.1.143 exposes no per-request/task no-takeover contract.

    Neither an empty Bot fallback list nor automaticRecovery.enabled=false
    disables quota-switch's automatic choice of other subscription instances.
    A client environment variable cannot prove the running server's environment.
    Do not add a force flag or accept a text promise as a substitute.
    """
    return {'send_allowed': False, 'status': 'native_takeover_uncontrolled',
            'reviewed_native_version': '0.1.143', 'scoped_opt_out_available': False,
            'reason': 'Native automatic quota takeover cannot be disabled/verified for this task; '
                      'send is blocked before reserving a journal. Model selection alone does not prevent native switching and resending.'}


def selection_snapshot(value):
    if not isinstance(value, dict):
        return None
    allowed = ('instanceId', 'model', 'variant', 'effort')
    return {key: value[key] for key in allowed if isinstance(value.get(key), str)} or None


def stored_runtime(project, state):
    """Project-scoped fields only; no prompts, capability tokens or credentials.

    The native persisted registry is useful for drift diagnostics, not proof that
    a process is idle or that its currently running global switch is disabled.
    """
    saved = journal(project)
    baseline = selection_snapshot((saved or {}).get('model_selection'))
    result = {'status': 'unavailable', 'source': 'persisted_native_registry',
              'expected_selection': baseline, 'current_selection': None,
              'live_idle_verified': False, 'automatic_restore': False}
    try:
        team = json.loads(workflow().deployment_path().read_text())
        planner = next(r['botId'] for r in team['roles'] if r['key'] == 'xhs-planner')
        if saved and (saved.get('bot_id') != planner or saved.get('thread_id') != state['planner_thread']):
            raise ValueError('Journal owner differs from the project planner')
        bots = json.loads((NATIVE_DATA / 'bots.json').read_text())
        matches = [b for b in bots if b.get('id') == planner]
        if len(matches) != 1:
            raise ValueError('Original planner is missing or ambiguous in the native registry')
        bot = matches[0]
        tasks = [t for t in bot.get('tasks', []) if t.get('threadId') == state['planner_thread']]
        if len(tasks) != 1:
            raise ValueError('Original task is missing or ambiguous in the native registry')
        current = selection_snapshot(tasks[0].get('modelSelection') or bot.get('modelSelection'))
        if not current:
            raise ValueError('Native task selection is unavailable')
        result.update(current_selection=current, bot_default_selection=selection_snapshot(bot.get('modelSelection')),
                      bot_fallback_count=len(bot.get('fallback') or []),
                      status='runtime_drift' if baseline and baseline != current else
                      'matches_send_snapshot' if baseline else 'no_send_baseline')
        # Only this non-secret policy field is retained from configuration.
        config = json.loads((NATIVE_DATA / 'config.json').read_text())
        policy = config.get('automaticRecovery') or {}
        if not isinstance(policy, dict):
            raise ValueError('Invalid automatic recovery configuration')
        result['global_automatic_recovery_enabled'] = policy.get('enabled') is True
        result['global_quota_switch'] = 'not_exposed_by_native_read_contract; enabled_by_default'
    except (ValueError, OSError, KeyError, TypeError, AttributeError, StopIteration) as error:
        result['read_error'] = type(error).__name__
    if result['status'] == 'runtime_drift':
        result['next_action'] = ('The task selection differs from its send snapshot. Do not resend or restore automatically; '
                                 'verify the exact task is idle and preserve any later manual model choice before an explicit task-only restore.')
    return result


@lru_cache(maxsize=None)
def module(filename):
    spec = importlib.util.spec_from_file_location('_recovery_' + filename.replace('-', '_'), ROOT / 'scripts' / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def workflow():
    return module('xhs-workflow.py')


def local_json(project, name):
    """Never follow evidence paths outside this project."""
    path = project / name
    path.resolve(strict=True).relative_to(project.resolve(strict=True))
    return json.loads(path.read_text())


def image_attempts(project):
    directory = project / 'generated-images'
    if not directory.exists():
        return []
    directory.resolve(strict=True).relative_to(project)
    evidence_dirs = {p.parent for p in directory.rglob('image-evidence.json')}
    # A grouping directory is not another attempt. Also ignore assets nested
    # below an attempt that already owns its terminal evidence.
    directories = {p for p in directory.rglob('*') if p.is_dir()
                   and not any(parent in evidence_dirs for parent in p.parents)}
    directories.update(evidence_dirs)
    attempts = {p for p in directories if p in evidence_dirs
                or not any(p in child.parents for child in directories)}
    result = []
    for attempt in sorted(attempts):
        attempt.resolve(strict=True).relative_to(project)
        path = attempt / 'image-evidence.json'
        if not path.is_file():
            result.append({'path': str(attempt.relative_to(project)), 'status': 'pending_or_unknown'})
            continue
        evidence = local_json(project, str(path.relative_to(project)))
        if not isinstance(evidence, dict):
            raise ValueError('Image evidence must be an object')
        result.append({**workflow().artifact(project, str(path.relative_to(project))),
                       'status': evidence.get('status'), 'reason': evidence.get('reason'),
                       'finished_at': evidence.get('finished_at'),
                       'pending': not bool(evidence.get('finished_at')) or evidence.get('status') not in
                       ('blocked', 'failed', 'generated_pending_visual_review')})
    return result


def delivery_observation(project):
    if not (project / 'delivery/receipt.json').exists():
        return None
    value = local_json(project, 'delivery/receipt.json')
    if not isinstance(value, dict):
        raise ValueError('Delivery receipt must be an object')
    return {**workflow().artifact(project, 'delivery/receipt.json'), 'status': value.get('status')}


def root_row(row):
    return {key: row.get(key) for key in ('id', 'status', 'outcome', 'created_at', 'brief_sha256')}


def verify_recovery_evidence(project, state, previous_send):
    if not previous_send:
        return
    archive = None
    archive_files = set()
    token = previous_send.get('draft_token')
    if token and token != state['dispatch_tokens']['draft']:
        revision = next((r for r in state.get('revisions', []) if r.get('draft_token') == token), None)
        if revision is None:
            raise ValueError('Recovery draft token changed without an immutable revision archive')
        archive = Path(revision['manifest']['path']).parent
        manifest = local_json(project, revision['manifest']['path'])
        archive_files = {row['path'] for row in manifest['files']}
    for saved in previous_send.get('protected_evidence', []):
        name = str(archive / saved['path']) if archive is not None and saved['path'] in archive_files else saved['path']
        if workflow().artifact(project, name)['sha256'] != saved['sha256']:
            raise ValueError('Recovery protected evidence changed: ' + saved['path'])


def inspect(project, state, rows=None):
    """Return a validated candidate; never modify the caller or write files."""
    project = Path(project).resolve(strict=True)
    wf = workflow()
    candidate = copy.deepcopy(state)
    if candidate.get('workflow') != 'xhs-three' or not candidate.get('planner_thread'):
        raise ValueError('Recovery requires an existing XHS project bound to a real planner thread')
    wf.verify_artifacts(project, candidate)
    verify_recovery_evidence(project, candidate, journal(project))
    thread = candidate['planner_thread']
    rows = read_assignments(thread) if rows is None else rows
    team = json.loads(wf.deployment_path().read_text())
    planner = next(r['botId'] for r in team['roles'] if r['key'] == 'xhs-planner')
    created = datetime.fromisoformat(candidate['created_at']).timestamp() * 1000
    for stage in ('collect', 'draft'):
        previous = candidate['receipts'].get(stage)
        token = candidate['dispatch_tokens'][stage]
        matches = [r for r in rows if token in r.get('tokens', [])]
        if previous:
            wf.bind_receipt(candidate, stage, previous['id'], rows)
        elif matches:
            if len(matches) != 1:
                raise ValueError('Multiple native assignments match the ' + stage + ' stage; do not redispatch')
            wf.bind_receipt(candidate, stage, matches[0]['id'], rows)
    known_ids = {r['id'] for r in candidate['receipts'].values()}
    if candidate.get('draft_amendment'):
        known_ids.add(candidate['draft_amendment']['id'])
    source_roots = {r.get('root_id') for r in rows if r['id'] in known_ids}
    roots = [r for r in rows if r.get('parent_id') is None and r.get('root_id') == r['id']
             and r.get('bot_id') == r.get('requester_bot_id') == planner
             and r.get('thread_id') == r.get('requester_thread_id') == thread
             and r.get('mode') == 'work' and (r.get('created_at', 0) >= created or r['id'] in source_roots)]
    saved_root = candidate.get('recovery', {}).get('source_root_id')
    roots_for_origin = [r for r in roots if r['id'] == saved_root] if saved_root else roots
    root = roots_for_origin[0] if len(roots_for_origin) == 1 else None
    attempts = image_attempts(project)
    delivery = delivery_observation(project)
    live = [root_row(r) for r in rows if r.get('status') not in TERMINAL and
            (r in roots or r['id'] in known_ids or any(t in r.get('tokens', []) for t in candidate['dispatch_tokens'].values()))]
    missing = [name for name in ('draft.md', 'cards.json', 'writing-report.json', 'output/preview.html')
               if not (project / name).is_file()]
    deliverable = {'status': 'incomplete', 'missing': missing}
    if not missing and candidate['receipts'].get('draft', {}).get('status') == 'completed':
        probe = copy.deepcopy(candidate)
        try:
            wf.record(project, probe, 'draft', 'draft.md', rows=rows)
            wf.finish(project, probe)
            deliverable['status'] = 'validated_for_review'
        except (ValueError, OSError, KeyError, StopIteration) as error:
            deliverable['validation_error'] = str(error)
    planner_status = ('provider_failure' if root and root['status'] == 'failed' and root.get('outcome') == 'provider_error'
                      else root['status'] if root else 'missing_or_ambiguous')
    pending_tool = (any(a.get('pending') or a['status'] == 'pending_or_unknown' for a in attempts)
                    or bool(delivery and delivery['status'] == 'preparing'))
    if state.get('status') == 'pending_user_review':
        status = 'pending_user_review'
    elif root is None:
        status = 'native_root_unconfirmed'
    elif live:
        status = 'waiting_native'
    elif pending_tool:
        status = 'pending_tool'
    elif delivery and delivery['status'] == 'awaiting_visual_review':
        status = 'awaiting_visual_review'
    elif deliverable['status'] == 'validated_for_review':
        status = 'ready_for_review'
    elif candidate['receipts'].get('draft'):
        status = 'incomplete_deliverable'
    else:
        status = planner_status
    observation = {'checked_at': wf.now(), 'status': status,
                   'planner_status': planner_status, 'source_root': root_row(root) if root else None,
                   'roots': [root_row(r) for r in roots], 'live_native': live,
                   'image_attempts': attempts, 'delivery': delivery, 'deliverable': deliverable}
    recovery = candidate.setdefault('recovery', {})
    recovery['observation'] = observation
    if root:
        recovery['source_root_id'] = root['id']
    candidate['next_action'] = next_action(observation)
    return candidate


def next_action(observation):
    status = observation['status']
    if status in ('waiting_native', 'pending_tool'):
        return '原派单或工具仍在运行/结果不明；等待并核对，不续接、不重派、不重做采集或生图。'
    if status == 'pending_user_review':
        return '保持原交付，等待用户确认；不重复续接。'
    if status == 'awaiting_visual_review':
        return '已生成交付文件，实际读图后 confirm；保留原稿、原回执和生图证据。'
    if status == 'ready_for_review':
        return '核对现有交付后 record/finish；原生 completed 不能代替负责人验稿。'
    return '核对原失败及缺失文件；本机无法验证按任务禁用原生自动接管，禁止发送续接，仅用现有材料本地机械收尾。'


def reconcile(project, state, rows=None):
    candidate = inspect(project, state, rows)
    state.clear()
    state.update(candidate)
    return state['recovery']['observation']


def journal(project):
    path = project / JOURNAL
    return local_json(project, JOURNAL) if path.exists() else None


def eligibility(project, candidate):
    observation = candidate['recovery']['observation']
    reasons = []
    if journal(project) is not None:
        reasons.append('A recovery send is already reserved; never resend, including delivery_unknown')
    if observation['planner_status'] != 'provider_failure':
        reasons.append('The original planner root must have a confirmed provider_error failure')
    if observation['status'] in ('waiting_native', 'pending_tool', 'native_root_unconfirmed', 'pending_user_review'):
        reasons.append('Native/tool work is pending, uncertain, or already delivered')
    if any(key not in candidate['artifacts'] for key in ('collect', 'brief')):
        reasons.append('Collection and brief must already be recorded; this recovery never dispatches work')
    if candidate['receipts'].get('draft', {}).get('status') != 'completed':
        reasons.append('The original writer must be completed; this recovery never retries a worker')
    if candidate.get('draft_amendment', {}).get('status', 'completed') != 'completed':
        reasons.append('A registered writer amendment has not completed')
    if not (project / 'draft.md').is_file() or not (project / 'draft.md').stat().st_size:
        reasons.append('An existing nonempty draft is required for mechanical delivery recovery')
    else:
        workflow().artifact(project, 'draft.md')
    if len(observation['roots']) != 1:
        reasons.append('Additional native root turns require inspection; this tool does not infer a safe resend')
    return {'allowed': not reasons, 'reasons': reasons}


def prompt(project, candidate, reason, recovery_id):
    observation = candidate['recovery']['observation']
    evidence = [a['path'] for a in observation['image_attempts'] if 'sha256' in a]
    lines = [f'小红书原任务的一次明确恢复：{reason}', f'恢复标记 XHS-RESUME:{recovery_id}',
             f'项目：{project}', f'原工作台 threadId：{candidate["planner_thread"]}；不重新 init、不建新任务。',
             '先读 .xhs/state.json、HANDOFF.md 和 .xhs/recovery/resume.json，保留原失败回执及全部证据。',
             '原采集和写作已经派过；禁止 coordinate_bots、另派或重试 worker，禁止重新采集、生图、换模型、启用新付费通道。',
             '本轮仅用已存在 draft.md 补机械交付；不重写旧稿、来源、简报、限额、用量或 image-evidence。',
             '若 cards.json 缺失，可按现有原稿制作文本卡片输入；不增加事实、不做文风返工。',
             f'同步交付入口：python3 {shlex.quote(str(ROOT / "scripts/xhs-deliver.py"))} prepare --project {shlex.quote(str(project))}',
             'prepare 不得传 image_prompt；有旧 image-evidence 时显式 --existing-image-evidence 项目相对路径，失败沿用模板并如实记 partial。',
             '现有生图证据：' + (json.dumps(evidence, ensure_ascii=False) if evidence else '无；仅模板，绝不发起生成。'),
             '若 delivery/receipt.json 为 preparing，等待原工具完成；若 awaiting_visual_review，直接实际读图，不重新 prepare。',
             f'实际读每张图后，用 python3 {ROOT}/scripts/xhs-deliver.py confirm --project ABS --reviewed-image 每张实际路径（可重复参数）。',
             '核对交付工具自动在报告标注 maintenance recovery、原 writer 回执及失败证据；confirm 后禁止手改 report，缺标记就报告阻断。',
             '不将机械收尾说成原 worker 已完成完整交稿。',
             '随后按原回执 record draft、finish；只到 pending_user_review，不能发布或代用户验收。',
             '任一结果缺失或额度再次失败就保留现场并报告阻断，不自动重试或改派。']
    return '\n'.join(lines)


def preview(project, state=None, rows=None, reason='继续已授权的原稿机械交付'):
    project = Path(project).resolve(strict=True)
    state = local_json(project, '.xhs/state.json') if state is None else state
    candidate = inspect(project, state, rows)
    admission = eligibility(project, candidate)
    admission['workflow_eligible'] = admission['allowed']
    guard = native_takeover_guard()
    if not guard['send_allowed']:
        admission['allowed'] = False
        admission['reasons'].append(guard['reason'])
    runtime = stored_runtime(project, candidate)
    return {'status': runtime['status'] if runtime['status'] == 'runtime_drift' else guard['status'],
            'observation': candidate['recovery']['observation'], 'resume': admission,
            'runtime': runtime, 'native_takeover_guard': guard,
            'journal': journal(project), 'prompt': prompt(project, candidate, reason, 'PREVIEW'),
            'model_policy': 'selection snapshot is not a native no-takeover guarantee; automatic sending is unavailable',
            'sent': False}


def protected_snapshot(project, state):
    names = {saved['path'] for saved in state['artifacts'].values()}
    names.update(a['path'] for a in state['recovery']['observation']['image_attempts'] if 'sha256' in a)
    names.add('draft.md')
    if (project / '.xhs/social-usage.json').exists():
        names.add('.xhs/social-usage.json')
    return [workflow().artifact(project, name) for name in sorted(names)]


def send(client, team, project, reason, *, rows=None, idle=None):
    """Explicit maintenance send. A reserved/uncertain attempt is never resent."""
    project = workflow().project_path(project)
    if not reason.strip() or len(reason) > 1000:
        raise ValueError('Recovery requires a specific 1–1000 character reason')
    guard = native_takeover_guard()
    if not guard['send_allowed']:
        raise ValueError(guard['reason'])
    idle = sender_idle if idle is None else idle
    wf = workflow()
    with wf.locked(project) as state_path:
        state = local_json(project, '.xhs/state.json')
        candidate = inspect(project, state, rows)
        admission = eligibility(project, candidate)
        if not admission['allowed']:
            raise ValueError('; '.join(admission['reasons']))
        role = next(r for r in team['roles'] if r['key'] == 'xhs-planner')
        fleet = client.call('GET', '/api/bots?messages=0')['bots']
        bot = next(b for b in fleet if b['id'] == role['botId'])
        if not module('provision-xhs-team.py').owned(bot, role):
            raise ValueError('Planner ownership does not match the local deployment')
        thread = candidate['planner_thread']
        task = next((t for t in bot.get('tasks', []) if t['threadId'] == thread), None)
        if task is None or bot.get('busy') or any(t.get('busy') for t in bot.get('tasks', [])) or not idle(thread):
            raise ValueError('The original planner must be confirmed idle in its original native conversation')
        for receipt in candidate['receipts'].values():
            worker = next((b for b in fleet if b['id'] == receipt['bot_id']), None)
            worker_task = next((t for t in (worker or {}).get('tasks', []) if t['threadId'] == receipt['thread_id']), None)
            if worker_task is None or worker_task.get('busy') or not idle(receipt['thread_id']):
                raise ValueError('Original worker runtime is still busy or cannot be confirmed idle')
        if role['botId'] != next(r['botId'] for r in json.loads(wf.deployment_path().read_text())['roles'] if r['key'] == 'xhs-planner'):
            raise ValueError('Recovery team differs from the receipt deployment')
        recovery_id = str(uuid.uuid4())
        text = prompt(project, candidate, reason.strip(), recovery_id)
        record = {'version': 1, 'status': 'prepared', 'created_at': wf.now(),
                  'send_id': recovery_id, 'thread_id': thread, 'bot_id': role['botId'],
                  'draft_token': candidate['dispatch_tokens']['draft'],
                  'reason': reason.strip(), 'source_root': candidate['recovery']['observation']['source_root'],
                  'model_selection': task.get('modelSelection') or bot.get('modelSelection'),
                  'model_policy': 'selection snapshot only; no model-switch request from this tool',
                  'prompt_sha256': hashlib.sha256(text.encode()).hexdigest(),
                  'before_state_sha256': hashlib.sha256(state_path.read_bytes()).hexdigest(),
                  'protected_evidence': protected_snapshot(project, candidate),
                  'observation': candidate['recovery']['observation']}
        directory = project / '.xhs/recovery'
        if directory.is_symlink():
            raise ValueError('Recovery directory cannot be a symlink')
        directory.mkdir(mode=0o700, exist_ok=True)
        wf.write(project / JOURNAL, record)
        candidate['updated_at'] = wf.now()
        wf.write(state_path, candidate)
        wf.handoff(project, candidate)
        record['status'] = 'sending'
        wf.write(project / JOURNAL, record)
    # Release the ledger lock before waking the planner, whose tools use it too.
    try:
        client.call('POST', f"/api/bots/{role['botId']}/messages",
                    {'text': text, 'threadId': thread, 'sendId': recovery_id})
    except Exception:
        record['status'] = 'delivery_unknown'
        record['updated_at'] = wf.now()
        wf.write(project / JOURNAL, record)
        raise
    record['status'] = 'sent'
    record['updated_at'] = wf.now()
    wf.write(project / JOURNAL, record)
    return {'status': 'sent', 'thread_id': thread, 'journal': str(project / JOURNAL),
            'model_change_requested': False, 'native_runtime_after_send': 'not_verified',
            'worker_dispatched': False, 'published': False}
