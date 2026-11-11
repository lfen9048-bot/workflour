#!/usr/bin/env bash
set -e

WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DSH_PROFILES_DIR="${HOME}/.dsh/profiles"
DESKTOP_NODE_MODULES="${DSH_PROFILES_DIR}/desktop/node_modules"

echo "=== 正在配置 Agent Coder 与 Agent Doc Profile ==="

for AGENT in "coder" "doc"; do
    PROFILE_NAME="agent-${AGENT}"
    PROFILE_DIR="${DSH_PROFILES_DIR}/${PROFILE_NAME}"
    AGENT_DIR="${WORKSPACE_DIR}/agents/${PROFILE_NAME}"

    mkdir -p "${PROFILE_DIR}"

    # 1. 写入 package.json
    cat <<EOF > "${PROFILE_DIR}/package.json"
{
  "name": "dsh-profile-${PROFILE_NAME}",
  "private": true,
  "dependencies": {
    "dsh-connect-workbuddy": "5.13.1"
  },
  "dsh": {
    "profile": {
      "bundles": [
        "@deepseek-ai/dsh-base",
        "@deepseek-ai/dsh-headless",
        "dsh-connect-workbuddy"
      ]
    }
  }
}
EOF

    # 2. 软链接共享 node_modules (WorkBuddy 等依赖)
    if [ ! -e "${PROFILE_DIR}/node_modules" ]; then
        ln -s "${DESKTOP_NODE_MODULES}" "${PROFILE_DIR}/node_modules"
        echo "[+] 关联 node_modules 到 ${PROFILE_NAME}"
    fi

    # 3. 基础 cordis.yml 与 workspace 配置
    echo "[]" > "${PROFILE_DIR}/cordis.yml"
    echo "packages: []" > "${PROFILE_DIR}/pnpm-workspace.yaml"

    # 4. 软链接配置 patch 到项目内的 patch.yml
    ln -sf "${AGENT_DIR}/cordis.patch.yml" "${PROFILE_DIR}/cordis.patch.yml"
    echo "[+] 关联 cordis.patch.yml 到 ${PROFILE_NAME}"
done

echo "=== 配置完成 ==="
echo "Agent Coder 目录: ${DSH_PROFILES_DIR}/agent-coder"
echo "Agent Doc 目录:   ${DSH_PROFILES_DIR}/agent-doc"
