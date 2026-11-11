// Optional installed-runtime integration probe. Run only in a disposable DSH_HOME.
import { readFileSync, writeFileSync, realpathSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { randomUUID } from 'node:crypto';
import { tmpdir } from 'node:os';
import { enqueue } from '../integrations/openmausbot/session-title/queue.mjs';
import { consume } from '../integrations/openmausbot/session-title/autogroup.mjs';
const home=realpathSync(process.env.DSH_HOME);
if (!home.startsWith(realpathSync(tmpdir())+'/')) throw Error('Disposable DSH_HOME required');
const root=realpathSync(process.argv[2]);
const modules='/Applications/DeepSeek Harness.app/Contents/Resources/app.asar/dsh/node_modules/@deepseek-ai';
const {loadProfileDirectory,loadLayeredEnv}=await import(pathToFileURL(join(modules,'dsh-app-boot/lib/index.js')).href);
const {runProfile}=await import(pathToFileURL(join(modules,'dsh/lib/profile-boot.js')).href);
const installAnchor=join(modules,'dsh/package.json');
const profile=loadProfileDirectory('dsh',join(home,'profiles/desktop'),installAnchor);
const app=await runProfile({environment:loadLayeredEnv('dsh'),profile:'desktop',resolvedProfile:{profile,installAnchor},patchFiles:[],args:['--no-open','--host','127.0.0.1','--port','0']});
try {
  const id=randomUUID();let session;
  const fiber=app.ctx.plugin({name:'workflour-native-autogroup-probe',inject:['sessions','sessionTitle','sessionPersistence'],async apply(ctx){
    session=ctx.sessions.create(id,{meta:{cwd:root}});
    ctx.sessionTitle.rename(session,'[验证] 隔离原生归组');
    const writer=await ctx.sessionPersistence.create(session.header);
    try { await writer.append(session.snapshotEvents()); await writer.flush(); }
    finally { await writer.close(); }
  }});
  await fiber;
  await fiber.dispose();
  if(app.ctx.sessions.get(id))throw Error('Probe session did not become cold');
  enqueue({session:{id,header:{cwd:root}}},'[验证] 隔离原生归组',root);
  const errors=[], published=[];
  const off=app.ctx.on('api-session/added',summary=>{if(summary.sessionId===id)published.push(summary);});
  const results=await consume(app.ctx,join(home,'workflour-session-queue'),root,error=>errors.push(String(error)));
  const result=results.find(row=>row.session_id===id);
  off();
  const receipt={status:result?.status,expected_title:result?.title,cold_path:true,no_model_prompt:true,list_summary_published:result?.list_summary_published===true,event_matches_native_id:published.some(row=>row.sessionId===id&&row.agentAvailable===false),errors};
  writeFileSync(process.argv[3],JSON.stringify(receipt,null,2)+'\n',{mode:0o600});
} finally {await app.shutdown.shutdown(0);}
