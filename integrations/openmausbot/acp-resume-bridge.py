#!/usr/bin/env python3
"""OpenMausBot-only ACP alias: session/load -> Harness session/resume.

OpenMausBot already stores its transcript. Its generic ACP driver nevertheless
calls session/load to reopen the model's session. Harness 0.2.1-rc.2 persists
the full Agent but exposes session/resume instead. Translate that one request;
do not advertise loadSession or pretend to replay a transcript to other clients.

An idle session already owned by this connection is durably closed before its
next load, so the resume mounts the request's fresh MCP connections. Busy or
unknown sessions are never closed automatically. All real results, errors and
notifications pass through; the private close result alone is consumed here.
No prompts, tool results, credentials, or session identifiers are logged here.
"""

import json
import os
import queue
import signal
import subprocess
import sys
import threading
import uuid
from pathlib import Path
import re
import base64


def session_binding(params):
    """Extract only OMB's two identifiers; never persist MCP headers or env."""
    found = []
    servers = params.get('mcpServers', []) if isinstance(params, dict) else []
    for server in servers if isinstance(servers, list) else []:
        if not isinstance(server, dict):
            continue
        envs = []
        env = server.get('env', [])
        if isinstance(env, list):
            envs.append({row.get('name'): row.get('value') for row in env if isinstance(row, dict)
                         and row.get('name') in ('OMB_BOT_ID', 'OMB_THREAD_ID')})
        headers = server.get('headers', [])
        for header in headers if isinstance(headers, list) else []:
            if not isinstance(header, dict) or str(header.get('name', '')).lower() != 'x-omb-agents-env':
                continue
            value = header.get('value')
            if not isinstance(value, str) or len(value) > 65536:
                raise ValueError('Invalid OMB session binding')
            try:
                decoded = json.loads(base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True))
            except (ValueError, UnicodeDecodeError):
                raise ValueError('Invalid OMB session binding') from None
            if not isinstance(decoded, dict):
                raise ValueError('Invalid OMB session binding')
            envs.append({k: decoded[k] for k in ('OMB_BOT_ID', 'OMB_THREAD_ID') if k in decoded})
        for env in envs:
            if not env:
                continue
            if any(not isinstance(env.get(k), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', env[k])
                   for k in ('OMB_BOT_ID', 'OMB_THREAD_ID')):
                raise ValueError('Incomplete OMB session binding')
            found.append({'bot_id': env['OMB_BOT_ID'], 'thread_id': env['OMB_THREAD_ID']})
    if found and any(item != found[0] for item in found):
        raise ValueError('Conflicting OMB session bindings')
    return found[0] if found else None


class SessionBindings:
    """Task identity journal, deliberately separate from model-control revision."""

    def write(self, session_id, binding):
        if not isinstance(session_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', session_id):
            raise ValueError('Invalid native session id')
        base = Path(os.environ.get('DSH_HOME', str(Path.home() / '.dsh'))) / 'workflour-session-bindings'
        target = base / (session_id + '.json')
        if base.is_symlink() or target.is_symlink():
            raise ValueError('Unsafe native task binding path')
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        value = {'schema_version': 1, 'session_id': session_id,
                 **(binding if binding is not None else {'scope': 'non_omb'})}
        temporary = target.with_suffix('.tmp-' + uuid.uuid4().hex)
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as output:
                json.dump(value, output)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def verify(self, session_id, binding):
        base = Path(os.environ.get('DSH_HOME', str(Path.home() / '.dsh'))) / 'workflour-session-bindings'
        target = base / (session_id + '.json')
        if base.is_symlink() or target.is_symlink():
            raise ValueError('Unsafe native task binding path')
        expected = {'schema_version': 1, 'session_id': session_id,
                    **(binding if binding is not None else {'scope': 'non_omb'})}
        if json.loads(target.read_text()) != expected:
            raise ValueError('Native task binding changed after session acknowledgement')


def harness_request(line):
    """Preserve wire IDs/params; only rename the explicit load request."""
    try:
        message = json.loads(line)
    except (ValueError, UnicodeDecodeError):
        return line
    if (
        isinstance(message, dict)
        and message.get("jsonrpc") == "2.0"
        and message.get("method") == "session/load"
        and "id" in message
    ):
        message["method"] = "session/resume"
        return (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
    return line


def frame(line):
    try:
        value = json.loads(line)
        return value if isinstance(value, dict) and value.get("jsonrpc") == "2.0" else None
    except (ValueError, UnicodeDecodeError):
        return None


def encode(message):
    return (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")


def rpc_key(value):
    # Numeric/string IDs are different; do not confuse 0 with a false value.
    return type(value).__name__, json.dumps(value, sort_keys=True)


def selection_from(result):
    """Read only the two acknowledged native controls, not arbitrary config."""
    selected = {}
    if not isinstance(result, dict):
        return selected
    models = result.get("models")
    if isinstance(models, dict) and isinstance(models.get("currentModelId"), str):
        selected["model"] = models["currentModelId"]
    options = result.get("configOptions")
    for option in options if isinstance(options, list) else []:
        if isinstance(option, dict) and option.get("id") in ("model", "reasoning_effort"):
            value = option.get("currentValue")
            if isinstance(value, str):
                selected[option["id"]] = value
    return selected


class ModelControls:
    """Persist a baseline separately from actual selection revisions.

    OMB resends the same reasoning setter every turn. It carries no human/UI
    provenance, so a successful same-value setter is necessarily idempotent.
    """

    def path(self, session_id):
        if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", session_id):
            raise ValueError("Invalid native session id")
        base = Path(os.environ.get("DSH_HOME", str(Path.home() / '.dsh'))) / 'workflour-fallback-controls'
        return base / (session_id + '.json')

    def read(self, session_id):
        try:
            value = json.loads(self.path(session_id).read_text())
        except FileNotFoundError:
            return {}
        if not isinstance(value, dict) or not isinstance(value.get("selection", {}), dict):
            raise ValueError("Invalid model control state")
        selection = value.get("selection", {})
        if any(key not in ("model", "reasoning_effort") or not isinstance(item, str)
               for key, item in selection.items()):
            raise ValueError("Invalid model control selection")
        return value

    def write(self, session_id, selection, changed=False):
        target = self.path(session_id)
        value = self.read(session_id)
        value.update({"schema_version": 2, "selection": dict(selection),
                      "revision": uuid.uuid4().hex if changed else value.get("revision")})
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = target.with_suffix('.tmp-' + uuid.uuid4().hex)
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as output:
                json.dump(value, output)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)


class ResumeBridge:
    """One connection's state; called serially by the relay's event loop.

    Ownership comes only from successful native new/resume responses. A prompt
    remains busy until its response, even after a cancel notification. Private
    close IDs are distinct from outstanding client requests; a later colliding
    client ID waits for that private response rather than being misrouted.
    """

    def __init__(self, controls=None, bindings=None):
        self.owned = set()
        self.pending = {}
        self.closes = {}
        self.held = {}
        self.can_close = False
        self.controls = controls
        self.selections = {}
        self.bindings = bindings
        self.unbound = set()
        self.binding_expectations = {}

    def binding_error(self, ident):
        return [('client', encode({'jsonrpc': '2.0', 'id': ident, 'error': {
            'code': -32603, 'message': 'Native task identity could not be verified or recorded; task was not started'}}))]

    def control_error(self, ident):
        return [("client", encode({"jsonrpc": "2.0", "id": ident, "error": {
            "code": -32603, "message": "Native model controls could not be recorded; task was not started. Retry model settings before sending a task"}}))]

    def baseline(self, session_id, result, fresh=False):
        saved = self.controls.read(session_id) if self.controls else {}
        previous = saved.get("selection")
        self.selections[session_id] = {
            "selection": dict(previous) if previous and not fresh else selection_from(result),
            # Initial OMB setup can differ from the profile. Commit it on the
            # first prompt, without incorrectly calling it a manual override.
            "initializing": fresh or not previous,
        }

    def busy(self, session_id):
        return any(p["session"] == session_id for p in self.pending.values()) or any(
            p["session"] == session_id for p in self.closes.values())

    def client(self, line):
        request = frame(line)
        if request is None or "method" not in request or "id" not in request:
            return [("child", line)]
        key = rpc_key(request["id"])
        if key in self.closes:
            self.held.setdefault(key, []).append(line)
            return []
        params = request.get("params")
        session_id = params.get("sessionId") if isinstance(params, dict) else None
        method = request["method"]
        if method == 'session/prompt' and session_id in self.unbound:
            return self.binding_error(request['id'])
        if method == 'session/prompt' and self.bindings:
            try:
                if session_id not in self.binding_expectations:
                    raise ValueError('Resume the session before starting a prompt')
                self.bindings.verify(session_id, self.binding_expectations[session_id])
            except (OSError, ValueError):
                return self.binding_error(request['id'])
        binding = None
        if method in ('session/new', 'session/load', 'session/resume') and self.bindings:
            try:
                binding = session_binding(params)
            except ValueError:
                return self.binding_error(request['id'])
        if method == "session/prompt" and session_id in self.selections:
            state = self.selections[session_id]
            if state["initializing"]:
                try:
                    if self.controls:
                        self.controls.write(session_id, state["selection"])
                except (OSError, ValueError):
                    return self.control_error(request["id"])
                state["initializing"] = False
        if method == "session/load" and isinstance(session_id, str) and session_id in self.owned and self.can_close:
            if self.busy(session_id):
                return [("client", encode({"jsonrpc": "2.0", "id": request["id"], "error": {
                    "code": -32602, "message": "session is busy; refusing to close it for session/load"}}))]
            while True:
                private_id = "acp-resume-bridge:" + uuid.uuid4().hex
                private_key = rpc_key(private_id)
                if private_key not in self.pending and private_key not in self.closes and private_key != key:
                    break
            self.closes[private_key] = {"session": session_id, "request": request}
            return [("child", encode({"jsonrpc": "2.0", "id": private_id,
                                       "method": "session/close", "params": {"sessionId": session_id}}))]
        translated = harness_request(line)
        changed = {}
        if isinstance(params, dict):
            if method == "session/set_model" and isinstance(params.get("modelId"), str):
                changed["model"] = params["modelId"]
            elif method == "session/set_config_option" and params.get("configId") in ("model", "reasoning_effort") and isinstance(params.get("value"), str):
                changed[params["configId"]] = params["value"]
        self.pending[key] = {"method": "session/resume" if method == "session/load" else method,
                             "session": session_id, "selection": changed, "binding": binding}
        return [("child", translated)]

    def child(self, line):
        response = frame(line)
        if response is None or "method" in response or "id" not in response or not (
            "result" in response or "error" in response
        ):
            return [("client", line)]
        key = rpc_key(response["id"])
        closing = self.closes.pop(key, None)
        if closing is not None:
            self.owned.discard(closing["session"])
            request = closing["request"]
            if "error" in response:
                output = [("client", encode({**response, "id": request["id"]}))]
            else:
                # Use the original load params, never cached MCP credentials.
                self.binding_expectations.pop(closing['session'], None)
                output = self.client(encode(request))
            for held in self.held.pop(key, []):
                output.extend(self.client(held))
            return output
        pending = self.pending.pop(key, None)
        if pending is not None:
            method, session_id = pending["method"], pending["session"]
            if method == "session/close":
                self.owned.discard(session_id)
            if "error" not in response:
                result = response.get("result")
                if method == 'session/close':
                    self.binding_expectations.pop(session_id, None)
                if pending["selection"] and session_id in self.selections:
                    state = self.selections[session_id]
                    before = state["selection"]
                    after = {**before, **pending["selection"], **selection_from(result)}
                    changed = any(name in before and before[name] != value for name, value in after.items())
                    try:
                        if not state["initializing"] and self.controls and after != before:
                            self.controls.write(session_id, after, changed=changed)
                    except (OSError, ValueError):
                        return self.control_error(response["id"])
                    state["selection"] = after
                if method == "initialize" and isinstance(result, dict):
                    capabilities = result.get("agentCapabilities")
                    sessions = capabilities.get("sessionCapabilities") if isinstance(capabilities, dict) else None
                    self.can_close = isinstance(sessions, dict) and isinstance(sessions.get("close"), dict)
                elif method == "session/new" and isinstance(result, dict):
                    if isinstance(result.get("sessionId"), str):
                        self.owned.add(result["sessionId"])
                        try:
                            if self.bindings:
                                self.bindings.write(result['sessionId'], pending['binding'])
                        except (OSError, ValueError):
                            self.unbound.add(result['sessionId'])
                            return self.binding_error(response['id'])
                        self.unbound.discard(result['sessionId'])
                        self.binding_expectations[result['sessionId']] = pending['binding']
                        try:
                            self.baseline(result["sessionId"], result, fresh=True)
                        except (OSError, ValueError):
                            return self.control_error(response["id"])
                elif method == "session/resume" and isinstance(session_id, str):
                    self.owned.add(session_id)
                    try:
                        if self.bindings:
                            self.bindings.write(session_id, pending['binding'])
                    except (OSError, ValueError):
                        self.unbound.add(session_id)
                        return self.binding_error(response['id'])
                    self.unbound.discard(session_id)
                    self.binding_expectations[session_id] = pending['binding']
                    try:
                        self.baseline(session_id, result)
                    except (OSError, ValueError):
                        return self.control_error(response["id"])
        return [("client", line)]


def relay(command):
    """Keep both pipe directions moving; propagate EOF, signals and exit status."""
    process = subprocess.Popen(command, env={**os.environ, 'WORKFLOUR_REQUIRE_SESSION_BINDING': 'enabled'},
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def forward_signal(number, _frame):
        if process.poll() is None:
            try:
                process.send_signal(number)
            except ProcessLookupError:
                pass

    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, forward_signal)

    events = queue.Queue()
    bridge = ResumeBridge(controls=ModelControls(), bindings=SessionBindings())

    def read_frames(fd, source):
        pending = b""
        try:
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    if pending:
                        events.put((source, pending))
                    break
                pending += chunk
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    events.put((source, line + b"\n"))
        except (OSError, ValueError):
            pass
        finally:
            events.put((source, None))

    # Raw reads avoid a daemon holding Python's buffered stdin lock at exit.
    threading.Thread(target=read_frames, args=(sys.stdin.fileno(), "client"), daemon=True).start()
    threading.Thread(target=read_frames, args=(process.stdout.fileno(), "child"), daemon=True).start()
    input_done = False
    try:
        while True:
            source, line = events.get()
            if line is None:
                if source == "child":
                    break
                input_done = True
                output = []
            else:
                output = bridge.client(line) if source == "client" else bridge.child(line)
            for destination, data in output:
                if destination == "child":
                    while data:
                        data = data[os.write(process.stdin.fileno(), data):]
                else:
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
            # A deferred resume must be sent before propagating the client's EOF.
            if input_done and not bridge.closes and not process.stdin.closed:
                process.stdin.close()
    except (BrokenPipeError, OSError):
        # The ACP client went away; do not leave the Harness process running.
        process.terminate()
    finally:
        if not process.stdin.closed:
            try:
                process.stdin.close()
            except (BrokenPipeError, OSError):
                pass
        process.stdout.close()
    code = process.wait()
    return code if code >= 0 else 128 - code


def main():
    if len(sys.argv) < 2:
        print("usage: acp-resume-bridge.py EXECUTABLE [ARG ...]", file=sys.stderr)
        return 2
    try:
        return relay(sys.argv[1:])
    except OSError as error:
        print("acp-resume-bridge: unable to start child: {}".format(error.strerror), file=sys.stderr)
        return 127


if __name__ == "__main__":
    sys.exit(main())
