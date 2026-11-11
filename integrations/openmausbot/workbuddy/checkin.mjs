#!/usr/bin/env node
/** Daily CN check-in only; no model requests, other promotions, or daemon.
 * --status reads our journal only. --daily-checkin is the explicit write action.
 * Upstream billing operations are reused through client.mjs (installed 5.13.1).
 */
import { mkdir, readFile, writeFile, rename, rm, lstat } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { homedir } from 'node:os';
import { randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { BridgeError, createBridge, safeErrorCode } from './client.mjs';

export const DEFAULT_STATE_PATH = join(homedir(), '.workflour/workbuddy/checkin-state.json');
const ID = /^[0-9a-f]{24}$/;
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const OUTCOMES = new Set(['checking', 'claim_pending', 'claimed_verified', 'already_verified', 'failed', 'unconfirmed', 'unsupported']);
const VERIFIED = new Set(['claimed_verified', 'already_verified']);
const ERROR_CODE = /^[a-z][a-z0-9_]{0,79}$/;

export function beijingDay(time = Date.now()) {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(time));
  const part = type => parts.find(item => item.type === type).value;
  return `${part('year')}-${part('month')}-${part('day')}`;
}

// Kernel flock releases on process death. The small child owns no credentials,
// talks to no network, and exits when its parent's pipe closes. Persistent lock
// files are harmless; unlike timestamp/PID locks, no unsafe stale-lock deletion.
const LOCK_SCRIPT = String.raw`
import fcntl, os, stat, sys
try:
    fd = os.open(sys.argv[1], os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    if not stat.S_ISREG(os.fstat(fd).st_mode): raise ValueError('not regular')
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit(75)
except Exception:
    sys.exit(74)
print('LOCKED', flush=True)
sys.stdin.buffer.read()
os.close(fd)
`;
export async function acquireLock(lockPath) {
  await mkdir(dirname(lockPath), { recursive: true, mode: 0o700 });
  return new Promise((resolveLock, reject) => {
    const child = spawn('python3', ['-c', LOCK_SCRIPT, lockPath], { stdio: ['pipe', 'pipe', 'ignore'] });
    let acquired = false, settled = false, output = '';
    child.stdin.on('error', () => {});
    const closed = new Promise(done => child.once('close', done));
    const fail = code => { if (!settled) { settled = true; clearTimeout(timer); reject(new BridgeError(code)); } };
    const timer = setTimeout(() => { child.kill(); fail('lock_unavailable'); }, 10000);
    child.once('error', () => fail('lock_unavailable'));
    child.once('close', code => { if (!acquired) fail(code === 75 ? 'checkin_already_running' : 'lock_unavailable'); });
    child.stdout.on('data', data => {
      output += data.toString();
      if (output.includes('LOCKED\n') && !settled) {
        acquired = true; settled = true; clearTimeout(timer);
        resolveLock(async () => { child.stdin.end(); await closed; });
      }
    });
  });
}

async function readState(statePath) {
  let raw;
  try {
    const info = await lstat(statePath);
    if (!info.isFile() || info.isSymbolicLink()) throw new BridgeError('state_not_regular');
    raw = JSON.parse(await readFile(statePath, 'utf8'));
  } catch (error) {
    if (error.code === 'ENOENT') return { schemaVersion: 1, days: {} };
    throw new BridgeError(safeErrorCode(error, 'state_unreadable'));
  }
  if (raw?.schemaVersion !== 1 || !raw.days || typeof raw.days !== 'object' || Array.isArray(raw.days)) throw new BridgeError('state_invalid');
  for (const [day, entry] of Object.entries(raw.days)) {
    if (!DAY.test(day) || !entry?.accounts || typeof entry.accounts !== 'object' || Array.isArray(entry.accounts)) throw new BridgeError('state_invalid');
    for (const [id, row] of Object.entries(entry.accounts)) {
      if (!ID.test(id) || !row || !OUTCOMES.has(row.status)) throw new BridgeError('state_invalid');
    }
  }
  return raw;
}
async function writeState(statePath, state) {
  const temporary = `${statePath}.${process.pid}.${randomUUID()}.tmp`;
  try {
    await writeFile(temporary, `${JSON.stringify(state, null, 2)}\n`, { mode: 0o600, flag: 'wx' });
    await rename(temporary, statePath);
  } finally { await rm(temporary, { force: true }); }
}
function publicRow(id, row) {
  const result = { accountId: id, status: row.status, verified: row.verified === true,
    claimAttempted: row.claimAttempted === true };
  for (const key of ['startedAtMs', 'updatedAtMs', 'verifiedAtMs', 'claimedCredit']) {
    if (typeof row[key] === 'number' && Number.isFinite(row[key])) result[key] = row[key];
  }
  for (const key of ['errorCode', 'claimErrorCode', 'readbackErrorCode']) {
    if (typeof row[key] === 'string' && ERROR_CODE.test(row[key])) result[key] = row[key];
  }
  return result;
}
export async function readStatus({ statePath = DEFAULT_STATE_PATH, clock = Date.now } = {}) {
  const state = await readState(statePath), day = beijingDay(clock());
  return { schemaVersion: 1, mode: 'status', day, timezone: 'Asia/Shanghai',
    journalOnly: true, accounts: Object.entries(state.days[day]?.accounts || {}).map(([id, row]) => publicRow(id, row)) };
}

