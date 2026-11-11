import test from 'node:test';
import assert from 'node:assert/strict';
import {createBudgetRouter} from '../integrations/openmausbot/model-fallback/budget-router.mjs';
const id='a'.repeat(24);
function fixture({creditsUnknown=false}={}){
 let loads=0,created=0,disposed=0,closed=0,invalidated=0,now=Date.now(),version=1;
 const models=()=>[{id:'deepseek-v4.1-flash',creditMultiplier:0,contextWindow:1000*version,maxTokens:100,reasoning:{supportedEfforts:['low','high']}}];
 const bridge={listAccounts:async()=>({cn:[{accountId:id,available:true}],global:[]}),fetchModels:async()=>({models:models()}),fetchCredits:async()=>{if(creditsUnknown)throw Error('unavailable');return {total:100,packages:[]}}};
 const metadataLoader=async()=>{loads++;await new Promise(r=>setTimeout(r,1));return {bridge,preferences:{pools:{cn:{orderAccountIds:[]}},enabledRegions:{cn:true,global:false}},plugin:{modulePath:'unused'}}};
 const catalogs=[];
 const wb={WorkBuddyUpstreamClient:class{},WorkBuddyCredentialStore:class {selectAccount(){} async resolve(){return {accountId:id,domain:'cn'}}},workbuddyAccountId:c=>c.accountId,regionOf:c=>c,
 WorkBuddyCatalog:class{constructor(){catalogs.push(this)}setRegionUsable(){}setRegionEnabled(){}set(rows){this.rows=rows}},
 deriveCatalog:r=>r,withEffectiveOff:r=>r,imageDefaultFor:()=>false,
 createWorkBuddyShim(){created++;return {ready:Promise.resolve(),close:async()=>{closed++}}},
 createWorkBuddyAdapter(){return {adapter:{},invalidate(){invalidated++}}}};
 const effects=[],ctx={effect:cb=>effects.push(cb()),llm:{registerAdapter:()=>()=>disposed++}};
 const r=createBudgetRouter(ctx,{metadataLoader,moduleLoader:async()=>wb,clock:()=>now,snapshotStorage:{read:async()=>null,write:async()=>{}}});
 return {r,catalogs,effects,next:()=>{version++;now+=400000},counts:()=>({loads,created,disposed,closed,invalidated})};
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
