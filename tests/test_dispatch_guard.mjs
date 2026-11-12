import test from 'node:test';
import assert from 'node:assert/strict';
import {install, dispatchArguments} from '../integrations/openmausbot/dispatch-guard/plugin.mjs';

function fixture() {
  const handlers = {}, calls = [];
  let state = 'prepared', receipt = true;
  const args = {bot_ids: ['worker'], message: 'WF-INTENT:known', thread: 'new'};
  const owner = {bot_id: 'lead', thread_id: 'thread'};
  install({on: (name, fn) => handlers[name] = fn}, {
    binding: id => { if (id !== 'session') throw Error('unbound'); return owner; },
    helper: async (action, payload) => {
      calls.push(action);
      if (action === 'preflight' || action === 'begin') {
        if (state !== 'prepared') throw Error('already sent');
        if (JSON.stringify(payload.arguments) !== JSON.stringify(args)) throw Error('mismatched payload');
        if (action === 'begin') state = 'sending';
        return {ok: true, intent_id: 'known'};
      }
      if (!receipt) { state = 'uncertain'; throw Error('uncertain'); }
      state = 'sent'; return {ok: true};
    }
  });
  const exec = {name: 'mcp__agents__coordinate_bots', arguments: args, agent: {session: {id: 'session'}}};
  let native = 0;
  async function run(entry = exec, gate = {kind: 'allow'}, body = async () => ({content: []})) {
    const decision = await handlers['tools/pre-execute'](entry, async () => gate);
    if (decision.kind !== 'allow') return decision;
    return handlers['tools/execute'](entry, async () => { native++; return body(); });
  }
  return {args, exec, handlers, run, calls, get native() {return native;}, get state() {return state;}, missingReceipt() {receipt=false;}};
}

test('exact prepared dispatch calls native once and journals real completion', async () => {
  const f=fixture(); await f.run();
  assert.equal(f.native,1); assert.equal(f.state,'sent'); assert.deepEqual(f.calls,['preflight','begin','finish']);
  const again=await f.run(); assert.equal(again.kind,'deny'); assert.equal(f.native,1);
});
test('missing marker and changed payload never call native', async () => {
  const f=fixture(); const result=await f.run({...f.exec,arguments:{...f.args,message:'no intent'}});
  assert.equal(result.kind,'deny'); assert.equal(f.native,0);
});
test('native approval rejection remains rejected without journal mutation', async () => {
  const f=fixture(); assert.equal((await f.run(f.exec,{kind:'deny',reason:'approval denied'})).kind,'deny');
  assert.equal(f.native,0); assert.deepEqual(f.calls,[]); assert.equal(f.state,'prepared');
});
test('uncertain result is not retried and still blocks after later call', async () => {
  const f=fixture(); f.missingReceipt(); await assert.rejects(f.run(),/uncertain/);
  assert.equal(f.native,1); assert.equal(f.state,'uncertain'); assert.equal((await f.run()).kind,'deny');
  assert.equal(f.native,1);
});
test('native thrown error still runs receipt reconciliation', async () => {
  const f=fixture(); await assert.rejects(f.run(f.exec,{kind:'allow'},async()=>{throw Error('transport')}),/transport/);
  assert.equal(f.native,1); assert.equal(f.state,'sent'); assert.equal(f.calls.at(-1),'finish');
});
test('binding absence rejects before native execution', async () => {
  const f=fixture(); const result=await f.run({...f.exec,agent:{session:{id:'other'}}});
  assert.equal(result.kind,'deny'); assert.equal(f.native,0);
});
test('tool directory wrappers do not bypass preflight', async () => {
  for (const wrapper of ['use_tool','call_tool']) {
    const f=fixture(); const exec={...f.exec,name:'mcp__agents__'+wrapper,arguments:{name:'coordinate_bots',arguments:{...f.args,message:'bad'}}};
    assert.equal((await f.run(exec)).kind,'deny'); assert.equal(f.native,0);
  }
});
test('native consultation and unrelated tools remain available', async () => {
  const f=fixture(); await f.run({...f.exec,arguments:{bot_ids:['worker'],message:'question',consult:true}});
  assert.equal(f.native,1); assert.deepEqual(f.calls,[]);
  assert.equal(dispatchArguments({name:'mcp__agents__list_bots',arguments:{}}),null);
});
test('notify and answers cannot bypass formal work validation', async () => {
  for (const flags of [{reply:'none'},{answers:' '},{answers:'claimed-question-id'},
    {consult:true,reply:'none'},{consult:true,answers:' '}]) {
    const f=fixture();const result=await f.run({...f.exec,arguments:{bot_ids:['worker'],message:'unprepared work',...flags}});
    assert.equal(result.kind,'deny');assert.equal(f.native,0);assert.deepEqual(f.calls,['preflight']);
  }
});
test('adding consult to a prepared work brief does not bypass exact validation', async () => {
  const f=fixture();const result=await f.run({...f.exec,arguments:{...f.args,consult:true}});
  assert.equal(result.kind,'deny');assert.equal(f.native,0);
});
test('concurrent tool bodies cannot both enter after successful preflight', async () => {
  const f=fixture(); const gate=async()=>({kind:'allow'});
  await Promise.all([f.handlers['tools/pre-execute'](f.exec,gate),f.handlers['tools/pre-execute'](f.exec,gate)]);
  let calls=0; const results=await Promise.allSettled([1,2].map(()=>f.handlers['tools/execute'](f.exec,async()=>{calls++;return {content:[]};})));
  assert.equal(calls,1); assert.equal(results.filter(r=>r.status==='rejected').length,1);
});
