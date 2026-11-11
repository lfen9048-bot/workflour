import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, rm, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { BridgeError, createBridge, loadPlugin, loadPreferences, normalizePreferences, safeErrorCode, summarizeCredits } from '../integrations/openmausbot/workbuddy/client.mjs';
import { acquireLock, beijingDay, readStatus, runDailyCheckin } from '../integrations/openmausbot/workbuddy/checkin.mjs';

const A = 'a'.repeat(24), B = 'b'.repeat(24), C = 'c'.repeat(24), G = 'd'.repeat(24), H = 'e'.repeat(24), I = 'f'.repeat(24);
const NOW = Date.parse('2026-11-11T02:00:00Z');
const SECRET = 'never-output-this-token-or-email@example.invalid';
const preferences = () => normalizePreferences({ accounts: { cn: A }, regions: {
  cn: { pool: { enabled: true, memberAccountIds: [A, B], orderAccountIds: [B, A] } },
  global: { enabled: true },
} });
async function sandbox(t) {
  const dir = await mkdtemp(join(tmpdir(), 'workflour-checkin-'));
  t.after(() => rm(dir, { recursive: true, force: true }));
  return { dir, statePath: join(dir, 'state.json') };
}
function fakeRuntime(options = {}) {
  const calls = [], credentials = { [A]: { id: A, token: SECRET, domain: 'cn' }, [B]: { id: B, token: SECRET, domain: 'cn' }, [C]: { id: C, token: SECRET, domain: 'cn' }, [G]: { id: G, token: SECRET, domain: 'global' }, [H]: { id: H, token: SECRET, domain: 'global' }, [I]: { id: I, token: SECRET, domain: 'global' } };
  class Store {
    constructor({ region, refresh }) { this.region = region; this.refresh = refresh; calls.push(['store', region]); }
    selectAccount(id) { this.id = id; calls.push(['select', id, this.region]); }
    async current() { calls.push(['current', this.id, this.region]); return credentials[this.id || (this.region === 'global' ? G : C)]; }
    async resolve() {
      calls.push(['resolve', this.id, this.region]);
      if (options.resolveError) throw options.resolveError;
      if (options.mismatch) return credentials[C];
      return this.refresh(await this.current());
    }
  }
  class Client {
    async refreshToken(value) { calls.push(['refresh', value?.id]); return value; }
    async fetchModels(value, signal, keepModelIds) {
      calls.push(['models', value.id, keepModelIds]);
      if (options.models) return options.models(value, signal, keepModelIds);
      return [{ id: 'ds', name: 'DeepSeek', creditMultiplier: 0.5, promos: [{ title: 'free until yesterday', endsAt: NOW - 1000 }], privateToken: SECRET }];
    }
    async fetchCredits(value) { calls.push(['credits', value.id]); return { packages: [{ packageName: 'daily', remain: 9, size: 10, monthly: false, expiresAtMs: NOW + 86400000 }], token: SECRET }; }
    async fetchCheckinStatus(value) { calls.push(['status', value.id]); return { active: true, todayCheckedIn: false, privateToken: SECRET }; }
    async claimDailyCheckin(value) { calls.push(['claim', value.id]); return { credit: 10, privateToken: SECRET }; }
  }
  return { runtime: { WorkBuddyCredentialStore: Store, WorkBuddyUpstreamClient: Client, workbuddyAccountId: c => c.id, regionOf: domain => domain }, calls, credentials };
}
function fakeCheckin(overrides = {}) {
  const calls = [], checked = new Set();
  const bridge = {
    getPreferences: preferences,
    async resolveCredential(id, region) { calls.push(['resolve', id]); return { accountId: id, region, enterprise: false, available: true }; },
    async fetchCheckinStatus(id) { calls.push(['status', id]); return { active: true, todayCheckedIn: checked.has(id) }; },
    async claimDailyCheckin(id) { calls.push(['claim', id]); checked.add(id); return { credit: 10 }; },
    ...overrides,
  };
  return { bridge, calls, checked };
}

