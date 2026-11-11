/**
 * Local, secret-free facade over the INSTALLED dsh-connect-workbuddy 5.13.1.
 * Upstream: https://github.com/dingminhua/dsh-connect-workbuddy
 * MIT, Copyright (c) 2026 LaoDing. No upstream sources are vendored/modified.
 * Only the official standalone CLI's dependency chunk is imported here. The
 * host entry has DSH peer dependencies and must only be imported by the host.
 */
import { readFile, realpath } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname, join, resolve, sep } from 'node:path';
import { pathToFileURL } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);
export const SUPPORTED_PLUGIN_VERSION = '5.13.1';
export const DEFAULT_PACKAGE_DIR = join(homedir(), '.dsh/profiles/desktop/node_modules/dsh-connect-workbuddy');
export const DEFAULT_PATCH_PATH = join(homedir(), '.dsh/profiles/desktop/cordis.patch.yml');
const ACCOUNT_ID = /^[0-9a-f]{24}$/;
const REGIONS = ['cn', 'global'];

export class BridgeError extends Error {
  constructor(code) { super(code); this.name = 'BridgeError'; this.code = code; }
}
export function safeErrorCode(error, fallback = 'upstream_failed') {
  if (error instanceof BridgeError) return error.code;
  if (error?.name === 'TimeoutError' || error?.name === 'AbortError') return 'request_timeout';
  if (error?.code === 'WORKBUDDY_ENCRYPTED_CREDENTIAL') return 'credential_unreadable';
  if (error?.code === 'WORKBUDDY_CREDENTIAL_REJECTED') return 'credential_rejected';
  return fallback; // Never echo upstream error messages, URLs, or credentials.
}
async function guarded(fn, fallback) {
  try { return await fn(); } catch (error) { throw new BridgeError(safeErrorCode(error, fallback)); }
}
function accountId(value, optional = false) {
  if (optional && (value === undefined || value === null || value === '')) return undefined;
  if (typeof value !== 'string' || !ACCOUNT_ID.test(value)) throw new BridgeError('invalid_account_id');
  return value;
}
function ids(values) {
  if (values === undefined) return [];
  if (!Array.isArray(values)) throw new BridgeError('invalid_pool_members');
  return [...new Set(values.map(value => accountId(value)))];
}
async function packageMetadata(packageDir) {
  return guarded(async () => {
    const actualDir = await realpath(packageDir);
    const pkg = JSON.parse(await readFile(join(actualDir, 'package.json'), 'utf8'));
    if (pkg.name !== 'dsh-connect-workbuddy' || pkg.version !== SUPPORTED_PLUGIN_VERSION) {
      throw new BridgeError('unsupported_plugin_version');
    }
    return { version: pkg.version, packageDir: actualDir };
  }, 'plugin_unavailable');
}

export async function loadPlugin({ packageDir = DEFAULT_PACKAGE_DIR } = {}) {
  const metadata = await packageMetadata(packageDir);
  return guarded(async () => {
    const modulePath = join(metadata.packageDir, 'lib/index.js');
    const source = await readFile(modulePath, 'utf8');
    const match = source.match(/^import \{([^}]+)\} from ["'](\.\/[^"']+)["'];/);
    if (!match) throw new BridgeError('plugin_exports_changed');
    const standaloneModulePath = await realpath(resolve(dirname(modulePath), match[2]));
    if (!standaloneModulePath.startsWith(join(metadata.packageDir, 'lib') + sep)) throw new BridgeError('plugin_exports_changed');
    const aliases = new Map(match[1].split(',').map(item => {
      const pair = item.trim().split(/\s+as\s+/); return [pair[1], pair[0]];
    }));
    const chunk = await import(pathToFileURL(standaloneModulePath).href);
    const exported = {};
    for (const name of ['WorkBuddyCredentialStore', 'WorkBuddyUpstreamClient', 'workbuddyAccountId', 'regionOf']) {
      exported[name] = chunk[aliases.get(name)];
      if (typeof exported[name] !== 'function') throw new BridgeError('plugin_exports_changed');
    }
    if (chunk[aliases.get('WORKBUDDY_CONNECT_VERSION')] !== SUPPORTED_PLUGIN_VERSION) throw new BridgeError('plugin_exports_changed');
    return { ...metadata, modulePath, standaloneModulePath, ...exported };
  }, 'plugin_load_failed');
}

// YAML stays in Ruby; only these preference fields cross the stdout boundary.
// Neither credentials nor the full configuration can reach this module/output.
const READ_PREFERENCES_RUBY = String.raw`
require 'yaml'
require 'json'
root = YAML.load_file(ARGV.fetch(0))
matches = []
walk = lambda do |v|
  if v.is_a?(Hash)
    if v['id'] == 'dsh-connect-workbuddy' || v['name'] == 'dsh-connect-workbuddy'
      matches << (v['config'] || {})
    else
      v.each_value { |x| walk.call(x) }
    end
  elsif v.is_a?(Array)
    v.each { |x| walk.call(x) }
  end
end
walk.call(root)
raise 'entry_count' unless matches.length == 1
c = matches[0]
out = {'accounts'=>{}, 'regions'=>{}}
%w[cn global].each do |r|
  out['accounts'][r] = (c['accounts'] || {})[r]
  v = (c['regions'] || {})[r] || {}
  p = v['pool'] || {}
  out['regions'][r] = {'enabled'=>v.fetch('enabled', true), 'enabledModelIds'=>v.fetch('enabledModelIds', []), 'pool'=>{
    'enabled'=>p.fetch('enabled', false), 'memberAccountIds'=>p.fetch('memberAccountIds', []),
    'orderAccountIds'=>p.fetch('orderAccountIds', [])}}
end
STDOUT.write(JSON.generate(out))
`;

