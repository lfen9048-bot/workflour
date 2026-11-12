#!/usr/bin/env python3
"""Provision the seven Plan/Code roles through native OpenMausBot APIs.

No prompts, account changes, legacy Bot deletion or model-directory refreshes.
Preflight every missing role before creating any Bot. Native API writes are not
a transaction: retain the private manifest after a partial network failure and
rerun create to resume without duplicates. Existing model choices are preserved.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
TEAM = ROOT / 'integrations/openmausbot/team-v2'
LEGACY_ROOT = Path('/Users/a1/Documents/a/workflour')
LEGACY_VAULT = '/Users/a1/Documents/Obsidian/多Agent协作开发工作流'
ROLE_KEYS = ('wf-manager', 'wf-plan-lead', 'wf-plan-review', 'wf-code-main',
             'wf-code-review', 'wf-code-helper', 'wf-assistant')


def local_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


control = local_module('model_control', 'bot-model.py')
paths = local_module('team_local_paths', 'workflour_paths.py')


def legacy_host():
    # An ignored Mac manifest copied into a checkout is never a new host's ID source.
    return sys.platform == 'darwin' and ROOT.resolve() == LEGACY_ROOT


def manifest_path(explicit=None):
    configured = explicit or os.environ.get('WORKFLOUR_TEAM_MANIFEST')
    if configured:
        # abspath keeps a final symlink visible to manifest/save_manifest.
        return Path(os.path.abspath(Path(configured).expanduser()))
    legacy = TEAM / 'deployment.json'
    if legacy_host() and legacy.is_file():
        return legacy
    return Path.home() / '.workflour/team-v2/deployment.json'


def role_file(value):
    if not isinstance(value, str) or not value:
        raise control.ControlError('Role file path is missing')
    relative = Path(value)
    if relative.is_absolute() or '..' in relative.parts:
        raise control.ControlError('Role paths must be repository-relative: ' + value)
    target = (ROOT / relative).resolve()
    if ROOT.resolve() not in target.parents or not target.is_file():
        raise control.ControlError('Role file missing or outside repository: ' + value)
    return target


def declared_roles():
    roles = json.loads((TEAM / 'roles.json').read_text(encoding='utf-8'))
    if not isinstance(roles, list) or len(roles) != len(ROLE_KEYS):
        raise control.ControlError('Expected exactly seven declared roles')
    keys = [r.get('key') for r in roles if isinstance(r, dict)]
    if len(keys) != len(roles) or set(keys) != set(ROLE_KEYS):
        raise control.ControlError('Role keys must be the seven unique Plan/Code keys')
    for role in roles:
        for field in ('name', 'instance', 'modelId', 'thinking'):
            if not isinstance(role.get(field), str) or not role[field]:
                raise control.ControlError(f"{role['key']}: missing {field}")
        if type(role.get('optional')) is not bool:
            raise control.ControlError(f"{role['key']}: optional must be boolean")
        role_file(role.get('soulFile'))
        role_file(role.get('skillsFile'))
    return sorted(roles, key=lambda r: ROLE_KEYS.index(r['key']))


def valid_uuid(value, label):
    try:
        parsed = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise control.ControlError(label + ' must be a UUID') from None
    if str(parsed) != value or parsed.int == 0:
        raise control.ControlError(label + ' must be a canonical, nonzero UUID')
    return value


def manifest(path=None, *, create=False):
    path = Path(path) if path is not None else manifest_path()
    if path.is_symlink():
        raise control.ControlError('Refusing a symlink deployment manifest')
    roles = declared_roles()
    if not path.exists():
        if not create:
            raise control.ControlError('Deployment manifest missing; run prepare or create first: ' + str(path))
        return {'version': 2, 'state': 'staging', 'deploymentId': str(uuid.uuid4()),
                'platform': sys.platform, 'repositoryRoot': str(ROOT),
                'roles': [{**r, 'botId': str(uuid.uuid4())} for r in roles]}
    saved = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(saved, dict) or saved.get('version') != 2 or saved.get('state') not in ('staging', 'active'):
        raise control.ControlError('Unsupported deployment manifest')
    entries = saved.get('roles')
    if not isinstance(entries, list) or len(entries) != len(ROLE_KEYS) or any(not isinstance(r, dict) for r in entries):
        raise control.ControlError('Manifest must contain exactly seven roles')
    keys = [r.get('key') for r in entries]
    if set(keys) != set(ROLE_KEYS) or len(set(keys)) != len(keys):
        raise control.ControlError('Manifest role keys are missing, duplicated or unknown')
    ids = [valid_uuid(r.get('botId'), 'Bot ID') for r in entries]
    if len(set(ids)) != len(ids):
        raise control.ControlError('Manifest Bot IDs must be unique')
    pending = saved.get('pendingInitialization', [])
    if not isinstance(pending, list) or any(not isinstance(k, str) or k not in ROLE_KEYS for k in pending) or len(set(pending)) != len(pending):
        raise control.ControlError('Invalid pending initialization journal')
    unconfirmed = saved.get('pendingCreateReadback', [])
    if not isinstance(unconfirmed, list) or any(not isinstance(k, str) or k not in pending for k in unconfirmed) or len(set(unconfirmed)) != len(unconfirmed):
        raise control.ControlError('Invalid pending creation readback journal')
    legacy = 'deploymentId' not in saved or saved.get('legacyOwnership') is True
    if legacy and not legacy_host():
        raise control.ControlError('Legacy Mac Bot IDs cannot be used on this host; prepare a new local manifest')
    if saved.get('platform', sys.platform) != sys.platform:
        raise control.ControlError('Deployment IDs belong to another platform; prepare a new local manifest')
    deployment_id = saved.get('deploymentId') or str(uuid.uuid5(uuid.NAMESPACE_URL, 'workflour-v2:' + ','.join(ids)))
    valid_uuid(deployment_id, 'Deployment ID')
    by_key = {r['key']: r['botId'] for r in entries}
    # Repository definitions own roles; private manifests bind local IDs, not old paths.
    result = {**saved, 'deploymentId': deployment_id, 'platform': sys.platform,
              'repositoryRoot': str(ROOT), 'roles': [{**r, 'botId': by_key[r['key']]} for r in roles]}
    if legacy:
        result['legacyOwnership'] = True
    return result


def save_manifest(path, team):
    path = Path(path)
    if path.is_symlink():
        raise control.ControlError('Refusing a symlink deployment manifest')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    control.write_journal(path, team)


def ownership_marker(role, team):
    return f"<!-- workflour-team:v2 deployment={team['deploymentId']} role={role['key']} -->"


def routes(team):
    return '\n'.join(f"- {r['key'].removeprefix('wf-')}: {r['name']} = {r['botId']}" for r in team['roles'])


def owns_bot(bot, role, team):
    text = bot.get('soul') or ''
    if ownership_marker(role, team) in text:
        return True
    # Legacy local IDs predate markers: require full exact routing, role and cwd.
    return bool(team.get('legacyOwnership') and legacy_host()
                and 'workflour-team:v2 deployment=' not in text
                and routes(team) in text
                and (bot.get('title') == role['name'] or bot.get('name') in (role['name'], role['name'] + '（新）'))
                and bot.get('cwd') == str(ROOT))


def soul(role, team):
    vault = paths.vault_path()
    base = role_file(role['soulFile']).read_text(encoding='utf-8')
    # Compatibility with documents copied from the historical Mac checkout.
    base = base.replace(str(LEGACY_ROOT), str(ROOT)).replace(LEGACY_VAULT, str(vault))
    return f'''{ownership_marker(role, team)}
## 本机部署路径（先按此解析角色文档）
Workflour 工具仓库根：{ROOT}
本机 Obsidian 知识库：{vault}
角色 Markdown 中的 agents/、scripts/、integrations/、docs/ 路径相对上面的仓库根，绝不是业务项目 cwd；读取与执行前转换成绝对路径。业务项目目录由本次任务明确给出。
知识库位置来自 WORKFLOUR_OBSIDIAN_VAULT 或本机默认；目录不存在时如实说明，不创建历史 Mac 路径。
{base}

## 本机新团队路由（版本 2）
{routes(team)}
只使用以上准确 ID，不把同名旧 Bot 当成员。角色名与当前模型分开；不要向祖先反向委派。
技能目录：{role_file(role['skillsFile'])}。首次相关任务按需读取，不一次性加载所有技能。
能力与浏览器说明：{ROOT}/agents/wf-shared/CAPABILITIES.md、{ROOT}/agents/wf-shared/BROWSER.md。其中旧 Mac 路径、版本、截图和成功记录是历史证据，不代表本机已安装、可读图或验证通过；本机应单独核验工具路径与能力。
普通业务不用扫描账号配置或环境自报模型；同一代码快照的有效测试证据复用，不为进度汇报重复运行。
控制工具：{ROOT}/scripts/bot-model.py；操作说明：{ROOT}/integrations/openmausbot/MODEL-CONTROLS.md。
用户要换模型/思考程度时，使用安全模型卡并明确仅当前任务或设为默认；原生顶部菜单可能修改默认，不能误称只改当前任务。所有角色均可换模型，跨运行时新建任务读取交接。
用户明确的能力探针只按探针范围执行，不因此启动完整开发流程或派给其他成员。
'''


def fleet(client):
    rows = client.call('GET', '/api/bots?messages=0')['bots']
    if len({b['id'] for b in rows}) != len(rows):
        raise control.ControlError('Server returned duplicate Bot IDs')
    return rows


def require_owned(bots, team, selected, *, present=False, idle=False):
    for role in selected:
        bot = bots.get(role['botId'])
        if bot is None:
            if present:
                raise control.ControlError(f"Create {role['key']} before updating instructions")
            continue
        if not owns_bot(bot, role, team):
            raise control.ControlError(f"Bot ID ownership mismatch for {role['key']}; no changes made to this Bot")
        if idle and (bot.get('busy') or any(t.get('busy') for t in bot.get('tasks', []))):
            raise control.ControlError(f"{role['key']} is busy; wait before updating instructions or activation")


def initial_selection(role):
    return {'instanceId': role['instance'], 'model': role['modelId'], 'variant': role['thinking']}


def create_settings(role, team, selection=None):
    """Native 0.1.143 creation schema; memoryEnabled is a separate PATCH."""
    bid, key = role['botId'], role['key']
    return {'name': role['name'], 'title': role['name'],
            'description': 'Workflour Plan/Code 团队 · ' + ('按需参与' if role['optional'] else '正式角色'),
            'soul': soul(role, team), 'section': 'Plan Team' if 'plan-' in key else 'Code Team' if 'code-' in key else '常用',
            'modelSelection': selection or initial_selection(role), 'cwd': str(ROOT), 'approvalMode': 'full',
            'peers': [r['botId'] for r in team['roles'] if r['botId'] != bid],
            'approvePeerComms': False, 'computer': 'off', 'browser': True,
            'composio': False, 'helperModel': False}


def verify_team(team, bots, expected_souls=None, created=(), *, active=False):
    errors, warnings, rows = [], [], []
    for role in team['roles']:
        bot = bots.get(role['botId'])
        desired = initial_selection(role)
        row = {'role': role['key'], 'exists': bot is not None}
        if bot is None:
            errors.append(role['key'] + ': Bot missing on readback')
        else:
            owned = owns_bot(bot, role, team)
            row.update(owned=owned, model_matches_initial=bot.get('modelSelection') == desired,
                       selection=bot.get('modelSelection'), approval=bot.get('approvalMode'), busy=bot.get('busy'))
            if not owned:
                errors.append(role['key'] + ': ownership not confirmed on readback')
            if bot.get('approvalMode') not in ('ask', 'edits', 'auto', 'full', 'custom'):
                errors.append(role['key'] + ': approval mode missing on readback')
            if not isinstance(bot.get('modelSelection'), dict) or not bot['modelSelection'].get('instanceId') or not bot['modelSelection'].get('model'):
                errors.append(role['key'] + ': model selection missing on readback')
            elif not row['model_matches_initial']:
                if role['botId'] in created:
                    errors.append(role['key'] + ': newly created model was not applied')
                else:
                    warnings.append(role['key'] + ': current model differs from initial role configuration; preserved as a manual choice')
            if expected_souls is not None and role['key'] in expected_souls and bot.get('soul') != expected_souls[role['key']]:
                errors.append(role['key'] + ': instructions readback differs; run instructions when this role is idle')
            if active and (bot.get('name') != role['name'] or bool(bot.get('pinned')) != (role['key'] in ('wf-manager', 'wf-assistant'))):
                errors.append(role['key'] + ': active name/pin not confirmed')
            if active and role['key'] == 'wf-manager' and bot.get('chiefOfStaff') is not True:
                errors.append(role['key'] + ': manager entry not confirmed')
        rows.append(row)
    if team.get('pendingInitialization'):
        errors.append('Initialization incomplete; rerun create with the same manifest: ' + ', '.join(team['pendingInitialization']))
    return {'ok': not errors, 'state': team['state'], 'roles': rows, 'errors': errors, 'warnings': warnings,
            'capability_validation': 'Configuration readback only; no model, browser, screenshot or tool probe was sent.'}


def provision(action, *, path=None, role_keys=None, client=None):
    path = manifest_path(path)
    team = manifest(path, create=action in ('prepare', 'create'))
    if role_keys and action != 'instructions':
        raise control.ControlError('--role is only supported for instructions')
    if set(role_keys or []) - set(ROLE_KEYS):
        raise control.ControlError('Unknown role keys')
    if action in ('instructions', 'activate') and team.get('pendingInitialization'):
        raise control.ControlError('Initialization incomplete; run create with the same manifest before ' + action)
    selected = [r for r in team['roles'] if not role_keys or r['key'] in role_keys]
    texts = {r['key']: soul(r, team) for r in selected}
    if action == 'prepare':
        save_manifest(path, team)
        return {'ok': True, 'manifest': str(path), 'roles': len(team['roles']),
                'note': 'Local IDs prepared only; native models and capabilities have not been checked.'}
    client = client or control.Client()
    before_rows = fleet(client)
    before = {b['id']: b for b in before_rows}
    require_owned(before, team, team['roles'])
    created = set()
    if action == 'create':
        # Check every missing role before any Bot write, not one role at a time.
        instances = control.rows(client.call('GET', '/api/instances'))
        selections, failures = {}, []
        for role in team['roles']:
            if role['botId'] in before:
                continue
            try:
                instance = next((i for i in instances if i['instanceId'] == role['instance']), None)
                if instance and instance.get('snapshot', {}).get('state') == 'unavailable':
                    raise control.ControlError('Runtime is unavailable')
                if instance and (instance.get('modelsUnconfirmed') is True or instance.get('models', {}).get('unconfirmed') is True):
                    raise control.ControlError('Model catalog is unconfirmed; explicitly refresh it before create')
                selections[role['key']] = control.selection(instances, role['instance'], role['modelId'], role['thinking'])
            except control.ControlError as error:
                failures.append(role['key'] + ': ' + str(error))
        if failures:
            raise control.ControlError('Preflight failed; no Bot was created:\n' + '\n'.join(failures))
        pending = set(team.get('pendingInitialization', []))
        unfinished = [r for r in team['roles'] if r['key'] in pending and r['botId'] in before]
        require_owned(before, team, unfinished, present=True, idle=True)
        settings_by_role = {r['key']: create_settings(r, team, selections[r['key']])
                            for r in team['roles'] if r['botId'] not in before}
        pending.update(settings_by_role)
        team['pendingInitialization'] = [k for k in ROLE_KEYS if k in pending]
        unconfirmed = set(team.get('pendingCreateReadback', [])) | set(settings_by_role)
        team['pendingCreateReadback'] = [k for k in ROLE_KEYS if k in unconfirmed]
        save_manifest(path, team)
        for role in team['roles']:
            if role['key'] not in pending:
                continue
            bid, key = role['botId'], role['key']
            current = {b['id']: b for b in fleet(client)}
            require_owned(current, team, [role], idle=True)
            if bid not in current:
                if key not in settings_by_role:
                    raise control.ControlError(key + ': disappeared after preflight; rerun create')
                client.call('POST', '/api/bots', {'id': bid, 'useDefaults': False, 'settings': settings_by_role[key],
                                               'modelSelection': selections[key], 'requireAvailableModel': True})
                created.add(bid)
            current = {b['id']: b for b in fleet(client)}
            require_owned(current, team, [role], present=True, idle=True)
            if key in unconfirmed:
                expected = create_settings(role, team)
                fields = ('soul', 'modelSelection', 'cwd', 'approvalMode', 'peers')
                missing = [field for field in fields if current[bid].get(field) != expected[field]]
                if missing:
                    raise control.ControlError(key + ': creation readback not confirmed for ' + ', '.join(missing) + '; inspect the native settings before retrying')
                unconfirmed.remove(key)
                team['pendingCreateReadback'] = [k for k in ROLE_KEYS if k in unconfirmed]
                save_manifest(path, team)
            if current[bid].get('memoryEnabled') is not False:
                client.call('PATCH', f'/api/bots/{bid}', {'memoryEnabled': False})
            confirmed = {b['id']: b for b in fleet(client)}
            require_owned(confirmed, team, [role], present=True)
            if confirmed[bid].get('memoryEnabled') is not False:
                raise control.ControlError(key + ': memory initialization not confirmed; rerun create with the same manifest')
            pending.remove(key)
            team['pendingInitialization'] = [k for k in ROLE_KEYS if k in pending]
            save_manifest(path, team)
    elif action in ('instructions', 'activate'):
        require_owned(before, team, selected, present=True, idle=True)
        for role in selected:
            # Recheck after prior API calls; never overwrite a newly busy role.
            current = {b['id']: b for b in fleet(client)}
            require_owned(current, team, selected, present=True, idle=True)
            patch = {'soul': texts[role['key']]}
            if action == 'activate':
                patch.update(name=role['name'], pinned=role['key'] in ('wf-manager', 'wf-assistant'))
            client.call('PATCH', f"/api/bots/{role['botId']}", patch)
    elif action != 'verify':
        raise control.ControlError('Unknown action')
    order = None
    if action == 'activate':
        current_rows = fleet(client)
        require_owned({b['id']: b for b in current_rows}, team, selected, present=True, idle=True)
        manager = next(r for r in team['roles'] if r['key'] == 'wf-manager')
        client.call('PATCH', f"/api/bots/{manager['botId']}", {'chiefOfStaff': True})
        ids = [r['botId'] for r in team['roles']]
        order = ids + [b['id'] for b in current_rows if b['id'] not in ids]
        client.call('PUT', '/api/bots/order', {'botIds': order})
    after_rows = fleet(client)
    expected = texts if action in ('instructions', 'verify', 'activate') else {r['key']: texts[r['key']] for r in team['roles'] if r['botId'] in created}
    result = verify_team(team, {b['id']: b for b in after_rows}, expected, created, active=action == 'activate')
    if order is not None and [b['id'] for b in after_rows] != order:
        result['errors'].append('Bot order readback differs; deployment was not marked active')
        result['ok'] = False
    if action == 'activate' and result['ok']:
        team['state'] = result['state'] = 'active'
        save_manifest(path, team)
    result['manifest'] = str(path)
    result['created_count'] = len(created)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'create', 'instructions', 'verify', 'activate'])
    parser.add_argument('--manifest', help='Private local manifest; overrides WORKFLOUR_TEAM_MANIFEST')
    parser.add_argument('--role', action='append', help='Limit an idle instructions update to explicit role keys')
    args = parser.parse_args(argv)
    result = provision(args.action, path=args.manifest, role_keys=args.role)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, control.ControlError) as error:
        raise SystemExit(str(error)) from None