test('preferences include only checked CN members and selected global; region off is respected', () => {
  const p = preferences();
  assert.deepEqual(p.allowedAccounts, { cn: [A, B], global: [] });
  assert.deepEqual(p.pools.cn.orderAccountIds, [B, A]);
  assert.equal(p.selectedAccounts.cn, A);
  assert.deepEqual(normalizePreferences({ accounts: { global: G }, regions: { cn: { enabled: false, pool: { memberAccountIds: [A] } } } }).allowedAccounts, { cn: [], global: [G] });
  assert.throws(() => normalizePreferences({ regions: { cn: { pool: { memberAccountIds: ['not-an-id'] } } } }), /invalid_account_id/);
  assert.deepEqual(p.enabledModelIds, { cn: [], global: [] });
  assert.deepEqual(p.imageModelIds, { cn: [], global: [] });
  assert.throws(() => normalizePreferences({ regions: { global: { enabledModelIds: [123] } } }), /invalid_model_preferences/);
});

test('image preferences preserve empty opt-out and exact regional IDs and reject malformed values', () => {
  const p = normalizePreferences({ regions: { cn: { imageModelIds: [] }, global: { imageModelIds: ['deepseek-v4.1-flash', 'deepseek-v4.1-flash'] } } });
  assert.deepEqual(p.imageModelIds, { cn: [], global: ['deepseek-v4.1-flash'] });
  assert.equal(p.imageModelIds.global.includes('deepseek-v4.1-flash-sg'), false);
  for (const invalid of [null, false, 'model', [123], [''], ['  '], ['x'.repeat(513)]]) {
    assert.throws(() => normalizePreferences({ regions: { global: { imageModelIds: invalid } } }), /invalid_image_preferences/);
  }
});

test('global pool enablement allows only checked members while disabled and region-off remain restricted', () => {
  const raw = { accounts: { global: G }, regions: { global: { pool: { enabled: true, memberAccountIds: [H, I], orderAccountIds: [I, H] } } } };
  const enabled = normalizePreferences(raw);
  assert.deepEqual(enabled.allowedAccounts.global, [H, I]);assert.deepEqual(enabled.pools.global.orderAccountIds, [I, H]);
  raw.regions.global.pool.enabled = false;
  assert.deepEqual(normalizePreferences(raw).allowedAccounts.global, [G]);
  raw.regions.global.pool.enabled = true;raw.regions.global.enabled = false;
  assert.deepEqual(normalizePreferences(raw).allowedAccounts.global, []);
});

test('standalone loader rejects unsupported plugin before importing code', async t => {
  const { dir } = await sandbox(t);
  await writeFile(join(dir, 'package.json'), JSON.stringify({ name: 'dsh-connect-workbuddy', version: '5.14.0' }));
  await assert.rejects(loadPlugin({ packageDir: dir }), /unsupported_plugin_version/);
});

test('loader imports standalone exports without evaluating the host entry', async t => {
  const { dir } = await sandbox(t);
  await mkdir(join(dir, 'lib'));
  await writeFile(join(dir, 'package.json'), JSON.stringify({ name: 'dsh-connect-workbuddy', version: '5.13.1', type: 'module' }));
  await writeFile(join(dir, 'lib/index.js'), 'import { C as WorkBuddyCredentialStore, V as WorkBuddyUpstreamClient, F as workbuddyAccountId, c as WORKBUDDY_CONNECT_VERSION, it as regionOf } from "./chunk.js";\nthrow new Error("host entry must not evaluate");');
  await writeFile(join(dir, 'lib/chunk.js'), 'export class C {} export class V {} export const F = c => c.id; export const c = "5.13.1"; export const it = d => d;');
  const loaded = await loadPlugin({ packageDir: dir });
  assert.equal(loaded.version, '5.13.1'); assert.equal(typeof loaded.WorkBuddyCredentialStore, 'function');
});

