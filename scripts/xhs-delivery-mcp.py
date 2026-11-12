#!/usr/bin/env python3
"""Workspace stdio MCP for the two bounded XHS delivery operations.

JSON-RPC stays on stdout. Each call runs in a separate process group so EOF,
cancellation and the server deadline can stop work without a late success.
Only Python's standard library is required on macOS and Ubuntu.
"""
import argparse
import contextlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ('2025-11-25', '2025-06-18', '2025-03-26', '2024-11-05')
MAX_MESSAGE = 1024 * 1024
# ACP's standard server schema has no timeout/tool-setting fields. Its bounded
# helper uses 120s generation + 30s rendering; leave 8s cleanup before 180s.
CALL_TIMEOUT = 170 if os.environ.get('WORKFLOUR_XHS_ACP_BOUNDED') == '1' else 560
PROJECT_SCHEMA = {'type': 'string', 'description': 'Absolute path to an existing xhs-three content project.'}
FILE_SCHEMA = {'type': ['string', 'null'], 'description': 'Existing file inside the content project, using a project-relative path.'}
TOOLS = [
    {'name': 'prepare_delivery',
     'description': 'Wait for the bounded image attempt and card rendering, then return files to inspect. Does not publish or confirm visual review.',
     'inputSchema': {'type': 'object', 'properties': {
         'project': PROJECT_SCHEMA, 'image_prompt_file': FILE_SCHEMA,
         'existing_image_evidence': FILE_SCHEMA}, 'required': ['project'], 'additionalProperties': False}},
    {'name': 'confirm_delivery',
     'description': 'Confirm delivery only after actually viewing every returned final card. Does not perform user acceptance or publishing.',
     'inputSchema': {'type': 'object', 'properties': {
         'project': PROJECT_SCHEMA,
         'reviewed_images': {'type': 'array', 'items': {'type': 'string'},
                             'minItems': 1, 'maxItems': 7, 'uniqueItems': True}},
         'required': ['project', 'reviewed_images'], 'additionalProperties': False}},
]


def strict_json(value):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = item
        return result

    def constant(_):
        raise ValueError('Non-finite JSON number')

    return json.loads(value, object_pairs_hook=pairs, parse_constant=constant)


def path_string(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096 or any(c in value for c in ('\x00', '\n', '\r')):
        raise ValueError(label + ' must be a nonempty path string')
    return value


def validate_arguments(name, arguments):
    if name not in {tool['name'] for tool in TOOLS}:
        raise ValueError('Unknown delivery tool')
    if not isinstance(arguments, dict):
        raise ValueError('arguments must be an object')
    allowed = {'project', 'image_prompt_file', 'existing_image_evidence'} if name == 'prepare_delivery' else {'project', 'reviewed_images'}
    required = {'project'} if name == 'prepare_delivery' else allowed
    if set(arguments) - allowed or required - set(arguments):
        raise ValueError('Missing or unexpected tool arguments')
    project = Path(path_string(arguments['project'], 'project'))
    if not project.is_absolute() or project.is_symlink() or not project.is_dir():
        raise ValueError('project must be an absolute, existing directory, not a symlink')
    project = project.resolve(strict=True)
    state_file = project / '.xhs/state.json'
    if state_file.parent.is_symlink() or state_file.is_symlink() or not state_file.is_file() or state_file.stat().st_size > MAX_MESSAGE:
        raise ValueError('project must have a regular .xhs/state.json')
    state = strict_json(state_file.read_text(encoding='utf-8'))
    if not isinstance(state, dict) or state.get('workflow') != 'xhs-three' or type(state.get('version')) is not int or state['version'] != 1:
        raise ValueError('Only version 1 xhs-three projects are supported')

    def project_file(value, label):
        relative = Path(path_string(value, label))
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError(label + ' must use a project-relative path without ..')
        current = project
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ValueError(label + ' must not contain symlinks')
        path = project / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError(label + ' must be an existing regular project file')
        canonical = path.resolve(strict=True)
        try:
            canonical.relative_to(project)
        except ValueError:
            raise ValueError(label + ' must stay inside the content project') from None
        return str(canonical.relative_to(project))

    validated = {'project': str(project)}
    if name == 'prepare_delivery':
        if arguments.get('image_prompt_file') is not None and arguments.get('existing_image_evidence') is not None:
            raise ValueError('Choose either image_prompt_file or existing_image_evidence')
        for key in ('image_prompt_file', 'existing_image_evidence'):
            value = arguments.get(key)
            validated[key] = None if value is None else project_file(value, key)
    else:
        images = arguments['reviewed_images']
        if not isinstance(images, list) or not 1 <= len(images) <= 7:
            raise ValueError('reviewed_images must contain 1 to 7 image paths')
        validated['reviewed_images'] = [project_file(value, 'reviewed_images') for value in images]
        if len(set(validated['reviewed_images'])) != len(images):
            raise ValueError('reviewed_images must not repeat a file')
    return validated


def tool_result(value, error=False):
    return {'content': [{'type': 'text', 'text': json.dumps(value, ensure_ascii=False, allow_nan=False)}], 'isError': error}


def worker():
    """Revalidate at execution time; helper logs must never pollute MCP stdout."""
    output = sys.stdout
    try:
        payload = strict_json(sys.stdin.buffer.read(MAX_MESSAGE + 1))
        with contextlib.redirect_stdout(sys.stderr):
            name = payload['name']
            args = validate_arguments(name, payload['arguments'])
            from xhs_delivery import prepare, confirm
            args['project'] = Path(args['project'])
            value = prepare(**args) if name == 'prepare_delivery' else confirm(**args)
            if not isinstance(value, dict):
                raise ValueError('Delivery helper did not return an object')
        result = tool_result(value)
    except Exception as error:
        result = tool_result({'error': str(error)}, True)
    output.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + '\n')
    output.flush()


