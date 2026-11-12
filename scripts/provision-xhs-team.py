#!/usr/bin/env python3
"""Provision only the three Xiaohongshu draft roles through native local APIs.

Portable declarations stay in Git. Machine-specific Bot IDs are stored under
~/.workflour/xhs by default. Existing roles' manual model choices are preserved.
This command never sends prompts, starts a workflow, publishes or reorders bots.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from xhs_paths import deployment_path

TEAM = ROOT / 'integrations/openmausbot/team-xhs'
KEYS = ('xhs-collector', 'xhs-planner', 'xhs-writer')
DEFAULT_MANIFEST = deployment_path()
spec = importlib.util.spec_from_file_location('model_control', ROOT / 'scripts/bot-model.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


def declarations():
    roles = json.loads((TEAM / 'roles.json').read_text())
    if len(roles) != 3 or {r['key'] for r in roles} != set(KEYS):
        raise control.ControlError('Expected exactly the three declared Xiaohongshu roles')
    for role in roles:
        for field in ('soulFile', 'skillsFile'):
            source = Path(role[field])
            if source.is_absolute() or not (ROOT / source).resolve().is_relative_to(ROOT):
                raise control.ControlError('Role paths must be repository-relative')
            if not (ROOT / source).is_file():
                raise control.ControlError('Missing declared role instruction file')
    return roles


def manifest(path, *, create=False):
    declared = declarations()
    if path.exists():
        value = json.loads(path.read_text())
        roles = value.get('roles', [])
        if value.get('team') != 'xhs' or len(roles) != 3 or {r.get('key') for r in roles} != set(KEYS):
            raise control.ControlError('Deployment manifest is not this three-role team')
        ids = [r.get('botId') for r in roles]
        if len(set(ids)) != 3 or any(not isinstance(bid, str) or str(uuid.UUID(bid)) != bid for bid in ids):
            raise control.ControlError('Deployment Bot IDs must be distinct native UUIDs')
        by_key = {r['key']: r['botId'] for r in roles}
        # Use current portable instructions; retain only the machine-owned IDs.
        value['roles'] = [{**r, 'botId': by_key[r['key']]} for r in declared]
        return value
    if not create:
        raise control.ControlError('Run prepare or create first; deployment manifest is missing')
    value = {'version': 1, 'team': 'xhs', 'state': 'prepared',
             'roles': [{**r, 'botId': str(uuid.uuid4())} for r in declared]}
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    control.write_journal(path, value)
    return value


def soul(role, team):
    content = (ROOT / role['soulFile']).read_text().replace('{{ROOT}}', str(ROOT))
    routes = '\n'.join(f"- {r['key']}: {r['name']} = {r['botId']}" for r in team['roles'])
    return content + f'''\n\n## 本机路由与工具\n{routes}
工具仓库：{ROOT}
本角色目录：{(ROOT / role['soulFile']).parent}
技能索引：{ROOT / role['skillsFile']}
内容项目工具：{ROOT}/scripts/xhs-workflow.py
采集工具：{ROOT}/scripts/xhs-collect.py（先查看 --help；不要猜参数）
只使用以上精确新团队ID。沿用原生委派回传，不能将会话文本当共享状态或向祖先反派。
本SOUL已由部署器解析路径；仓库源文件里的工具根占位以此Bot指令为准。
用户手动换模型优先，设置入口复用 {ROOT}/scripts/bot-model.py 和现有安全模型卡。
'''


def owned(bot, role):
    return bot.get('description', '').startswith('Workflour 小红书图文 · ' + role['key'])


def provision(client, team, action):
    fleet = client.call('GET', '/api/bots?messages=0')['bots']
    bots = {b['id']: b for b in fleet}
    instances = control.rows(client.call('GET', '/api/instances'))
    selected = team['roles']
    protected_fields = ('name', 'section', 'soul', 'cwd', 'modelSelection', 'approvalMode')
    own_ids = {role['botId'] for role in selected}
    protected = {bid: {k: b.get(k) for k in protected_fields}
                 for bid, b in bots.items() if bid not in own_ids}
    for role in selected:
        existing = bots.get(role['botId'])
        if existing and not owned(existing, role):
            raise control.ControlError('A deployment ID belongs to another Bot; no changes made')
        if action == 'instructions' and (not existing or existing.get('busy') or any(t.get('busy') for t in existing.get('tasks', []))):
            raise control.ControlError('All three owned roles must exist and be idle before updating instructions')
    selections = {}
    # Check all required catalogs before the first native write. Existing Bot
    # models are not validated against defaults or changed by repeated create.
    if action == 'create':
        for role in selected:
            if role['botId'] not in bots:
                selections[role['key']] = control.selection(
                    instances, role['instance'], role['modelId'], role['thinking'])
    for role in selected:
        bid = role['botId']
        if action == 'create' and bid not in bots:
            selection = selections[role['key']]
            settings = {
                'name': role['name'], 'title': role['name'],
                'description': 'Workflour 小红书图文 · ' + role['key'] + ' · 仅草稿',
                'section': '小红书', 'soul': soul(role, team),
                'modelSelection': selection, 'cwd': str(ROOT),
                'approvalMode': 'full', 'computer': 'off', 'browser': True,
                'composio': False, 'helperModel': False,
                'peers': [r['botId'] for r in selected if r['botId'] != bid],
                'approvePeerComms': False,
            }
            client.call('POST', '/api/bots', {'id': bid, 'useDefaults': False,
                        'settings': settings, 'modelSelection': selection, 'requireAvailableModel': True})
            client.call('PATCH', f'/api/bots/{bid}', {'memoryEnabled': False})
        elif action == 'instructions':
            client.call('PATCH', f'/api/bots/{bid}', {'soul': soul(role, team)})
    after = {b['id']: b for b in client.call('GET', '/api/bots?messages=0')['bots']}
    rows = []
    for role in selected:
        b = after.get(role['botId'])
        initial = {'instanceId': role['instance'], 'model': role['modelId'], 'variant': role['thinking']}
        rows.append({'role': role['key'], 'botId': role['botId'], 'exists': bool(b),
                     'owned': bool(b and owned(b, role)),
                     'initial_model_matches': bool(b and b.get('modelSelection') == initial),
                     'selection': b.get('modelSelection') if b else None,
                     'busy': b.get('busy') if b else None})
    if action in ('create', 'instructions') and all(r['exists'] and r['owned'] for r in rows):
        team['state'] = 'active'
    unchanged = all(bid in after and {k: after[bid].get(k) for k in protected_fields} == before
                    for bid, before in protected.items())
    return {'team': 'xhs', 'state': team['state'], 'roles': rows,
            'other_bots_configuration_matches_snapshot': unchanged,
            'model_prompts_sent': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'create', 'instructions', 'verify'))
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST,
                        help='Private machine-local deployment; never copy IDs to another machine')
    args = parser.parse_args()
    path = args.manifest.expanduser().resolve()
    team = manifest(path, create=args.action in ('prepare', 'create'))
    if args.action == 'prepare':
        print(json.dumps({'manifest': str(path), 'state': team['state'], 'roles': len(team['roles'])}, ensure_ascii=False))
        return
    result = provision(control.Client(), team, args.action)
    if args.action in ('create', 'instructions'):
        control.write_journal(path, team)
    print(json.dumps({'manifest': str(path), **result}, ensure_ascii=False, indent=2))
    if not all(r['exists'] and r['owned'] for r in result['roles']):
        raise control.ControlError('Team verification incomplete')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, control.ControlError, OSError, KeyError) as error:
        raise SystemExit(str(error)) from None