test('YAML reader returns allowlisted preferences and no secret configuration', async t => {
  const { dir } = await sandbox(t);
  await writeFile(join(dir, 'package.json'), JSON.stringify({ name: 'dsh-connect-workbuddy', version: '5.13.1' }));
  const path = join(dir, 'prefs.yml');
  await writeFile(path, `plugins:\n  - id: dsh-connect-workbuddy\n    name: dsh-connect-workbuddy\n    config:\n      secretToken: ${SECRET}\n      accounts:\n        cn: ${A}\n      regions:\n        cn:\n          enabledModelIds: [cn-selected]\n          imageModelIds: []\n          pool:\n            enabled: true\n            memberAccountIds: [${A}, ${B}]\n        global:\n          enabledModelIds: [global-selected, global-selected]\n          imageModelIds: [deepseek-v4.1-flash, deepseek-v4.1-flash]\n`);
  const p = await loadPreferences({ desktopPatchPath: path, packageDir: dir });
  assert.deepEqual(p.allowedAccounts.cn, [A, B]);
  assert.deepEqual(p.enabledModelIds, { cn: ['cn-selected'], global: ['global-selected'] });
  assert.deepEqual(p.imageModelIds, { cn: [], global: ['deepseek-v4.1-flash'] });
  assert.ok(!JSON.stringify(p).includes(SECRET));
  await writeFile(path, 'plugins:\n  - id: dsh-connect-workbuddy\n    config:\n      regions:\n        global:\n          imageModelIds: [123]\n');
  await assert.rejects(loadPreferences({ desktopPatchPath: path, packageDir: dir }), /invalid_image_preferences/);
  await writeFile(path, 'entries: []');
  await assert.rejects(loadPreferences({ desktopPatchPath: path, packageDir: dir }), /preferences_unreadable/);
});

test('bridge resolves implicit global current once, never includes unchecked CN, and exposes no credentials', async () => {
  const fake = fakeRuntime();
  const bridge = await createBridge({ preferences: preferences(), runtime: fake.runtime, clock: () => NOW });
  assert.deepEqual(bridge.getPreferences().allowedAccounts, { cn: [A, B], global: [G] });
  const accounts = await bridge.listAccounts();
  assert.deepEqual(accounts.cn.map(a => a.accountId), [A, B]);
  assert.equal(accounts.global[0].accountId, G);
  const resolved = await bridge.resolveCredential(B, 'cn');
  assert.equal(resolved.accountId, B);
  assert.ok(fake.calls.some(c => c[0] === 'refresh' && c[1] === B));
  await assert.rejects(bridge.fetchCredits('cn', C), /account_not_allowed/);
  const outputs = [accounts, resolved, await bridge.fetchModels('global', G), await bridge.fetchCredits('cn', A), await bridge.fetchCheckinStatus(B), await bridge.claimDailyCheckin(B)];
  assert.ok(!JSON.stringify(outputs).includes(SECRET));
  assert.equal(outputs[2].models[0].promos[0].endsAt, NOW - 1000); // raw public validity preserved, not declared free
});

test('CN-only checkin bridge does not resolve/read a global credential', async () => {
  const fake = fakeRuntime();
  const bridge = await createBridge({ preferences: preferences(), runtime: fake.runtime, includeGlobal: false });
  await bridge.listAccounts();
  assert.deepEqual(bridge.getPreferences().allowedAccounts.global, []);
  assert.equal(fake.calls.some(c => c[0] === 'store' && c[1] === 'global'), false);
});

