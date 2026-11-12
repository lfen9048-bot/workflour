/** Quota recovery at the host request boundary, never a replayed user task.
 * Host contract verified against DSH 0.2.1-rc.2 agent-loop + llm-retry.
 * No credentials, prompts or tool results are copied into our journal.
 */
import {readFileSync,writeFileSync,mkdirSync,renameSync} from 'node:fs';
import {join} from 'node:path';
import {homedir} from 'node:os';
import {createBudgetRouter} from './budget-router.mjs';
import {DS_IDS,isDeepSeek,isManaged} from './budget-policy.mjs';
import {createTaskCapabilities} from './task-capabilities.mjs';
export const name='workflour-model-fallback';
export const inject=['agents','llm'];
export const BACKUPS=[{provider:'workbuddy',model:'deepseek-v4.1-flash'},
  {provider:'workbuddy',model:'glm-5.3-flash'},
  {provider:'deepseek-official',model:'deepseek-flash'}];
export const routeKey=r=>JSON.stringify([r.provider,r.model]);
const pick=r=>({provider:r.provider,model:r.model,...r.reasoningEffort===undefined?{}:{reasoningEffort:r.reasoningEffort}});
// Beijing 13:00 is UTC 05:00. A running turn pins its epoch until it ends.
export const RESET_TIME='13:00';
export const resetEpoch=(time=Date.now())=>new Date(time-5*3600_000).toISOString().slice(0,10);
export function failureKind(failure){
  const code=String(failure?.code||'').toUpperCase();
  if(['QUOTA','ACCOUNT_QUOTA'].includes(code))return 'quota';
  if(['TRANSPORT','TIMEOUT','SERVER','EMPTY_RESPONSE'].includes(code))return 'connection';
  if(code==='RATE_LIMIT')return 'rate-limit';
  if(['ABORTED','CANCELLED','CANCELED'].includes(code))return 'stopped';
  return 'other';
}
export function stateFor(previous,selected,epoch){
  const same=previous&&(routeKey(selected)===routeKey(previous.primary)||routeKey(selected)===routeKey(previous.active));
  // Explicit selection of a different route wins. Do not copy old effort to it.
  if(!same)return {epoch,primary:pick(selected),active:pick(selected),tried:[]};
  if(previous.epoch!==epoch)return {epoch,primary:previous.primary,active:previous.primary,tried:[]};
  // Effort changes on the requested primary are user choices, too.
  if(routeKey(selected)===routeKey(previous.primary)){
    if(routeKey(previous.active)===routeKey(previous.primary))previous.active=pick(selected);
    previous.primary=pick(selected);
  }
  return previous;
}
function fileStore(base){
  mkdirSync(base,{recursive:true,mode:0o700});
  const path=id=>{if(!/^[A-Za-z0-9_-]{1,160}$/.test(id))throw Error('Invalid session identity');return join(base,id+'.json')};
  return {read(id){try{return JSON.parse(readFileSync(path(id),'utf8'))}catch(e){if(e.code==='ENOENT')return null;throw e}},
    write(id,value){const p=path(id),tmp=p+'.'+process.pid+'.tmp';writeFileSync(tmp,JSON.stringify(value,null,2)+'\n',{mode:0o600});renameSync(tmp,p)}};
}
export function install(ctx,{store,clock=Date.now,notice,controlRevision,budget,capabilities}={}){
  capabilities??=createTaskCapabilities({clock});
  store??=fileStore(join(process.env.DSH_HOME||join(homedir(),'.dsh'),'workflour-fallback'));
  controlRevision??=(id=>{try{return JSON.parse(readFileSync(join(process.env.DSH_HOME||join(homedir(),'.dsh'),'workflour-fallback-controls',id+'.json'),'utf8')).revision}catch(e){if(e.code==='ENOENT')return null;throw e}});
  notice??=((id,text)=>process.stdout.write(JSON.stringify({jsonrpc:'2.0',method:'session/update',params:{sessionId:id,update:{sessionUpdate:'agent_message_chunk',content:{type:'text',text:'\n【系统·模型状态】'+text+'\n'}}}})+'\n'));
  const turns=new Map();
  function publish(agent,state,text){
    state.events=[...(state.events||[]),{at:new Date(clock()).toISOString(),text}].slice(-40);
    store.write(agent.session.id,state);
    notice(agent.session.id,text);
  }
  const needsImage=current=>current.required_capabilities?.includes('image');
  async function imageUsable(candidate){
    try{
      const declaration=await budget?.imageDeclared?.(candidate);
      return !!declaration&&await capabilities.confirmedImage({...candidate,nativeProvider:declaration.provider},declaration.workbuddyVersion);
    }catch{return false}
  }
  function imageBlocked(agent,current){
    publish(agent,current,'当前任务要求实际读图，但所选模型或同系列额度线路没有同时通过图片声明与真实读图验证。已保留任务并停止自动选择；未跨模型或转用付费 API，也未覆盖手动选择。');
    throw Error('Required image capability is unavailable or unverified');
  }
  function state(agent,turn,selected){
    const id=agent.session.id,key=id+':'+turn;
    let entry=turns.get(key);
    if(!entry){
      for(const key of turns.keys())if(key.startsWith(id+':'))turns.delete(key);
      const old=store.read(id),revision=controlRevision(id);
      const changed=!!old&&old.control_revision!==revision;
      const samePrimary=!!old&&routeKey(selected)===routeKey(old.primary);
      // A level change chooses the depth of the same model, not a paid source.
      // Evaluate before stateFor updates old.primary in place. An explicit
      // same-value reset marker (when supplied) still opts into that route.
      const effortOnly=changed&&samePrimary&&selected.reasoningEffort!==old.primary.reasoningEffort;
      const newRoute=!!old&&!samePrimary&&routeKey(selected)!==routeKey(old.active);
      const current=stateFor(old?.control_revision===revision?old:null,selected,resetEpoch(clock()));
      current.control_revision=revision;
      // A nonempty marker alone is not proof of a human action: OMB sends
      // initial/unchanged model setters too. Only a revision CHANGE after an
      // existing request establishes a new explicit preference.
      current.manual_route=old?.manual_route===true||newRoute||(changed&&!effortOnly);
      entry={state:current,turn};turns.set(key,entry);
      // Remember normal, successful configuration resolution too. Otherwise
      // a first paid-model turn would leave no baseline and a later explicit
      // switch to DS would incorrectly look like a fresh default session.
      store.write(id,current);
      if(old&&old.control_revision===revision&&old.epoch!==current.epoch&&routeKey(old.active)!==routeKey(current.active))publish(agent,current,'已到北京时间 '+RESET_TIME+'，当前新回合恢复原模型 '+routeKey(current.active)+'；未中断此前执行。');
    }
    return entry.state;
  }
  async function chooseBudget(agent,current,signal,{fallback=false,sameRegionOnly=false}={}){
    let candidates;
    try{candidates=await budget.candidates({signal})}catch(e){
      if(signal.aborted)return;
      publish(agent,current,'无法取得有效的 WorkBuddy 价格或额度信息；已停止自动选择，未转用付费 API。');
      throw Error('WorkBuddy billing metadata unavailable');
    }
    if(signal.aborted)return;
    // Cost routing is an equivalent DeepSeek-source choice. A different
    // model family becomes eligible only after an explicit quota failure.
    if(!fallback&&isDeepSeek(current.primary))candidates=candidates.filter(c=>Object.values(DS_IDS).some(ids=>ids.includes(c.model)));
    if(needsImage(current))candidates=candidates.filter(c=>isDeepSeek(current.primary)&&Object.values(DS_IDS).some(ids=>ids.includes(c.model)));
    if(sameRegionOnly)candidates=candidates.filter(c=>c.region===current.billing?.region&&c.tier===current.billing?.tier&&c.model===current.active.model);
    if(fallback&&!sameRegionOnly&&!needsImage(current)&&await budget.apiAllowed())candidates.push({provider:'deepseek-official',model:'deepseek-flash'});
    for(const candidate of candidates){
      if(current.tried.includes(routeKey(candidate)))continue;
      if(needsImage(current)){
        const usable=await imageUsable(candidate);if(signal.aborted)return;
        if(!usable)continue;
      }
      let resolved;
      try{
        await budget.ensure(candidate);signal.throwIfAborted();
        // Same-model billing changes preserve the actual chosen effort.
        const effort=isDeepSeek(current.primary)&&candidate.model.startsWith('deepseek-')?current.primary.reasoningEffort:undefined;
        if(effort&&candidate.supportedEfforts&&!candidate.supportedEfforts.includes(effort))continue;
        resolved=await ctx.llm.resolveCallConfig({...pick(candidate),...(effort?{reasoningEffort:effort}:{})},signal);
      }catch(e){
        if(signal.aborted)return;
        // A broken route/config is not a quota event and must not jump to API.
        publish(agent,current,'WorkBuddy 目标通道无法加载；已保留任务，未把配置故障当成额度耗尽。');
        throw Error('WorkBuddy billing route unavailable');
      }
      if(signal.aborted)return;
      const previous=current.active;current.active=pick(resolved);current.billing=candidate;delete current.confirmed_at;
      if(routeKey(previous)!==routeKey(current.active))publish(agent,current,
        `${fallback?'当前请求需要切换':'按免费与临期额度优先规则选择'}：${budget.describe(candidate)}；思考档位：${current.active.reasoningEffort||'模型默认'}。只处理当前模型请求，不重派任务；尚未确认实际返回。`);
      return true;
    }
    if(!fallback){if(needsImage(current))imageBlocked(agent,current);throw Error('No verified WorkBuddy billing route is available')}
    return false;
  }
  ctx.on('agent/request',async ({agent,turn,signal},next)=>{
    const original=await next();if(signal.aborted)return original;
    const current=state(agent,turn,original);
    const entry=turns.get(agent.session.id+':'+turn);
    if(!entry.capabilitiesInitialized){
      try{
        const requirements=await capabilities.requirements(agent.session.id,{signal});
        current.required_capabilities=requirements.required_capabilities;
        current.capability_intents=requirements.intents;
        entry.capabilitiesInitialized=true;
      }catch(error){
        if(signal.aborted)return original;
        publish(agent,current,'无法核对当前任务的原生派单身份或能力要求；已停止自动选择并保留任务，未转用付费模型。');
        throw Error('Native task capability lookup failed');
      }
    }
    if(signal.aborted)return original;
    if(budget){
      if(!entry.budgetInitialized){
        // Default DS Flash follows the cost policy. Explicit alternate models
        // (including the paid -sg menu route) are tried as chosen first.
        if(!current.manual_route&&['workbuddy','workbuddy-global'].includes(current.primary.provider)&&current.primary.model==='deepseek-v4.1-flash')
          await chooseBudget(agent,current,signal);
        else if(isManaged(current.active)){
          if(!current.billing)throw Error('Billing handoff is missing; select a model explicitly');
          await budget.ensure(current.billing);
        }
        entry.budgetInitialized=true;
      }
      // A free promotion can end between two model calls in one long turn.
      // Check before the NEXT request, never interrupt an in-flight stream.
      if(isManaged(current.active)&&budget.valid&&!(await budget.valid(current.billing)))await chooseBudget(agent,current,signal);
      if(isManaged(current.active))await budget.ensure(current.billing);
    }
    if(needsImage(current)){
      const usable=await imageUsable(current.billing||current.active);
      if(signal.aborted)return original;
      if(!usable)imageBlocked(agent,current);
    }
    const {reasoningEffort,...rest}=original;
    return {...rest,...current.active};
  },{prepend:true});
  ctx.on('agent/request-error',async (payload,next)=>{
    const {agent,turn,failure,signal}=payload;
    if(signal.aborted)return;
    // Native bounded transient retries get first refusal. No task redispatch.
    const downstream=await next();if(signal.aborted||downstream?.kind==='retry')return downstream;
    const current=turns.get(agent.session.id+':'+turn)?.state;
    if(!current)return;
    const kind=failureKind(failure);
    if(budget&&isManaged(current.active)&&kind!=='quota'){
      // Match native pool's account failover while never turning a connection,
      // invalid credential or queue error into permission to buy API tokens.
      const cause=budget.reason(current.active);
      if(['rate-limited','credential-rejected','unavailable','failed'].includes(cause)){
        current.tried=[...new Set([...current.tried,routeKey(current.active)])];
        if(await chooseBudget(agent,current,signal,{fallback:true,sameRegionOnly:true}))return {kind:'retry'};
      }
    }
    if(kind!=='quota'){
      if(kind!=='stopped')publish(agent,current,kind==='connection'?'模型请求遇到连接、服务或超时错误；这不代表额度不足。现有重试未恢复，已保留任务，请检查连接后继续。':kind==='rate-limit'?'模型请求受到限流或排队；这不等于余额不足。已保留任务，未自动消耗付费 API。':'模型请求失败（'+String(failure.code||'UNKNOWN').replace(/[^A-Z0-9_]/g,'')+'）；已保留任务，未自动改派。');
      return downstream;
    }
    current.tried=[...new Set([...current.tried,routeKey(current.active)])];
    if(budget){
      if(await chooseBudget(agent,current,signal,{fallback:true}))return {kind:'retry'};
      if(needsImage(current))return imageBlocked(agent,current);
      publish(agent,current,'已用尽本次可确认的免费、临期及普通额度通道；任务暂停。未知额度不会被当成已耗尽，不会无限重试或重新派单。');
      return;
    }
    if(needsImage(current))return imageBlocked(agent,current);
    for(const candidate of BACKUPS){
      if(current.tried.includes(routeKey(candidate)))continue;
      let resolved;
      try{resolved=await ctx.llm.resolveCallConfig(candidate,signal)}catch(error){
        if(signal.aborted)return;
        current.tried.push(routeKey(candidate));
        publish(agent,current,'备用模型 '+routeKey(candidate)+' 无法加载，继续检查下一候选；没有把目录缓存当成调用成功。');continue;
      }
      if(signal.aborted)return;
      const previous=current.active;current.active=pick(resolved);delete current.confirmed_at;
      publish(agent,current,'当前模型报告额度/用量上限，尝试 '+routeKey(previous)+' → '+routeKey(current.active)+(candidate.provider==='deepseek-official'?'（使用已授权的 DeepSeek API 额度）':'（WorkBuddy 额度）')+'，思考档位：'+(current.active.reasoningEffort||'模型默认')+'。只续接失败的模型请求，不重新派发任务；尚未确认新模型返回成功。');
      return {kind:'retry'};
    }
    publish(agent,current,'已用尽本次允许的备用模型，任务暂停。请补充额度或手动选模型后继续；不会无限重试或重复派单。');
  },{prepend:true});
  ctx.on('agent/turn-stopping',({agent,turn})=>{
    const current=turns.get(agent.session.id+':'+turn)?.state;
    const replied=current&&(agent.session.snapshotEvents?.()||[]).some(e=>e.type==='assistant/message'&&e.data.turn===turn&&!e.data.interrupted&&e.data.message?.source?.provider===current.active.provider&&e.data.message?.source?.model===current.active.model);
    if(replied&&routeKey(current.active)!==routeKey(current.primary)){
      current.confirmed_at=new Date(clock()).toISOString();
      publish(agent,current,(budget&&current.billing?budget.describe(current.billing):'备用模型 '+routeKey(current.active))+' 已实际返回回复；任务完成情况以最终回执为准。Bot 默认设置未改，北京时间 '+RESET_TIME+' 后的新回合重新检查原模型及额度优先规则。');
    }
    turns.delete(agent.session.id+':'+turn);
  });
  return {turns};
}
export function apply(ctx){install(ctx,{...(process.env.WORKFLOUR_QUOTA_POLICY==='enabled'?{budget:createBudgetRouter(ctx)}:{})})}
