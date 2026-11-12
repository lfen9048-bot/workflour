import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {createTaskCapabilities} from '../integrations/openmausbot/model-fallback/task-capabilities.mjs';
import {install} from '../integrations/openmausbot/model-fallback/plugin.mjs';
import {createBudgetRouter} from '../integrations/openmausbot/model-fallback/budget-router.mjs';
const sha=value=>createHash('sha256').update(value).digest('hex');
function imageProbe(){return {schema_version:1,status:'passed',passed:true,exact_match:true,nonce_in_prompt:false,
  public_answer:'00674539',model_answer:'00674539',expected_sha256:sha('00674539'),image_sha256:sha('image bytes'),
  stop_reason:'end_turn',protocol_error_count:0,actual_tool_scope:'one_read_image',image_tool_completed:true,
  workbuddy_version:'5.13.1',started_at:'2026-11-12T00:00:00Z',finished_at:'2026-11-12T00:00:01Z',
  fallback:{active:{provider:'workbuddy-global',model:'deepseek-v4.1-flash-sg'},confirmed_at:'2026-11-12T00:00:00.500Z'},
  billing:{nativeProvider:'workbuddy-global',model:'deepseek-v4.1-flash-sg'},
  tools:[{event:'tool_call',id:'read-one',title:'read_image',paths:['/isolated/input.png'],status:'in_progress'},
         {event:'tool_call_update',id:'read-one',status:'completed'}]};}

test('native identity lookup does not inspect prompt and fails on corrupt binding',async t=>{
 const dir=await mkdtemp(join(tmpdir(),'wf-capabilities-'));t.after(()=>rm(dir,{recursive:true,force:true}));
 let observed;
 const capability=createTaskCapabilities({bindingHome:dir,requirementsRunner:async b=>{observed=b;return {required_capabilities:['image'],intents:['intent-one']}}});
 assert.deepEqual((await capability.requirements('no-binding')).required_capabilities,[]);
 await writeFile(join(dir,'one.json'),JSON.stringify({schema_version:1,session_id:'one',bot_id:'b',thread_id:'t'}));
 assert.deepEqual(await capability.requirements('one'),{required_capabilities:['image'],intents:['intent-one']});
 assert.equal(observed.thread_id,'t');
 await writeFile(join(dir,'one.json'),'corrupt');
 await assert.rejects(()=>capability.requirements('one'),/unreadable/);
 const strict=createTaskCapabilities({bindingHome:dir,requireBinding:true});
 await assert.rejects(()=>strict.requirements('missing'),/unreadable/);
 await writeFile(join(dir,'isolated.json'),JSON.stringify({schema_version:1,session_id:'isolated',scope:'non_omb'}));
 assert.deepEqual(await strict.requirements('isolated'),{required_capabilities:[],intents:[]});
});

test('image proof requires exact provider/model/plugin version and unchanged evidence',async t=>{
 const dir=await mkdtemp(join(tmpdir(),'wf-image-proof-'));t.after(()=>rm(dir,{recursive:true,force:true}));
 const proof=join(dir,'proof.json'),registryPath=join(dir,'registry.json');
 const bytes=JSON.stringify(imageProbe());await writeFile(proof,bytes);
 const record={provider:'workbuddy-global',model:'deepseek-v4.1-flash-sg',capability:'image',status:'passed',checked_at:'2026-11-12T00:01:00Z',workbuddy_version:'5.13.1',evidence_path:proof,evidence_sha256:sha(bytes)};
 await writeFile(registryPath,JSON.stringify({schema_version:1,records:[record]}));
 const capability=createTaskCapabilities({registryPath,clock:()=>Date.parse('2026-11-12T01:00:00Z')});
 assert.equal(await capability.confirmedImage(record,'5.13.1'),true);
 assert.equal(await capability.confirmedImage({...record,provider:'workbuddy'},'5.13.1'),false);
 assert.equal(await capability.confirmedImage(record,'5.13.2'),false);
 assert.equal(await capability.confirmedImage({...record,model:'deepseek-v4.1-flash'},'5.13.1'),false);
 await writeFile(proof,bytes+'changed');assert.equal(await capability.confirmedImage(record,'5.13.1'),false);
});