test('enabled global pool survives implicit current-account lookup without adding an unchecked current account', async () => {
  const p = normalizePreferences({ accounts: { cn: A }, regions: {
    cn: { pool: { enabled: true, memberAccountIds: [A, B] } },
    global: { pool: { enabled: true, memberAccountIds: [H, I] } },
  } });
  const fake = fakeRuntime(), bridge = await createBridge({ preferences: p, runtime: fake.runtime });
  assert.equal(bridge.getPreferences().selectedAccounts.global, G);
  assert.deepEqual(bridge.getPreferences().allowedAccounts, { cn: [A, B], global: [H, I] });
  const roster = await bridge.listAccounts();assert.deepEqual(roster.global.map(a => a.accountId), [H, I]);
  assert.equal(roster.cn.length + roster.global.length, 4);
  await bridge.fetchModels('global', H);await bridge.fetchCredits('global', I);
  await assert.rejects(bridge.fetchModels('global', G), /account_not_allowed/);
  assert.equal(fake.calls.some(c => c[0] === 'select' && c[1] === G), false);
  assert.deepEqual(p.allowedAccounts.global, [H, I]); // Caller configuration is not mutated.
});

test('disabled global pool keeps only the explicitly selected account even with other checked members', async () => {
  const p = normalizePreferences({ accounts: { global: G }, regions: { global: { pool: { enabled: false, memberAccountIds: [H, I] } } } });
  const fake = fakeRuntime(), bridge = await createBridge({ preferences: p, runtime: fake.runtime });
  assert.deepEqual((await bridge.listAccounts()).global.map(a => a.accountId), [G]);
  await assert.rejects(bridge.fetchModels('global', H), /account_not_allowed/);
  assert.equal(fake.calls.some(c => c[0] === 'select' && [H, I].includes(c[1])), false);
});

test('global region off and includeGlobal false never read or use enabled global pool accounts', async () => {
  for (const regionEnabled of [false, true]) {
    const p = normalizePreferences({ regions: { global: { enabled: regionEnabled, pool: { enabled: true, memberAccountIds: [G, H] } } } });
    const fake = fakeRuntime(), bridge = await createBridge({ preferences: p, runtime: fake.runtime, includeGlobal: regionEnabled ? false : true });
    assert.deepEqual((await bridge.listAccounts()).global, []);
    assert.deepEqual(bridge.getPreferences().allowedAccounts.global, []);
    await assert.rejects(bridge.fetchModels('global', G), regionEnabled ? /account_not_allowed/ : /region_disabled/);
    assert.equal(fake.calls.some(c => c[0] === 'store' && c[1] === 'global'), false);
  }
});

test('enabled but empty global pool does not fall back to the native current account', async () => {
  const p = normalizePreferences({ regions: { global: { pool: { enabled: true, memberAccountIds: [] } } } });
  const fake = fakeRuntime(), bridge = await createBridge({ preferences: p, runtime: fake.runtime });
  assert.equal(bridge.getPreferences().selectedAccounts.global, G);
  assert.deepEqual(bridge.getPreferences().allowedAccounts.global, []);
  assert.deepEqual((await bridge.listAccounts()).global, []);
  await assert.rejects(bridge.fetchModels('global', G), /account_not_allowed/);
});

test('global pool member identity or region mismatch is rejected before metadata requests', async () => {
  for (const kind of ['identity', 'region']) {
    const p = normalizePreferences({ accounts: { global: G }, regions: { global: { pool: { enabled: true, memberAccountIds: [G, H] } } } });
    const fake = fakeRuntime();
    if (kind === 'identity') fake.credentials[H] = { ...fake.credentials[I] };
    else fake.credentials[H].domain = 'cn';
    const bridge = await createBridge({ preferences: p, runtime: fake.runtime });
    await assert.rejects(bridge.fetchModels('global', H), kind === 'identity' ? /account_identity_mismatch/ : /account_region_mismatch/);
    assert.equal(fake.calls.some(c => c[0] === 'models'), false);
  }
});

test('implicit global current lookup rejects a credential from another region', async () => {
  const fake = fakeRuntime();fake.credentials[G].domain = 'cn';
  await assert.rejects(createBridge({ preferences: preferences(), runtime: fake.runtime }), /account_region_mismatch/);
  assert.equal(fake.calls.some(c => ['models', 'credits', 'refresh'].includes(c[0])), false);
});