export function normalizePreferences(raw, pluginVersion = SUPPORTED_PLUGIN_VERSION) {
  const pools = {}, selectedAccounts = {}, enabledRegions = {}, enabledModelIds = {};
  for (const region of REGIONS) {
    const r = raw.regions?.[region] || {}, p = r.pool || {};
    if (r.enabled !== undefined && typeof r.enabled !== 'boolean') throw new BridgeError('invalid_region_preferences');
    if (p.enabled !== undefined && typeof p.enabled !== 'boolean') throw new BridgeError('invalid_pool_preferences');
    const models = r.enabledModelIds ?? [];
    if (!Array.isArray(models) || models.some(id => typeof id !== 'string' || !id.trim() || id.length > 512)) throw new BridgeError('invalid_model_preferences');
    enabledModelIds[region] = [...new Set(models)];
    enabledRegions[region] = r.enabled !== false;
    selectedAccounts[region] = accountId(raw.accounts?.[region], true);
    pools[region] = { enabled: p.enabled === true, memberAccountIds: ids(p.memberAccountIds), orderAccountIds: ids(p.orderAccountIds) };
  }
  return { pluginVersion, pools, selectedAccounts, enabledRegions, enabledModelIds,
    allowedAccounts: { cn: enabledRegions.cn ? [...pools.cn.memberAccountIds] : [],
      global: enabledRegions.global && selectedAccounts.global ? [selectedAccounts.global] : [] } };
}

export async function loadPreferences({ desktopPatchPath = DEFAULT_PATCH_PATH, packageDir = DEFAULT_PACKAGE_DIR } = {}) {
  const metadata = await packageMetadata(packageDir);
  return guarded(async () => {
    const { stdout } = await execFileAsync('ruby', ['-e', READ_PREFERENCES_RUBY, desktopPatchPath], {
      timeout: 10000, maxBuffer: 64 * 1024, encoding: 'utf8',
    });
    return normalizePreferences(JSON.parse(stdout), metadata.version);
  }, 'preferences_unreadable');
}

const finite = value => typeof value === 'number' && Number.isFinite(value);
function copyFields(source, keys) {
  return Object.fromEntries(keys.filter(key => source[key] !== undefined).map(key => [key, structuredClone(source[key])]));
}
export function summarizeCredits(raw, now = Date.now()) {
  if (!raw || !Array.isArray(raw.packages)) throw new BridgeError('invalid_credit_response');
  const packages = raw.packages.map(p => ({
    packageName: typeof p.packageName === 'string' ? p.packageName : '(unnamed)',
    remain: finite(p.remain) ? Math.max(0, p.remain) : 0,
    size: finite(p.size) ? Math.max(0, p.size) : 0, monthly: p.monthly === true,
    ...(finite(p.refreshAtMs) ? { refreshAtMs: p.refreshAtMs } : {}),
    ...(finite(p.expiresAtMs) ? { expiresAtMs: p.expiresAtMs } : {}),
  })).filter(p => p.remain > 0 && (p.monthly || p.expiresAtMs === undefined || p.expiresAtMs > now));
  const expiring = packages.filter(p => !p.monthly && p.expiresAtMs !== undefined);
  const soon = expiring.filter(p => p.expiresAtMs <= now + 3 * 86400000);
  return { total: packages.reduce((sum, p) => sum + p.remain, 0), packages,
    expiringSoon: soon.reduce((sum, p) => sum + p.remain, 0),
    ...(expiring.length ? { nearestExpiryMs: Math.min(...expiring.map(p => p.expiresAtMs)) } : {}),
    ...(soon.length ? { expiringSoonEarliestExpiryMs: Math.min(...soon.map(p => p.expiresAtMs)) } : {}) };
}