test('a passed registry row cannot override failed, wrong-route or incomplete image evidence',async t=>{
 const dir=await mkdtemp(join(tmpdir(),'wf-image-proof-invalid-'));t.after(()=>rm(dir,{recursive:true,force:true}));
 const proof=join(dir,'proof.json'),registryPath=join(dir,'registry.json');
 const row={provider:'workbuddy-global',model:'deepseek-v4.1-flash-sg',capability:'image',status:'passed',checked_at:'2026-11-12T00:01:00Z',workbuddy_version:'5.13.1',evidence_path:proof};
 const caps=createTaskCapabilities({registryPath,clock:()=>Date.parse('2026-11-12T01:00:00Z')});
 for(const change of [p=>({actual_image_read:true}),p=>({...p,status:'failed',passed:false}),p=>({...p,nonce_in_prompt:true}),
   p=>({...p,expected_sha256:sha('wrong')}),p=>({...p,tools:[p.tools[0]]}),p=>({...p,tools:[...p.tools,{event:'tool_call',id:'extra',title:'read'}]}),
   p=>({...p,stop_reason:'cancelled'}),p=>({...p,fallback:{...p.fallback,active:{provider:'workbuddy',model:p.fallback.active.model}}}),
   p=>({...p,workbuddy_version:'old'}),p=>({...p,protocol_error_count:1})]){
   const bytes=JSON.stringify(change(imageProbe()));await writeFile(proof,bytes);
   await writeFile(registryPath,JSON.stringify({schema_version:1,records:[{...row,evidence_sha256:sha(bytes)}]}));
   assert.equal(await caps.confirmedImage(row,'5.13.1'),false);
 }
});

test('adjudication must preserve and revalidate the original failed exact-match report',async t=>{
 const dir=await mkdtemp(join(tmpdir(),'wf-image-adjudication-'));t.after(()=>rm(dir,{recursive:true,force:true}));
 const sourcePath=join(dir,'original.json'),proof=join(dir,'adjudication.json'),registryPath=join(dir,'registry.json');
 const original={...imageProbe(),status:'failed',passed:false,exact_match:false,public_answer:'【系统·模型状态】route notice\n00674539'};
 const source=JSON.stringify(original);await writeFile(sourcePath,source);
 const row={provider:'workbuddy-global',model:'deepseek-v4.1-flash-sg',capability:'image',status:'passed',checked_at:'2026-11-12T00:01:00Z',workbuddy_version:'5.13.1',evidence_path:proof};
 const adjudication={schema_version:1,status:'passed',provider:row.provider,model:row.model,workbuddy_version:row.workbuddy_version,
   source_evidence:sourcePath,source_sha256:sha(source),image_sha256:original.image_sha256,expected_sha256:original.expected_sha256,
   model_answer:'00674539',image_tool_completed:true,actual_reply_confirmed_at:original.fallback.confirmed_at};
 const bytes=JSON.stringify(adjudication);await writeFile(proof,bytes);
 await writeFile(registryPath,JSON.stringify({schema_version:1,records:[{...row,evidence_sha256:sha(bytes)}]}));
 const caps=createTaskCapabilities({registryPath,clock:()=>Date.parse('2026-11-12T01:00:00Z')});
 assert.equal(await caps.confirmedImage(row,'5.13.1'),true);
 await writeFile(sourcePath,source+' ');assert.equal(await caps.confirmedImage(row,'5.13.1'),false);
});

