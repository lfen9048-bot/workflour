#!/usr/bin/env bash
# 生成 OpenMausBot 使用的 DSH ACP profiles；WorkBuddy 仅为模型/额度插件。
#
# 幂等：重复执行不会产生重复条目，不清空已有会话或 WorkBuddy 运行状态。
# 不启动任何模型任务。
# 默认仍生成原 Coder/Doc 和 Antigravity 实例。
# --only ROLE 仅生成指定角色；wf-* 为新 Plan/Code 团队的独立配置。
#
# 产物：
#   ~/.dsh/profiles/omb-coder/{package.json,cordis.yml,cordis.patch.yml,pnpm-workspace.yaml,node_modules}
#   ~/.dsh/profiles/omb-doc/   同上
#
# 设计要点：
#   - 运行 patch 是真实文件，不是指向项目模板的软链接：
#     WorkBuddy 插件会把账号/目录状态写回 patch，软链接会污染项目目录。
#   - 项目模板 integrations/openmausbot/profiles/*.patch.yml 不含账号信息。
#   - 账号配置（accounts / regions 等）在 setup 时从对应旧 profile 的
#     `dsh --dump-config` 组合结果中抽取；凭据正文仍留在 ~/.dsh。
#   - 若目标 patch 已存在 workbuddy 条目，则保留它（保留插件新写入的状态）。
set -euo pipefail
umask 077

SETUP_ROLE="default"
if [ "$#" -ne 0 ]; then
    if [ "$#" -eq 2 ] && [ "$1" = "--only" ] && [[ "$2" =~ ^(deepseek-coder|kimi-planner|glm-planner|glm-reviewer|coordinator|assistant|manager|wf-manager|wf-plan-lead|wf-plan-review|wf-code-main|wf-code-review|wf-code-helper|wf-assistant|xhs-collector|xhs-planner|xhs-writer|xhs-writer-dsh)$ ]]; then
        SETUP_ROLE="$2"
    else
        printf '%s\n' "用法: integrations/openmausbot/setup.sh [--only ROLE]；新团队角色见 integrations/openmausbot/team-v2/roles.json" >&2
        exit 2
    fi
fi

WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DSH_HOME="${DSH_HOME:-${HOME}/.dsh}"
DSH_BIN_OVERRIDE="${DSH_BIN:-}"
DSH_BIN="/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh"
if [ -n "${DSH_BIN_OVERRIDE}" ]; then
    DSH_BIN="${DSH_BIN_OVERRIDE}"
elif [ ! -x "${DSH_BIN}" ]; then
    DSH_BIN="$(command -v dsh || true)"
fi
WORKFLOUR_DSH_SOURCE_PROFILE="${WORKFLOUR_DSH_SOURCE_PROFILE:-desktop}"
[[ "${WORKFLOUR_DSH_SOURCE_PROFILE}" =~ ^[a-zA-Z0-9_-]+$ ]] || { printf '%s\n' 'Invalid WorkBuddy source profile' >&2; exit 2; }
export WORKFLOUR_DSH_SOURCE_PROFILE
DESKTOP_NODE_MODULES="${DSH_HOME}/profiles/${WORKFLOUR_DSH_SOURCE_PROFILE}/node_modules"
TEMPLATE_DIR="${WORKSPACE_DIR}/integrations/openmausbot/profiles"
BACKUP_DIR=""

log() { printf '%s\n' "$*" >&2; }

if [ "${SETUP_ROLE}" != "wf-code-main" ] && [ "${SETUP_ROLE}" != "xhs-writer" ]; then
    [ -x "${DSH_BIN}" ] || { log "找不到 dsh: 设置 DSH_BIN 或把 dsh 加入 PATH"; exit 1; }
    [ -d "${DESKTOP_NODE_MODULES}" ] || { log "找不到共享 node_modules: ${DESKTOP_NODE_MODULES}"; exit 1; }
fi

