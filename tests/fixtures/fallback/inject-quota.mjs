// Loaded only by the isolated acceptance launcher; never by formal Bots.
export const name='workflour-quota-fixture';
export const inject=['llm'];
export function apply(ctx){ctx.on('llm/stream',(options,next)=>{
 if(options.provider!=='workbuddy')return next();
 return (async function*(){yield {type:'finish',reason:{kind:'error',failure:{code:'QUOTA',message:'Synthetic quota fixture; no upstream WorkBuddy request',retryable:false}}}})();
},{prepend:true})}
