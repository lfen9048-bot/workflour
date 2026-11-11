#!/usr/bin/env node
// Runs under the installed Electron-as-Node runtime. Calls public DSH services;
// never edits native logs, headers, workspace storage or projection caches.
import { readFileSync, writeFileSync, realpathSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';

export function validateManifest(manifest) {
  if (manifest.schema_version !== 1 || !Array.isArray(manifest.actions) || !Array.isArray(manifest.sessions)) throw Error('Invalid organization manifest');
  const root = realpathSync(manifest.project_root);
  const allowed = new Set(manifest.workspaces.map(row => realpathSync(row.cwd)));
  for (const cwd of allowed) if (cwd !== root && !cwd.startsWith(root + '/')) throw Error('Workspace outside project');
  const sessions = new Map(manifest.sessions.map(row => [row.session_id, row]));
  for (const action of manifest.actions) {
    const record = sessions.get(action.session_id);
    const verifiedCapture = action.operation === 'rename_archive' && record?.auxiliary_capture === true && record.source_kind === 'OpenMausBot memory-capture' && typeof record.bot_id === 'string' && /^omb-acp-memory-[A-Za-z0-9]+$/.test(action.cwd.split('/').pop());
    if (!verifiedCapture && !allowed.has(realpathSync(action.cwd))) throw Error('Action outside declared project workspaces');
    if (action.kind === 'session' && (!sessions.has(action.session_id) || sessions.get(action.session_id).cwd !== action.cwd)) throw Error('Unverified session identity');
  }
  return allowed;
}

export async function organize(ctx, manifest) {
  validateManifest(manifest);
  const results = [];
  for (const entry of manifest.workspaces) {
    const workspace = ctx.workspaceRegistry.list().find(row => row.path === entry.cwd);
    // The UI creates/renames workspaces first. Refuse to invent an unregistered
    // directory here; it would defeat a reviewable UI action manifest.
    if (!workspace) { results.push({ kind: 'workspace', cwd: entry.cwd, status: 'missing_registration' }); continue; }
    for (const record of manifest.sessions.filter(row => row.cwd === entry.cwd)) {
      if (record.open_turn || record.delegation_depth > 0) { results.push({ session_id: record.session_id, status: 'skipped_active_or_child' }); continue; }
      try {
        const already = workspace.sessionIds.includes(record.session_id);
        await workspace.attachSession(record.session_id);
        results.push({ kind: 'membership', session_id: record.session_id, workspace_id: workspace.id, status: already ? 'already_attached' : 'attached' });
      } catch {
        results.push({ kind: 'membership', session_id: record.session_id, status: 'failed_no_storage_edit' });
      }
    }
  }
  for (const action of manifest.actions.filter(row => row.kind === 'session' && ['rename', 'rename_archive'].includes(row.operation))) {
    const record = manifest.sessions.find(row => row.session_id === action.session_id);
    if (record.open_turn || record.delegation_depth > 0) continue;
    try {
      const accepted = await ctx.sessionController.rename({ sessionId: action.session_id, title: action.after_title });
      const session = ctx.sessions?.get(action.session_id);
      if (session && ctx.sessionProjectionCache) await ctx.sessionProjectionCache.write(session);
      results.push({ kind: 'rename', session_id: action.session_id, before_title: action.before_title, title: accepted.title, seq: accepted.seq, status: 'renamed', projection_checkpoint: Boolean(session && ctx.sessionProjectionCache) });
    } catch {
      results.push({ kind: 'rename', session_id: action.session_id, status: 'failed_or_locked_no_storage_edit' });
    }
    if (action.operation === 'rename_archive') {
      try {
        await ctx.workspaceRegistry.archiveSession(action.session_id);
        results.push({ kind: 'archive', session_id: action.session_id, before_archived: action.before_archived, status: 'archived' });
      } catch { results.push({ kind: 'archive', session_id: action.session_id, status: 'failed_or_active_not_forced' }); }
    }
  }
  return results;
}

export async function restore(ctx, manifest, receipt, workspaceBaseline) {
  validateManifest(manifest);
  const sessionIds = new Set(manifest.sessions.map(row => row.session_id));
  const workspacePaths = new Set(manifest.workspaces.map(row => row.cwd));
  if (receipt.results.some(row => row.session_id && !sessionIds.has(row.session_id))) throw Error('Undo receipt contains an unrelated session');
  if (workspaceBaseline.workspaces.some(row => !workspacePaths.has(row.cwd))) throw Error('Undo baseline contains an unrelated workspace');
  const restored = [];
  for (const result of [...receipt.results].reverse()) {
    if (result.kind === 'archive' && result.status === 'archived' && !result.before_archived) {
      await ctx.workspaceRegistry.unarchiveSession(result.session_id);
      restored.push({ kind: 'unarchive', session_id: result.session_id });
    } else if (result.kind === 'rename' && result.status === 'renamed' && result.before_title) {
      await ctx.sessionController.rename({ sessionId: result.session_id, title: result.before_title });
      const session = ctx.sessions?.get(result.session_id);
      if (session && ctx.sessionProjectionCache) await ctx.sessionProjectionCache.write(session);
      restored.push({ kind: 'restore_title', session_id: result.session_id });
    } else if (result.kind === 'membership' && result.status === 'attached') {
      const workspace = ctx.workspaceRegistry.list().find(row => row.id === result.workspace_id);
      if (workspace) await workspace.detachSession(result.session_id);
      restored.push({ kind: 'detach_added_membership', session_id: result.session_id });
    }
  }
  for (const entry of workspaceBaseline.workspaces) {
    const workspace = ctx.workspaceRegistry.list().find(row => row.path === entry.cwd);
    if (!workspace) continue;
    if (entry.before_title === null) await ctx.workspaceRegistry.delete(workspace.id);
    else await workspace.setTitle(entry.before_title);
    restored.push({ kind: 'restore_workspace_registration', cwd: entry.cwd });
  }
  return restored;
}

async function main() {
  const args = process.argv.slice(2);
  const arg = flag => args[args.indexOf(flag) + 1];
  if (!args.includes('--manifest') || !args.includes('--out')) throw Error('--manifest and --out required');
  const manifest = JSON.parse(readFileSync(arg('--manifest'), 'utf8'));
  validateManifest(manifest);
  if (!args.includes('--apply')) {
    writeFileSync(arg('--out'), JSON.stringify({ status: 'validated_not_applied', actions: manifest.actions.length }) + '\n', { flag: 'wx', mode: 0o600 });
    return;
  }
  if (!args.includes('--desktop-stopped')) throw Error('Close idle DSH desktop and verify ACP workers idle before --apply');
  const resources = process.env.DSH_APP_RESOURCES || '/Applications/DeepSeek Harness.app/Contents/Resources';
  const modules = join(resources, 'app.asar/dsh/node_modules/@deepseek-ai');
  const { loadProfileDirectory, loadLayeredEnv } = await import(pathToFileURL(join(modules, 'dsh-app-boot/lib/index.js')).href);
  const { runProfile } = await import(pathToFileURL(join(modules, 'dsh/lib/profile-boot.js')).href);
  const home = manifest.dsh_home;
  const installAnchor = join(modules, 'dsh/package.json');
  const profile = loadProfileDirectory('dsh', join(home, 'profiles/desktop'), installAnchor);
  const application = await runProfile({ environment: loadLayeredEnv('dsh'), profile: 'desktop', resolvedProfile: { profile, installAnchor }, patchFiles: [], args: ['--no-open', '--host', '127.0.0.1', '--port', '0'] });
  try {
    const undo = args.includes('--undo');
    const results = undo
      ? await restore(application.ctx, manifest, JSON.parse(readFileSync(arg('--receipt'), 'utf8')), JSON.parse(readFileSync(arg('--baseline'), 'utf8')))
      : await organize(application.ctx, manifest);
    writeFileSync(arg('--out'), JSON.stringify({ status: undo ? 'restored_via_native_services' : 'applied_via_native_services', results }, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  } finally { await application.shutdown.shutdown(0); }
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(new URL(import.meta.url).pathname)) main().catch(() => { process.stderr.write('Native DSH organization failed; no direct storage fallback was used.\n'); process.exitCode = 1; });