export async function runDailyCheckin({ bridge, statePath = DEFAULT_STATE_PATH, clock = Date.now } = {}) {
  const release = await acquireLock(`${statePath}.lock`);
  try {
    // Refuse to overwrite a damaged journal before any upstream action.
    const state = await readState(statePath);
    const client = bridge || await createBridge({ includeGlobal: false, clock });
    const preferences = client.getPreferences();
    const allowed = preferences.allowedAccounts.cn;
    if (!Array.isArray(allowed) || allowed.some(id => !ID.test(id))) throw new BridgeError('invalid_pool_members');
    if (!allowed.length) throw new BridgeError(preferences.enabledRegions.cn ? 'no_cn_pool_members' : 'cn_region_disabled');
    const rows = [];
    for (const id of [...new Set(allowed)]) {
      const startedAtMs = clock(), day = beijingDay(startedAtMs);
      state.days[day] ||= { accounts: {} };
      const previous = state.days[day].accounts[id];
      const row = { status: 'checking', verified: false, claimAttempted: false, startedAtMs,
        attempts: (Number.isInteger(previous?.attempts) ? previous.attempts : 0) + 1 };
      state.days[day].accounts[id] = row;
      const save = async () => { row.updatedAtMs = clock(); state.updatedAtMs = row.updatedAtMs; await writeState(statePath, state); };
      await save();
      try {
        const account = await client.resolveCredential(id, 'cn');
        if (account.accountId !== id || account.region !== 'cn') throw new BridgeError('account_identity_mismatch');
        if (account.enterprise) { row.status = 'unsupported'; row.errorCode = 'enterprise_checkin_unsupported'; }
        else {
          const before = await client.fetchCheckinStatus(id);
          if (beijingDay(clock()) !== day) throw new BridgeError('beijing_day_changed');
          if (before.todayCheckedIn === true) {
            row.status = 'already_verified'; row.verified = true; row.verifiedAtMs = clock();
          } else if (before.todayCheckedIn === false) {
            if (!before.active) throw new BridgeError('checkin_activity_inactive');
            // A prior crash/timeout after sending a claim is NOT permission to
            // send it again. Re-read can resolve it; otherwise preserve doubt.
            if (previous?.claimAttempted || previous?.verified) {
              row.claimAttempted = previous.claimAttempted === true;
              throw new BridgeError('prior_claim_not_confirmed');
            }
            row.status = 'claim_pending'; row.claimAttempted = true;
            await save(); // Journal intent before a potentially ambiguous network write.
            try {
              const claim = await client.claimDailyCheckin(id);
              if (typeof claim.credit === 'number' && Number.isFinite(claim.credit)) row.claimedCredit = claim.credit;
            } catch (error) { row.claimErrorCode = safeErrorCode(error, 'claim_failed'); }
            // A timeout may occur after the upstream commits. Only a fresh read
            // proves success; never repeat a claim just because its reply was lost.
            try {
              const after = await client.fetchCheckinStatus(id);
              if (beijingDay(clock()) !== day) throw new BridgeError('beijing_day_changed');
              if (after.todayCheckedIn !== true) throw new BridgeError('checkin_not_confirmed');
              row.status = 'claimed_verified'; row.verified = true; row.verifiedAtMs = clock();
            } catch (error) {
              row.status = 'unconfirmed'; row.readbackErrorCode = safeErrorCode(error, 'readback_failed');
            }
          } else throw new BridgeError('invalid_checkin_response');
        }
      } catch (error) {
        row.status = row.claimAttempted ? 'unconfirmed' : 'failed'; row.errorCode = safeErrorCode(error, 'checkin_failed');
      }
      await save();
      rows.push({ day, ...publicRow(id, row) });
    }
    return { schemaVersion: 1, mode: 'daily-checkin', timezone: 'Asia/Shanghai',
      day: beijingDay(clock()), ok: rows.every(row => VERIFIED.has(row.status)), accounts: rows };
  } finally { await release(); }
}

export async function main(args = process.argv.slice(2)) {
  try {
    if (args.length !== 1 || !['--status', '--daily-checkin'].includes(args[0])) throw new BridgeError('usage_status_or_daily_checkin');
    const result = args[0] === '--status' ? await readStatus() : await runDailyCheckin();
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return result.ok === false ? 1 : 0;
  } catch (error) {
    process.stdout.write(`${JSON.stringify({ ok: false, errorCode: safeErrorCode(error, 'checkin_failed') })}\n`);
    return 1;
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = await main();
