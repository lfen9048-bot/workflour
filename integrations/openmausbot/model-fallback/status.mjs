import {readdirSync,readFileSync,writeFileSync,mkdirSync,renameSync} from 'node:fs';
import {homedir} from 'node:os';
import {join} from 'node:path';
import {resetEpoch,routeKey,RESET_TIME} from './plugin.mjs';
const base=join(process.env.DSH_HOME||join(homedir(),'.dsh'),'workflour-fallback');
mkdirSync(base,{recursive:true,mode:0o700});
const epoch=resetEpoch(),sessions=[];
for(const file of readdirSync(base)){
 if(!/^[a-f0-9-]{36}\.json$/.test(file))continue;
 try{const s=JSON.parse(readFileSync(join(base,file),'utf8'));sessions.push({session:file.slice(0,-5),primary:s.primary,active:s.active,
   restoration:s.epoch!==epoch?RESET_TIME+' 已到，新回合恢复原模型；运行中的回合保持原样':routeKey(s.primary)!==routeKey(s.active)?'备用中，下一次北京时间 '+RESET_TIME+' 后恢复':'原模型',confirmed_at:s.confirmed_at||null});}
 catch{sessions.push({session:file.slice(0,-5),error:'状态文件无法解析，禁止据此重发任务'})}
}
const result={checked_at:new Date().toISOString(),timezone:'Asia/Shanghai',reset_time:RESET_TIME,epoch,bot_defaults_modified:false,sessions};
if(process.argv.includes('--daily-check')){const p=join(base,'daily-check.json');writeFileSync(p+'.tmp',JSON.stringify(result,null,2)+'\n',{mode:0o600});renameSync(p+'.tmp',p)}
console.log(JSON.stringify(result,null,2));
if(sessions.some(s=>s.error))process.exitCode=1;