const cn={provider:'workflour-wb-cn-a',nativeProvider:'workbuddy',region:'cn',accountId:'a',model:'deepseek-v4.1-flash',tier:'regular'};
const global={provider:'workflour-wb-global-b',nativeProvider:'workbuddy-global',region:'global',accountId:'b',model:'deepseek-v4.1-flash-sg',tier:'free'};
function fixture({image=true,verified=[cn.provider],lookupError=false}={}){
 const records=new Map(),handlers={},notices=[],ensured=[];let rev=null,apiChecks=0;
 const ctx={on:(n,f)=>handlers[n]=f,llm:{resolveCallConfig:async r=>r}};
 const caps={requirements:async()=>{if(lookupError)throw Error('bad binding');return {required_capabilities:image?['image']:[],intents:['i']}},confirmedImage:async r=>verified.includes(r.provider)};
 const budget={candidates:async()=>[global,cn,{...cn,provider:'workflour-wb-cn-c',model:'glm-5.3-flash'}],ensure:async r=>ensured.push(r.provider),describe:r=>r.provider,imageDeclared:async r=>({provider:r.nativeProvider||r.provider,workbuddyVersion:'5.13.1'}),apiAllowed:async()=>{apiChecks++;return true}};
 install(ctx,{store:{read:id=>structuredClone(records.get(id)||null),write:(id,v)=>records.set(id,structuredClone(v))},controlRevision:()=>rev,capabilities:caps,budget,notice:(id,s)=>notices.push(s)});
 const p={agent:{session:{id:'s'}},turn:1,signal:new AbortController().signal};
 const native={provider:'workbuddy',model:'deepseek-v4.1-flash',reasoningEffort:'high'};
 return {records,notices,ensured,p,handlers,native,revision:v=>rev=v,apiChecks:()=>apiChecks,request:(value=native,turn=1)=>handlers['agent/request']({...p,turn},async()=>value),error:()=>handlers['agent/request-error']({...p,failure:{code:'QUOTA'}},async()=>{})};
}
test('image requirement filters incapable cheap route before preserving original cost ordering',async()=>{
 const f=fixture();assert.equal((await f.request()).provider,cn.provider);assert.deepEqual(f.ensured,[cn.provider,cn.provider]);
 const g=fixture({verified:[global.provider,cn.provider]});assert.equal((await g.request()).provider,global.provider);
 const text=fixture({image:false,verified:[]});assert.equal((await text.request()).provider,global.provider);
});
test('unknown image capability never changes model family or purchases API fallback',async()=>{
 const f=fixture({verified:[]});await assert.rejects(()=>f.request(),/image capability/);assert.equal(f.ensured.length,0);assert.equal(f.apiChecks(),0);
 const g=fixture();await g.request();await assert.rejects(()=>g.error(),/image capability/);assert.equal(g.apiChecks(),0);assert.equal(g.ensured.includes('deepseek-official'),false);
});
test('manual model selection is not replaced to satisfy image requirements',async()=>{
 const f=fixture({verified:[cn.provider]});await f.request();
 f.revision('manual-change');
 await assert.rejects(()=>f.request({provider:'workbuddy-global',model:'deepseek-v4.1-flash-sg'},2),/image capability/);
 assert.equal(f.records.get('s').primary.provider,'workbuddy-global');
 assert.equal(f.ensured.includes(global.provider),false);
});
test('binding lookup failure blocks before attempting any model route',async()=>{
 const f=fixture({lookupError:true});await assert.rejects(()=>f.request(),/capability lookup/);assert.deepEqual(f.ensured,[]);
});

test('image declaration requires exact live checkbox, catalog account and plugin version',async()=>{
 const id='a'.repeat(24),model='deepseek-v4.1-flash';
 const prefs={pluginVersion:'5.13.1',imageModelIds:{cn:[model]},enabledRegions:{cn:true,global:false},pools:{cn:{orderAccountIds:[]}}};
 let live=structuredClone(prefs);
 const bridge={listAccounts:async()=>({cn:[{accountId:id,available:true}],global:[]}),fetchModels:async()=>({models:[{id:model,creditMultiplier:0}]}),fetchCredits:async()=>({total:1,packages:[]})};
 const r=createBudgetRouter({}, {metadataLoader:async()=>({preferences:prefs,plugin:{version:'5.13.1'},bridge}),imagePreferencesLoader:async()=>live,snapshotStorage:{read:async()=>null,write:async()=>{}}});
 const route={provider:'workflour-wb-cn-'+id,region:'cn',accountId:id,model};
 assert.deepEqual(await r.imageDeclared(route),{workbuddyVersion:'5.13.1',provider:'workbuddy'});
 assert.equal(await r.imageDeclared({...route,accountId:'b'.repeat(24)}),null);
 live.imageModelIds.cn=[];assert.equal(await r.imageDeclared(route),null);
 live=structuredClone(prefs);live.pluginVersion='5.13.2';assert.equal(await r.imageDeclared(route),null);
 assert.equal(await r.imageDeclared({...route,model:model+'-sg'}),null);
});
