import test from 'node:test';
import assert from 'node:assert/strict';
import {install,stateFor,resetEpoch,failureKind,routeKey,BACKUPS} from '../integrations/openmausbot/model-fallback/plugin.mjs';
const selected={provider:'workbuddy',model:'kimi-k3.1-pro',reasoningEffort:'max'};
function fixture(){
 const handlers={},records=new Map(),notices=[];let stamp=Date.parse('2026-11-10T23:59:00Z');
 const ctx={on(name,fn){handlers[name]=fn},llm:{async resolveCallConfig(r){return {...r,reasoningEffort:'high'}}}};
 const plugin=install(ctx,{clock:()=>stamp,store:{read:id=>structuredClone(records.get(id)||null),write:(id,r)=>records.set(id,structuredClone(r))},notice:(id,text)=>notices.push(text)});
 const ac=new AbortController(),agent={session:{id:'one'}},p={agent,turn:1,signal:ac.signal};
 return {ctx,handlers,records,notices,ac,plugin,agent,p,setTime:t=>stamp=Date.parse(t),request:(opts={})=>handlers['agent/request']({...p,...opts},async()=>selected),error:(code,opts={})=>handlers['agent/request-error']({...p,failure:{code},...opts},async()=>undefined)};
}
test('quota walks only the authorized chain without inheriting incompatible effort',async()=>{
 const f=fixture();assert.deepEqual(await f.request(),selected);
 for(const candidate of BACKUPS){assert.deepEqual(await f.error('QUOTA'),{kind:'retry'});let r=await f.request();assert.equal(routeKey(r),routeKey(candidate));assert.equal(r.reasoningEffort,'high')}
 assert.equal(await f.error('QUOTA'),undefined);assert.match(f.notices.at(-1),/任务暂停/);
 assert.equal(f.notices.filter(x=>x.includes(' → ')).length,3);
});
test('default already in backup chain is never called twice',async()=>{
 const f=fixture();const initial=BACKUPS[1];
 await f.handlers['agent/request'](f.p,async()=>initial);
 await f.error('QUOTA');assert.equal(routeKey(await f.handlers['agent/request'](f.p,async()=>initial)),routeKey(BACKUPS[0]));
 await f.error('QUOTA');assert.equal(routeKey(await f.handlers['agent/request'](f.p,async()=>initial)),routeKey(BACKUPS[2]));
});
test('stop, transport, policy and busy are not quota',async()=>{
 for(const code of ['TRANSPORT','TIMEOUT','AUTH','RATE_LIMIT','CONTENT_FILTER','INVALID_REQUEST']){let f=fixture();await f.request();assert.equal(await f.error(code),undefined);assert.equal(routeKey(await f.request()),routeKey(selected));assert.equal(f.notices.some(x=>x.includes(' → ')),false)}
 let f=fixture();await f.request();f.ac.abort();assert.equal(await f.error('QUOTA'),undefined);assert.equal(f.notices.length,0);
 assert.equal(failureKind({code:'RATE_LIMIT',message:'quota'}),'rate-limit');
});
test('native transient retry decision is preserved',async()=>{
 const f=fixture();await f.request();assert.deepEqual(await f.handlers['agent/request-error']({...f.p,failure:{code:'TRANSPORT'}},async()=>({kind:'retry'})),{kind:'retry'});assert.equal(f.notices.length,0);
});
test('13:00 reset waits until next turn and survives process restart',async()=>{
 const f=fixture();await f.request();await f.error('QUOTA');f.setTime('2026-11-11T05:01:00Z');
 assert.equal(routeKey(await f.request()),routeKey(BACKUPS[0]));
 f.handlers['agent/turn-stopping'](f.p);
 const r=await f.request({turn:2});assert.equal(routeKey(r),routeKey(selected));assert.match(f.notices.at(-1),/13:00/);
 assert.equal(resetEpoch(Date.parse('2026-11-11T04:59:59Z')),'2026-11-10');
 const old={epoch:'2026-11-10',primary:selected,active:BACKUPS[0],tried:['old']};
 assert.deepEqual(stateFor(old,BACKUPS[0],'2026-11-11').active,selected);
});
test('manual different model wins, no forced daily restore to an older user choice',()=>{
 const old={epoch:'2026-11-10',primary:selected,active:BACKUPS[0],tried:['old']};
 const manual={provider:'custom',model:'chosen',reasoningEffort:'low'};
 assert.deepEqual(stateFor(old,manual,'2026-11-11').primary,manual);
});
test('explicitly choosing the active backup clears fallback and becomes the manual choice',async()=>{
 const f=fixture();await f.request();await f.error('QUOTA');f.handlers['agent/turn-stopping'](f.p);
 const handlers={},notices=[];
 install({on:(n,fn)=>handlers[n]=fn,llm:f.ctx.llm},{store:{read:id=>structuredClone(f.records.get(id)),write:(id,r)=>f.records.set(id,structuredClone(r))},clock:()=>Date.parse('2026-11-10T23:59:00Z'),controlRevision:()=> 'explicit-choice',notice:(id,t)=>notices.push(t)});
 const manual={...BACKUPS[0],reasoningEffort:'low'};
 assert.deepEqual(await handlers['agent/request']({...f.p,turn:2},async()=>manual),manual);
 assert.deepEqual(await handlers['agent/request']({...f.p,turn:3},async()=>manual),manual);
 assert.equal(notices.length,0);
});
test('missing backup fails visibly and never counts as successful call',async()=>{
 const f=fixture();f.ctx.llm.resolveCallConfig=async()=>{throw Error('missing')};await f.request();assert.equal(await f.error('QUOTA'),undefined);assert.equal(f.notices.length,4);assert.match(f.notices[0],/无法加载/);
});
test('cancellation while checking a candidate cannot switch or retry',async()=>{
 const f=fixture();await f.request();f.ctx.llm.resolveCallConfig=async r=>{f.ac.abort();return r};assert.equal(await f.error('QUOTA'),undefined);assert.equal(f.notices.length,0);
});
test('success notice requires a real assistant message from the selected backup',async()=>{
 const f=fixture();await f.request();await f.error('QUOTA');
 f.agent.session.snapshotEvents=()=>[{type:'assistant/message',data:{turn:1,message:{source:BACKUPS[0]}}}];
 f.handlers['agent/turn-stopping'](f.p);assert.match(f.notices.at(-1),/已实际返回回复/);
 const g=fixture();await g.request();await g.error('QUOTA');g.handlers['agent/turn-stopping'](g.p);
 assert.equal(g.notices.some(n=>n.includes('已实际返回回复')),false);
});
