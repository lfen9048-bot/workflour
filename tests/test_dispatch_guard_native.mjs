/** Offline integration with the installed DSH registry, never MCP/model calls.
 * Mac: ELECTRON_RUN_AS_NODE=1 '<DSH app>/Contents/MacOS/DeepSeek Harness'
 *        --test tests/test_dispatch_guard_native.mjs
 * Other installs: DSH_TOOLS_ROOT=<.../node_modules/@deepseek-ai> node --test ...
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {join} from 'node:path';
import {install} from '../integrations/openmausbot/dispatch-guard/plugin.mjs';

const root = process.env.DSH_TOOLS_ROOT || '/Applications/DeepSeek Harness.app/Contents/Resources/app.asar/dsh/node_modules/@deepseek-ai';
const available = existsSync(join(root, 'dsh-tools/lib/index.js'));
let Context, ToolRuntime, defineContentToolFixture;
if (available) {
  ({Context} = await import(pathToFileURL(join(root, 'cordis/lib/index.js'))));
  ({ToolRuntime, defineContentToolFixture} = await import(pathToFileURL(join(root, 'dsh-tools/lib/index.js'))));
}

function fixture() {
  const ctx = new Context();
  ctx.provide('systemPrompt', {tools() {return () => {};}});
  new ToolRuntime(ctx);
  let state = 'prepared', bodies = 0, counter = 0;
  const journal = [];
  const native = defineContentToolFixture({name:'mcp__agents__coordinate_bots',description:'Offline memory-only transport',
    parameters:{message:{type:'string'}},execute:async()=>{bodies++;return [{type:'text',text:'offline receipt'}];}});
  ctx.tools.register(native);
  install(ctx, {
    binding: () => ({bot_id:'offline',thread_id:'offline'}),
    helper: async (action, payload) => {
      journal.push(action);
      if (action === 'finish') {state = 'sent';return {ok:true};}
      if (state !== 'prepared') throw Error('already started');
      if (payload.arguments.message !== 'WF-INTENT:offline prepared') throw Error('not prepared');
      if (action === 'begin') state = 'sending';
      return {ok:true,intent_id:'offline'};
    }
  });
  return {ctx,journal,get bodies(){return bodies;},get state(){return state;},
    run: (message='WF-INTENT:offline prepared') => ctx.tools.execute({callId:'offline-'+(++counter),
      name:native.name,arguments:{message},signal:new AbortController().signal})};
}

test('installed registry denies missing marker before native body', {skip:!available}, async()=>{
  const f=fixture();const result=await f.run('missing marker');
  assert.equal(result.isError,true);assert.equal(f.bodies,0);assert.equal(f.state,'prepared');
  assert.deepEqual(f.journal,['preflight']);
});
test('installed registry executes journaled dispatch only once', {skip:!available}, async()=>{
  const f=fixture();assert.equal((await f.run()).isError,false);
  assert.equal(f.bodies,1);assert.equal(f.state,'sent');
  assert.deepEqual(f.journal,['preflight','begin','finish']);
  assert.equal((await f.run()).isError,true);assert.equal(f.bodies,1);
});
test('installed registry preserves a native denial', {skip:!available}, async()=>{
  const f=fixture();f.ctx.on('tools/pre-execute',async()=>({kind:'deny',reason:'offline approval denied'}));
  assert.equal((await f.run()).isError,true);assert.equal(f.bodies,0);
  assert.deepEqual(f.journal,[]);assert.equal(f.state,'prepared');
});
