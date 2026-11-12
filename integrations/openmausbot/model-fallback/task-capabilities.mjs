/** Task capabilities come from native assignment identity, never prompt text.
 * A catalog checkbox is necessary but not evidence of a successful image read.
 */
import {readFile,lstat} from 'node:fs/promises';
import {join,resolve,isAbsolute} from 'node:path';
import {homedir} from 'node:os';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {createHash} from 'node:crypto';

const identity=value=>typeof value==='string'&&/^[A-Za-z0-9_-]{1,160}$/.test(value);
const hash=value=>createHash('sha256').update(value).digest('hex');
const sha=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const answerOf=report=>typeof report?.public_answer==='string'?report.public_answer.split('\n').filter(line=>!line.startsWith('【系统·模型状态】')).join('\n').trim():'';

function imageProbeValid(probe,row,{adjudicated=false}={}){
  if(probe?.schema_version!==1||probe.nonce_in_prompt!==false||probe.stop_reason!=='end_turn'||probe.protocol_error_count!==0||probe.error_type)return false;
  if(!sha(probe.image_sha256)||!sha(probe.expected_sha256)||!Array.isArray(probe.tools))return false;
  const calls=probe.tools.filter(tool=>tool.event==='tool_call');
  if(calls.length!==1||calls[0].title!=='read_image'||!calls[0].id||!Array.isArray(calls[0].paths)||calls[0].paths.length!==1)return false;
  const updates=probe.tools.filter(tool=>tool.id===calls[0].id);
  if(!updates.some(tool=>tool.status==='completed')||updates.some(tool=>['failed','cancelled'].includes(tool.status)))return false;
  const answer=answerOf(probe);
  if(!/^[0-9]{8}$/.test(answer)||hash(answer)!==probe.expected_sha256)return false;
  const active=probe.fallback?.active,confirmed=Date.parse(probe.fallback?.confirmed_at);
  const started=Date.parse(probe.started_at),finished=Date.parse(probe.finished_at),checked=Date.parse(row.checked_at);
  if(![confirmed,started,finished,checked].every(Number.isFinite)||confirmed<started||confirmed>finished||finished>checked+5000)return false;
  if(active?.provider!==row.provider||active.model!==row.model||probe.billing?.nativeProvider!==row.provider||probe.billing.model!==row.model)return false;
  if(adjudicated)return probe.status==='failed'&&probe.passed===false&&probe.exact_match===false;
  return probe.status==='passed'&&probe.passed===true&&probe.exact_match===true&&probe.model_answer===answer&&
    probe.actual_tool_scope==='one_read_image'&&probe.image_tool_completed===true&&probe.workbuddy_version===row.workbuddy_version;
}

async function evidenceValid(bytes,row){
  const evidence=JSON.parse(bytes);
  if(!evidence?.source_evidence)return imageProbeValid(evidence,row);
  if(evidence.schema_version!==1||evidence.status!=='passed'||evidence.provider!==row.provider||evidence.model!==row.model||
    evidence.workbuddy_version!==row.workbuddy_version||!isAbsolute(evidence.source_evidence)||!sha(evidence.source_sha256))return false;
  const source=await readFile(evidence.source_evidence);
  if(hash(source)!==evidence.source_sha256)return false;
  const probe=JSON.parse(source);
  return imageProbeValid(probe,row,{adjudicated:true})&&evidence.model_answer===answerOf(probe)&&
    evidence.expected_sha256===probe.expected_sha256&&evidence.image_sha256===probe.image_sha256&&
    evidence.image_tool_completed===true&&evidence.actual_reply_confirmed_at===probe.fallback.confirmed_at;
}
const defaultScript=fileURLToPath(new URL('../../../scripts/prepare-dispatch.py',import.meta.url));
async function runRequirements(binding,{signal}={}){
  return new Promise((accept,reject)=>{
    const child=execFile('python3',[defaultScript,'requirements'],{timeout:10000,maxBuffer:65536,signal},(error,stdout)=>{
      if(error)return reject(Error('Native task capability lookup failed'));
      try{accept(JSON.parse(stdout))}catch{reject(Error('Native task capability response is invalid'))}
    });
    child.stdin.on('error',()=>{});
    child.stdin.end(JSON.stringify({bot_id:binding.bot_id,thread_id:binding.thread_id}));
  });
}
export function createTaskCapabilities({bindingHome,registryPath,requirementsRunner=runRequirements,clock=Date.now,
  requireBinding=process.env.WORKFLOUR_REQUIRE_SESSION_BINDING==='enabled'}={}){
  bindingHome??=join(process.env.DSH_HOME||join(homedir(),'.dsh'),'workflour-session-bindings');
  registryPath??=process.env.WORKFLOUR_IMAGE_CAPABILITIES||join(homedir(),'.workflour/model-capabilities/image.json');
  return {
    async requirements(sessionId,{signal}={}){
      if(!identity(sessionId))throw Error('Invalid native session identity');
      let binding;
      try{
        const path=join(bindingHome,sessionId+'.json');
        if((await lstat(bindingHome)).isSymbolicLink()||(await lstat(path)).isSymbolicLink())throw Error('Unsafe native binding');
        binding=JSON.parse(await readFile(path,'utf8'));
      }
      catch(error){if(error.code==='ENOENT'&&!requireBinding)return {required_capabilities:[],intents:[]};throw Error('Native task binding is unreadable')}
      if(binding?.schema_version===1&&binding.session_id===sessionId&&binding.scope==='non_omb'&&!binding.bot_id&&!binding.thread_id)return {required_capabilities:[],intents:[]};
      if(binding?.schema_version!==1||binding.session_id!==sessionId||!identity(binding.bot_id)||!identity(binding.thread_id))throw Error('Native task binding is invalid');
      const result=await requirementsRunner(binding,{signal});
      if(!Array.isArray(result?.required_capabilities)||result.required_capabilities.some(v=>v!=='image')||!Array.isArray(result.intents))throw Error('Native task capabilities are unsupported or invalid');
      return {required_capabilities:[...new Set(result.required_capabilities)],intents:result.intents};
    },
    async confirmedImage(route,workbuddyVersion){
      if(!workbuddyVersion||!isAbsolute(registryPath))return false;
      const provider=route.nativeProvider||route.provider;
      if(!['workbuddy','workbuddy-global'].includes(provider))return false;
      let registry;
      try{registry=JSON.parse(await readFile(registryPath,'utf8'))}catch{return false}
      if(registry?.schema_version!==1||!Array.isArray(registry.records))return false;
      for(const row of registry.records){
        if(row?.provider!==provider||row.model!==route.model||row.capability!=='image'||row.status!=='passed'||row.workbuddy_version!==workbuddyVersion)continue;
        const checked=Date.parse(row.checked_at);
        if(!Number.isFinite(checked)||checked>clock()+5000||!isAbsolute(row.evidence_path||'')||!/^[a-f0-9]{64}$/.test(row.evidence_sha256||''))continue;
        try{
          const bytes=await readFile(resolve(row.evidence_path));
          if(hash(bytes)===row.evidence_sha256&&await evidenceValid(bytes,row))return true;
        }catch{/* Missing or changed proof is unknown, not image-capable. */}
      }
      return false;
    }
  };
}
