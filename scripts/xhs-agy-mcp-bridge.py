#!/usr/bin/env python3
"""Inject one workspace-approved MCP only for the deployed XHS writer.

All other ACP frames and all child output pass through unchanged. This does not
load arbitrary workspace MCPs, change permissions, issue prompts, or log frames.
Only standard ACP stdio fields are sent. ACP cannot carry the workspace's 600s
timeout/per-tool settings; the injected MCP runs with a 170s bounded deadline.
"""
import argparse
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from xhs_paths import deployment_path

SERVER_NAME = 'workflour_xhs_delivery'
TOOLS = {'prepare_delivery', 'confirm_delivery'}
MAX_FRAME = 1024 * 1024
MAX_PENDING = 2 * MAX_FRAME


class BridgeError(ValueError):
    """Safe public errors, never including received environment or credentials."""


def strict_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError('Duplicate key')
            result[key] = value
        return result

    def constant(_):
        raise ValueError('Non-finite number')

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def local_writer_id(manifest):
    try:
        if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > MAX_FRAME:
            return None
        state = strict_json(manifest.read_bytes())
        roles = state.get('roles') if isinstance(state, dict) else None
        if not isinstance(roles, list):
            return None
        writers = [row for row in roles if isinstance(row, dict) and row.get('key') == 'xhs-writer']
        if len(writers) != 1:
            return None
        value = writers[0].get('botId')
        return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,160}', value) else None
    except (ValueError, OSError):
        return None


def is_writer(params, root, manifest):
    cwd = params.get('cwd')
    if not isinstance(cwd, str) or not Path(cwd).is_absolute():
        return False
    try:
        if Path(cwd).resolve(strict=True) != root.resolve(strict=True):
            return False
    except (ValueError, OSError):
        return False
    servers = params.get('mcpServers')
    if not isinstance(servers, list):
        return False
    identities = []
    for server in servers:
        if not isinstance(server, dict):
            return False
        env = server.get('env', [])
        if not isinstance(env, list):
            return False
        values = [row.get('value') for row in env
                  if isinstance(row, dict) and row.get('name') == 'OMB_BOT_ID']
        if len(values) > 1:
            return False
        if values:
            identities.extend(values)
    writer = local_writer_id(manifest)
    return bool(writer and identities and all(value == writer for value in identities))


def approved_server(root):
    directory = root / '.agents'
    path = directory / 'mcp_config.json'
    script = root / 'scripts/xhs-delivery-mcp.py'
    try:
        if directory.is_symlink() or path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FRAME:
            raise ValueError()
        config = strict_json(path.read_bytes())
        server = config['mcpServers'][SERVER_NAME]
        if not isinstance(server, dict):
            raise ValueError()
    except (ValueError, OSError, KeyError, TypeError):
        raise BridgeError('XHS delivery MCP is not configured safely for this workspace; run configure-xhs-delivery.py first') from None
    command, args = server.get('command'), server.get('args')
    try:
        if (not isinstance(command, str) or not Path(command).is_absolute()
                or not os.path.samefile(command, sys.executable)
                or args != [str(script)] or script.is_symlink() or not script.is_file()):
            raise ValueError()
        enabled = server.get('enabledTools')
        disabled = server.get('disabledTools', [])
        if (server.get('disabled') is True
                or enabled is not None and (not isinstance(enabled, list) or not TOOLS.issubset(enabled))
                or not isinstance(disabled, list) or TOOLS.intersection(disabled)):
            raise ValueError()
    except (ValueError, OSError, TypeError):
        raise BridgeError('XHS delivery MCP configuration conflicts with the approved local tools; inspect the workspace config') from None
    return {'name': SERVER_NAME, 'command': command, 'args': args,
            'env': [{'name': 'WORKFLOUR_XHS_ACP_BOUNDED', 'value': '1'}]}


def rewrite(raw, root=ROOT, manifest=None):
    """Return (upstream bytes, local error bytes); non-targets retain exact bytes."""
    if len(raw) > MAX_FRAME:
        return raw, None
    try:
        message = strict_json(raw)
    except (ValueError, UnicodeError):
        return raw, None
    if (not isinstance(message, dict) or message.get('jsonrpc') != '2.0'
            or message.get('method') not in ('session/new', 'session/load', 'session/resume')
            or type(message.get('id')) not in (int, str)
            or not isinstance(message.get('params'), dict)):
        return raw, None
    params = message['params']
    root = root.resolve()
    if not is_writer(params, root, manifest or deployment_path()):
        return raw, None
    try:
        server = approved_server(root)
        existing = [value for value in params['mcpServers'] if value.get('name') == SERVER_NAME]
        if existing:
            if len(existing) != 1 or existing[0] != server:
                raise BridgeError('Conflicting XHS delivery MCP registration in this ACP session')
            return raw, None
        params['mcpServers'].append(server)
        return (json.dumps(message, ensure_ascii=False, allow_nan=False) + '\n').encode(), None
    except BridgeError as error:
        reply = {'jsonrpc': '2.0', 'id': message['id'],
                 'error': {'code': -32602, 'message': str(error)}}
        return None, (json.dumps(reply) + '\n').encode()


