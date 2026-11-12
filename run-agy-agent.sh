#!/usr/bin/env bash
# Antigravity（agy）的 ACP 协议入口，供 OpenMausBot 的 customAcp 驱动调用。
#
# 用法：run-agy-agent.sh [--version]
#
# 为什么用 customAcp 包装而不是 OpenMausBot 内置的 antigravityAgent 驱动：
#   内置驱动要求 Google 官方运行时，即两个文件同时存在：
#     agy_acp_server.par  +  localharness_external
#   需从 dl.google.com 下载约 114MB 的 zip（解压后 280MB+）。
#   而本机 agy 1.4.12 已自带 `agy acp --stdio`，是标准 ACP 服务，
#   实测 initialize / session/new / session/prompt 全部正常，
#   还能返回 token 用量。所以用 customAcp 直接包它，省一次大文件下载。
#
# 与 run-acp-agent.sh 的差异：
#   - 不需要 --profile（agy 自己管身份和登录，走 Google 账号）
#   - 不需要 DSH_HOME（不涉及 WorkBuddy 凭据）
#   - 工作目录由 OpenMausBot 通过 cwd 传入，这里不写死
#
# stdout 只留给 ACP JSONL；诊断信息一律写 stderr。
set -euo pipefail

AGY_BIN="${AGY_BIN:-${HOME}/.local/bin/agy}"

if [ ! -x "${AGY_BIN}" ]; then
    echo "run-agy-agent.sh: 找不到可执行的 agy: ${AGY_BIN}" >&2
    exit 127
fi

# OpenMausBot 的 customAcp 驱动会用 --version 做安装探测，
# 不支持就会把实例显示为 unavailable。
if [ "$#" -ge 1 ] && [ "$1" = "--version" ]; then
    exec "${AGY_BIN}" --version
fi

if [ "$#" -ne 0 ]; then
    echo "run-agy-agent.sh: 只接受可选参数 --version，收到: $*" >&2
    exit 2
fi

# --stdio: 使用 stdio JSON-RPC 传输（ACP 默认）
# --disable-telemetry: 减少非必要外部请求；不影响模型调用
WORKFLOUR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${WORKFLOUR_ROOT}/scripts/xhs-agy-mcp-bridge.py" \
    "${AGY_BIN}" acp --stdio --disable-telemetry
