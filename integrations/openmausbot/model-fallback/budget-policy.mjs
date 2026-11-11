/** Cost ordering around WorkBuddy 5.13.1's native account rules.
 * rankAccounts follows dingminhua/dsh-connect-workbuddy (MIT), account-pool.ts.
 * Cross-region ordering is Workflour policy; it does not control upstream's
 * choice of a credit package within an account. No credentials enter here.
 */
export const POLICY_VERSION = 1;
export const SNAPSHOT_TTL = 5 * 60_000;
export const SOON_MS = 3 * 86400_000;
export const DS_IDS = {cn:['deepseek-v4.1-flash'],global:['deepseek-v4.1-flash','deepseek-v4.1-flash-sg']};
export const isDeepSeek = r => ['workbuddy','workbuddy-global'].includes(r.provider) && Object.values(DS_IDS).flat().includes(r.model);
export const isManaged = r => String(r?.provider||'').startsWith('workflour-wb-');
export const providerFor = (region,id) => {
  if(!['cn','global'].includes(region)||!/^[a-f0-9]{16,64}$/.test(id))throw Error('Invalid WorkBuddy account identity');
  return `workflour-wb-${region}-${id}`;
};
const number = x => typeof x==='number' && Number.isFinite(x);
function second(value){
  if(number(value))return value>=0&&value<=86400?value:null;
  if(typeof value!=='string'||!/^\d{1,2}:\d{2}(?::\d{2})?$/.test(value))return null;
  const [h,m,s=0]=value.split(':').map(Number);return h<24&&m<60&&s<60?h*3600+m*60+s:null;
}
export function promoActive(promo,now){
  const s=promo?.schedule;if(!s)return true;
  if(s.dailyUnusable===true)return false;
  if(s.validFrom!==undefined&&(!number(s.validFrom)||now<s.validFrom))return false;
  if(s.validUntil!==undefined&&(!number(s.validUntil)||now>=s.validUntil))return false;
  if(s.daily===undefined)return true;
  if(!Array.isArray(s.daily)||!s.daily.length||!s.timezone)return false;
  try{
    const parts=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:s.timezone,hourCycle:'h23',hour:'2-digit',minute:'2-digit',second:'2-digit'}).formatToParts(now).map(x=>[x.type,x.value]));
    const t=Number(parts.hour)*3600+Number(parts.minute)*60+Number(parts.second);
    return s.daily.some(w=>{const a=second(w.start),b=second(w.end);return a!==null&&b!==null&&(a<=b?t>=a&&t<b:t>=a||t<b)});
  }catch{return false}
}
export function effectivePrice(model,now){
  const base=model.creditMultiplier;
  const promos=(model.promos||[]).filter(p=>number(p.discount?.multiplier)&&['replace','strikethrough'].includes(p.discount.displayMode));
  const active=promos.filter(p=>promoActive(p,now)).sort((a,b)=>(b.priority||0)-(a.priority||0))[0];
  if(active)return active.discount.multiplier>=0?active.discount.multiplier:null;
  // Upstream may bake a temporary zero into the base. An expired offer never
  // proves that the same cached/raw zero remains a permanent free price.
  if(promos.some(p=>p.discount.multiplier===base&&!promoActive(p,now)))return null;
  return number(base)&&base>=0?base:null;
}
export function excluded(probe,now){
  if(!probe||probe.outcome==='ok'||['policy-rejected','channel-rejected'].includes(probe.outcome))return false;
  if(['credential-rejected','account-restricted','not-found'].includes(probe.outcome))return true;
  const wait=probe.outcome==='model-busy'?120_000:30*60_000;
  return now < (probe.retryAtMs ?? ((probe.atMs||now)+wait));
}
export function rankAccounts(rows,order=[],now=Date.now()){
  const pos=id=>{const i=order.indexOf(id);return i<0?Infinity:i};
  return rows.filter(r=>r.available!==false&&!excluded(r.probe,now)).sort((a,b)=>{
    const ar=a.credits?.expiringSoon>0,br=b.credits?.expiringSoon>0;
    if(ar!==br)return ar?-1:1;
    if(pos(a.accountId)!==pos(b.accountId))return pos(a.accountId)-pos(b.accountId);
    if(ar&&br){const d=(a.credits.expiringSoonEarliestExpiryMs??Infinity)-(b.credits.expiringSoonEarliestExpiryMs??Infinity);if(d)return d}
    return (b.credits?.expiringSoon||0)-(a.credits?.expiringSoon||0)
      ||(b.credits?.total||0)-(a.credits?.total||0)
      ||(b.tokenExpiresAtMs||0)-(a.tokenExpiresAtMs||0)||a.accountId.localeCompare(b.accountId);
  });
}
function risk(credits,now){
  const entries=(credits?.packages||[]).filter(p=>!p.monthly&&p.remain>0&&number(p.expiresAtMs)&&p.expiresAtMs>now&&p.expiresAtMs-now<=SOON_MS);
  return {expiringSoon:entries.reduce((n,p)=>n+p.remain,0),expiringSoonEarliestExpiryMs:entries.length?Math.min(...entries.map(p=>p.expiresAtMs)):undefined};
}
export function orderedCandidates(snapshot,now=Date.now()){
  if(!snapshot||!number(snapshot.fetchedAtMs)||now-snapshot.fetchedAtMs>SNAPSHOT_TTL||snapshot.fetchedAtMs>now+5000)throw Error('额度与价格读数已过期或无效，需要重新读取');
  if(!snapshot.accounts||!['cn','global'].every(r=>Array.isArray(snapshot.accounts[r])))throw Error('额度账号快照无效，需要重新读取');
  const buckets={cn:{free:[],expiring:[],regular:[]},global:{free:[],expiring:[],regular:[]}};
  for(const region of ['cn','global']){
    const raw=(snapshot.accounts?.[region]||[]).map(a=>({...a,credits:a.credits?{...a.credits,...risk(a.credits,now)}:undefined}));
    for(const a of rankAccounts(raw,snapshot.pools?.[region]?.orderAccountIds||[],now)){
      if(a.error)continue;
      const ids=[...DS_IDS[region],'glm-5.3-flash'];
      for(const id of ids){
        const model=(a.models||[]).find(m=>m.id===id);if(!model)continue;
        const price=effectivePrice(model,now);if(price===null)continue;
        const free=price===0;
        // A missing credit answer can still serve a VERIFIED free model; it
        // cannot justify spending paid credits or ranking expiry.
        if(!free&&(!a.credits||a.credits.total<=0))continue;
        const tier=free?'free':a.credits.expiringSoon>0?'expiring':'regular';
        buckets[region][tier].push({provider:providerFor(region,a.accountId),model:id,region,accountId:a.accountId,
          nativeProvider:region==='cn'?'workbuddy':'workbuddy-global',tier,price,
          ...(tier==='expiring'?{expiresAtMs:a.credits.expiringSoonEarliestExpiryMs,expiringAmount:a.credits.expiringSoon}:{}),
          supportedEfforts:model.reasoning?.supportedEfforts||[],defaultEffort:model.reasoning?.defaultEffort||'high'});
      }
    }
  }
  // Free first. Within either region preserve native pool ordering. Merge the
  // expiring heads by deadline across regions (never sort a non-transitive
  // comparator combining regional manual order with cross-region deadlines).
  const out=[...buckets.global.free,...buckets.cn.free];
  const queues=[buckets.cn.expiring,buckets.global.expiring].map(x=>[...x]);
  while(queues.some(q=>q.length)){
    let i=!queues[0].length?1:!queues[1].length?0:queues[0][0].expiresAtMs<=queues[1][0].expiresAtMs?0:1;
    out.push(queues[i].shift());
  }
  // Established ordinary-credit preference is CN before international paid.
  out.push(...buckets.cn.regular,...buckets.global.regular);
  return out;
}