test('model fetch passes regional selected IDs to native live-roster filter without fabricating retired IDs', async () => {
  const p = normalizePreferences({ accounts: { cn: A, global: G }, regions: {
    cn: { pool: { memberAccountIds: [A] }, enabledModelIds: ['cn-extra'] },
    global: { enabledModelIds: ['global-ordinary', 'retired-selected'] },
  } });
  const fake = fakeRuntime({ models: (_value, signal, keep) => {
    assert.equal(signal, undefined);
    const published = [{ id: 'global-sg', name: 'SG' }, { id: 'global-ordinary', name: 'Ordinary', creditMultiplier: 0 }];
    return published.filter(m => m.id === 'global-sg' || keep.includes(m.id));
  } });
  const bridge = await createBridge({ preferences: p, runtime: fake.runtime });
  const result = await bridge.fetchModels('global', G);
  assert.deepEqual(fake.calls.find(c => c[0] === 'models')[2], ['global-ordinary', 'retired-selected']);
  assert.deepEqual(result.models.map(m => m.id), ['global-sg', 'global-ordinary']);
  assert.equal(result.models.some(m => m.id === 'retired-selected' || m.id === 'cn-extra'), false);
  assert.equal(result.models[1].creditMultiplier, 0);
});

test('bridge fails closed on identity mismatch and sanitizes raw errors', async () => {
  const fake = fakeRuntime({ mismatch: true });
  const bridge = await createBridge({ preferences: preferences(), runtime: fake.runtime, includeGlobal: false });
  await assert.rejects(bridge.resolveCredential(A, 'cn'), /account_identity_mismatch/);
  const bad = fakeRuntime({ resolveError: new Error(SECRET) });
  const bridge2 = await createBridge({ preferences: preferences(), runtime: bad.runtime, includeGlobal: false });
  await assert.rejects(bridge2.resolveCredential(A, 'cn'), error => error.message === 'credential_unavailable' && !JSON.stringify(error).includes(SECRET));
  assert.equal(safeErrorCode(new Error(SECRET)), 'upstream_failed');
});

test('a refreshed credential cannot silently change region', async () => {
  const fake = fakeRuntime(); fake.credentials[A].domain = 'global';
  const bridge = await createBridge({ preferences: preferences(), runtime: fake.runtime, includeGlobal: false });
  await assert.rejects(bridge.fetchCredits('cn', A), /account_region_mismatch/);
  assert.equal(fake.calls.some(c => c[0] === 'credits'), false);
});

test('bridge blocks enterprise checkin before any status/claim request', async () => {
  const fake = fakeRuntime(); fake.credentials[A].enterpriseId = 'enterprise';
  const bridge = await createBridge({ preferences: preferences(), runtime: fake.runtime, includeGlobal: false });
  await assert.rejects(bridge.fetchCheckinStatus(A), /enterprise_checkin_unsupported/);
  await assert.rejects(bridge.claimDailyCheckin(A), /enterprise_checkin_unsupported/);
  assert.equal(fake.calls.some(c => ['status', 'claim'].includes(c[0])), false);
});

test('credit summary counts future one-off expiry, never monthly refresh or expired packages', () => {
  const credit = summarizeCredits({ packages: [
    { packageName: 'monthly', remain: 40, size: 50, monthly: true, refreshAtMs: NOW + 1000 },
    { packageName: 'tomorrow', remain: 10, size: 10, monthly: false, expiresAtMs: NOW + 86400000 },
    { packageName: 'later', remain: 20, size: 20, monthly: false, expiresAtMs: NOW + 5 * 86400000 },
    { packageName: 'expired', remain: 200, size: 200, monthly: false, expiresAtMs: NOW },
    { packageName: 'unknown', remain: 3, size: 3, monthly: false },
  ] }, NOW);
  assert.equal(credit.total, 73); assert.equal(credit.expiringSoon, 10);
  assert.equal(credit.nearestExpiryMs, NOW + 86400000);
  assert.equal(credit.expiringSoonEarliestExpiryMs, NOW + 86400000);
  assert.equal(credit.packages[0].refreshAtMs, NOW + 1000);
});

