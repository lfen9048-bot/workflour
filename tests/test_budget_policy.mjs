import test from 'node:test';
import assert from 'node:assert/strict';
import {effectivePrice,promoActive,orderedCandidates,SNAPSHOT_TTL,SOON_MS,rankAccounts,providerFor} from '../integrations/openmausbot/model-fallback/budget-policy.mjs';
import {install,routeKey} from '../integrations/openmausbot/model-fallback/plugin.mjs';
const now=Date.parse('2026-11-11T10:00:00Z'),id=n=>String(n).padStart(24,'0');
const model=(name,price)=>({id:name,creditMultiplier:price,contextWindow:100000,maxTokens:8000,reasoning:{supportedEfforts:['low','high','max'],defaultEffort:'high'}});
const acct=(n,models,expires,remain=100)=>({accountId:id(n),available:true,models,credits:{total:remain,packages:[{remain,expiresAtMs:expires}]}});
function snap(){return {fetchedAtMs:now,pools:{cn:{orderAccountIds:[]},global:{orderAccountIds:[]}},accounts:{
 cn:[acct(1,[model('deepseek-v4.1-flash',.11),model('glm-5.3-flash',.08)],now+86400000),acct(2,[model('deepseek-v4.1-flash',.11)],now+10*86400000)],
 global:[acct(3,[model('deepseek-v4.1-flash',0),model('deepseek-v4.1-flash-sg',.11)],now+3600000)]}}}
