/** Native DSH 0.2.1-rc.2 tool waterfalls; no replacement of native permissions.
 * Prepared dispatches are checked before MCP execution and journaled before
 * invoking the original tool. An uncertain send is never replayed here.
 */
import {readFileSync, lstatSync} from 'node:fs';
import {homedir} from 'node:os';
import {join, resolve, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';

export const name = 'workflour-dispatch-guard';
export const inject = ['tools'];
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const UUID = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const prefixes = ['mcp__agents__', 'agents__', 'agents_', ''];
const rawName = name => {
  for (const prefix of prefixes) if (name.startsWith(prefix)) return name.slice(prefix.length);
};

export function dispatchArguments(exec) {
  let called = rawName(String(exec.name || '')), args = exec.arguments;
  // OMB's discoverable tool bridge/directory must not bypass a direct guard.
  for (let depth = 0; depth < 3 && ['use_tool', 'call_tool'].includes(called); depth++) {
    if (!args || typeof args !== 'object') return null;
    called = rawName(String(args.name || '')); args = args.arguments;
  }
  return called === 'coordinate_bots' ? args : null;
}

export function sessionBinding(sessionId) {
  if (typeof sessionId !== 'string' || !/^[A-Za-z0-9_-]{1,160}$/.test(sessionId)) throw Error('Missing native session identity');
  const base = join(process.env.DSH_HOME || join(homedir(), '.dsh'), 'workflour-session-bindings');
  if (lstatSync(base).isSymbolicLink()) throw Error('Unsafe native session binding directory');
  const path = join(base, sessionId + '.json');
  if (lstatSync(path).isSymbolicLink()) throw Error('Unsafe native session binding');
  const value = JSON.parse(readFileSync(path, 'utf8'));
  if (value.schema_version !== 1 || value.session_id !== sessionId || !UUID.test(value.bot_id) || !UUID.test(value.thread_id)) {
    throw Error('Unconfirmed native session binding; dispatch was not started');
  }
  return {bot_id: value.bot_id, thread_id: value.thread_id};
}

export async function invokeHelper(action, input) {
  return new Promise((resolvePromise, reject) => {
    const child = spawn('python3', [join(root, 'scripts/prepare-dispatch.py'), action], {stdio: ['pipe', 'pipe', 'pipe']});
    let output = '', settled = false;
    const fail = reason => { if (!settled) { settled = true; clearTimeout(timer); reject(Error(reason)); } };
    const timer = setTimeout(() => { child.kill(); fail('Dispatch journal check timed out; inspect receipts before retrying'); }, 15000);
    child.once('error', () => fail('Dispatch journal helper unavailable; no automatic resend'));
    child.stdout.on('data', chunk => {
      output += chunk;
      if (output.length > 128000) { child.kill(); fail('Dispatch journal returned oversized data'); }
    });
    // Never print inherited environment, request content or credential details.
    child.stderr.resume();
    child.once('close', code => {
      if (settled) return;
      try {
        const result = JSON.parse(output);
        if (code !== 0 || result.ok === false) return fail(result.error || 'Dispatch outcome is uncertain; reconcile native receipts, never resend');
        settled = true; clearTimeout(timer); resolvePromise(result);
      } catch { fail('Dispatch journal result unreadable; inspect receipts before retrying'); }
    });
    child.stdin.on('error', () => fail('Dispatch journal input failed'));
    child.stdin.end(JSON.stringify(input));
  });
}

export function install(ctx, {helper = invokeHelper, binding = sessionBinding} = {}) {
  const isDispatch = exec => {
    const args = dispatchArguments(exec);
    // Only the native consultation mode has the "act on nothing" envelope.
    // reply:none still enqueues executable notify work. `answers` may be
    // trimmed away by the MCP adapter, or ignored for an external caller;
    // neither is a safe shortcut around formal dispatch validation.
    // A prepared work brief cannot be reclassified as a consultation either.
    if (args && args.consult === true && !Object.hasOwn(args, 'answers')
        && (args.reply === undefined || args.reply === 'resume')
        && typeof args.message === 'string' && !/WF-(?:INTENT|DISPATCH|CONTRACT)/.test(args.message)) return null;
    return args;
  };
  ctx.on('tools/pre-execute', async (exec, next) => {
    const decision = await next();
    if (decision.kind !== 'allow') return decision;
    const args = isDispatch(exec);
    if (args === null) return decision;
    try {
      const owner = binding(exec.agent?.session?.id);
      await helper('preflight', {arguments: args, binding: owner});
      return decision;
    } catch (error) {
      return {kind: 'deny', reason: 'Workflour 派单未发送：' + error.message};
    }
  }, {prepend: true});
  ctx.on('tools/execute', async (exec, next) => {
    const args = isDispatch(exec);
    if (args === null) return next();
    const owner = binding(exec.agent?.session?.id);
    // begin repeats validation under the project lock. Concurrent calls can
    // both pass preflight but only one is allowed to enter the native tool.
    const started = await helper('begin', {arguments: args, binding: owner});
    let result, bodyError;
    try { result = await next(); } catch (error) { bodyError = error; }
    // Always reconcile after body invocation, including tool errors/cancel.
    // If the helper itself fails, the durable 'sending' state still blocks a
    // retry after restart. Native success remains distinct from file evidence.
    await helper('finish', {intent_id: started.intent_id, binding: owner});
    if (bodyError) throw bodyError;
    return result;
  }, {prepend: true});
}

export function apply(ctx) {
  if (process.env.WORKFLOUR_DISPATCH_GUARD === 'enabled') install(ctx);
}
