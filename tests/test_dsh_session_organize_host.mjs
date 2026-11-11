import { strict as assert } from 'node:assert';
import { tmpdir } from 'node:os';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { organize, restore, validateManifest } from '../scripts/dsh-session-organize-host.mjs';
const root = mkdtempSync(join(tmpdir(), 'dsh-organize-test-'));
try {
  const calls = [];
  const workspace = { path: root, id: 'workspace', sessionIds: [], async attachSession(id) { calls.push(['attach', id]); this.sessionIds.push(id); }, async detachSession(id) { calls.push(['detach', id]); }, async setTitle(title) { calls.push(['workspace-title', title]); } };
  const ctx = { workspaceRegistry: { list: () => [workspace] }, sessionController: { async rename({ sessionId, title }) { calls.push(['rename', sessionId]); return { title, seq: 4 }; } }, sessions: { get: id => ({id}) }, sessionProjectionCache: { async write(session) { calls.push(['checkpoint', session.id]); } } };
  const manifest = { schema_version: 1, project_root: root, workspaces: [{ cwd: root }], sessions: [{ session_id: 'idle', cwd: root, open_turn: false }, { session_id: 'busy', cwd: root, open_turn: true }], actions: [{ kind: 'session', operation: 'rename', session_id: 'idle', cwd: root, before_title: 'before', after_title: 'after' }] };
  const result = await organize(ctx, manifest);
  assert.deepEqual(calls, [['attach', 'idle'], ['rename', 'idle'], ['checkpoint', 'idle']]);
  assert.equal(result.find(row => row.kind === 'rename').projection_checkpoint, true);
  assert(result.some(row => row.status === 'skipped_active_or_child'));
  assert.throws(() => validateManifest({ ...manifest, actions: [{ ...manifest.actions[0], session_id: 'other' }] }), /Unverified/);
  assert.throws(() => validateManifest({ ...manifest, workspaces: [{ cwd: tmpdir() }] }), /outside/);
  await restore(ctx, manifest, {results: result}, {workspaces: [{cwd: root, before_title: 'Original workspace'}]});
  assert(calls.some(row => row[0] === 'detach' && row[1] === 'idle'));
  assert(calls.some(row => row[0] === 'workspace-title' && row[1] === 'Original workspace'));
  console.log('Native service organizer: idle-only calls and identity/scope guards passed.');
} finally { rmSync(root, { recursive: true }); }