test('Beijing date changes at 16:00 UTC, not host midnight', () => {
  assert.equal(beijingDay(Date.parse('2026-11-10T15:59:59Z')), '2026-11-10');
  assert.equal(beijingDay(Date.parse('2026-11-10T16:00:00Z')), '2026-11-11');
});

test('two selected CN members each query, claim, read back; same-day rerun queries without claiming', async t => {
  const { statePath } = await sandbox(t), fake = fakeCheckin();
  let result = await runDailyCheckin({ bridge: fake.bridge, statePath, clock: () => NOW });
  assert.equal(result.ok, true); assert.deepEqual(result.accounts.map(a => a.status), ['claimed_verified', 'claimed_verified']);
  assert.deepEqual(fake.calls.filter(c => c[0] === 'claim'), [['claim', A], ['claim', B]]);
  assert.equal(fake.calls.filter(c => c[0] === 'status').length, 4);
  fake.calls.length = 0;
  result = await runDailyCheckin({ bridge: fake.bridge, statePath, clock: () => NOW + 1000 });
  assert.equal(result.ok, true); assert.ok(result.accounts.every(a => a.status === 'already_verified'));
  assert.equal(fake.calls.filter(c => c[0] === 'claim').length, 0);
  assert.equal(fake.calls.filter(c => c[0] === 'status').length, 2);
  assert.equal((await stat(statePath)).mode & 0o777, 0o600);
});

test('one account failing does not block the other and raw errors never enter journal', async t => {
  const { statePath } = await sandbox(t), fake = fakeCheckin();
  fake.bridge.resolveCredential = async (id, region) => { if (id === A) throw new Error(SECRET); return { accountId: id, region }; };
  const result = await runDailyCheckin({ bridge: fake.bridge, statePath, clock: () => NOW });
  assert.equal(result.ok, false); assert.equal(result.accounts[0].status, 'failed');
  assert.equal(result.accounts[1].status, 'claimed_verified');
  assert.ok(!(await readFile(statePath, 'utf8')).includes(SECRET));
});

test('enterprise and inactive accounts cause no claim', async t => {
  const { statePath } = await sandbox(t), fake = fakeCheckin();
  fake.bridge.resolveCredential = async (id, region) => ({ accountId: id, region, enterprise: id === A });
  fake.bridge.fetchCheckinStatus = async () => ({ active: false, todayCheckedIn: false });
  const result = await runDailyCheckin({ bridge: fake.bridge, statePath, clock: () => NOW });
  assert.deepEqual(result.accounts.map(a => a.status), ['unsupported', 'failed']);
  assert.equal(fake.calls.some(c => c[0] === 'claim'), false);
});

test('already checked in remains verified when activity is inactive', async t => {
  const { statePath } = await sandbox(t), fake = fakeCheckin();
  fake.bridge.fetchCheckinStatus = async () => ({ active: false, todayCheckedIn: true });
  const result = await runDailyCheckin({ bridge: fake.bridge, statePath, clock: () => NOW });
  assert.equal(result.ok, true);
  assert.ok(result.accounts.every(row => row.status === 'already_verified' && row.verified));
  assert.equal(fake.calls.some(c => c[0] === 'claim'), false);
});

test('timeout after successful upstream claim is success only after readback', async t => {
  const { statePath } = await sandbox(t), fake = fakeCheckin();
  fake.bridge.claimDailyCheckin = async id => { fake.checked.add(id); const e = new Error(SECRET); e.name = 'TimeoutError'; throw e; };
  const result = await runDailyCheckin({ bridge: fake.bridge, statePath, clock: () => NOW });
  assert.equal(result.ok, true);
  assert.ok(result.accounts.every(a => a.verified && a.claimErrorCode === 'request_timeout'));
});

