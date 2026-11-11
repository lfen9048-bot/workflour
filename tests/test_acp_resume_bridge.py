"""Wire and process-contract checks for the OpenMausBot/Harness resume alias."""

import importlib.util
import json
import os
import signal
import subprocess
import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

BRIDGE = Path(__file__).resolve().parents[1] / "integrations/openmausbot/acp-resume-bridge.py"
SPEC = importlib.util.spec_from_file_location("acp_resume_bridge", BRIDGE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WireTests(unittest.TestCase):
    def test_load_keeps_id_and_complete_session_params(self):
        request = {"jsonrpc": "2.0", "id": "opaque-请求", "method": "session/load", "params": {
            "sessionId": "existing-session", "cwd": "/tmp/项目",
            "mcpServers": [{"name": "tool", "command": "/bin/echo", "args": ["safe"], "env": []}],
        }}
        result = json.loads(MODULE.harness_request(json.dumps(request).encode()))
        self.assertEqual(result, {**request, "method": "session/resume"})

    def test_numeric_zero_id_is_preserved(self):
        result = json.loads(MODULE.harness_request(b'{"jsonrpc":"2.0","id":0,"method":"session/load"}\n'))
        self.assertEqual(result["id"], 0)
        self.assertEqual(result["method"], "session/resume")

    def test_other_frames_are_byte_for_byte_unchanged(self):
        for line in [
            b'{"jsonrpc":"2.0","id":3,"method":"session/prompt","params":{"text":"session/load"}}\r\n',
            b'{"jsonrpc":"2.0","id":"permission","result":{"outcome":{"outcome":"cancelled"}}}\n',
            b'{"jsonrpc":"2.0","method":"session/cancel","params":{"sessionId":"one"}}\n',
            b'{"jsonrpc":"2.0","method":"session/load"}\n',
            b'{"id":1,"method":"session/load"}\n',
            b'not-json\n', b'\xff\n', b'\n', b'[]\n',
        ]:
            with self.subTest(line=line):
                self.assertEqual(MODULE.harness_request(line), line)


class ModelControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        environment = patch.dict(os.environ, {"DSH_HOME": self.tmp.name})
        environment.start()
        self.addCleanup(environment.stop)
        self.store = MODULE.ModelControls()
        self.bridge = MODULE.ResumeBridge(controls=self.store)
        self.ident = 0

    def exchange(self, method, params=None, result=None, failed=False):
        self.ident += 1
        sent = self.bridge.client(MODULE.encode({"jsonrpc": "2.0", "id": self.ident,
            "method": method, "params": params or {}}))
        if sent and sent[0][0] == "client":
            return json.loads(sent[0][1])
        response = {"jsonrpc": "2.0", "id": self.ident}
        response.update({"error": {"code": -1}} if failed else {"result": result or {}})
        return json.loads(self.bridge.child(MODULE.encode(response))[0][1])

    def new(self):
        self.exchange("session/new", result={"sessionId": "one", "configOptions": [
            {"id": "model", "currentValue": "default"},
            {"id": "reasoning_effort", "currentValue": "high"}]})

    def set(self, key, value, **kwargs):
        return self.exchange("session/set_config_option", {
            "sessionId": "one", "configId": key, "value": value}, **kwargs)

    def prompt(self):
        return self.exchange("session/prompt", {"sessionId": "one", "prompt": []})

    def test_initial_model_and_thinking_are_baseline_and_repeat_is_idempotent(self):
        self.new()
        self.set("model", "chosen")
        self.set("reasoning_effort", "low")
        self.prompt()
        baseline = self.store.read("one")
        self.assertEqual(baseline["selection"], {"model": "chosen", "reasoning_effort": "low"})
        self.assertIsNone(baseline["revision"])
        for _ in range(3):
            self.set("reasoning_effort", "low")
            self.prompt()
        self.assertEqual(self.store.read("one"), baseline)
        self.assertEqual(self.store.path("one").stat().st_mode & 0o777, 0o600)

    def test_only_successful_actual_changes_advance_revision(self):
        self.new(); self.prompt()
        self.set("model", "changed", failed=True)
        self.assertIsNone(self.store.read("one")["revision"])
        self.set("model", "changed")
        first = self.store.read("one")["revision"]
        self.assertIsInstance(first, str)
        self.set("model", "changed")
        self.assertEqual(self.store.read("one")["revision"], first)
        self.set("reasoning_effort", "low")
        self.assertNotEqual(self.store.read("one")["revision"], first)

    def test_acknowledged_native_value_takes_precedence_over_requested_value(self):
        self.new(); self.prompt()
        self.set("reasoning_effort", "low", result={"configOptions": [
            {"id": "reasoning_effort", "currentValue": "high"}]})
        self.assertIsNone(self.store.read("one")["revision"])

    def test_restart_resume_preserves_baseline_and_detects_changed_native_model_setter(self):
        self.new(); self.prompt()
        self.bridge = MODULE.ResumeBridge(controls=self.store)
        self.exchange("session/load", {"sessionId": "one"}, result={"models": {"currentModelId": "default"}})
        self.set("reasoning_effort", "high")
        self.assertIsNone(self.store.read("one")["revision"])
        self.exchange("session/set_model", {"sessionId": "one", "modelId": "other"})
        self.assertTrue(self.store.read("one")["revision"])
        self.assertEqual(self.store.read("one")["selection"]["model"], "other")

    def test_legacy_marker_is_preserved_while_baseline_is_established(self):
        target = self.store.path("one")
        target.parent.mkdir()
        target.write_text('{"revision":"legacy"}')
        self.exchange("session/load", {"sessionId": "one"}, result={"models": {"currentModelId": "default"}})
        self.set("reasoning_effort", "high"); self.prompt()
        self.assertEqual(self.store.read("one")["revision"], "legacy")
        self.set("reasoning_effort", "high"); self.prompt()
        self.assertEqual(self.store.read("one")["revision"], "legacy")

    def test_corrupt_state_and_failed_baseline_write_block_prompt_explicitly(self):
        self.new()
        with patch.object(self.store, "write", side_effect=OSError("disk full")):
            response = self.prompt()
        self.assertEqual(response["error"]["code"], -32603)
        self.assertFalse(self.bridge.busy("one"))
        target = self.store.path("one")
        target.parent.mkdir()
        target.write_text('corrupt')
        self.bridge = MODULE.ResumeBridge(controls=self.store)
        response = self.exchange("session/load", {"sessionId": "one"})
        self.assertEqual(response["error"]["code"], -32603)


class ReloadTests(unittest.TestCase):
    def setUp(self):
        self.bridge = MODULE.ResumeBridge()
        self.send(1, "initialize")
        self.reply(1, {"agentCapabilities": {"sessionCapabilities": {"close": {}}}})
        self.send(2, "session/new", {"cwd": "/tmp", "mcpServers": []})
        self.reply(2, {"sessionId": "owned"})

    def send(self, request_id, method, params=None):
        return self.bridge.client(MODULE.encode({"jsonrpc": "2.0", "id": request_id,
                                                "method": method, "params": params or {}}))

    def reply(self, request_id, result):
        return self.bridge.child(MODULE.encode({"jsonrpc": "2.0", "id": request_id, "result": result}))

    def test_owned_idle_load_really_closes_then_resumes_with_fresh_params(self):
        params = {"sessionId": "owned", "cwd": "/tmp", "mcpServers": [{"name": "new-mcp"}]}
        output = self.send("load", "session/load", params)
        private = json.loads(output[0][1])
        self.assertEqual(private["method"], "session/close")
        self.assertEqual(private["params"], {"sessionId": "owned"})
        self.assertNotEqual(private["id"], "load")
        resumed = self.reply(private["id"], {})
        self.assertEqual(json.loads(resumed[0][1]), {"jsonrpc": "2.0", "id": "load",
                                                   "method": "session/resume", "params": params})
        real = {"configOptions": [{"id": "model", "currentValue": "native-model"}]}
        response = self.reply("load", real)
        self.assertEqual(json.loads(response[0][1])["result"], real)
        self.assertIn("owned", self.bridge.owned)
        # A second load is another real close, not a cached response.
        self.assertEqual(json.loads(self.send(0, "session/load", params)[0][1])["method"], "session/close")

    def test_busy_prompt_is_never_closed_cancelled_or_replayed(self):
        prompt = self.send("prompt", "session/prompt", {"sessionId": "owned", "prompt": [{"type": "text", "text": "once"}]})
        self.assertEqual(json.loads(prompt[0][1])["method"], "session/prompt")
        cancel = MODULE.encode({"jsonrpc": "2.0", "method": "session/cancel", "params": {"sessionId": "owned"}})
        self.assertEqual(self.bridge.client(cancel), [("child", cancel)])
        refused = self.send("load", "session/load", {"sessionId": "owned"})
        self.assertEqual(refused[0][0], "client")
        self.assertEqual(json.loads(refused[0][1])["error"]["code"], -32602)
        self.assertFalse(self.bridge.closes)
        self.reply("prompt", {"stopReason": "cancelled"})
        self.assertEqual(json.loads(self.send("load2", "session/load", {"sessionId": "owned"})[0][1])["method"], "session/close")

    def test_configuration_and_reload_inflight_also_block_close(self):
        self.send(3, "session/set_config_option", {"sessionId": "owned", "configId": "model", "value": "m"})
        self.assertEqual(self.send(4, "session/load", {"sessionId": "owned"})[0][0], "client")
        self.reply(3, {"configOptions": []})
        self.send(5, "session/load", {"sessionId": "owned"})
        self.assertEqual(self.send(6, "session/load", {"sessionId": "owned"})[0][0], "client")

    def test_close_failure_is_propagated_and_does_not_resume(self):
        private = json.loads(self.send(3, "session/load", {"sessionId": "owned"})[0][1])
        error = {"code": -32603, "message": "flush failed", "data": {"native": True}}
        output = self.bridge.child(MODULE.encode({"jsonrpc": "2.0", "id": private["id"], "error": error}))
        self.assertEqual(output, [("client", MODULE.encode({"jsonrpc": "2.0", "id": 3, "error": error}))])
        self.assertNotIn("owned", self.bridge.owned)

    def test_unknown_other_process_session_is_not_closed_and_error_passes_through(self):
        output = self.send(3, "session/load", {"sessionId": "elsewhere"})
        self.assertEqual(json.loads(output[0][1])["method"], "session/resume")
        error = MODULE.encode({"jsonrpc": "2.0", "id": 3, "error": {"code": -32602, "message": "locked elsewhere"}})
        self.assertEqual(self.bridge.child(error), [("client", error)])
        self.assertEqual(self.bridge.owned, {"owned"})

    def test_successful_resume_becomes_owned_without_touching_another_busy_session(self):
        self.send(3, "session/prompt", {"sessionId": "owned", "prompt": []})
        self.send(4, "session/load", {"sessionId": "restored"})
        self.reply(4, {"configOptions": []})
        private = json.loads(self.send(5, "session/load", {"sessionId": "restored"})[0][1])
        self.assertEqual(private["params"], {"sessionId": "restored"})
        self.assertTrue(self.bridge.busy("owned"))

    def test_notifications_and_child_requests_do_not_consume_response_ids(self):
        private = json.loads(self.send(3, "session/load", {"sessionId": "owned"})[0][1])
        for message in [
            {"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": "owned"}},
            {"jsonrpc": "2.0", "id": private["id"], "method": "session/request_permission", "params": {}},
        ]:
            line = MODULE.encode(message)
            self.assertEqual(self.bridge.child(line), [("client", line)])
        self.assertEqual(json.loads(self.reply(private["id"], {})[0][1])["method"], "session/resume")

    def test_private_id_collision_does_not_swallow_client_request(self):
        private = json.loads(self.send(3, "session/load", {"sessionId": "owned"})[0][1])
        self.assertEqual(self.send(private["id"], "session/list"), [])
        output = self.reply(private["id"], {})
        self.assertEqual([json.loads(data)["method"] for _, data in output], ["session/resume", "session/list"])
        native = {"sessions": []}
        self.assertEqual(json.loads(self.reply(private["id"], native)[0][1])["result"], native)

    def test_failed_new_resume_and_explicit_close_do_not_create_ownership(self):
        self.send(3, "session/load", {"sessionId": "missing"})
        self.bridge.child(MODULE.encode({"jsonrpc": "2.0", "id": 3, "error": {"code": -32602, "message": "missing"}}))
        self.assertNotIn("missing", self.bridge.owned)
        self.send(4, "session/close", {"sessionId": "owned"})
        self.reply(4, {})
        self.assertNotIn("owned", self.bridge.owned)

    def test_close_capability_is_required_and_malformed_frames_pass_through(self):
        for capability in [False, None, "false", True]:
            self.send(10, "initialize")
            self.reply(10, {"agentCapabilities": {"sessionCapabilities": {"close": capability}}})
            self.assertFalse(self.bridge.can_close)
            self.assertEqual(json.loads(self.send(3, "session/load", {"sessionId": "owned"})[0][1])["method"], "session/resume")
            self.reply(3, {})
        for line in [b'not-json\n', b'\xff\n', b'[]\n', b'{"jsonrpc":"2.0","method":"session/load"}\n']:
            self.assertEqual(self.bridge.client(line), [("child", line)])
        self.send(4, "session/load", {"sessionId": []})