# New workflow roles inherit the desktop's checked account pool on ACP startup,
# via a private --patch layer. Validate that source before creating/changing any
# profile; legacy profiles keep their original behavior and are not synchronized.
case "${SETUP_ROLE}" in
    wf-manager|wf-plan-lead|wf-plan-review|wf-code-review|wf-code-helper|wf-assistant|xhs-collector|xhs-planner|xhs-writer-dsh)
        /usr/bin/ruby "${WORKSPACE_DIR}/scripts/workbuddy-pool-sync.rb" \
            --profile "omb-${SETUP_ROLE}" --check >/dev/null
        log "[+] 账号池来源已核对：ACP 启动时读取 ${WORKFLOUR_DSH_SOURCE_PROFILE} 成员、开关与排序"
        ;;
esac

if [ "${SETUP_ROLE}" != "wf-code-main" ] && [ "${SETUP_ROLE}" != "xhs-writer" ]; then
    BACKUP_DIR="$(mktemp -d "${DSH_HOME}/backup-omb-$(date +%Y%m%d-%H%M%S)-XXXXXX")"
fi

# 从 dsh --dump-config 的组合树里截出某个顶层条目的文本块。
# 顶层条目以 "- id: " 开头；块在该行之后的下一行 "- id: " 或 "- insert:" 处结束。
extract_entry() {
    local file="$1" id="$2"
    awk -v want="- id: ${id}" '
        $0 == want { f = 1; print; next }
        f && (/^- id: / || /^- insert:/) { exit }
        f { print }
    ' "$file"
}

