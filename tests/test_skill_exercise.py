"""Offline checks for evaluation isolation; never starts a model or service."""
import importlib.util
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("skill_exercise", ROOT / "tests/skills-specialization-live.py")
exercise = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exercise)


class SkillExerciseTests(unittest.TestCase):
    def test_read_evidence_uses_exact_structured_normalized_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            method = root / "SKILL.md"
            method.write_text("not requested")
            backup = root / "SKILL.md.backup"
            backup.write_text("actually requested")
            process = object.__new__(exercise.EvidenceProcess)
            process.fixture, process.methods = root, [method]
            process.session, process.report = "local", {"tools": []}
            process.consume({"method": "session/update", "params": {"sessionId": "local", "update": {
                "sessionUpdate": "tool_call", "toolCallId": "read-backup", "title": "read",
                "kind": "other", "status": "pending", "rawInput": {
                    "path": "./SKILL.md.backup", "note": str(method), "cwd": str(method)}}}})
            process.consume({"method": "session/update", "params": {"sessionId": "local", "update": {
                "sessionUpdate": "tool_call_update", "toolCallId": "read-backup", "status": "completed"}}})
            _, reads = exercise.file_observations(process.report["tools"], process.read_allowed)
            self.assertEqual([item["path"] for item in reads], [str(backup)])
            self.assertEqual(exercise.tool_file_paths({"rawInput": {"command": f"cat {method}"}}, root), [])
            self.assertEqual(exercise.tool_file_paths({"locations": [{"path": "./SKILL.md"}],
                                                      "rawInput": {"file_path": str(method)}}, root), [method])

    def test_image_permission_is_limited_to_explicit_fixture_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            fixture, methods = root / "fixture", root / "methods"
            fixture.mkdir(); methods.mkdir()
            (fixture / "image.png").write_bytes(b"fixture placeholder")
            method = methods / "SKILL.md"
            method.write_text("method")
            process = object.__new__(exercise.EvidenceProcess)
            process.fixture, process.methods = fixture, [method]
            process.session, process.text_only = "local", False
            def request(raw, kind="other"):
                return {"sessionId": "local", "toolCall": {
                    "title": "read_image", "kind": kind, "rawInput": raw}}
            for kind in ("other", "read"):
                with self.subTest(kind=kind):
                    self.assertEqual(process.allow_permission(request({"path": "./image.png"}, kind)),
                                     (True, "declared_fixture_image_read"))
                    self.assertEqual(process.allow_permission(request({"path": "../methods/image.png"}, kind)),
                                     (False, "image_outside_fixture"))
                    self.assertEqual(process.allow_permission(request({"cwd": str(fixture)}, kind)),
                                     (False, "missing_image_path"))
                    observed, reads = exercise.file_observations([{"id": "img", "title": "read_image",
                        "kind": kind, "status": "completed", "paths": [str(fixture / "image.png")]}], process.read_allowed)
                    self.assertEqual(len(observed), 1)
                    self.assertEqual(reads, [])  # Image observation is not a Markdown method read.
            process.text_only = True
            self.assertEqual(process.allow_permission(request({"path": "./image.png"})),
                             (False, "text_only_screening"))

    def test_unreadable_final_hashes_preserve_completed_and_failed_reports(self):
        for prompt_fails in (False, True):
            with self.subTest(prompt_fails=prompt_fails), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                fixture = root / "fixture"
                fixture.mkdir()
                (fixture / "TASK.md").write_text("Local fake protocol only.")
                observed_file = fixture / "temporary.txt"
                observed_file.write_text("read before removal")
                overlay = root / "runtime.yml"
                overlay.write_text("isolated: true\n")
                launcher = root / "never-launched"
                launcher.write_text("#!/bin/sh\nexit 99\n")
                launcher.chmod(0o700)
                output = root / "result.json"

                class Child:
                    def poll(self): return 0
                    def wait(self, timeout=None): return 0

                class FakeProcess:
                    def __init__(self, role, fixture, methods, report, text_only=False):
                        self.proc, self.report = Child(), report
                        self.session, self.protocol_errors, self.stderr_line_count = None, [], 0

                    def call(self, method, params, timeout):
                        options = [{"id": "model", "currentValue": "fake-model",
                                    "options": [{"value": "fake-model"}]},
                                   {"id": "reasoning_effort", "currentValue": "high",
                                    "options": [{"value": "high"}]}]
                        if method == "initialize":
                            return {"protocolVersion": 1}
                        if method == "session/new":
                            return {"sessionId": "fake-local", "configOptions": options}
                        if method == "session/set_config_option":
                            return {"configOptions": options}
                        if method == "session/prompt":
                            self.report["public_answer"] = "preserve this result"
                            self.report["tools"].append({"id": "read-one", "title": "read", "kind": "other",
                                                         "status": "completed", "paths": [str(observed_file)]})
                            observed_file.unlink()
                            overlay.unlink()
                            if prompt_fails:
                                raise exercise.ProbeError("fake_prompt_failure")
                            return {"stopReason": "end_turn"}
                        raise AssertionError(method)

                    def close_stdin(self): pass
                    def read_allowed(self, path): return exercise.inside(path, fixture)

                previous_launcher = exercise.smoke.LAUNCHER
                with patch.object(exercise, "EvidenceProcess", FakeProcess), \
                     patch.object(exercise, "fallback_metadata", lambda session: None), \
                     contextlib.redirect_stdout(io.StringIO()):
                    result = exercise.main(["--case", "research", "--variant", "baseline",
                        "--fixture", str(fixture), "--output", str(output), "--role", "eval",
                        "--launcher", str(launcher), "--model-id", "fake-model", "--method-mode", "inline",
                        "--text-only", "--runtime-file", str(overlay)])
                report = json.loads(output.read_text())
                self.assertEqual(result, 1 if prompt_fails else 0)
                self.assertEqual(report["status"], "failed" if prompt_fails else "completed")
                if prompt_fails:
                    self.assertEqual(report["error"], "fake_prompt_failure")
                self.assertEqual(report["public_answer"], "preserve this result")
                self.assertEqual(report["runtime_integrity"], "unverified")
                self.assertIsNone(report["runtime_files_after"][str(overlay)])
                self.assertEqual(report["runtime_file_observations_after"][str(overlay)]["error"], "FileNotFoundError")
                self.assertEqual(report["completed_read_files"][0]["file_status_after"], "unreadable")
                self.assertEqual(report["completed_read_files"][0]["hash_error_after"], "FileNotFoundError")
                self.assertEqual(exercise.smoke.LAUNCHER, previous_launcher)

    def test_only_completed_reads_count_as_read_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "reference.md"
            file.write_text("method")
            for kind, status in [("read", "failed"), ("edit", "completed")]:
                observed, reads = exercise.file_observations([
                    {"id": "one", "kind": kind, "paths": [str(file)]},
                    {"id": "one", "status": status, "paths": []}], lambda path: True)
                self.assertEqual(len(observed), 1)
                self.assertEqual(reads, [])
            _, reads = exercise.file_observations([
                {"id": "one", "kind": "read", "paths": [str(file)]},
                {"id": "one", "status": "completed", "paths": []}], lambda path: True)
            self.assertEqual(reads[0]["path"], str(file))
            _, reads = exercise.file_observations([
                {"id": "two", "kind": "other", "title": "read", "paths": [str(file)]},
                {"id": "two", "status": "completed"}], lambda path: True)
            self.assertEqual(reads[0]["path"], str(file))

    def test_generic_kind_uses_exact_tool_name_not_title_substrings(self):
        self.assertEqual(exercise.tool_operation({"kind": "other", "title": "bash"}), "execute")
        self.assertEqual(exercise.tool_operation({"kind": "other", "title": "read_image"}), "read_image")
        self.assertEqual(exercise.tool_operation({"kind": "other", "title": "echo read file"}), "other")
        self.assertEqual(exercise.tool_operation({"kind": "edit", "title": "read"}), "edit")

    def test_transport_starts_outside_repository_when_requested(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            launcher = root / "local-only.sh"
            launcher.write_text('#!/bin/sh\nprintf \'{"cwd":"%s"}\\n\' "$PWD"\n')
            launcher.chmod(0o700)
            with exercise.launcher_for("eval", launcher):
                process = exercise.smoke.AcpProcess("eval", launch_cwd=root)
                message = process._queue.get(timeout=3)
                process.proc.wait(timeout=3)
                process.close_stdin()
                process._reader.join(timeout=1)
                process._err.join(timeout=1)
                process.proc.stdout.close()
                process.proc.stderr.close()
                self.assertEqual(Path(json.loads(message)["cwd"]).resolve(), root.resolve())

    def test_text_screening_refuses_all_tool_permissions(self):
        process = object.__new__(exercise.EvidenceProcess)
        process.text_only = True
        self.assertEqual(process.allow_permission({"toolCall": {"kind": "execute", "rawInput": {"command": "true"}}}),
                         (False, "text_only_screening"))

    def test_without_method_baseline_is_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "TASK.md").write_text("Read the supplied facts and answer briefly.")
            args = exercise.parse_args(["--case", "research", "--variant", "baseline", "--fixture", str(root),
                                       "--output", str(root / "result.json"), "--role", "wf-plan-lead",
                                       "--method-mode", "inline", "--text-only"])
            self.assertEqual(args.method, [])

    def test_explicit_model_must_be_advertised_before_any_selection(self):
        class Process:
            def call(self, *args):
                raise AssertionError("an unavailable model must never be selected")
        with self.assertRaisesRegex(exercise.ProbeError, "not_advertised"):
            exercise.choose_model(Process(), {"models": {"availableModels": [{"modelId": "other"}]}},
                                  "eval", "low", lambda: 1, "mimo")

    def test_failed_ack_is_not_reported_as_model_success(self):
        class Process:
            session = "isolated"
            report = {"config_confirmations": []}

            def call(self, *args):
                return {"models": {"currentModelId": "wrong-model"}}
        with self.assertRaisesRegex(exercise.ProbeError, "not_acknowledged"):
            exercise.choose_model(Process(), {"models": {"availableModels": [{"modelId": "mimo"}]}},
                                  "eval", "low", lambda: 1, "mimo")

    def test_custom_launcher_is_restored_on_error(self):
        before = exercise.smoke.LAUNCHER
        with self.assertRaises(RuntimeError):
            with exercise.launcher_for("eval", Path("/private/tmp/isolated-launcher")):
                self.assertNotEqual(exercise.smoke.LAUNCHER, before)
                raise RuntimeError("exercise failed")
        self.assertEqual(exercise.smoke.LAUNCHER, before)


if __name__ == "__main__":
    unittest.main()