class ProcessTests(unittest.TestCase):
    def invoke(self, child, data=b""):
        return subprocess.run([sys.executable, str(BRIDGE), sys.executable, "-u", "-c", child],
                              input=data, capture_output=True, timeout=8)

    def test_round_trip_and_child_stderr_not_filtered(self):
        result = self.invoke(
            'import sys; sys.stderr.write("diagnostic\\n"); '
            'sys.stdout.buffer.write(sys.stdin.buffer.read()); sys.stdout.flush()',
            b'{"jsonrpc":"2.0","id":7,"method":"session/load","params":{"sessionId":"s"}}\n',
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["method"], "session/resume")
        self.assertEqual(result.stderr, b"diagnostic\n")

    def test_child_stdout_is_never_parsed_or_dropped(self):
        result = self.invoke('import sys; sys.stdout.buffer.write(b"plain log\\n\\xff\\n")')
        self.assertEqual(result.stdout, b"plain log\n\xff\n")

    def test_large_bidirectional_payload_does_not_deadlock(self):
        payload = json.dumps({"jsonrpc": "2.0", "id": "big", "method": "session/load",
                              "params": {"extra": "a" * 400000}}).encode() + b"\n"
        result = self.invoke('import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())', payload)
        self.assertEqual(json.loads(result.stdout)["params"]["extra"], "a" * 400000)

    def test_child_exit_code_and_eof(self):
        self.assertEqual(self.invoke('import sys; sys.stdin.read(); sys.exit(7)').returncode, 7)

    def test_termination_is_forwarded_to_the_child(self):
        child = ('import signal,sys,time; '
                 'signal.signal(signal.SIGTERM,lambda *_:sys.exit(0)); '
                 'print("ready",flush=True); time.sleep(30)')
        process = subprocess.Popen([sys.executable, str(BRIDGE), sys.executable, "-u", "-c", child],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.assertEqual(process.stdout.readline(), b"ready\n")
            process.terminate()
            self.assertEqual(process.wait(timeout=5), 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdin.close()
            process.stdout.close()
            process.stderr.close()


if __name__ == "__main__":
    unittest.main()
