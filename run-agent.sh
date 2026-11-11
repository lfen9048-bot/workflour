#!/usr/bin/env bash
set -e

DSH_BIN="/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh"

if [ $# -lt 2 ]; then
    echo "用法: ./run-agent.sh <coder|doc> <任务内容>"
    echo "示例: ./run-agent.sh coder '你好，请做个自我介绍并列出你可用的 skills'"
    exit 1
fi

AGENT_TYPE="$1"
shift
PROMPT="$*"

case "${AGENT_TYPE}" in
    coder)
        PROFILE="agent-coder"
        ;;
    doc)
        PROFILE="agent-doc"
        ;;
    *)
        echo "错误: 未知的 agent 类型 '${AGENT_TYPE}'，请使用 'coder' 或 'doc'"
        exit 1
        ;;
esac

echo ">>> 启动 ${PROFILE} 执行任务..."
exec "${DSH_BIN}" --profile "${PROFILE}" "${PROMPT}"
