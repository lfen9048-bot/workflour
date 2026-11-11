import {readFile,mkdir,writeFile,rename} from 'node:fs/promises';
import {homedir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {orderedCandidates,SNAPSHOT_TTL,isManaged,providerFor} from './budget-policy.mjs';

const HOME=()=>process.env.DSH_HOME||join(homedir(),'.dsh');
const dir=()=>join(HOME(),'workflour-billing');
async function read(path){try{return JSON.parse(await readFile(path,'utf8'))}catch(e){if(e.code==='ENOENT')return null;throw Error('额度状态文件损坏，已停止自动选择')}}
async function write(path,value){await mkdir(dir(),{recursive:true,mode:0o700});const tmp=path+'.'+process.pid+'.tmp';await writeFile(tmp,JSON.stringify(value)+'\n',{mode:0o600});await rename(tmp,path)}
export function describeRoute(r){
  if(!r?.region)return r?.provider==='deepseek-official'?'DeepSeek API':`${r.provider} / ${r.model}`;
  const source=r.region==='global'?'WorkBuddy 国际版':'WorkBuddy 国内版';
  const tier=r.tier==='free'?'已核对免费':r.tier==='expiring'?`临期积分，${new Date(r.expiresAtMs).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})} 到期`:'普通积分';
  return `${source} / ${r.model} / 账号 …${r.accountId.slice(-6)}（${tier}）`;
}
export function createBudgetRouter(ctx,{clock=Date.now,bridgeFactory,moduleLoader,metadataLoader,snapshotStorage={read,write}}={}){
  let bridge,preferences,plugin,pending,snapshot,initializing;
  const adapters=new Map(),failures=new Map(),creating=new Map();
  async function init(){
    if(plugin)return;
    if(!initializing)initializing=(async()=>{
      if(metadataLoader){({bridge,preferences,plugin}=await metadataLoader());return}
      const lib=await import('../workbuddy/client.mjs');
      const prefs=await lib.loadPreferences();
      const instance=bridgeFactory?await bridgeFactory(prefs):await lib.createBridge({preferences:prefs});
      const loaded=await lib.loadPlugin();
      preferences=instance.getPreferences?.()||prefs;bridge=instance;plugin=loaded;
    })();
    try{await initializing}catch(e){initializing=null;throw e}
  }
  async function refresh(force=false){
    await init();
    if(!force&&snapshot&&clock()-snapshot.fetchedAtMs<SNAPSHOT_TTL)return snapshot;
    if(pending)return pending;
    pending=(async()=>{
      const roster=await bridge.listAccounts();
      const fingerprint=createHash('sha256').update(JSON.stringify({pools:preferences.pools,enabled:preferences.enabledRegions,models:preferences.enabledModelIds,accounts:roster})).digest('hex');
      const cached=await snapshotStorage.read(join(dir(),'snapshot.json'));
      if(!force&&cached?.fingerprint===fingerprint&&clock()-cached.fetchedAtMs<SNAPSHOT_TTL&&cached.fetchedAtMs<=clock()+5000){snapshot=cached;return snapshot}
      const now=clock(),result={version:1,fingerprint,fetchedAtMs:now,pools:preferences.pools,accounts:{cn:[],global:[]},errors:[]};
      await Promise.all(['cn','global'].map(async region=>{
        if(preferences.enabledRegions?.[region]===false)return;
        const nativeProbes=(await snapshotStorage.read(join(HOME(),`.workbuddy-pool.${region}.json`)))?.probes||{};
        result.accounts[region]=await Promise.all((roster[region]||[]).map(async a=>{
          const row={accountId:a.accountId,available:a.available,enterprise:a.enterprise,tokenExpiresAtMs:a.tokenExpiresAtMs,probe:nativeProbes[a.accountId]};
          // Never persist upstream messages or account names from the pool file.
          if(row.probe)row.probe=Object.fromEntries(['outcome','atMs','retryAtMs'].filter(k=>row.probe[k]!==undefined).map(k=>[k,row.probe[k]]));
          const answers=await Promise.allSettled([bridge.fetchModels(region,a.accountId),bridge.fetchCredits(region,a.accountId)]);
          if(answers[0].status==='fulfilled')row.models=answers[0].value.models;
          else {row.error='catalog_unavailable';result.errors.push({region,accountId:a.accountId,kind:'catalog'})}
          if(answers[1].status==='fulfilled')row.credits=answers[1].value;
          else result.errors.push({region,accountId:a.accountId,kind:'credits'});
          return row;
        }));
      }));
      // Timestamp when reading began, so a slow read never extends freshness.
      await snapshotStorage.write(join(dir(),'snapshot.json'),result);snapshot=result;return result;
    })();
    try{return await pending}finally{pending=null}
  }
  async function candidates({signal,force=false}={}){
    const data=await refresh(force);signal?.throwIfAborted();
    return orderedCandidates(data,clock());
  }
  async function ensure(candidate){
    if(!isManaged(candidate))return candidate;
    await init();
    const data=await refresh();
    const account=data.accounts[candidate.region]?.find(a=>a.accountId===candidate.accountId);
    if(!account?.models?.some(m=>m.id===candidate.model))throw Error('实际账号目录中没有目标模型');
    const id=providerFor(candidate.region,candidate.accountId);
    const fingerprint=JSON.stringify(account.models);
    if(creating.has(id))await creating.get(id);
    if(adapters.has(id)){
      const old=adapters.get(id);
      if(old.fingerprint!==fingerprint){old.setModels(account.models);old.adapter.invalidate();old.fingerprint=fingerprint}
      return candidate;
    }
    const job=(async()=>{
    const wb=moduleLoader?await moduleLoader():await import(pathToFileURL(plugin.modulePath).href);
    const client=new wb.WorkBuddyUpstreamClient();
    const store=new wb.WorkBuddyCredentialStore({region:candidate.region,refresh:c=>client.refreshToken(c)});
    store.selectAccount(candidate.accountId);
    const resolve=store.resolve.bind(store);
    store.resolve=async()=>{const c=await resolve();if(wb.workbuddyAccountId(c)!==candidate.accountId||wb.regionOf(c.domain)!==candidate.region)throw Error('Billing account identity mismatch');return c};
    const catalog=new wb.WorkBuddyCatalog(candidate.region);
    catalog.setRegionUsable(true);catalog.setRegionEnabled(true);
    const setModels=rows=>{
      const models=wb.deriveCatalog(rows,new Set(rows.map(m=>m.id))).map(m=>({...m,multimodal:wb.imageDefaultFor(m.id)}));
      catalog.set(wb.withEffectiveOff(models,new Set()));
    };
    setModels(account.models);
    const shim=wb.createWorkBuddyShim({store,client,catalog,onAccountFailure:(accountId,failure)=>{
      failures.set(id,{accountId,outcome:wb.outcomeOfFailure(failure.status,failure.message),atMs:clock()});
    }});
    try{
      await shim.ready;
      const adapter=wb.createWorkBuddyAdapter({store,shim,catalog,provider:id,modelIdentity:id,
        displayName:`WorkBuddy ${candidate.region==='cn'?'国内':'国际'} · …${candidate.accountId.slice(-6)}`,
        resolveAttachments:()=>ctx.get?.('attachments')});
      // DSH enumerates every registered adapter, even without a settings
      // directory. Exact resolveModel remains available to this router only.
      adapter.adapter.listModels=async()=>[];
      const dispose=ctx.llm.registerAdapter([id],adapter.adapter);
      let closing;
      const cleanup=()=>{if(!closing){dispose();closing=Promise.resolve().then(()=>shim.close())}return closing};
      ctx.effect?.(()=>cleanup);adapters.set(id,{adapter,shim,cleanup,catalog,setModels,fingerprint});
    }catch(e){await shim.close();throw e}
    })();
    creating.set(id,job);
    try{await job}finally{creating.delete(id)}
    return candidate;
  }
  function reason(active){return failures.get(active.provider)?.outcome}
  return {candidates,ensure,reason,describe:describeRoute,refresh,
    async valid(candidate){const rows=await candidates();return rows.some(r=>r.provider===candidate.provider&&r.model===candidate.model&&r.tier===candidate.tier)},
    async apiAllowed(){const s=await refresh();return !s.errors.length},
    async close(){await Promise.all([...adapters.values()].map(entry=>entry.cleanup()));adapters.clear()}};
}
