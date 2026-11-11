import test from 'node:test';
import assert from 'node:assert/strict';
import {orderedCandidates} from '../integrations/openmausbot/model-fallback/budget-policy.mjs';
const now=Date.now();
test('damaged snapshot timestamps and account containers fail closed',()=>{
  for(const fetchedAtMs of [undefined,null,'0',NaN,Infinity])
    assert.throws(()=>orderedCandidates({fetchedAtMs,accounts:{cn:[],global:[]}},now));
  for(const accounts of [null,{}, {cn:{},global:[]}])
    assert.throws(()=>orderedCandidates({fetchedAtMs:now,accounts},now));
});
test('monthly plans are not promoted ahead of expiring grants',()=>{
  const rows=orderedCandidates({fetchedAtMs:now,accounts:{cn:[{
    accountId:'a'.repeat(24),models:[{id:'deepseek-v4.1-flash',creditMultiplier:.1}],
    credits:{total:100,packages:[{monthly:true,remain:100,expiresAtMs:now+10000}]}
  }],global:[]}},now);
  assert.equal(rows[0].tier,'regular');
});
