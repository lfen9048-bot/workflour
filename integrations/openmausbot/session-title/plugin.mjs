import { resolve, dirname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeFileSync } from 'node:fs';
import { enqueue } from './queue.mjs';

export const name = 'workflour-session-title';
export const inject = ['sessionTitle'];
const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');

export function deriveTitle(request, root = projectRoot) {
  const first = request.messages[0];
  if (!first) throw Error('No eligible human message');
  const cwd = request.session.header.cwd;
  if (typeof cwd !== 'string' || !(resolve(cwd) === root || resolve(cwd).startsWith(root + sep))) {
    return { title: request.currentTitle?.title || first.text.replace(/\s+/g, ' ').trim().slice(0, 80) || '会话', messageSeqs: [first.seq] };
  }
  const explicit = first.text.match(/^工作流会话标题[：:]\s*(.+)$/m)?.[1];
  const role = first.text.match(/^You are ([^,\n]{1,60}),/m)?.[1]?.replace(/^Code Team /, '') || 'Agent';
  const title = (explicit || `[${role}] 工作任务 · ${String(request.session.id).slice(0, 8)}`).replace(/[\x00-\x1f\x7f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 100);
  return { title, messageSeqs: [first.seq] };
}

export function apply(ctx) {
  // The native service owns append, cancellation, durability and user-title
  // precedence. This provider returns metadata only and makes no model calls.
  ctx.sessionTitle.register({ id: name, automatic: 'first-prompt', async generate(request) {
    const result = deriveTitle(request);
    // Queue metadata only. The desktop is the sole workspace-registry writer.
    // A queue write failure must not prevent the native title from being saved.
    try { enqueue(request, result.title, projectRoot); } catch (error) {
      const issue = `DSH 会话归组入队失败: ${error?.code || error?.name || 'Error'}; 标题仍保存，修复队列权限后需重新入队此会话`;
      process.stderr.write('[workflour] ' + issue + '\n');
      try { writeFileSync(resolve(request.session.header.cwd, '.workflour/session-title-error.json'), JSON.stringify({session_id:request.session.id, issue, at:new Date().toISOString()}), {mode:0o600}); } catch {}
    }
    return result;
  } });
}
