#!/usr/bin/env python3
"""Start one draft with the actual native thread ID; never retry an uncertain send."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


team_tool = module('xhs_team', 'provision-xhs-team.py')
workflow = module('xhs_workflow', 'xhs-workflow.py')


def start(client, team, project, topic, image=False):
    project = Path(project).expanduser()
    if not project.is_absolute() or project.exists():
        raise ValueError('Use a new absolute project directory; an existing launch is never resent')
    if not topic.strip() or len(topic) > 300:
        raise ValueError('Topic must have 1–300 characters')
    role = next(r for r in team['roles'] if r['key'] == 'xhs-planner')
    bot = next(b for b in client.call('GET', '/api/bots?messages=0')['bots'] if b['id'] == role['botId'])
    if not team_tool.owned(bot, role):
        raise ValueError('Planner ownership does not match the local deployment')
    if bot.get('busy') or any(t.get('busy') for t in bot.get('tasks', [])):
        raise ValueError('Planner is busy; wait for the current task instead of starting another')
    project.mkdir(parents=True, exist_ok=False)
    (project / '.xhs').mkdir(mode=0o700)
    journal = project / '.xhs/launch.json'
    receipt = {'status': 'creating_task', 'bot_id': role['botId'], 'send_id': str(uuid.uuid4())}
    team_tool.control.write_journal(journal, receipt)
    try:
        task = client.call('POST', f"/api/bots/{role['botId']}/tasks", {'title': '小红书 · ' + topic[:60], 'select': True})
        thread = task['task']['threadId']
        if not isinstance(thread, str) or not thread:
            raise ValueError('Native API did not return a thread ID')
        receipt.update(status='initializing', thread_id=thread)
        team_tool.control.write_journal(journal, receipt)
        with workflow.locked(project) as state_path:
            state = workflow.initialize(project, topic, thread)
            state['image_policy'] = {'max_requests': 1 if image else 0, 'useG1Credits': False}
            state['delivery_contract'] = 'synchronous-v1'
            workflow.set_limits(project, state, 'all', 3, 2, 2)
            state['updated_at'] = workflow.now()
            workflow.write(state_path, state)
            workflow.handoff(project, state)
        images = ('允许至多1次Gemini原生生图，useG1Credits=false；失败保留原因并交模板。'
                  if image else '本次仅模板卡片，不调用AI生图，报告template_only。')
        prompt = (f'小红书图文新任务：{topic}\n项目已初始化：{project}\n'
                  f'本次真实OpenMausBot工作台threadId：{thread}；账本已绑定，不重新init，不用DSH_SESSION_ID。\n'
                  '先读项目AGENTS.md/HANDOFF.md及本角色技能，按已安装三角色流程原生派单和回传。'
                  '采集至多3条候选、精读2条、每条至多2评论，任务更小上限优先。'
                  'X/YouTube共用的请求限额已写入账本；若指定某平台更小上限，派单前用collection-limits补充对应source。'
                  '正文200–350字、一个标题、3标签、两张1080×1440卡片；保留原始来源URL，日期未知不猜。'
                  + images + '\n只交草稿，实际读图后到pending_user_review；不发布、不创建定时任务。')
        receipt['status'] = 'sending'
        team_tool.control.write_journal(journal, receipt)
        client.call('POST', f"/api/bots/{role['botId']}/messages",
                    {'text': prompt, 'threadId': thread, 'sendId': receipt['send_id']})
        receipt['status'] = 'sent'
    except Exception:
        receipt['status'] = 'delivery_unknown' if receipt['status'] == 'sending' else 'incomplete'
        team_tool.control.write_journal(journal, receipt)
        raise
    team_tool.control.write_journal(journal, receipt)
    return {'status': 'sent', 'project': str(project), 'thread_id': thread,
            'receipt': str(journal), 'published': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--topic', required=True)
    parser.add_argument('--image', action='store_true', help='Allow at most one native image request')
    args = parser.parse_args()
    os.umask(0o077)
    team = team_tool.manifest(team_tool.DEFAULT_MANIFEST)
    print(json.dumps(start(team_tool.control.Client(), team, args.project, args.topic, args.image), ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, StopIteration) as error:
        raise SystemExit('start-xhs: ' + str(error)) from None