test('verified free precedes both regions expiry, then CN ordinary credit',()=>{
 const rows=orderedCandidates(snap(),now);assert.deepEqual(rows.map(r=>[r.region,r.model,r.tier]),[
 ['global','deepseek-v4.1-flash','free'],['global','deepseek-v4.1-flash-sg','expiring'],
 ['cn','deepseek-v4.1-flash','expiring'],['cn','glm-5.3-flash','expiring'],['cn','deepseek-v4.1-flash','regular']]);
});
test('CN expiring first when it expires before international; balances do not override expiry',()=>{
 const s=snap();s.accounts.cn[0].credits.packages[0].expiresAtMs=now+1000;
 assert.equal(orderedCandidates(s,now).filter(r=>r.tier==='expiring')[0].region,'cn');
});
test('native within-region manual order is kept; it never puts ordinary before expiring',()=>{
 const s=snap();s.accounts.cn.push(acct(4,[model('deepseek-v4.1-flash',.11)],now+2*86400000));
 s.pools.cn.orderAccountIds=[id(2),id(4),id(1)];
 const rows=orderedCandidates(s,now).filter(r=>r.region==='cn'&&r.model==='deepseek-v4.1-flash');
 assert.deepEqual(rows.map(r=>r.accountId),[id(4),id(1),id(2)]);
});
test('expired zero promotion, missing rates and stale snapshots cannot count as free',()=>{
 const m={...model('deepseek-v4.1-flash',0),promos:[{discount:{multiplier:0,displayMode:'replace'},schedule:{validUntil:now-1}}]};
 assert.equal(effectivePrice(m,now),null);assert.equal(effectivePrice({id:'x'},now),null);
 assert.throws(()=>orderedCandidates({...snap(),fetchedAtMs:now-SNAPSHOT_TTL-1},now),/过期/);
});
test('promotion daily windows support midnight and reject invalid schedules',()=>{
 const p={schedule:{timezone:'Asia/Shanghai',daily:[{start:'17:00',end:'09:00'}]}};
 assert.equal(promoActive(p,now),true);p.schedule.daily[0].start='25:01';assert.equal(promoActive(p,now),false);
 assert.equal(promoActive({schedule:{dailyUnusable:true}},now),false);
});
test('already expired packages are never ranked as expiring; exactly 3 days is included',()=>{
 const s=snap();s.accounts.cn[0].credits.packages=[{remain:100,expiresAtMs:now-1},{remain:1,expiresAtMs:now+SOON_MS}];
 const r=orderedCandidates(s,now).find(r=>r.region==='cn');assert.equal(r.expiringAmount,1);assert.equal(r.expiresAtMs,now+SOON_MS);
});
test('unknown credit cannot justify a paid route, but a verified free route is usable',()=>{
 const s=snap();delete s.accounts.global[0].credits;
 const r=orderedCandidates(s,now).filter(r=>r.region==='global');assert.equal(r.length,1);assert.equal(r[0].tier,'free');
});
test('account exclusion and membership are respected, distinct accounts never deduplicate',()=>{
 const s=snap();s.accounts.cn[0].probe={outcome:'rate-limited',retryAtMs:now+5000};
 const rows=orderedCandidates(s,now);assert.ok(!rows.some(r=>r.accountId===id(1)));
 assert.notEqual(providerFor('cn',id(1)),providerFor('cn',id(2)));
 assert.deepEqual(rankAccounts([{accountId:id(1),probe:{outcome:'account-restricted'}}],[],now),[]);
});
function runtime(){
 const handlers={},records=new Map(),notices=[];let revision=null,failReason;
 const ctx={on:(k,v)=>handlers[k]=v,llm:{resolveCallConfig:async r=>({...r,reasoningEffort:r.reasoningEffort||'high'})}};
 const rows=orderedCandidates(snap(),now);
 const budget={candidates:async()=>rows,ensure:async()=>{},apiAllowed:async()=>true,describe:r=>r.region||r.provider,reason:()=>failReason};
 install(ctx,{budget,clock:()=>now,controlRevision:()=>revision,store:{read:k=>structuredClone(records.get(k)||null),write:(k,v)=>records.set(k,structuredClone(v))},notice:(_,t)=>notices.push(t)});
 const controller=new AbortController(),agent={session:{id:'cost-test'}},payload={agent,turn:1,signal:controller.signal};
 const selected={provider:'workbuddy',model:'deepseek-v4.1-flash',reasoningEffort:'low'};
 return {handlers,records,notices,budget,rows,payload,controller,selected,revision:v=>revision=v,failReason:v=>failReason=v,
 request:async(p={})=>handlers['agent/request']({...payload,...p},async()=>selected),
 error:async code=>handlers['agent/request-error']({...payload,failure:{code}},async()=>undefined)};
}
test('default DS uses verified free account and keeps low effort',async()=>{
 const f=runtime(),r=await f.request();assert.equal(routeKey(r),routeKey(f.rows[0]));assert.equal(r.reasoningEffort,'low');assert.ok(f.notices[0].includes('尚未确认'));
});
test('initial DS cost routing fails closed when only GLM is eligible',async()=>{
 const f=runtime();f.budget.candidates=async()=>f.rows.filter(r=>r.model==='glm-5.3-flash');
 let registrations=0;f.budget.ensure=async()=>{registrations++};
 await assert.rejects(f.request(),/No verified WorkBuddy billing route/);
 assert.equal(registrations,0);assert.equal(f.records.get('cost-test').active.model,f.selected.model);
});
test('promotion expiration cannot silently switch DS to GLM within the turn',async()=>{
 const f=runtime();await f.request();
 f.budget.valid=async()=>false;f.budget.candidates=async()=>f.rows.filter(r=>r.model==='glm-5.3-flash');
 let registrations=0;f.budget.ensure=async()=>{registrations++};
 await assert.rejects(f.request(),/No verified WorkBuddy billing route/);
 assert.equal(registrations,0);assert.equal(f.records.get('cost-test').active.model,f.selected.model);
});
test('quota visits international expiry, CN expiry, ordinary credits, then API exactly once',async()=>{
 const f=runtime();await f.request();
 for(const row of f.rows.slice(1)){assert.deepEqual(await f.error('QUOTA'),{kind:'retry'});assert.equal(routeKey(await f.request()),routeKey(row))}
 assert.deepEqual(await f.error('QUOTA'),{kind:'retry'});assert.equal((await f.request()).provider,'deepseek-official');
 assert.equal(await f.error('QUOTA'),undefined);
});
test('connection failure is not quota and cannot fall through to paid API',async()=>{
 const f=runtime();await f.request();assert.equal(await f.error('TRANSPORT'),undefined);assert.equal(routeKey(await f.request()),routeKey(f.rows[0]));
});
test('unknown account metadata blocks API fallback',async()=>{
 const f=runtime();f.budget.apiAllowed=async()=>false;await f.request();
 for(let i=1;i<f.rows.length;i++)await f.error('QUOTA');assert.equal(await f.error('QUOTA'),undefined);
 assert.notEqual((await f.request()).provider,'deepseek-official');
});
test('new explicit selection wins after a prior round; no false disable from initial revision',async()=>{
 const f=runtime();f.revision('initial');await f.request();assert.equal(f.records.get('cost-test').active.provider,f.rows[0].provider);
 f.handlers['agent/turn-stopping'](f.payload);f.revision('manual-new');
 assert.deepEqual(await f.request({turn:2}),f.selected);
});
test('changing only thinking retains equivalent DS cost routing and the actual new effort',async()=>{
 const f=runtime();await f.request();await f.error('QUOTA');
 assert.equal((await f.request()).provider,f.rows[1].provider);
 f.handlers['agent/turn-stopping'](f.payload);f.revision('thinking-high');f.selected.reasoningEffort='high';
 const high=await f.request({turn:2});assert.equal(routeKey(high),routeKey(f.rows[0]));assert.equal(high.reasoningEffort,'high');
 assert.equal(f.records.get('cost-test').manual_route,false);
 // Repeated native setter / next turn leaves the same control revision. An
 // exhausted route stays skipped and a harmless repeat cannot reset it.
 await f.handlers['agent/request-error']({...f.payload,turn:2,failure:{code:'QUOTA'}},async()=>undefined);
 f.handlers['agent/turn-stopping']({...f.payload,turn:2});
 const next=await f.request({turn:3});assert.equal(routeKey(next),routeKey(f.rows[1]));assert.equal(next.reasoningEffort,'high');
 assert.equal(f.records.get('cost-test').manual_route,false);
});
test('explicit provider changes stay manual through subsequent thinking changes',async()=>{
 const f=runtime();await f.request();f.handlers['agent/turn-stopping'](f.payload);
 f.revision('provider-change');f.selected.provider='workbuddy-global';
 assert.deepEqual(await f.request({turn:2}),f.selected);
 assert.equal(f.records.get('cost-test').manual_route,true);
 f.handlers['agent/turn-stopping']({...f.payload,turn:2});f.revision('thinking-high');f.selected.reasoningEffort='high';
 assert.deepEqual(await f.request({turn:3}),f.selected);
 assert.equal(f.records.get('cost-test').manual_route,true);
});
test('ordinary paid-model turn establishes a baseline before explicit DS selection',async()=>{
 const f=runtime();f.selected.model='kimi-k3.1-pro';f.selected.reasoningEffort='high';
 assert.deepEqual(await f.request(),f.selected);assert.equal(f.notices.length,0);
 assert.equal(f.records.get('cost-test').primary.model,'kimi-k3.1-pro');
 f.handlers['agent/turn-stopping'](f.payload);f.revision('choose-ds');f.selected.model='deepseek-v4.1-flash';
 assert.deepEqual(await f.request({turn:2}),f.selected);
 assert.equal(f.records.get('cost-test').manual_route,true);
});
test('failed route loading cannot silently buy API tokens',async()=>{
 const f=runtime();f.budget.ensure=async()=>{throw Error('broken registration')};await assert.rejects(f.request(),/route unavailable/);
 assert.ok(f.notices.at(-1).includes('配置故障'));
});
test('stop while metadata loads never changes source or retries',async()=>{
 const f=runtime();f.budget.candidates=async()=>{f.controller.abort();return f.rows};const r=await f.request();assert.deepEqual(r,f.selected);assert.equal(f.notices.length,0);
});