export async function createBridge({ preferences, packageDir = DEFAULT_PACKAGE_DIR, runtime, clock = Date.now, includeGlobal = true } = {}) {
  const prefs = structuredClone(preferences || await loadPreferences({ packageDir }));
  const api = runtime || await loadPlugin({ packageDir });
  if (prefs.pluginVersion !== SUPPORTED_PLUGIN_VERSION) throw new BridgeError('unsupported_plugin_version');
  const client = new api.WorkBuddyUpstreamClient();
  const stores = new Map();
  const newStore = region => new api.WorkBuddyCredentialStore({ region, refresh: c => client.refreshToken(c) });
  // When the desktop has no explicit global selection, use its native current
  // account only. This is a read, not a refresh, account switch, or pool scan.
  if (!includeGlobal) prefs.allowedAccounts.global = [];
  if (includeGlobal && prefs.enabledRegions.global && !prefs.selectedAccounts.global) {
    await guarded(async () => {
      const credential = await newStore('global').current();
      if (credential) {
        const id = accountId(api.workbuddyAccountId(credential));
        prefs.selectedAccounts.global = id;
        prefs.allowedAccounts.global = [id];
      }
    }, 'global_account_unreadable');
  }
  function select(region, requestedId) {
    if (!REGIONS.includes(region)) throw new BridgeError('unsupported_region');
    if (!prefs.enabledRegions[region]) throw new BridgeError('region_disabled');
    const allowed = prefs.allowedAccounts[region];
    const id = accountId(requestedId || (allowed.includes(prefs.selectedAccounts[region]) ? prefs.selectedAccounts[region] : allowed[0]), true);
    if (!id || !allowed.includes(id)) throw new BridgeError('account_not_allowed');
    const key = `${region}:${id}`;
    if (!stores.has(key)) { const store = newStore(region); store.selectAccount(id); stores.set(key, store); }
    return { id, store: stores.get(key) };
  }
  async function credential(region, requestedId) {
    const { id, store } = select(region, requestedId);
    return guarded(async () => {
      const value = await store.resolve();
      if (!value || api.workbuddyAccountId(value) !== id) throw new BridgeError('account_identity_mismatch');
      if (api.regionOf(value.domain) !== region) throw new BridgeError('account_region_mismatch');
      return { value, id };
    }, 'credential_unavailable');
  }
  const summary = (value, id, region) => ({ accountId: id, region, available: true,
    enterprise: value.enterpriseId !== undefined && value.enterpriseId !== '',
    poolMember: prefs.pools[region].memberAccountIds.includes(id), selected: prefs.selectedAccounts[region] === id });
  async function checkinCall(id, method) {
    const { value, id: actualId } = await credential('cn', id);
    if (value.enterpriseId !== undefined && value.enterpriseId !== '') throw new BridgeError('enterprise_checkin_unsupported');
    return guarded(async () => {
      const raw = await client[method](value);
      if (method === 'fetchCheckinStatus') {
        if (typeof raw?.active !== 'boolean' || typeof raw?.todayCheckedIn !== 'boolean') throw new BridgeError('invalid_checkin_response');
        return { accountId: actualId, region: 'cn', fetchedAtMs: clock(), ...copyFields(raw,
          ['active', 'todayCheckedIn', 'streakDays', 'dailyCredit', 'todayCredit', 'isStreakDay', 'nextStreakDay', 'streakBonusDays', 'streakBonusCredit']) };
      }
      return { accountId: actualId, region: 'cn', fetchedAtMs: clock(), ...copyFields(raw, ['credit', 'streakDays', 'isStreakDay']) };
    }, 'checkin_request_failed');
  }
  return Object.freeze({
    getPreferences: () => structuredClone(prefs),
    async listAccounts() {
      const out = { cn: [], global: [] };
      for (const region of REGIONS) for (const id of prefs.allowedAccounts[region]) {
        const { store } = select(region, id);
        const value = await guarded(() => store.current(), 'credential_unavailable');
        if (value && api.workbuddyAccountId(value) !== id) throw new BridgeError('account_identity_mismatch');
        out[region].push(value ? summary(value, id, region) : { accountId: id, region, available: false,
          enterprise: false, poolMember: prefs.pools[region].memberAccountIds.includes(id), selected: prefs.selectedAccounts[region] === id });
      }
      return out;
    },
    async resolveCredential(id, region) { const resolved = await credential(region, id); return summary(resolved.value, resolved.id, region); },
    async fetchModels(region, id) {
      const resolved = await credential(region, id);
      return guarded(async () => {
        // Match the native plugin: selected IDs survive its CLI-subset filter
        // only if the LIVE upstream config still publishes them. Do not append
        // cached/selected models to the returned roster ourselves.
        const raw = await client.fetchModels(resolved.value, undefined, prefs.enabledModelIds?.[region] || []);
        if (!Array.isArray(raw)) throw new BridgeError('invalid_model_response');
        return { region, accountId: resolved.id, fetchedAtMs: clock(), models: raw.map(model => copyFields(model,
          ['id', 'name', 'contextWindow', 'maxTokens', 'creditMultiplier', 'supportsImages', 'multimodal', 'reasoning', 'promos', 'supportsToolCall'])) };
      }, 'catalog_request_failed');
    },
    async fetchCredits(region, id) {
      const resolved = await credential(region, id);
      return guarded(async () => ({ region, accountId: resolved.id, fetchedAtMs: clock(),
        ...summarizeCredits(await client.fetchCredits(resolved.value), clock()) }), 'credits_request_failed');
    },
    fetchCheckinStatus: id => checkinCall(id, 'fetchCheckinStatus'),
    claimDailyCheckin: id => checkinCall(id, 'claimDailyCheckin'),
  });
}