# 生成或更新一个 profile。
#   $1 = coder|doc|deepseek-coder|kimi-planner|glm-planner|glm-reviewer
setup_profile() {
    local role="$1"
    local profile="omb-${role}"
    local source_profile="agent-${role}"
    if [ "${role}" != "coder" ] && [ "${role}" != "doc" ]; then
        source_profile="agent-doc"
    fi
    local profile_dir="${DSH_HOME}/profiles/${profile}"
    local template="${TEMPLATE_DIR}/${role}.patch.yml"
    local target="${profile_dir}/cordis.patch.yml"

    [ -f "${template}" ] || { log "缺少模板: ${template}"; return 1; }

    mkdir -p "${profile_dir}"

    # 1. package.json —— ACP 组合，不复制 desktop 组件，也不用 headless bundle
    cat > "${profile_dir}/package.json" <<EOF
{
  "name": "dsh-profile-${profile}",
  "private": true,
  "dependencies": {
    "dsh-connect-workbuddy": "5.13.1"
  },
  "dsh": {
    "profile": {
      "bundles": [
        "@deepseek-ai/dsh-base",
        "@deepseek-ai/dsh-acp-app",
        "dsh-connect-workbuddy"
      ]
    }
  }
}
EOF

    # 2. 空的 profile 根与 workspace 声明
    cat > "${profile_dir}/cordis.yml" <<'EOF'
# dsh profile root — an empty entry list. The tree is composed as patches:
# each bundle in package.json's dsh.profile.bundles, then cordis.patch.yml, then any
# --patch overlays. Edit cordis.patch.yml, not this file.
[]
EOF
    printf 'packages: []\n' > "${profile_dir}/pnpm-workspace.yaml"

    # 3. 复用 desktop 的 node_modules（不升级、不修改共享依赖）
    if [ ! -e "${profile_dir}/node_modules" ]; then
        ln -s "${DESKTOP_NODE_MODULES}" "${profile_dir}/node_modules"
        log "[+] ${profile}: 关联 node_modules"
    fi

    # 4. 取 workbuddy 配置块：优先沿用目标 patch 里已有的，其次从源 profile 组合树抽取
    local workbuddy_block=""
    if [ -f "${target}" ]; then
        workbuddy_block="$(extract_entry "${target}" "dsh-connect-workbuddy")"
    fi
    # New teams can start on Ubuntu with only a logged-in Web profile.
    # Read its own saved entry; never require a historical Mac Doc profile.
    case "${role}" in
        wf-*|xhs-*)
            if [ -z "${workbuddy_block}" ] && [ -f "${DSH_HOME}/profiles/${WORKFLOUR_DSH_SOURCE_PROFILE}/cordis.patch.yml" ]; then
                workbuddy_block="$(extract_entry "${DSH_HOME}/profiles/${WORKFLOUR_DSH_SOURCE_PROFILE}/cordis.patch.yml" "dsh-connect-workbuddy")"
            fi
            source_profile="${WORKFLOUR_DSH_SOURCE_PROFILE}"
            ;;
    esac
    # 新角色复用已工作的 Doc 登录配置，避免为此启动旧 headless profile。
    if [ -z "${workbuddy_block}" ] && [ "${role}" != "coder" ] && [ "${role}" != "doc" ] \
            && [ -f "${DSH_HOME}/profiles/omb-doc/cordis.patch.yml" ]; then
        workbuddy_block="$(extract_entry "${DSH_HOME}/profiles/omb-doc/cordis.patch.yml" "dsh-connect-workbuddy")"
    fi
    if [ -z "${workbuddy_block}" ]; then
        local composed
        composed="$(mktemp)"
        if ! "${DSH_BIN}" --profile "${source_profile}" --dump-config > "${composed}" 2>/dev/null; then
            log "[!] ${profile}: 无法组合 ${source_profile}，跳过账号块抽取"
        fi
        workbuddy_block="$(extract_entry "${composed}" "dsh-connect-workbuddy")"
        rm -f "${composed}"
    fi
    if [ -z "${workbuddy_block}" ]; then
        log "[!] ${profile}: 未取得 dsh-connect-workbuddy 账号块，需要手工补齐后再启动"
        return 1
    fi

    # 5. 备份既有 patch，再写新 patch（模板条目 + 账号块）
    if [ -f "${target}" ]; then
        cp -p "${target}" "${BACKUP_DIR}/${profile}.cordis.patch.yml"
        log "[+] ${profile}: 已备份旧 patch 到 ${BACKUP_DIR}"
    fi

    {
        # Parse before replacing paths, so spaces, quotes and YAML punctuation
        # in the checkout path cannot change the generated configuration.
        # Legacy templates remain supported; only this private copy is rendered.
        /usr/bin/ruby -r yaml - "${template}" "${WORKSPACE_DIR}" <<'RUBY'
template, root = ARGV
tree = YAML.safe_load(File.read(template), permitted_classes: [], permitted_symbols: [], aliases: false)
raise 'Expected a profile patch list' unless tree.is_a?(Array)
render = lambda do |value|
  case value
  when String
    ['/Users/a1/Documents/a/workflour', '@WORKSPACE_ROOT@', '{{ROOT}}'].reduce(value) do |text, token|
      text.gsub(token) { root }
    end
  when Array then value.map { |item| render.call(item) }
  when Hash then value.transform_values { |item| render.call(item) }
  else value
  end
end
tree = render.call(tree)
tree.each do |entry|
  next unless entry.is_a?(Hash) && entry['id'] == 'skill-filesystem'
  Array(entry.fetch('config', {})['customSkillDirs']).each do |path|
    raise 'Configured role skill directory is missing' unless path.is_a?(String) && File.directory?(path)
  end
end
puts YAML.dump(tree)
RUBY
        printf '\n'
        printf '%s\n' "${workbuddy_block}"
    } > "${target}.new"
    # XHS model choices are scoped to these profiles; desktop/account pools stay intact.
    case "${role}" in
        xhs-collector|xhs-planner|xhs-writer-dsh)
            /usr/bin/ruby -r yaml -r json - "${target}.new" "${WORKSPACE_DIR}/integrations/openmausbot/team-xhs/models.json" <<'RUBY'
path, declaration = ARGV
rows = YAML.safe_load(File.read(path), permitted_classes: [], permitted_symbols: [], aliases: false)
entry = rows.select { |r| r.is_a?(Hash) && r['id'] == 'dsh-connect-workbuddy' }
raise 'Expected exactly one WorkBuddy config' unless entry.length == 1
wanted = JSON.parse(File.read(declaration)).fetch('workbuddy')
wanted.each do |region, choices|
  target_region = entry[0].fetch('config').fetch('regions').fetch(region)
  %w[enabledModelIds imageModelIds].each do |field|
    target_region[field] = (target_region.fetch(field, []) + choices.fetch(field)).uniq
  end
