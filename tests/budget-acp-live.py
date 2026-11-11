#!/usr/bin/env python3
"""Opt-in real WorkBuddy billing probe. Never run via unittest discovery.

One small model request, no tools; records public answer and safe billing
metadata only. Does not artificially exhaust accounts or call paid API.
"""
import importlib.util
import json
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('smoke', root / 'tests/acp-smoke.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
p = s.AcpProcess('wf-assistant')
report = {'started_at': time.time(), 'role': 'wf-assistant', 'synthetic_quota': False}
sid = None
try:
    p.send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
        'protocolVersion': 1, 'clientCapabilities': {},
        'clientInfo': {'name': 'workflour-budget-validation', 'version': '1'}}})
    p.wait_for_id(1, 90)
    p.send({'jsonrpc': '2.0', 'id': 2, 'method': 'session/new', 'params': {
        'cwd': str(root / 'examples/omb-smoke'), 'mcpServers': []}})
    new = p.wait_for_id(2, 45)['result']
    sid = new['sessionId']
    report['session'] = sid
    report['menu_has_internal_provider'] = 'workflour-wb-' in json.dumps(new)
    print(json.dumps({'stage': 'handshake', 'session': sid}), flush=True)
    p.send({'jsonrpc': '2.0', 'id': 10, 'method': 'session/set_config_option', 'params': {
        'sessionId': sid, 'configId': 'reasoning_effort', 'value': 'low'}})
    selected = p.wait_for_id(10, 30)['result']
    report['confirmed_effort_setting'] = next(o.get('currentValue') for o in selected['configOptions'] if o['id'] == 'reasoning_effort')
    assert report['confirmed_effort_setting'] == 'low'
    p.send({'jsonrpc': '2.0', 'id': 3, 'method': 'session/prompt', 'params': {
        'sessionId': sid, 'prompt': [{'type': 'text', 'text':
        '这是一次模型通路验证。不要使用工具、不要读写文件、不要委派、不加载其他任务。只回复 BILLING-READY。'}]}})
    report['response'] = p.wait_for_id(3, 180)['result']
    events = [json.loads(l) for l in p.stdout_lines if l.strip().startswith('{')]
    updates = [x.get('params', {}).get('update', {}) for x in events if x.get('method') == 'session/update']
    report['public_answer'] = ''.join(x.get('content', {}).get('text', '') for x in updates
                                     if x.get('sessionUpdate') == 'agent_message_chunk')
    report['tool_calls'] = sum(x.get('sessionUpdate') == 'tool_call' for x in updates)
    report['protocol_error_count'] = len(s.validate_stdout(p))
    state_file = Path.home() / '.dsh/workflour-fallback' / (sid + '.json')
    state = json.loads(state_file.read_text())
    report['billing'] = {k: state.get(k) for k in ['primary', 'active', 'billing', 'confirmed_at', 'epoch', 'manual_route']}
    # Catalog enumeration after the internal adapter has actually registered.
    p.send({'jsonrpc': '2.0', 'id': 11, 'method': 'session/new', 'params': {
        'cwd': str(root / 'examples/omb-smoke'), 'mcpServers': []}})
    catalog = p.wait_for_id(11, 30)['result']
    report['menu_after_request_has_internal_provider'] = 'workflour-wb-' in json.dumps(catalog)
    p.send({'jsonrpc': '2.0', 'id': 12, 'method': 'session/close', 'params': {'sessionId': catalog['sessionId']}})
    p.wait_for_id(12, 10)
    report['ok'] = ('BILLING-READY' in report['public_answer'] and report['tool_calls'] == 0
                    and report['protocol_error_count'] == 0 and bool(state.get('confirmed_at'))
                    and state['active']['provider'].startswith('workflour-wb-')
                    and state['active']['reasoningEffort'] == 'low'
                    and not report['menu_after_request_has_internal_provider'])
except Exception as e:
    report['error_type'] = type(e).__name__
    # Exception responses can contain upstream values. Keep full details only
    # in the live process; evidence stores public stream and classification.
    report['ok'] = False
    report['public_answer'] = ''.join(json.loads(l).get('params', {}).get('update', {}).get('content', {}).get('text', '')
        for l in p.stdout_lines if l.strip().startswith('{') and json.loads(l).get('params', {}).get('update', {}).get('sessionUpdate') == 'agent_message_chunk')
finally:
    if sid and p.proc.poll() is None:
        p.send({'jsonrpc': '2.0', 'id': 4, 'method': 'session/close', 'params': {'sessionId': sid}})
        try: p.wait_for_id(4, 10)
        except Exception: pass
    p.close_stdin()
    p.terminate()
    report['finished_at'] = time.time()
    path = root / 'tests/evidence/workbuddy-quota-20261111/budget-acp-live.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)
raise SystemExit(0 if report.get('ok') else 1)
