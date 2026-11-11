#!/usr/bin/env bash
# OpenMausBot ACP 协议入口：coder | doc | deepseek-coder
#
# 用法：run-acp-agent.sh coder|doc|deepseek-coder|kimi-planner|glm-planner|glm-reviewer|coordinator|assistant|manager [--version]
#
# 约束（来自实施计划 §4）：
#   1. 接受 coder / doc / deepseek-coder，映射到对应 omb-* profile；
#      未知角色以非零退出。
#   2. 使用内置 dsh 与 --profile 启动，不依赖 PATH 里存在 dsh。
#   3. 不带任务文本、不加 headless 参数、不启动 desktop profile。
#   4. stdout 只留给 ACP JSONL；任何诊断写 stderr。
#   5. 不重定向丢弃 stdin；stdin 结束或被停止时正常退出。
#
# `--version` 是 OpenMausBot 的安装探测（它会对配置里的 cli 跑 --version），
# 不是 ACP 请求；该路径同样只写 stdout 一行版本号。
set -euo pipefail

DSH_BIN="/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh"

if [ ! -x "${DSH_BIN}" ]; then
    echo "run-acp-agent.sh: 找不到可执行的 dsh: ${DSH_BIN}" >&2
    exit 127
fi

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "用法: run-acp-agent.sh ROLE [--version]；新 DSH 角色见 integrations/openmausbot/team-v2/roles.json" >&2
    exit 2
fi

case "$1" in
    coder) PROFILE="omb-coder" ;;
    doc)   PROFILE="omb-doc" ;;
    deepseek-coder|kimi-planner|glm-planner|glm-reviewer|coordinator|assistant|manager|wf-manager|wf-plan-lead|wf-plan-review|wf-code-review|wf-code-helper|wf-assistant) PROFILE="omb-$1" ;;
    *)
        echo "run-acp-agent.sh: 未知 DSH 角色 '$1'；Antigravity 使用 run-agy-agent.sh，角色清单见 integrations/openmausbot/team-v2/roles.json" >&2
        exit 2
        ;;
esac

# 固定 DSH_HOME，复用已有 WorkBuddy 凭据库与登录；不新建空 home。
export DSH_HOME="${DSH_HOME:-${HOME}/.dsh}"

if [ "$#" -eq 2 ]; then
    if [ "$2" != "--version" ]; then
        echo "run-acp-agent.sh: 未知参数 '$2'（只支持 --version）" >&2
        exit 2
    fi
    exec "${DSH_BIN}" --version
fi

if [ ! -d "${DSH_HOME}/profiles/${PROFILE}" ]; then
    echo "run-acp-agent.sh: profile 不存在: ${DSH_HOME}/profiles/${PROFILE}" >&2
    if [ "${PROFILE}" != "omb-coder" ] && [ "${PROFILE}" != "omb-doc" ]; then
        echo "先运行 integrations/openmausbot/setup.sh --only ${PROFILE#omb-} 生成 profile" >&2
    else
        echo "先运行 integrations/openmausbot/setup.sh 生成 profile" >&2
    fi
    exit 1
fi

# The custom ACP driver reopens a saved session with session/load, whereas this
# Harness version exposes session/resume. Keep the native persisted Agent (and
# its tool results) instead of falling back to a new Agent rebuilt from chat.
# This alias is specific to OpenMausBot, which owns the visible transcript.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
DSH_ARGS=("${DSH_BIN}" --profile "${PROFILE}")
unset WORKFLOUR_QUOTA_POLICY
case "${PROFILE}" in
    omb-wf-*)
        export WORKFLOUR_QUOTA_POLICY=enabled
        # The desktop owns the checked account list and native pool ordering.
        # Compose a process-private config layer at startup; an existing ACP
        # process keeps its snapshot until it exits. The helper prints only its
        # path to stdout (captured here), and failures stop before Harness boots.
        POOL_PATCH="$(/usr/bin/ruby "${SCRIPT_DIR}/scripts/workbuddy-pool-sync.rb" \
            --profile "${PROFILE}" --prepare --owner-pid "$$")"
        DSH_ARGS+=(--patch "${POOL_PATCH}")
        ;;
esac
exec /usr/bin/python3 "${SCRIPT_DIR}/integrations/openmausbot/acp-resume-bridge.py" \
    "${DSH_ARGS[@]}" \
    --patch "${SCRIPT_DIR}/integrations/openmausbot/session-title/cordis.patch.yml" \
    --patch "${SCRIPT_DIR}/integrations/openmausbot/model-fallback/cordis.patch.yml"
