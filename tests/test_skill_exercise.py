"""Offline checks for evaluation isolation; never starts a model or service."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("skill_exercise", ROOT / "tests/skills-specialization-live.py")
exercise = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exercise)


class SkillExerciseTests(unittest.TestCase):
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
