#!/usr/bin/env python3
"""Observe explicitly registered local workflows; never dispatch or settle work.

Writes only its own managed Markdown area and diagnostic files. Run once by
launchd every 20 seconds; failed exports remain visible and retry next time.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import tempfile
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_assignments import read_assignments, matching, workflow_threads, effective_status
from workflour_paths import vault_path
SPEC = importlib.util.spec_from_file_location('record_export', Path(__file__).with_name('export-agent-record.py'))
EXPORT = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(EXPORT)
BASE = Path.home() / '.workflour/observer'
VAULT = vault_path()
LABEL = 'com.workflour.workflow-observer'


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, text):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refuse managed output symlink')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == text:
        return
    fd, tmp = tempfile.mkstemp(prefix='.observer-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def dump(path, data):
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def registry(base=BASE):
    path = base / 'projects.json'
    return json.loads(path.read_text()) if path.exists() else []


def register(project, vault=VAULT, base=BASE):
    root = Path(project).resolve(strict=True)
    target = Path(vault).resolve(strict=True)
    if not (root / '.workflour/handoff.json').is_file() or not target.is_dir():
        raise ValueError('Expected initialized project and existing vault')
    base.mkdir(parents=True, exist_ok=True)
    with (base / 'registry.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = registry(base)
        slug = re.sub(r'[^\w\-一-鿿]', '-', root.name)[:50] + '-' + hashlib.sha256(str(root).encode()).hexdigest()[:10]
        row = {'project': str(root), 'vault': str(target), 'slug': slug}
        found = next((r for r in rows if r['project'] == str(root)), None)
        if found and any(found.get(k) != value for k, value in row.items()):
            raise ValueError('Project already registered with different destination')
        if not found: rows.append(row)
        dump(base / 'projects.json', rows)
    return row


def set_suspended(project, reason=None, *, resume=False, base=BASE):
    target = str(Path(project).resolve(strict=True))
    if not resume and (not reason or not reason.strip()):
        raise ValueError('Suspension needs an explicit reason; records are retained')
    with (base / 'registry.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = registry(base)
        row = next((r for r in rows if r['project'] == target), None)
        if row is None:
            raise ValueError('Project is not registered')
        dump(base / ('registry-backup-' + datetime.now().strftime('%Y%m%d%H%M%S%f') + '.json'), rows)
        row['suspended'] = not resume
        row['suspension_reason'] = None if resume else reason.strip()
        row['changed_at'] = now()
        dump(base / 'projects.json', rows)
        return row


def safe_text(value):
    return EXPORT.redact(str(value)).replace('|', '\\|').replace('\n', ' ')


def role_label(key):
    if key == 'coordinator': return '项目总控'
    if key == 'coordinator-previous': return '项目总控（旧会话）'
    if key == 'plan-lead': return 'Plan · 项目负责人'
    if key == 'plan-lead-previous': return 'Plan · 项目负责人（旧会话）'
    phases={'planning':'独立提案','discussion':'交叉回应','plan':'计划整合','implement':'编码','review':'独立审核','verify':'测试复核','research':'调研初案','plan-review':'方案评审','experience':'实际体验','acceptance':'待用户验收'}
    roles={'kimi':'方案主持','deepseek':'协作编码','glm-plan':'风险规划','glm-review':'独立审核','agy':'主力编码','coordinator':'项目总控','plan-lead':'项目负责人','plan-review':'方案与体验评审','code-main':'主编码','code-review':'独立审核','code-helper':'协作编码'}
    old=key.endswith('-previous')
    key=key.removesuffix('-previous')
    for phase in sorted(phases, key=len, reverse=True):
        label=phases[phase]
        for sep in ('/','-'):
            if key.startswith(phase+sep):
                role=key[len(phase)+1:]
                return label+' · '+roles.get(role,role)+('（旧尝试）' if old else '')
    return key


def link(path, label):
    return f'[{label}](<{path}>)'


def project_snapshot(root, state):
    result = {}
    for name in state.get('code_files', []):
        path = (root / name).resolve()
        path.relative_to(root)
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return result


def collect(root, ledger, handoff, rows):
    alerts, lines, threads = [], [], {}
    for tid in workflow_threads(ledger):
        owner = 'plan-lead' if ledger.get('workflow') == 'plan-code' else 'coordinator'
        threads[tid] = owner if tid == ledger.get('coordinator_thread') else owner + '-previous'
    entries = list(ledger.get('assignments', {}).items())
    entries += [(h['key'] + '-previous', h['item']) for h in ledger.get('attempt_history', [])]
    for key, item in entries:
        conflict = None
        try:
            native = matching(ledger, item, rows)
        except ValueError as exc:
            native = None
            conflict = str(exc)
            alerts.append(f'{key}：回执核对冲突：{conflict}。核对并显式登记真实补充；禁止清标记、忽略回执或重复派单。')
        current = not key.endswith('-previous')
        # Verification runs in the chief's own conversation, not as a native
        # worker dispatch. Its receipt is recorded after the command finishes.
        local_verify = bool(re.fullmatch(r'verify/coordinator(?:@[12])?(?:-previous)?', key))
        local_plan = (ledger.get('workflow') == 'plan-code' and item.get('execution') == 'local'
                      and key in ('research/plan-lead', 'plan/plan-lead'))
        status = effective_status(native) if native else item['status']
        status_names = {'completed':'已返回（仍需证据验证）', 'failed':'失败', 'cancelled':'已停止',
                        'stopped':'已停止', 'needs_input':'等待审批或输入', 'waiting':'等待',
                        'running':'运行中', 'claimed':'已占位，待核对派单', 'queued':'排队', 'resume':'等待续接'}
        desc = status_names.get(status, status)
        if local_verify and status == 'claimed':
            desc = '总控本地复测，等待测试证据'
        if local_plan:
            desc = '负责人已记录（需核对证据）' if status == 'completed' else desc
        receipt_label = item.get('assignment_id', '负责人自身工作，无委派' if local_plan else ('等待本地测试证据' if local_verify else '未绑定'))
        lines.append(f"| {safe_text(role_label(key))} | {safe_text(desc)} | {safe_text(item.get('status'))} | {safe_text(receipt_label)} |")
        for addition in native.get('supplements', []) if native else []:
            lines.append(f"| {safe_text(role_label(key))}·已登记补充 | {safe_text(status_names.get(addition['status'], addition['status']))} | 独立原生回执 | {safe_text(addition['id'])} |")
        worker_thread = native['thread_id'] if native else item.get('thread_id')
        if worker_thread and not local_plan and not local_verify:
            threads[worker_thread] = re.sub(r'[^A-Za-z0-9_-]', '-', key)
        if current and status in ('failed', 'stopped', 'cancelled'):
            if item.get('supplements'):
                alerts.append(f'{key}：{desc}。先 reconcile，检查失败的补充并保留全部回执；禁止 retry 重跑已完成主任务。')
            else:
                alerts.append(f'{key}：{desc}。先 reconcile、检查部分改动；明确继续后用 retry，禁止直接重发。')
        if current and status in ('needs_input', 'waiting', 'queued', 'resume'):
            alerts.append(f'{key}：{desc}。查看工作台原任务/审批卡，保留回执，不重复派单。')
        if current and not native and not conflict and item.get('assignment_id') and not item['assignment_id'].startswith('local-test:'):
            alerts.append(f'{key}：原生回执未找到；暂停重试并核对来源会话。')
        if current and not item.get('assignment_id') and not local_verify and not local_plan:
            alerts.append(f'{key}：回执未绑定，先按 WF-DISPATCH 标记 reconcile；不能凭超时重发。')
    snapshot = project_snapshot(root, handoff)
    for section in ('review', 'verification'):
        if handoff.get(section, {}).get('status') == 'passed' and handoff[section].get('snapshot') != snapshot:
            alerts.append(f'{section}：代码已经变化，旧快照失效；重新审核/测试。')
    if handoff.get('stage') == 'acceptance' and handoff.get('acceptance', {}).get('status') == 'pending':
        alerts.append('等待用户验收：技术完成不等于用户接受，不自动标 done。')
    return alerts, lines, threads


def _sync_project(row, read_native=read_assignments, read_thread=EXPORT.read_thread):
    root, vault = Path(row['project']).resolve(strict=True), Path(row['vault']).resolve(strict=True)
    output = vault / '07-自动记录' / row['slug']
    if output.resolve() != output or not output.is_relative_to(vault):
        raise ValueError('Managed vault path escapes through symlink')
    ledger_path = root / '.workflour/coordination.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    handoff = json.loads((root / '.workflour/handoff.json').read_text())
    errors = []
    try:
        rows = [row for thread in workflow_threads(ledger) for row in read_native(thread)]
    except Exception as exc:
        rows = []; errors.append('原生派单状态读取失败：' + type(exc).__name__ + '；不据此重发，检查本机 OpenMausBot。')
    alerts, lines, threads = collect(root, ledger, handoff, rows)
    title_error = root / '.workflour/session-title-error.json'
    if title_error.exists():
        alerts.append('DSH 会话入队曾失败：查看 .workflour/session-title-error.json；修复权限并重新入队，确认后清除此诊断。')
    records = []
    for tid, role in threads.items():
        try:
            messages = read_thread(tid)
            for message in messages:
                card=message.get('card', {}) if isinstance(message,dict) else {}
                if (card.get('requestId') and not any(card.get(k) for k in ('answered','dismissed','expired'))):
                    kind='等待审批' if card.get('requestType') == 'permission' else '等待用户输入'
                    alerts.append(f'{role_label(role)}：{kind}；打开工作台对应会话处理，不重复派单。')
            text = EXPORT.render(messages, tid, role)
            text = text.replace(f'# {role}：独立会话记录', f'# {role_label(role)}：独立会话记录', 1)
            text = re.sub(r'^- 导出时间:.*$', '- 自动更新：以本机可见会话为准', text, flags=re.M)
            write(output / '记录' / (tid + '.md'), text)
            records.append(f'- [[07-自动记录/{row["slug"]}/记录/{tid}|{role_label(role)}]]')
        except urllib.error.HTTPError as exc:
            exc.close()
            if exc.code == 404:
                errors.append(f'角色记录 {role} 的会话 {tid} 不存在（HTTP 404）；核对工作台会话ID，不自动改绑或重派。旧项目可显式 suspend 保留记录。')
            else:
                errors.append(f'角色记录 {role} 同步失败：HTTP {exc.code}；保留旧记录，下轮重试。')
        except Exception as exc:
            errors.append(f'角色记录 {role} 同步失败：{type(exc).__name__}；保留上次记录，后台下轮重试。')
    # Prior exported attempts remain discoverable even after a new task archives
    # the previous ledger. Only our generated UUID records are linked.
    records_dir=output/'记录'
    if records_dir.is_dir():
        for path in sorted(records_dir.glob('*.md')):
            if re.fullmatch(r'[A-Za-z0-9_-]{1,128}',path.stem) and path.stem not in threads:
                records.append(f'- [[07-自动记录/{row["slug"]}/记录/{path.stem}|历史会话 {path.stem[:8]}]]')
    title = safe_text(root.name)
    home = f'# {title} · 自动项目记录\n\n此目录由本机观察器维护；手写笔记放在自动目录以外。\n\n'
    home += f'- 项目：{link(root, "打开项目")}\n- [[07-自动记录/{row['slug']}/进度|进度]] · [[07-自动记录/{row['slug']}/异常|异常]]\n'
    home += '- ' + link(root/'HANDOFF.md', '共享交接') + ' · ' + link(root/'PROJECT-WORKFLOW.md', '使用流程') + '\n'
    home += f'- 当前任务：{safe_text(ledger.get("task_id", handoff.get("task_id")))}\n\n## 角色会话\n\n' + '\n'.join(records) + '\n\n## 材料与测试证据\n\n'
    for name, rel in handoff.get('artifacts', {}).items():
        if rel:
            file = (root / rel).resolve(); file.relative_to(root)
            home += '- ' + link(file, safe_text({'spec':'需求','plan':'计划','tasks':'任务清单','review':'审核结论','verification':'测试验证','acceptance':'验收材料','docs':'文档'}.get(name,name))) + '\n'
    home += '- ' + link(root/'.workflour/evidence', '完整测试输出') + '\n'
    home += '\n## 代码与角色产物\n\n'
    for name in handoff.get('code_files', []):
        file=(root/name).resolve();file.relative_to(root)
        if file.is_file(): home += '- ' + link(file,safe_text(name)) + '\n'
    records_root=root/'records'
    if records_root.is_dir() and not records_root.is_symlink():
        for file in sorted(records_root.rglob('*.md'))[:200]:
            resolved=file.resolve();resolved.relative_to(root)
            if resolved.is_file(): home += '- ' + link(resolved,safe_text(str(file.relative_to(root)))) + '\n'
    progress = f'# 当前进度\n\n- 派单阶段：{safe_text(ledger.get("phase", "尚未启动"))}\n- 项目阶段：{safe_text(handoff.get("stage"))}\n- 负责人：{safe_text(handoff.get("owner"))}\n- 下一步：{safe_text(handoff.get("next_action"))}\n- 用户验收：{safe_text(handoff.get("acceptance", {}).get("status"))}\n\n| 阶段/角色 | 原生状态 | 账本状态 | 回执 |\n| --- | --- | --- | --- |\n' + '\n'.join(lines) + '\n'
    write(output/'首页.md', home); write(output/'进度.md', progress)
    write(output/'异常.md', '# 异常与等待\n\n' + '\n'.join('- ' + safe_text(a) for a in errors+alerts or ['当前未发现阻塞；这不代替独立代码和测试验证。']) + '\n')
    status = {'checked_at':now(), 'ok':not errors, 'alerts':alerts, 'errors':errors, 'output':str(output), 'exported_threads':len(records)}
    dump(root/'.workflour/observer-status.json', status)
    return status


def sync_project(row, read_native=read_assignments, read_thread=EXPORT.read_thread):
    root=Path(row['project']).resolve(strict=True)
    path=root/'.workflour/observer.lock'
    fd=os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd,'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _sync_project(row,read_native,read_thread)


def run_all(base=BASE):
    base.mkdir(parents=True, exist_ok=True)
    with (base/'sync.lock').open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return {'busy':True}
        statuses, by_vault = [], {}
        for row in registry(base):
            if row.get('suspended'):
                status = {'ok': True, 'suspended': True, 'checked_at': now(), 'alerts': ['已暂停自动同步：' + row.get('suspension_reason', '') + '；旧记录保留，恢复使用 resume。'], 'errors': []}
                try:
                    dump(Path(row['project'])/'.workflour/observer-status.json', status)
                except OSError:
                    status.update(ok=False, errors=['暂停状态写入失败；注册表中的暂停仍有效，旧记录保留。'])
                statuses.append({**status, 'project': row['project']})
                by_vault.setdefault(row['vault'], []).append((row,status))
                continue
            try: status = sync_project(row)
            except Exception as exc:
                status = {'ok':False, 'checked_at':now(), 'errors':[f'同步失败：{type(exc).__name__}；检查项目/知识库是否可写，修复后自动重试。']}
                try: dump(Path(row['project'])/'.workflour/observer-status.json', status)
                except OSError: pass
            status['project'] = row['project']; statuses.append(status)
            by_vault.setdefault(row['vault'], []).append((row,status))
        queue = Path.home()/'.dsh/workflour-session-queue'
        diagnostics = queue/'diagnostics.json'
        queue_errors = []
        if diagnostics.exists():
            try:
                d = json.loads(diagnostics.read_text())
                queue_errors = d.get('issues', [])
            except (OSError, ValueError): queue_errors = ['DSH 分类诊断不可读']
        for vault, items in by_vault.items():
            try:
                content = '# 工作流自动记录\n\n只观察已注册项目；不派单、不审批、不修改任务状态。\n\n'
                for row,status in items:
                    badge = ('已暂停（未同步）：' + row.get('suspension_reason', '')) if status.get('suspended') else '同步正常' if status.get('ok') else '同步失败：检查项目或知识库权限，保留旧记录并自动重试'
                    content += f'- [[07-自动记录/{row["slug"]}/首页|{safe_text(Path(row["project"]).name)}]]：{badge}，异常/等待 {len(status.get("alerts", []))} 项\n'
                content += '\n## DSH 会话分类\n\n' + '\n'.join('- ' + safe_text(e) for e in queue_errors or ['未报告分类异常。桌面关闭时分类队列等候下次打开。']) + '\n'
                write(Path(vault)/'07-自动记录/首页.md', content)
            except Exception as exc:
                statuses.append({'ok':False, 'errors':['知识库索引写入失败：'+type(exc).__name__]})
        report = {'checked_at':now(), 'ok':all(s.get('ok') for s in statuses), 'projects':statuses, 'dsh_issues':queue_errors}
        dump(base/'status.json', report)
        write(base/'异常.md', '# 本机自动记录诊断\n\n' + json.dumps(report,ensure_ascii=False,indent=2) + '\n')
        return report


def install():
    BASE.mkdir(parents=True, exist_ok=True)
    path = Path.home()/'Library/LaunchAgents'/f'{LABEL}.plist'
    spec = {'Label':LABEL, 'ProgramArguments':[sys.executable,str(Path(__file__).resolve()),'sync'],
            'RunAtLoad':True,'StartInterval':20, 'ProcessType':'Background',
            'StandardOutPath':str(BASE/'observer.log'), 'StandardErrorPath':str(BASE/'observer-error.log')}
    if path.exists():
        previous=plistlib.loads(path.read_bytes())
        if previous.get('Label') != LABEL or previous.get('ProgramArguments',[None,None])[1] != str(Path(__file__).resolve()):
            raise ValueError('Refuse unrelated LaunchAgent')
        subprocess.run(['launchctl','bootout',f'gui/{os.getuid()}/{LABEL}'],capture_output=True)
    path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(plistlib.dumps(spec))
    subprocess.run(['launchctl','bootstrap',f'gui/{os.getuid()}',str(path)],check=True)
    return {'installed':str(path),'interval_seconds':20}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('register');p.add_argument('--project',required=True);p.add_argument('--vault',default=str(VAULT))
    p=sub.add_parser('sync');p.add_argument('--project', help='Only sync an already registered project')
    sub.add_parser('status');sub.add_parser('install')
    for action in ('suspend', 'resume'):
        p=sub.add_parser(action);p.add_argument('--project',required=True)
        if action == 'suspend': p.add_argument('--reason',required=True)
    args=parser.parse_args()
    try:
        if args.command=='register': result=register(args.project,args.vault)
        elif args.command=='sync':
            if args.project:
                target=str(Path(args.project).resolve(strict=True))
                row=next((r for r in registry() if r['project']==target),None)
                if not row: raise ValueError('Project not registered; run register first')
                result=sync_project(row)
            else: result=run_all()
        elif args.command=='install': result=install()
        elif args.command in ('suspend', 'resume'):
            result=set_suspended(args.project,getattr(args,'reason',None),resume=args.command=='resume')
        else:
            result=json.loads((BASE/'status.json').read_text())
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(result['checked_at'])).total_seconds()
            result['age_seconds']=round(age)
            if age > 120:
                result.update(ok=False, warning='自动记录心跳超过120秒；检查本机launchd/systemd观察器服务和错误日志，旧记录可能过时')
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if result.get('ok',True) else 1
    except Exception as exc:
        print(f'Observer: {type(exc).__name__}: {exc}',file=sys.stderr);return 1

if __name__=='__main__': raise SystemExit(main())
