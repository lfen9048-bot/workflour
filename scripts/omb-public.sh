#!/usr/bin/env bash
# 用户级launchd托管OpenMausBot和SSH隧道；不依赖启动终端，不使用nohup或宽泛pgrep。
# up启动并在登录时恢复；down停止并取消登录启动；restart仅在Bot空闲时执行。
# 首次迁移：先有序停止已确认的旧前台服务/旧隧道守护，再up；不自动杀未知进程。
set -euo pipefail
WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "${WORKSPACE}/integrations/openmausbot/launchd/manage.py" "$@"
