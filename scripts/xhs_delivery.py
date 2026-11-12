"""Synchronous, resumable-read-only delivery preparation for the three XHS roles.

One invocation owns generation, fallback, and rendering. Its durable receipt is
not a business-stage completion. A separate explicit visual acknowledgement is
required before writing the final report; the planner still owns the ledger.
"""
from contextlib import contextmanager
import copy
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
# ACP transports only standard MCP server fields. Do not assume CLI workspace
# timeoutSeconds applies there: keep the whole call inside its native 180s cap.
ACP_BOUNDED = os.environ.get('WORKFLOUR_XHS_ACP_BOUNDED') == '1'
IMAGE_TIMEOUT = 120 if ACP_BOUNDED else 420
RENDER_TIMEOUT = 30 if ACP_BOUNDED else 90


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


workflow = module('delivery_workflow', 'xhs-workflow.py')
images = module('delivery_images', 'xhs-image.py')
renderer = module('delivery_renderer', 'render-xhs-cards.py')


class DeliveryCancelled(BaseException):
    pass


@contextmanager
def cancellation():
    def stop(signum, frame):
        raise DeliveryCancelled()
    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def local_file(project, name):
    if not isinstance(name, str) or not name:
        raise ValueError('Expected a nonempty project-relative path')
    path = Path(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Use a project-relative file path without ..')
    current = project
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise ValueError('Delivery files must not be symlinks')
    return workflow.artifact(project, name)


@contextmanager
def delivery_lock(project):
    directory = project / 'delivery'
    if directory.is_symlink():
        raise ValueError('Refuse symlink delivery directory')
    directory.mkdir(exist_ok=True, mode=0o700)
    path = directory / 'lock'
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Delivery is already running; do not repeat generation') from None
        yield directory


def project_state(project):
    project = Path(project).expanduser()
    if not project.is_absolute():
        raise ValueError('Use an absolute content project path')
    project = project.resolve(strict=True)
    local_file(project, '.xhs/state.json')
    state = json.loads((project / '.xhs/state.json').read_text())
    if state.get('workflow') != 'xhs-three':
        raise ValueError('Expected an initialized XHS three-role project')
    if state.get('status') != 'active' or state.get('stage') not in ('draft', 'review'):
        raise ValueError('Delivery preparation requires an active draft/review stage')
    if not all(key in state.get('artifacts', {}) for key in ('collect', 'brief')):
        raise ValueError('Lock collection and brief before delivery')
    workflow.verify_artifacts(project, state)
    return project, state


@contextmanager
def checked_delivery(project):
    project = Path(project).expanduser()
    if not project.is_absolute() or not (project / '.xhs/state.json').is_file():
        raise ValueError('Use an initialized absolute XHS project')
    project = project.resolve(strict=True)
    # Same order as revise: ledger first, delivery second. Release the ledger
    # while the slow tool runs; keep the delivery lock until all writes finish.
    with workflow.locked(project):
        project, state = project_state(project)
        lock = delivery_lock(project)
        directory = lock.__enter__()
    try:
        yield project, state, directory
    finally:
        lock.__exit__(None, None, None)


def check_snapshot(project, snapshot):
    for saved in snapshot:
        if local_file(project, saved['path']) != saved:
            raise ValueError('Delivery input/output changed: ' + saved['path'])


def save_receipt(directory, receipt, status, **fields):
    receipt.update(status=status, updated_at=workflow.now(), **fields)
    workflow.write(directory / 'receipt.json', receipt)


def native_generation(project, evidence_name, reused=False):
    saved = local_file(project, evidence_name)
    evidence = json.loads((project / saved['path']).read_text())
    if not isinstance(evidence, dict) or not evidence.get('finished_at'):
        raise ValueError('Image evidence is not a finished native result; do not regenerate')
    if evidence.get('status') == 'blocked':
        if evidence.get('images'):
            raise ValueError('Blocked image evidence unexpectedly contains images; inspect it')
        return ({'status': 'blocked', 'reason': evidence.get('reason', 'native_image_blocked'),
                 'evidence': saved['path'], 'ai_generated': False, 'model': 'unverified'}, [saved], [])
    generation = {'status': 'reused' if reused else 'passed', 'evidence': saved['path'],
                  'ai_generated': True, 'model': 'unverified'}
    verified = workflow.generation_artifacts(project, generation)
    originals = [item['path'] for key, item in verified.items() if key.startswith('image_original_')]
    return generation, list(verified.values()), originals


def run_renderer(project, input_name):
    command = [sys.executable, str(ROOT / 'scripts/render-xhs-cards.py'),
               '--project', str(project), '--input', input_name]
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, _ = process.communicate(timeout=RENDER_TIMEOUT)
        if process.returncode:
            raise ValueError('Card rendering failed; inspect card length and browser installation')
        return json.loads(stdout)
    finally:
        # Chrome and the alternate Python interpreter belong to this group.
        images.stop_process_group(process)


def result(receipt):
    return {key: receipt[key] for key in
            ('status', 'image_generation', 'review_required', 'report', 'limitations') if key in receipt}


def prepare(project, image_prompt_file=None, existing_image_evidence=None):
    if image_prompt_file is not None and existing_image_evidence is not None:
        raise ValueError('Choose a new request OR existing evidence, never both')
    request = {'image_prompt_file': image_prompt_file, 'existing_image_evidence': existing_image_evidence}
    with checked_delivery(project) as (project, state, directory):
        receipt_file = directory / 'receipt.json'
        if receipt_file.exists():
            local_file(project, 'delivery/receipt.json')
            receipt = json.loads(receipt_file.read_text())
            if receipt.get('draft_token') != state['dispatch_tokens']['draft']:
                raise ValueError('Delivery belongs to a different draft revision')
            if receipt.get('request') != request:
                raise ValueError('Delivery already attempted; keep the original request and evidence')
            if receipt.get('status') not in ('awaiting_visual_review', 'ready'):
                raise ValueError('Delivery incomplete/failed; inspect its receipt, never automatically regenerate')
            check_snapshot(project, receipt['snapshot'])
            return result(receipt)
        if (project / 'writing-report.json').exists() or (project / 'output').exists():
            raise ValueError('Existing delivery must be inspected, not overwritten')
        snapshot = [local_file(project, name) for name in ('draft.md', 'cards.json')]
        snapshot += [state['artifacts'][key] for key in ('collect', 'brief')]
        cards = json.loads((project / 'cards.json').read_text())
        # Validate text-only fallback before spending the one image request.
        if not isinstance(cards, dict) or any(card.get('image') or card.get('layout') == 'image-cover'
                                             for card in cards.get('cards', []) if isinstance(card, dict)):
            raise ValueError('Prepare text-only cards.json; the tool adds a validated image if available')
        renderer.build(project, cards)
        prompt = None
        if image_prompt_file is not None:
            if (project / '.xhs/recovery/resume.json').exists():
                raise ValueError('Recovery must reuse existing evidence; a new image request is forbidden')
            prior = project / 'generated-images'
            if (any(project.rglob('image-evidence.json')) or
                    (prior.exists() and any(path.is_dir() for path in prior.iterdir()))):
                raise ValueError('Prior image work exists; inspect and explicitly reuse it, never generate again')
            policy = state.get('image_policy', {})
            if policy.get('max_requests') != 1 or policy.get('useG1Credits') is not False:
                raise ValueError('This project has no recorded one-image subscription-only authorization')
            snapshot.append(local_file(project, image_prompt_file))
            prompt = (project / image_prompt_file).read_text()
            if not prompt.strip() or len(prompt) > 10000:
                raise ValueError('Image prompt must contain 1–10000 characters')
            if (directory / 'image').exists():
                raise ValueError('A previous image request exists; inspect and reuse its evidence')
        if existing_image_evidence is not None:
            generation, evidence_snapshot, originals = native_generation(project, existing_image_evidence, reused=True)
        else:
            generation, evidence_snapshot, originals = {'status': 'template_only', 'ai_generated': False}, [], []
        receipt = {'version': 1, 'created_at': workflow.now(), 'request': request,
                   'draft_token': state['dispatch_tokens']['draft'],
                   'snapshot': snapshot, 'published': False}
        # Durable reservation BEFORE any billable request. A crash is uncertain,
        # never permission to repeat the model call.
        save_receipt(directory, receipt, 'preparing')
        try:
            with cancellation():
                if prompt is not None:
                    (directory / 'image').mkdir(mode=0o700)
                    images.run_print(directory / 'image', prompt, timeout=IMAGE_TIMEOUT, max_images=1)
                    generation, evidence_snapshot, originals = native_generation(project, 'delivery/image/image-evidence.json')
                snapshot += evidence_snapshot
                check_snapshot(project, snapshot)
                render_cards = copy.deepcopy(cards)
                if originals:
                    render_cards['cards'][0].update(image=originals[0], layout='image-cover')
                workflow.write(directory / 'cards.render.json', render_cards)
                save_receipt(directory, receipt, 'preparing', image_generation=generation, snapshot=snapshot)
                rendered = run_renderer(project, 'delivery/cards.render.json')
                final_images = [item['path'] for item in rendered['images']]
                if not final_images:
                    raise ValueError('Renderer returned no actual PNGs')
                for name in final_images:
                    saved = local_file(project, name)
                    if workflow.png_dimensions((project / name).read_bytes()) != (1080, 1440):
                        raise ValueError('Expected actual 1080×1440 cards')
                    snapshot.append(saved)
                limitations = list(state.get('source_limitations', []))
                if generation['status'] == 'blocked':
                    limitations.append('原生生图受阻；保留原始失败证据，本次交付模板卡片：' + str(generation['reason']))
                report = {'status': 'partial' if generation['status'] == 'blocked' else 'ready',
                          'images': final_images, 'limitations': limitations,
                          'image_generation': generation, 'draft_file': 'draft.md',
                          'delivery_method': 'synchronous_local_tool', 'published': False}
                recovery_path = project / '.xhs/recovery/resume.json'
                if recovery_path.exists():
                    local_file(project, '.xhs/recovery/resume.json')
                    recovery = json.loads(recovery_path.read_text())
                    report['maintenance_recovery'] = {
                        'kind': 'mechanical_delivery_from_existing_writer_draft',
                        'source_writer_receipt': state.get('receipts', {}).get('draft', {}).get('id'),
                        'recovery_send_id': recovery.get('send_id'),
                        'draft_sha256': local_file(project, 'draft.md')['sha256']}
                workflow.write(directory / 'report.pending.json', report)
                snapshot += [local_file(project, name) for name in
                             ('delivery/cards.render.json', 'delivery/report.pending.json',
                              'output/render-manifest.json', 'output/preview.html')]
                check_snapshot(project, snapshot)
                save_receipt(directory, receipt, 'awaiting_visual_review', snapshot=snapshot,
                             review_required=originals + final_images, limitations=limitations,
                             report='delivery/report.pending.json')
                return result(receipt)
        except BaseException as error:
            save_receipt(directory, receipt, 'failed', error=type(error).__name__,
                         reason='No automatic retry; preserve evidence and inspect incomplete delivery')
            raise


def confirm(project, reviewed_images):
    with checked_delivery(project) as (project, state, directory):
        local_file(project, 'delivery/receipt.json')
        receipt = json.loads((directory / 'receipt.json').read_text())
        if receipt.get('draft_token') != state['dispatch_tokens']['draft']:
            raise ValueError('Delivery belongs to a different draft revision')
        if receipt.get('status') not in ('awaiting_visual_review', 'ready'):
            raise ValueError('Preparation has not finished; a native end_turn is not delivery completion')
        if (not isinstance(reviewed_images, list) or any(not isinstance(p, str) for p in reviewed_images)
                or sorted(reviewed_images) != sorted(receipt['review_required'])):
            raise ValueError('Actually inspect and acknowledge every generated original and final card')
        check_snapshot(project, receipt['snapshot'])
        report = json.loads((directory / 'report.pending.json').read_text())
        confirmation = receipt.get('confirmation')
        if not confirmation:
            confirmation = {'acknowledged_images': reviewed_images, 'at': workflow.now(),
                            'method': 'explicit_writer_or_planner_acknowledgement'}
            save_receipt(directory, receipt, 'awaiting_visual_review', confirmation=confirmation)
        report['visual_review'] = confirmation
        path = project / 'writing-report.json'
        if receipt['status'] == 'ready':
            return result(receipt)
        if path.exists():
            local_file(project, 'writing-report.json')
            if json.loads(path.read_text()) != report:
                raise ValueError('A different report appeared during visual review; inspect instead of overwriting')
        else:
            workflow.write(path, report)
        receipt['snapshot'].append(local_file(project, 'writing-report.json'))
        save_receipt(directory, receipt, 'ready', report='writing-report.json')
        return result(receipt)
