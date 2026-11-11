import { mkdirSync, writeFileSync, renameSync, readFileSync, unlinkSync, existsSync, realpathSync } from 'node:fs';
import { join, resolve, sep } from 'node:path';
import { homedir } from 'node:os';

export const queueRoot = () => join(process.env.DSH_HOME || join(homedir(), '.dsh'), 'workflour-session-queue');
export function within(root, cwd) { return typeof cwd === 'string' && (resolve(cwd) === root || resolve(cwd).startsWith(root + sep)); }
export function savePrivate(path, value) {
  const temp = path + '.' + process.pid + '.tmp';
  writeFileSync(temp, JSON.stringify(value, null, 2) + '\n', { mode: 0o600 });
  renameSync(temp, path);
}
export function enqueue(request, title, projectRoot, directory = queueRoot()) {
  const session = request.session;
  let cwd, root;
  try { cwd = realpathSync(session.header.cwd); root = realpathSync(projectRoot); } catch { return false; }
  if (!within(root, cwd) || !/^[A-Za-z0-9-]+$/.test(session.id)) return false;
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  savePrivate(join(directory, session.id + '.json'), { version: 1, session_id: session.id, cwd, title, queued_at: new Date().toISOString() });
  return true;
}
export function acquireConsumer(directory = queueRoot()) {
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  const path = join(directory, '.consumer.lock');
  if (existsSync(path)) {
    const prior = Number(readFileSync(path, 'utf8'));
    try { process.kill(prior, 0); return null; } catch { unlinkSync(path); }
  }
  try { writeFileSync(path, String(process.pid), { flag: 'wx', mode: 0o600 }); } catch { return null; }
  return () => { if (existsSync(path) && Number(readFileSync(path, 'utf8')) === process.pid) unlinkSync(path); };
}
