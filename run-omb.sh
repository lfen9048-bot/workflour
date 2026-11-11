#!/usr/bin/env bash
# OpenMausBot 启停入口：local | remote | pair <HTTPS origin>
#
#   run-omb.sh local            前台启动本地服务（默认 http://127.0.0.1:8799）
#   run-omb.sh remote           前台启动远程模式（内置托管 HTTPS，caffeinate 保持唤醒）
#   run-omb.sh pair <origin>    为手机生成 client 邀请，origin 必须是本次实际
#                               HTTPS 地址，不能是占位符
#
# 固定版本 0.1.143。不把 Mac 永久设为不休眠：remote 用 caffeinate -i 包住
# 前台进程，服务停止后 caffeinate 随之退出。
set -euo pipefail

OMB_VERSION="0.1.143"
OMB_PORT="${OMB_PORT:-8799}"

usage() {
    cat >&2 <<'EOF'
用法:
  run-omb.sh local
  run-omb.sh remote
  run-omb.sh pair <本次实际 HTTPS origin>

说明:
  local   前台启动本地服务
  remote  前台启动远程模式（内置托管 HTTPS，需要先 openmausbot login）
  pair    生成手机 client 邀请；origin 形如 https://c-xxxx.trycloudflare.com
          占位符会被拒绝
EOF
}

if [ "$#" -lt 1 ]; then
    usage
    exit 2
fi

case "$1" in
    local)
        if [ "$#" -ne 1 ]; then
            usage
            exit 2
        fi
        exec npx --yes "openmausbot@${OMB_VERSION}" serve
        ;;
    remote)
        if [ "$#" -ne 1 ]; then
            usage
            exit 2
        fi
        # --no-pair：手机走单独的 client 邀请，不在这里生成 owner 邀请。
        exec caffeinate -i npx --yes "openmausbot@${OMB_VERSION}" serve --tunnel --no-pair
        ;;
    pair)
        if [ "$#" -ne 2 ]; then
            usage
            exit 2
        fi
        ORIGIN="$2"
        case "${ORIGIN}" in
            https://*)
                ;;
            *)
                echo "run-omb.sh: 只接受 https:// 开头的实际地址，收到 '${ORIGIN}'" >&2
                exit 2
                ;;
        esac
        case "${ORIGIN}" in
            *'<'*|*'>'*|*example*|*xxxx*|*placeholder*|*'...'*)
                echo "run-omb.sh: '${ORIGIN}' 看起来是占位符，请填本次实际 HTTPS origin" >&2
                exit 2
                ;;
        esac
        # 手机是普通客户端，不能用 owner/admin 邀请。
        exec npx --yes "openmausbot@${OMB_VERSION}" pair --client --label Phone --public-url "${ORIGIN}"
        ;;
    -h|--help|help)
        usage
        exit 0
        ;;
    *)
        echo "run-omb.sh: 未知子命令 '$1'" >&2
        usage
        exit 2
        ;;
esac
