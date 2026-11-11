#!/usr/bin/env python3
"""Idempotent native provisioning for the versioned Plan/Code team.

Creates only the explicitly listed new IDs. Does not delete legacy bots, send
prompts, or overwrite an existing bot's manually selected model.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]
TEAM = ROOT / 'integrations/openmausbot/team-v2'
MANIFEST = TEAM / 'deployment.json'
spec = importlib.util.spec_from_file_location('model_control', ROOT / 'scripts/bot-model.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


def manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    roles = json.loads((TEAM / 'roles.json').read_text())
    result = {'version': 2, 'state': 'staging', 'roles': []}
    for role in roles:
        result['roles'].append({**role, 'botId': str(uuid.uuid4())})
    control.write_journal(MANIFEST, result)
    return result


def soul(role, team):
    base = Path(role['soulFile']).read_text()
    routes = '\n'.join(f"- {r['key'].removeprefix('wf-')}: {r['name']} = {r['botId']}" for r in team['roles'])
    return base + f'''\n\n## 本机新团队路由（版本 2）\n{routes}
只使用以上准确 ID，不把同名旧 Bot 当成员。角色名与当前模型分开；不要向祖先反向委派。
技能目录：{role['skillsFile']}。首次相关任务按需读取，不一次性加载所有技能。
本机已经实测的工具与限制：{ROOT}/agents/wf-shared/CAPABILITIES.md；遇到网页读取问题先看这里，不反复空试。
普通业务不用扫描账号配置或环境自报模型；同一代码快照的有效测试证据复用，不为进度汇报重复运行。
控制工具：{ROOT}/scripts/bot-model.py；操作说明：{ROOT}/integrations/openmausbot/MODEL-CONTROLS.md。
用户要换模型/思考程度时，使用安全模型卡并明确仅当前任务或设为默认；原生顶部菜单可能修改默认，不能误称只改当前任务。所有角色均可换模型，跨运行时新建任务读取交接。
用户明确的能力探针只按探针范围执行，不因此启动完整开发流程或派给其他成员。
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'create', 'instructions', 'verify', 'activate'])
    parser.add_argument('--role', action='append', help='Limit an instructions update to explicit role keys')
    args = parser.parse_args()
    team = manifest()
    if args.role and args.action != 'instructions':
        parser.error('--role is only supported for instructions')
    unknown = set(args.role or []) - {r['key'] for r in team['roles']}
    if unknown:
        parser.error('Unknown roles: ' + ', '.join(sorted(unknown)))
    selected = [r for r in team['roles'] if not args.role or r['key'] in args.role]
    if args.action == 'prepare':
        print(json.dumps({'manifest': str(MANIFEST), 'roles': len(team['roles'])}))
        return
    client = control.Client()
    bots = {b['id']: b for b in client.call('GET', '/api/bots?messages=0')['bots']}
    instances = control.rows(client.call('GET', '/api/instances'))
    ids = [r['botId'] for r in team['roles']]
    if args.action in ('instructions', 'activate'):
        # Validate every target before applying any patch, so a busy later role
        # cannot leave an accidental partial instruction deployment.
        for role in selected:
            b = bots.get(role['botId'])
            if not b:
                raise control.ControlError('Create all selected bots before updating instructions')
            if b.get('busy') or any(t.get('busy') for t in b.get('tasks', [])):
                raise control.ControlError(f"{role['name']} is busy; instructions unchanged")
    for role in selected:
        bid = role['botId']
        existing = bots.get(bid)
        if args.action == 'create' and not existing:
            selection = control.selection(instances, role['instance'], role['modelId'], role['thinking'])
            key = role['key']
            section = 'Plan Team' if 'plan-' in key else 'Code Team' if 'code-' in key else '常用'
            peers = [x for x in ids if x != bid]
            settings = {
                'name': role['name'] + ('（新）' if key in ('wf-manager', 'wf-assistant') else ''),
                'title': role['name'], 'description': 'Workflour Plan/Code 团队 · ' + ('按需参与' if role['optional'] else '正式角色'),
                'soul': soul(role, team), 'section': section,
                'modelSelection': selection, 'cwd': str(ROOT), 'approvalMode': 'full',
                'peers': peers, 'approvePeerComms': False,
                # ACP agents already own their authorized file/shell tools.
                # Desktop screen control is a separate product grant, not needed
                # for headless Playwright and cannot be granted by a server API.
                'computer': 'off', 'browser': True, 'composio': False,
                'helperModel': False,
            }
            result = client.call('POST', '/api/bots', {'id': bid, 'useDefaults': False,
                                'settings': settings, 'modelSelection': selection, 'requireAvailableModel': True})
            existing = result['bot']
            client.call('PATCH', f'/api/bots/{bid}', {'memoryEnabled': False})
            print(json.dumps({'created': role['name'], 'id': bid}, ensure_ascii=False))
        elif args.action in ('instructions', 'activate'):
            if not existing:
                raise control.ControlError('Create all new bots before updating instructions')
            if existing.get('busy') or any(t.get('busy') for t in existing.get('tasks', [])):
                raise control.ControlError(f"{role['name']} is busy; instructions unchanged")
            patch = {'soul': soul(role, team)}
            if args.action == 'activate':
                patch.update(name=role['name'], pinned=role['key'] in ('wf-manager', 'wf-assistant'))
            client.call('PATCH', f'/api/bots/{bid}', patch)
    after = {b['id']: b for b in client.call('GET', '/api/bots?messages=0')['bots']}
    if args.action == 'activate':
        # A chief is a native supervision role; Plan lead coordinates via ordinary
        # native delegation. Only the daily manager gets the prominent chief UI.
        manager = next(r for r in team['roles'] if r['key'] == 'wf-manager')
        client.call('PATCH', f"/api/bots/{manager['botId']}", {'chiefOfStaff': True})
        client.call('PUT', '/api/bots/order', {'botIds': ids})
        team['state'] = 'active'
        control.write_journal(MANIFEST, team)
    rows = []
    for role in team['roles']:
        b = after.get(role['botId'])
        desired = {'instanceId': role['instance'], 'model': role['modelId'], 'variant': role['thinking']}
        rows.append({'role': role['key'], 'exists': b is not None,
                     'model_matches_initial': bool(b and b['modelSelection'] == desired),
                     'selection': b.get('modelSelection') if b else None,
                     'approval': b.get('approvalMode') if b else None,
                     'busy': b.get('busy') if b else None})
    print(json.dumps({'state': team['state'], 'roles': rows}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, control.ControlError) as error:
        raise SystemExit(str(error)) from None