end
File.write(path, YAML.dump(rows))
File.chmod(0600, path)
RUBY
            ;;
    esac
    mv "${target}.new" "${target}"

    log "[+] ${profile}: 已写入 ${target}"
}

if [ "${SETUP_ROLE}" = "default" ]; then
    setup_profile coder
    setup_profile doc
elif [ "${SETUP_ROLE}" != "wf-code-main" ] && [ "${SETUP_ROLE}" != "xhs-writer" ]; then
    setup_profile "${SETUP_ROLE}"
fi

# ---------------------------------------------------------------------------
# OpenMausBot 实例配置：合并进 ~/.openmausbot/config.json，不整体替换已有配置。
# ---------------------------------------------------------------------------
OMB_DATA_DIR="${OMB_DATA_DIR:-${HOME}/.openmausbot}"
OMB_CONFIG="${OMB_DATA_DIR}/config.json"
OMB_BACKUP_DIR="${OMB_DATA_DIR}/backups"

merge_omb_config() {
    mkdir -p "${OMB_DATA_DIR}" "${OMB_BACKUP_DIR}"

    if [ -f "${OMB_CONFIG}" ]; then
        local config_backup
        config_backup="$(mktemp "${OMB_BACKUP_DIR}/config.json.$(date +%Y%m%d-%H%M%S).bak.XXXXXX")"
        cp -p "${OMB_CONFIG}" "${config_backup}"
        log "[+] 已备份 ${OMB_CONFIG}"
    fi

    python3 - "${OMB_CONFIG}" "${WORKSPACE_DIR}" "${SETUP_ROLE}" <<'PY'
import json
import os
import shlex
import sys

config_path, workspace, setup_role = sys.argv[1:]

data = {}
if os.path.exists(config_path):
    with open(config_path, encoding="utf-8") as handle:
        text = handle.read().strip()
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            print(f"config.json 不是合法 JSON，拒绝改写: {error}", file=sys.stderr)
            sys.exit(1)
if not isinstance(data, dict):
    print("config.json 顶层不是对象，拒绝改写", file=sys.stderr)
    sys.exit(1)

instances = data.get("instances")
if not isinstance(instances, dict):
    instances = {}

wanted = {
    "omb-coder": ("Harness Coder", "coder"),
    "omb-doc": ("Harness Doc", "doc"),
}

# Antigravity 单独处理：它不需要 dsh profile，走 run-agy-agent.sh 包装
# 本机 agy 的 `agy acp --stdio`（原生 ACP 服务）。
# 不用 OpenMausBot 内置的 antigravityAgent 驱动，因为那个要求下载
# agy_acp_server.par + localharness_external（约 114MB zip）。
wanted_direct = {
    "agy-gemini": ("Antigravity (Gemini)", shlex.quote(f"{workspace}/run-agy-agent.sh")),
}

if setup_role != "default":
    names = {"deepseek-coder": "DSH 协作编码", "kimi-planner": "DSH 方案主持",
             "glm-planner": "DSH 风险规划", "glm-reviewer": "DSH 独立审核",
             "coordinator": "Code Team Coordinator", "assistant": "General Assistant",
             "manager": "General Manager",
             "wf-manager": "DSH · 大管家",
             "wf-plan-lead": "DSH · Plan 项目负责人",
             "wf-plan-review": "DSH · Plan 方案与体验评审",
             "wf-code-review": "DSH · Code 独立审核",
             "wf-code-helper": "DSH · Code 协作编码",
             "wf-assistant": "DSH · 通用助手",
             "xhs-collector": "DSH · 小红书采集",
             "xhs-planner": "DSH · 小红书思考",
             "xhs-writer-dsh": "DSH · 小红书写作（可选）"}
    if setup_role in ("wf-code-main", "xhs-writer"):
        wanted = {}
    else:
        wanted = {f"omb-{setup_role}": (names[setup_role], setup_role)}
        wanted_direct = {}

changed = False

for instance_id, (display_name, cli) in wanted_direct.items():
    desired = {
        "driver": "customAcp",
        "displayName": display_name,
        "config": {"cli": cli},
    }
    existing = instances.get(instance_id)
    if existing is None:
        instances[instance_id] = desired
        changed = True
        print(f"[+] 新增实例 {instance_id}", file=sys.stderr)
        continue
    if not isinstance(existing, dict):
        print(f"[!] 已有键 {instance_id} 不是对象，未改动", file=sys.stderr)
        continue
    existing_cli = (existing.get("config") or {}).get("cli")
    if existing.get("driver") != "customAcp" or not isinstance(existing_cli, str) \
            or "run-agy-agent.sh" not in existing_cli:
        print(
            f"[!] 已有 {instance_id} 归属不明"
            f"（driver={existing.get('driver')!r}），保留原样",
            file=sys.stderr,
        )
        continue
    merged = {
        **existing,
        **desired,
        "config": {**existing.get("config", {}), **desired["config"]},
    }
    if merged != existing:
        instances[instance_id] = merged
        changed = True
        print(f"[+] 更新实例 {instance_id}", file=sys.stderr)
    else:
        print(f"[=] 实例 {instance_id} 已是最新", file=sys.stderr)
for instance_id, (display_name, role) in wanted.items():
    desired = {
        "driver": "customAcp",
        "displayName": display_name,
        "config": {"cli": f"{shlex.quote(f'{workspace}/run-acp-agent.sh')} {role}"},
    }
    existing = instances.get(instance_id)
    if existing is None:
        instances[instance_id] = desired
        changed = True
        print(f"[+] 新增实例 {instance_id}", file=sys.stderr)
        continue
    if not isinstance(existing, dict):
        print(f"[!] 已有键 {instance_id} 不是对象，未改动", file=sys.stderr)
        continue
    existing_cli = (existing.get("config") or {}).get("cli")
    if existing.get("driver") != "customAcp" or not isinstance(existing_cli, str) \
            or "run-acp-agent.sh" not in existing_cli:
        print(
            f"[!] 已有 {instance_id} 归属不明"
            f"（driver={existing.get('driver')!r}），保留原样",
            file=sys.stderr,
        )
        continue
    merged = {
        **existing,
        **desired,
        "config": {**existing.get("config", {}), **desired["config"]},
    }
    if merged != existing:
        instances[instance_id] = merged
        changed = True
        print(f"[+] 更新实例 {instance_id}", file=sys.stderr)
    else:
        print(f"[=] 实例 {instance_id} 已是最新", file=sys.stderr)

data["instances"] = instances

if not changed and os.path.exists(config_path):
    print("[=] config.json 无需改动", file=sys.stderr)
else:
    tmp = config_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, config_path)
    print(f"[+] 已写入 {config_path}", file=sys.stderr)
PY
}

merge_omb_config

log ""
log "=== OpenMausBot 接入配置就绪 ==="
if [ "${SETUP_ROLE}" = "default" ]; then
    log "ACP profiles: ${DSH_HOME}/profiles/omb-coder, ${DSH_HOME}/profiles/omb-doc"
elif [ "${SETUP_ROLE}" != "wf-code-main" ] && [ "${SETUP_ROLE}" != "xhs-writer" ]; then
    log "ACP profile:  ${DSH_HOME}/profiles/omb-${SETUP_ROLE}"
else
    log "ACP runtime:  agy-gemini（独立 Antigravity，无 DSH profile）"
fi
log "profile 备份: ${BACKUP_DIR}"
log "实例配置:     ${OMB_CONFIG}"
log "实例备份:     ${OMB_BACKUP_DIR}"
log ""
log "启动（前台，需人工执行）：npx --yes openmausbot@0.1.143 serve"