def run(command):
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=None, start_new_session=True)
    stopping = 0
    parent_closed = False
    native_code = None

    def stop(signum, _frame):
        nonlocal stopping
        stopping = signum

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    buffer = b''
    oversized = False
    upstream, downstream, deferred_replies = bytearray(), bytearray(), bytearray()
    child_boundary = True
    child_open = True
    incoming, outgoing = sys.stdin.fileno(), sys.stdout.fileno()
    child_in, child_out = process.stdin.fileno(), process.stdout.fileno()
    original_blocking = {fd: os.get_blocking(fd) for fd in (incoming, outgoing)}
    for fd in (incoming, outgoing, child_in, child_out):
        os.set_blocking(fd, False)

    def local_reply(reply):
        # A child JSON-RPC response may span pipe reads. Never insert our error
        # response into the middle of its frame, even when output is congested.
        (downstream if child_boundary else deferred_replies).extend(reply)

    def child_output(value):
        nonlocal child_boundary
        if deferred_replies:
            end = value.find(b'\n')
            if end >= 0:
                downstream.extend(value[:end + 1])
                downstream.extend(deferred_replies)
                deferred_replies.clear()
                value = value[end + 1:]
                child_boundary = True
        if value:
            downstream.extend(value)
            child_boundary = value.endswith(b'\n')

    try:
        while not stopping and (child_open or downstream):
            native_code = process.poll()
            readers = []
            if child_open and len(downstream) < MAX_PENDING:
                readers.append(child_out)
            if child_open and native_code is None and len(upstream) < MAX_PENDING and len(downstream) + len(deferred_replies) < MAX_PENDING:
                readers.append(incoming)
            writers = ([outgoing] if downstream else []) + ([child_in] if upstream and native_code is None and child_open else [])
            readable, writable, _ = select.select(readers, writers, [], 0.1)
            if child_out in readable:
                value = os.read(child_out, 65536)
                if value:
                    child_output(value)
                else:
                    child_open = False
            elif native_code is not None and child_out in readers:
                # Drain buffered native output, but a descendant retaining its
                # pipe must not hide the original ACP process's failure forever.
                child_open = False
            if incoming in readable:
                chunk = os.read(incoming, 65536)
                if not chunk:
                    parent_closed = True
                    break
                if oversized:
                    end = chunk.find(b'\n')
                    if end < 0:
                        upstream.extend(chunk)
                        chunk = b''
                    else:
                        upstream.extend(chunk[:end + 1])
                        chunk, oversized = chunk[end + 1:], False
                buffer += chunk
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    forwarded, reply = rewrite(line + b'\n')
                    if forwarded is not None:
                        upstream.extend(forwarded)
                    if reply is not None:
                        local_reply(reply)
                if len(buffer) > MAX_FRAME:
                    upstream.extend(buffer)
                    buffer, oversized = b'', True
            for fd, pending in ((outgoing, downstream), (child_in, upstream)):
                if fd not in writable or not pending:
                    continue
                try:
                    count = os.write(fd, pending[:65536])
                    del pending[:count]
                except BlockingIOError:
                    pass
                except BrokenPipeError:
                    if fd == outgoing:
                        parent_closed = True
                        raise
                    upstream.clear()
                    child_open = False
    except BrokenPipeError:
        pass
    finally:
        process.stdin.close()
        # Preserve an actual native failure instead of reporting every EOF as 0.
        if native_code is None:
            native_code = process.poll()
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        process.stdout.close()
        for fd, blocking in original_blocking.items():
            os.set_blocking(fd, blocking)
    if stopping:
        return 128 + stopping
    if parent_closed:
        return 0
    code = native_code if native_code is not None else process.returncode
    return 128 - code if code < 0 else code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs=argparse.REMAINDER, help='Native agy command and its unchanged arguments')
    args = parser.parse_args()
    if not args.command:
        parser.error('a native ACP command is required')
    try:
        return run(args.command)
    except OSError:
        raise SystemExit('xhs-agy-mcp-bridge: could not run the native ACP command') from None


if __name__ == '__main__':
    raise SystemExit(main())
