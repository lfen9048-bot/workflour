import { readdirSync, readFileSync, lstatSync, mkdirSync, unlinkSync, realpathSync } from 'node:fs';
import { resolve, join, dirname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { queueRoot, within, savePrivate, acquireConsumer } from './queue.mjs';

export const name = 'workflour-workspace-autogroup';
export const inject = ['workspaceRegistry', 'sessionPersistence', 'sessionProjectionCache', 'sessions', 'sessionTitle', 'sessionController'];
export const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const sleep = delay => new Promise(done => setTimeout(done, delay));
const cacheTitle = cache => typeof cache?.values?.title === 'string' ? cache.values.title : cache?.values?.title?.title;

export async function consume(ctx, directory = queueRoot(), root = projectRoot, onError = () => {}) {
  root = realpathSync(root);
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  const receiptRoot = join(directory, 'receipts');
  mkdirSync(receiptRoot, { recursive: true, mode: 0o700 });
  const results = [];
  for (const file of readdirSync(directory).filter(file => file !== 'diagnostics.json' && /^[A-Za-z0-9-]+\.json$/.test(file)).slice(0, 30)) {
    const path = join(directory, file);
    if (!lstatSync(path).isFile() || lstatSync(path).isSymbolicLink()) continue;
    let item;
    try { item = JSON.parse(readFileSync(path, 'utf8')); } catch { results.push({session_id: file, status: 'invalid_queue_json'}); continue; }
    if (!item || typeof item !== 'object' || Array.isArray(item) || item.version !== 1 || file !== item.session_id + '.json' || !within(root, item.cwd) || typeof item.title !== 'string' || item.title.length > 100) {
      results.push({ session_id: item?.session_id, status: 'rejected_scope_or_shape' });
      continue;
    }
    let handle;
    try {
      // A read handle takes no writer ownership and is safe alongside ACP.
      handle = await ctx.sessionPersistence.open(item.session_id, 'read');
      const cwd = realpathSync(handle.header.cwd);
      if (cwd !== realpathSync(item.cwd) || !within(root, cwd)) { results.push({session_id:item.session_id,status:'rejected_header_scope'}); continue; }
      const slice = await handle.read(0, 100000);
      if (slice.events.length >= 100000) { results.push({session_id:item.session_id,status:'deferred_large_session'}); continue; }
      const titleEvents = slice.events.filter(event => event.type === 'session/title');
      const latest = titleEvents.at(-1)?.data;
      // generate() queues before the title service commits. Never checkpoint
      // the old fallback just because the queue file arrived first.
      const expected = latest?.source?.kind === 'user' ? latest.title : item.title;
      if (!latest || latest.title !== expected) { results.push({session_id:item.session_id,status:'waiting_for_native_title'}); continue; }
      const live = ctx.sessions.get(item.session_id);
      if (live) await ctx.sessionProjectionCache.write(live);
      else {
        ctx.sessionProjectionCache.coldSnapshot(handle.header, handle.inheritedEventCount, slice.events);
        for (let attempt = 0; attempt < 100 && cacheTitle(ctx.sessionProjectionCache.cachedSnapshot(handle.header)) !== expected; attempt++) await sleep(20);
      }
      if (cacheTitle(ctx.sessionProjectionCache.cachedSnapshot(handle.header)) !== expected) { results.push({session_id:item.session_id,status:'waiting_for_projection'}); continue; }
      let workspace = ctx.workspaceRegistry.list().find(row => row.path === cwd);
      if (!workspace) workspace = await ctx.workspaceRegistry.create(cwd, '工作流 · ' + basename(cwd));
      const already = workspace.sessionIds.includes(item.session_id);
      await workspace.attachSession(item.session_id);
      // External ACP Sessions are not created in this desktop's SessionStore,
      // so no local session/created notification reached the sidebar. Publish
      // the real cold-safe public list row through its documented upsert event.
      // Do not restore a Session or invent an Agent to make it visible.
      const { items } = await ctx.sessionController.list({});
      const summary = items.find(row => row.sessionId === item.session_id);
      if (!summary) { results.push({session_id:item.session_id,status:'waiting_for_native_list'}); continue; }
      ctx.emit('api-session/added', summary);
      const receipt = { version: 1, session_id: item.session_id, cwd, title: expected, workspace_id: workspace.id, status: already ? 'already_grouped' : 'grouped', list_summary_published: true, processed_at: new Date().toISOString(), owner_pid: process.pid };
      savePrivate(join(receiptRoot, file), receipt);
      unlinkSync(path);
      results.push(receipt);
    } catch (error) { onError(error); results.push({session_id:item.session_id,status:'deferred_native_unavailable'}); }
    finally { if (handle) await handle.close(); }
  }
  const issues = results.filter(row => !['grouped', 'already_grouped'].includes(row.status))
    .map(row => `${row.session_id || 'unknown'}: ${row.status}; 保留队列，检查 DSH 桌面与原生会话后自动重试`);
  savePrivate(join(directory, 'diagnostics.json'), {checked_at: new Date().toISOString(), issues});
  return results;
}

export function apply(ctx) {
  const release = acquireConsumer();
  if (!release) return;
  let running = false, stopped = false;
  const tick = async () => {
    if (running || stopped) return;
    running = true;
    try { await consume(ctx); } catch (error) {
      const issues = [`DSH 分类器异常: ${error?.code || error?.name || 'Error'}; 检查队列目录权限，下一轮自动重试`];
      try { savePrivate(join(queueRoot(), 'diagnostics.json'), {checked_at: new Date().toISOString(), issues}); } catch {}
      process.stderr.write('[workflour] ' + issues[0] + '\n');
    }
    finally { running = false; }
  };
  ctx.effect(() => {
    const timer = setInterval(() => { void tick(); }, 3000);
    void tick();
    return () => { stopped = true; clearInterval(timer); release(); };
  }, 'workflour.autogroup.desktop-single-writer');
}
