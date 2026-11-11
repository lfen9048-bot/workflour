#!/usr/bin/env python3
"""Synthetic WorkBuddy quota, real existing DeepSeek API request (small billable probe)."""
import importlib.util,json,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('smoke',root/'tests/acp-smoke.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s);s.LAUNCHER=root/'tests/fixtures/fallback/launch.sh'
p=s.AcpProcess('coordinator');report={'synthetic_quota':True,'workbuddy_upstream_calls':0};sid=None
try:
 p.send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':1,'clientCapabilities':{},'clientInfo':{'name':'workflour-fallback-validation','version':'1'}}});p.wait_for_id(1,60)
 p.send({'jsonrpc':'2.0','id':2,'method':'session/new','params':{'cwd':str(root/'examples/omb-smoke'),'mcpServers':[]}});x=p.wait_for_id(2,40);sid=x['result']['sessionId'];report['session']=sid
 p.send({'jsonrpc':'2.0','id':3,'method':'session/prompt','params':{'sessionId':sid,'prompt':[{'type':'text','text':'这是模型通路验证。不要使用工具、不要读写文件、不要委派。只回复 FALLBACK-READY。'}]}});report['response']=p.wait_for_id(3,180)['result']
 report['updates']=[json.loads(l)['params']['update'] for l in p.stdout_lines if l.startswith('{') and json.loads(l).get('method')=='session/update' and json.loads(l).get('params',{}).get('update',{}).get('sessionUpdate')=='agent_message_chunk']
 report['protocol_errors']=s.validate_stdout(p)
 report['tool_call_count']=sum(1 for l in p.stdout_lines if l.startswith('{') and json.loads(l).get('params',{}).get('update',{}).get('sessionUpdate')=='tool_call')
except Exception as e:report['error']=str(e)[:1000]
finally:
 if sid:
  p.send({'jsonrpc':'2.0','id':4,'method':'session/close','params':{'sessionId':sid}})
  try:p.wait_for_id(4,10)
  except:pass
 p.close_stdin();p.terminate()
 path=root/'tests/evidence/manager-naiwa-20261110/fallback-live.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False)[:6000])
