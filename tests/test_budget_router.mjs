import test from 'node:test';
import assert from 'node:assert/strict';
import {createBudgetRouter} from '../integrations/openmausbot/model-fallback/budget-router.mjs';
const id='a'.repeat(24);
const globalId='b'.repeat(24);
function fixture({creditsUnknown=false,regions=['cn'],imageModelIds={cn:[],global:[]},modelRows,snapshotStorage={read:async()=>null,write:async()=>{}}}={}){
 let loads=0,created=0,disposed=0,closed=0,invalidated=0,modelFetches=0,now=Date.parse('2026-11-11T00:00:00Z'),version=1;
 const models=region=>modelRows?.[region]||[{id:'deepseek-v4.1-flash',creditMultiplier:0,contextWindow:1000*version,maxTokens:100,reasoning:{supportedEfforts:['low','high']}}];
 const bridge={listAccounts:async()=>({cn:regions.includes('cn')?[{accountId:id,available:true}]:[],global:regions.includes('global')?[{accountId:globalId,available:true}]:[]}),fetchModels:async region=>{modelFetches++;return {models:models(region)}},fetchCredits:async()=>{if(creditsUnknown)throw Error('unavailable');return {total:100,packages:[]}}};
 const metadataLoader=async()=>{loads++;await new Promise(r=>setTimeout(r,1));return {bridge,preferences:{pools:{cn:{orderAccountIds:[]},global:{orderAccountIds:[]}},enabledRegions:{cn:regions.includes('cn'),global:regions.includes('global')},imageModelIds},plugin:{modulePath:'unused'}}};
 const catalogs=[];
 const wb={WorkBuddyUpstreamClient:class{},WorkBuddyCredentialStore:class {constructor({region}){this.region=region}selectAccount(id){this.id=id} async resolve(){return {accountId:this.id,domain:this.region}}},workbuddyAccountId:c=>c.accountId,regionOf:c=>c,
 WorkBuddyCatalog:class{constructor(region){this.region=region;catalogs.push(this)}setRegionUsable(){}setRegionEnabled(){}set(rows){this.rows=rows}},
 deriveCatalog:r=>r,withEffectiveOff:r=>r,
 createWorkBuddyShim(){created++;return {ready:Promise.resolve(),close:async()=>{closed++}}},
 createWorkBuddyAdapter(){return {adapter:{},invalidate(){invalidated++}}}};
 const effects=[],ctx={effect:cb=>effects.push(cb()),llm:{registerAdapter:()=>()=>disposed++}};
 const r=createBudgetRouter(ctx,{metadataLoader,moduleLoader:async()=>wb,clock:()=>now,snapshotStorage});
 return {r,catalogs,effects,fetches:()=>modelFetches,next:()=>{version++;now+=400000},counts:()=>({loads,created,disposed,closed,invalidated})};
}
test('concurrent requests share initialization and one native adapter per account',async()=>{
 const f=fixture(),[a,b]=await Promise.all([f.r.candidates(),f.r.candidates()]);
 await Promise.all([f.r.ensure(a[0]),f.r.ensure(b[0])]);assert.deepEqual(f.counts(),{loads:1,created:1,disposed:0,closed:0,invalidated:0});
 await f.r.close();f.effects.forEach(fn=>fn());assert.equal(f.counts().closed,1);assert.equal(f.counts().disposed,1);
});
test('a refreshed upstream model changes the existing adapter catalog',async()=>{
 const f=fixture();let [a]=await f.r.candidates();await f.r.ensure(a);assert.equal(f.catalogs[0].rows[0].contextWindow,1000);
 f.next();[a]=await f.r.candidates();await f.r.ensure(a);assert.equal(f.catalogs[0].rows[0].contextWindow,2000);assert.equal(f.counts().invalidated,1);assert.equal(f.counts().created,1);await f.r.close();
});
test('quota unknown blocks API even though free route remains available',async()=>{
 const f=fixture({creditsUnknown:true});assert.equal((await f.r.candidates()).length,1);assert.equal(await f.r.apiAllowed(),false);await f.r.close();
});

test('runtime image capabilities follow exact saved regional IDs, not upstream guesses or sibling models',async()=>{
 const rows=['deepseek-v4.1-flash','deepseek-v4.1-flash-sg','glm-5.3-flash'].map(id=>({id,creditMultiplier:0,supportsImages:true,multimodal:true}));
 const f=fixture({regions:['cn','global'],modelRows:{cn:rows,global:rows},imageModelIds:{cn:['deepseek-v4.1-flash'],global:['glm-5.3-flash']}});
 const routes=await f.r.candidates();
 await f.r.ensure(routes.find(r=>r.region==='cn'));await f.r.ensure(routes.find(r=>r.region==='global'));
 const flags=region=>Object.fromEntries(f.catalogs.find(c=>c.region===region).rows.map(m=>[m.id,m.multimodal]));
 assert.deepEqual(flags('cn'),{'deepseek-v4.1-flash':true,'deepseek-v4.1-flash-sg':false,'glm-5.3-flash':false});
 assert.deepEqual(flags('global'),{'deepseek-v4.1-flash':false,'deepseek-v4.1-flash-sg':false,'glm-5.3-flash':true});
 await f.r.close();
});

test('empty image selection disables known multimodal models without changing route ordering',async()=>{
 const rows=['deepseek-v4.1-flash','deepseek-v4.1-flash-sg','glm-5.3-flash'].map(id=>({id,creditMultiplier:0,multimodal:true}));
 const common={regions:['cn','global'],modelRows:{cn:rows,global:rows}};
 const enabled=fixture({...common,imageModelIds:{cn:['deepseek-v4.1-flash'],global:['glm-5.3-flash']}}),disabled=fixture({...common,imageModelIds:{cn:[],global:[]}});
 const before=await enabled.r.candidates(),after=await disabled.r.candidates();assert.deepEqual(after,before);
 for(const region of ['cn','global'])await disabled.r.ensure(after.find(r=>r.region===region));
 assert.ok(disabled.catalogs.flatMap(c=>c.rows).every(m=>m.multimodal===false));
 await enabled.r.close();await disabled.r.close();
});

test('a new process cannot reuse a snapshot fingerprint from different saved image selections',async()=>{
 const saved=new Map(),storage={read:async path=>structuredClone(saved.get(path)||null),write:async(path,value)=>saved.set(path,structuredClone(value))};
 const first=fixture({imageModelIds:{cn:['deepseek-v4.1-flash'],global:[]},snapshotStorage:storage});
 await first.r.candidates();const oldFingerprint=(await first.r.refresh()).fingerprint;assert.equal(first.fetches(),1);await first.r.close();
 const unchanged=fixture({imageModelIds:{cn:['deepseek-v4.1-flash'],global:[]},snapshotStorage:storage});
 await unchanged.r.candidates();assert.equal(unchanged.fetches(),0);await unchanged.r.close();
 const changed=fixture({imageModelIds:{cn:[],global:[]},snapshotStorage:storage});
 const [route]=await changed.r.candidates();assert.equal(changed.fetches(),1);assert.notEqual((await changed.r.refresh()).fingerprint,oldFingerprint);
 await changed.r.ensure(route);assert.equal(changed.catalogs[0].rows[0].multimodal,false);await changed.r.close();
});