def stop_group(process):
    """The helper also cleans its own nested native-image process group."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        pass
    # Also stop children remaining after the worker has already exited.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


class Server:
    def __init__(self):
        self.active = None
        self.initialized = False
        self.stopping = False

    def emit(self, request_id, result=None, error=None):
        response = {'jsonrpc': '2.0', 'id': request_id}
        response['error' if error is not None else 'result'] = error if error is not None else result
        print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)

    def protocol_error(self, request_id, code, message):
        self.emit(request_id, error={'code': code, 'message': message})

    def cancel(self):
        if self.active:
            _, process, output, _ = self.active
            self.active = None
            stop_group(process)
            output.close()

    def request(self, raw):
        try:
            message = strict_json(raw)
        except (ValueError, UnicodeError):
            self.protocol_error(None, -32700, 'Invalid JSON')
            return
        if not isinstance(message, dict) or message.get('jsonrpc') != '2.0' or not isinstance(message.get('method'), str):
            self.protocol_error(None, -32600, 'Invalid request')
            return
        request_id = message.get('id')
        has_id = 'id' in message
        if has_id and (type(request_id) not in (int, str)):
            self.protocol_error(None, -32600, 'Invalid request id')
            return
        method, params = message['method'], message.get('params', {})
        if not has_id:
            if method == 'notifications/cancelled' and isinstance(params, dict) and self.active and type(params.get('requestId')) in (int, str) and params['requestId'] == self.active[0]:
                self.cancel()
            return
        if not isinstance(params, dict):
            self.protocol_error(request_id, -32602, 'params must be an object')
        elif self.active and request_id == self.active[0]:
            self.protocol_error(request_id, -32600, 'Request id is already active')
        elif method == 'initialize':
            if not isinstance(params.get('protocolVersion'), str):
                self.protocol_error(request_id, -32602, 'protocolVersion is required')
                return
            self.initialized = True
            version = params['protocolVersion']
            self.emit(request_id, {'protocolVersion': version if version in VERSIONS else VERSIONS[0],
                                   'capabilities': {'tools': {}},
                                   'serverInfo': {'name': 'workflour-xhs-delivery', 'version': '1.0.0'}})
        elif method == 'ping':
            self.emit(request_id, {})
        elif not self.initialized:
            self.protocol_error(request_id, -32000, 'Initialize the server first')
        elif method == 'tools/list':
            self.emit(request_id, {'tools': TOOLS})
        elif method == 'tools/call':
            try:
                if set(params) - {'name', 'arguments', '_meta'}:
                    raise ValueError('Unexpected tools/call parameters')
                name = params.get('name')
                if not isinstance(name, str):
                    raise ValueError('Tool name must be a string')
                args = validate_arguments(name, params.get('arguments', {}))
                if self.active:
                    raise ValueError('A delivery call is still running; wait for its result')
                output = tempfile.TemporaryFile()
                try:
                    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker'],
                                               stdin=subprocess.PIPE, stdout=output, stderr=sys.stderr,
                                               start_new_session=True, cwd=ROOT)
                    self.active = (request_id, process, output, time.monotonic())
                    process.stdin.write(json.dumps({'name': name, 'arguments': args}).encode() + b'\n')
                    process.stdin.close()
                except Exception:
                    if self.active:
                        self.cancel()
                    else:
                        output.close()
                    raise
            except (ValueError, OSError) as error:
                self.emit(request_id, tool_result({'error': str(error)}, True))
        else:
            self.protocol_error(request_id, -32601, 'Method not found')

    def poll(self):
        if not self.active:
            return
        request_id, process, output, started = self.active
        if time.monotonic() - started >= CALL_TIMEOUT:
            self.cancel()
            self.emit(request_id, tool_result({'error': 'Delivery deadline exceeded; inspect partial files before retrying.'}, True))
        elif process.poll() is not None:
            self.active = None
            try:
                stop_group(process)
                output.seek(0)
                raw = output.read(MAX_MESSAGE + 1)
                if process.returncode != 0 or len(raw) > MAX_MESSAGE:
                    raise ValueError('Delivery worker failed or exceeded its result limit')
                result = strict_json(raw)
                if not isinstance(result, dict) or type(result.get('isError')) is not bool or not isinstance(result.get('content'), list):
                    raise ValueError('Delivery worker returned an invalid result')
            except (ValueError, UnicodeError) as error:
                result = tool_result({'error': str(error)}, True)
            finally:
                output.close()
            self.emit(request_id, result)

    def run(self):
        def stop(_signum, _frame):
            self.stopping = True

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        buffer = b''
        try:
            while not self.stopping:
                readable, _, _ = select.select([sys.stdin.buffer], [], [], 0.1)
                if readable:
                    chunk = os.read(sys.stdin.fileno(), 65536)
                    if not chunk:  # EOF cancels work; it is not a success signal.
                        break
                    buffer += chunk
                    while b'\n' in buffer:
                        line, buffer = buffer.split(b'\n', 1)
                        if len(line) > MAX_MESSAGE:
                            self.protocol_error(None, -32700, 'Message size limit exceeded')
                            return
                        if line.strip():
                            self.request(line)
                    if len(buffer) > MAX_MESSAGE:
                        self.protocol_error(None, -32700, 'Message size limit exceeded')
                        break
                self.poll()
        except BrokenPipeError:
            pass
        finally:
            self.cancel()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker()
    else:
        Server().run()


if __name__ == '__main__':
    main()