test('claim reply without positive readback stays unconfirmed and is never blindly retried', async t => {
  const { statePath } = await sandbox(t), fake = fakeCheckin();
  fake.bridge.claimDailyCheckin = async id => { fake.calls.push(['claim', id]); return { credit: 10 }; };
  const first = await runDailyCheckin({ bridge: fake.bridge, statePath, clock: () => NOW });
  assert.equal(first.ok, false); assert.ok(first.accounts.every(a => a.status === 'unconfirmed' && !a.verified));
  fake.calls.length = 0;
  const second = await runDailyCheckin({ bridge: fake.bridge, statePath, clock: () => NOW });
  assert.equal(second.ok, false); assert.ok(second.accounts.every(a => a.errorCode === 'prior_claim_not_confirmed'));
  assert.equal(fake.calls.some(c => c[0] === 'claim'), false);
});

test('readback network failure is not reported as verified', async t => {
  const { statePath } = await sandbox(t), fake = fakeCheckin();
  fake.bridge.fetchCheckinStatus = async id => { if (fake.checked.has(id)) throw new Error(SECRET); return { active: true, todayCheckedIn: false }; };
  const result = await runDailyCheckin({ bridge: fake.bridge, statePath, clock: () => NOW });
  assert.equal(result.ok, false); assert.ok(result.accounts.every(a => a.status === 'unconfirmed' && a.readbackErrorCode === 'readback_failed'));
});

test('crossing Beijing midnight does not credit yesterday from a new-day readback', async t => {
  const { statePath } = await sandbox(t), fake = fakeCheckin();
  let now = Date.parse('2026-11-10T15:59:59Z');
  fake.bridge.claimDailyCheckin = async id => { fake.checked.add(id); now = Date.parse('2026-11-10T16:00:01Z'); return { credit: 10 }; };
  const result = await runDailyCheckin({ bridge: fake.bridge, statePath, clock: () => now });
  assert.equal(result.accounts[0].status, 'unconfirmed');
  assert.equal(result.accounts[0].readbackErrorCode, 'beijing_day_changed');
  assert.equal(result.accounts[0].day, '2026-11-10');
  assert.equal(result.accounts[1].day, '2026-11-11');
});

test('status is only a local journal read and reports absence without claiming success', async t => {
  const { statePath } = await sandbox(t);
  const result = await readStatus({ statePath, clock: () => NOW });
  assert.equal(result.journalOnly, true); assert.deepEqual(result.accounts, []);
  const child = spawnSync(process.execPath, ['integrations/openmausbot/workbuddy/checkin.mjs', '--invalid'], { encoding: 'utf8' });
  assert.equal(child.status, 1); assert.equal(JSON.parse(child.stdout).errorCode, 'usage_status_or_daily_checkin');
});

test('damaged journal is preserved and blocks all upstream calls', async t => {
  const { statePath } = await sandbox(t), fake = fakeCheckin();
  await writeFile(statePath, '{broken');
  await assert.rejects(runDailyCheckin({ bridge: fake.bridge, statePath, clock: () => NOW }), /state_unreadable/);
  assert.equal(fake.calls.length, 0); assert.equal(await readFile(statePath, 'utf8'), '{broken');
});

test('kernel lock excludes concurrent invocation, releases normally, and leaves reusable file', async t => {
  const { statePath } = await sandbox(t), lockPath = `${statePath}.lock`;
  const release = await acquireLock(lockPath);
  await assert.rejects(acquireLock(lockPath), /checkin_already_running/);
  await release();
  const again = await acquireLock(lockPath); await again();
});

test('empty selection fails closed instead of using another native default account', async t => {
  const { statePath } = await sandbox(t), fake = fakeCheckin();
  fake.bridge.getPreferences = () => normalizePreferences({});
  await assert.rejects(runDailyCheckin({ bridge: fake.bridge, statePath }), /no_cn_pool_members/);
  assert.equal(fake.calls.length, 0);
});
