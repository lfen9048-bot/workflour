"""Meaningful stage-gate, evidence, recovery and path-boundary regressions."""

import contextlib
import concurrent.futures
import importlib.util
import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

CHECKER = Path(__file__).resolve().parents[1] / "scripts/workflow-check.py"
SPEC = importlib.util.spec_from_file_location("workflow_check", CHECKER)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        (self.root / ".workflour").mkdir()
        self.state_path = self.root / ".workflour/handoff.json"
        self.code = self.root / "code.py"
        self.code.write_text("answer = 42\n")
        artifacts = {}
        for name in ("spec", "plan", "tasks", "review", "verification", "docs", "acceptance"):
            artifacts[name] = "records/" + name + ".md"
            path = self.root / artifacts[name]
            path.parent.mkdir(exist_ok=True)
            path.write_text("# " + name + "\n\nEvidence for " + name + ".\n")
        self.state = {
            "schema_version": 1, "task_id": "TEST-001", "stage": "acceptance",
            "owner": "Doc", "next_owner": "User", "next_action": "Review delivery",
            "implementation_owner": "Coder", "blockers": [],
            "requirements": [{"id": "REQ-1", "criterion": "answer equals 42"}],
            "artifacts": artifacts, "code_files": ["code.py"], "changed_files": ["code.py"],
            "baseline": {"code.py": None}, "tests": [],
            "review": {"status": "passed", "reviewer": "Gemini", "findings": [],
                       "snapshot": {"code.py": MODULE.digest(self.code)}},
            "verification": {"status": "pending"},
            "acceptance": {"status": "pending", "source": "", "quote": "", "at": ""},
        }
        self.write_state()

    def write_state(self):
        self.state_path.write_text(json.dumps(self.state))

    def project(self):
        return MODULE.Project(self.root)

    def run_test(self, project, argv):
        with contextlib.redirect_stdout(io.StringIO()):
            return project.run_test(argv)

    def passing(self):
        project = self.project()
        self.assertEqual(self.run_test(project, [sys.executable, "-c", "print('test passed')"]), 0)
        return project

    def test_current_evidence_allows_acceptance_but_not_done(self):
        project = self.passing()
        self.assertTrue(project.check("acceptance")["ok"])
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "Explicit user acceptance"):
            project.check("done")

    def team(self):
        project = self.passing()
        project.state["workflow"] = {"kind": "code-team", "docs_required": False}
        participants = ["Kimi", "DeepSeek", "GLM Planner"]
        records = []
        for index, owner in enumerate(participants):
            name = f"records/planning-{index}.md"
            (self.root / name).write_text(f"Independent contribution by {owner}\n")
            records.append({"owner": owner, "record": name})
        project.state["planning"] = {"participants": participants, "contributions": records,
                                     "status": "settled", "discussion_rounds": 2}
        project.state["work_items"] = [{"id": "CODE-1", "owner": "Antigravity",
                                         "files": ["code.py"], "status": "completed"}]
        return project

    def test_team_can_skip_docs_but_not_acceptance(self):
        project = self.team()
        (self.root / project.state["artifacts"]["docs"]).unlink()
        self.assertTrue(project.check("acceptance")["ok"])
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "docs is disabled"):
            project.check("docs")
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "Explicit user acceptance"):
            project.check("done")

    def test_team_rejects_overlapping_files_and_missing_owner(self):
        project = self.team()
        project.state["work_items"].append({"id": "CODE-2", "owner": "DeepSeek",
                                           "files": ["./code.py"], "status": "completed"})
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "Overlapping"):
            project.check("plan")
        project.state["work_items"][1]["files"] = ["extra.py"]
        (self.root / "extra.py").write_text("answer = 2\n")
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "included in code_files"):
            project.check("implement")
        (self.root / "extra.py").write_text("answer = 'broken'\n")
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "included in code_files"):
            project.check("acceptance")
        project.state["code_files"].append("extra.py")
        project.state["baseline"]["extra.py"] = None
        project.state["review"]["reviewer"] = "DeepSeek"
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "Reviewer must differ"):
            project.check("review")
        project.state["work_items"][0]["files"] = ["other.py"]
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "Every code_file"):
            project.check("implement")

    def test_team_requires_separate_planning_records_and_completed_work(self):
        project = self.team()
        project.state["planning"]["contributions"][1]["record"] = "records/planning-0.md"
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "records must be separate"):
            project.check("plan")
        project.state["planning"]["contributions"][1]["record"] = "records/planning-1.md"
        project.state["planning"]["discussion_rounds"] = 3
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "two discussion rounds"):
            project.check("plan")
        project.state["planning"]["discussion_rounds"] = 1
        project.state["work_items"][0]["status"] = "running"
        self.assertTrue(project.check("plan")["ok"])
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "incomplete"):
            project.check("implement")

    def test_done_needs_explicit_record_bound_to_current_snapshot(self):
        project = self.passing()
        project.state["acceptance"] = {
            "status": "accepted", "source": "user chat", "quote": "Accepted", "at": "2026-11-09T12:00:00Z",
        }
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "current code snapshot"):
            project.check("done")
        project.state["acceptance"]["snapshot"] = project.snapshot()
        self.assertTrue(project.check("done")["ok"])
        self.assertIn("not proof of human authorization", project.check("done")["meaning"])

    def test_code_change_invalidates_review_and_verification(self):
        project = self.passing()
        self.code.write_text("answer = 41\n")
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "Code changed after review"):
            project.check("acceptance")
        project.state["review"]["snapshot"] = project.snapshot()
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "not passed verification"):
            project.check("acceptance")

    def test_same_command_retry_passes_and_keeps_failed_evidence(self):
        project = self.project()
        # The input is deliberately outside code_files; code remains unchanged.
        # This simulates repairing a test environment, then rerunning exact argv.
        flag = self.root / "ready"
        argv = [sys.executable, "-c", "from pathlib import Path; raise SystemExit(0 if Path('ready').exists() else 1)"]
        self.assertEqual(self.run_test(project, argv), 1)
        with self.assertRaises(MODULE.InvalidHandoff):
            project.check("acceptance")
        flag.touch()
        self.assertEqual(self.run_test(project, argv), 0)
        self.assertEqual([record["exit_code"] for record in project.state["tests"]], [1, 0])
        self.assertTrue(project.check("acceptance")["ok"])
        saved = self.project()
        self.assertEqual(len(saved.state["tests"]), 2)
        self.assertNotEqual(saved.state["tests"][0]["evidence"], saved.state["tests"][1]["evidence"])

    def test_mutated_latest_or_historical_evidence_is_rejected(self):
        project = self.passing()
        self.run_test(project, [sys.executable, "-c", "print('test passed')"])
        for index in (0, 1):
            with self.subTest(index=index):
                evidence = self.root / project.state["tests"][index]["evidence"]
                original = evidence.read_bytes()
                evidence.write_text("edited test output")
                with self.assertRaisesRegex(MODULE.InvalidHandoff, "evidence is missing or has changed"):
                    project.check("acceptance")
                evidence.write_bytes(original)

    def test_implementer_cannot_review_own_code(self):
        project = self.passing()
        for name in ("Coder", " coder ", "CODER"):
            with self.subTest(name=name):
                project.state["review"]["reviewer"] = name
                with self.assertRaisesRegex(MODULE.InvalidHandoff, "Reviewer must differ"):
                    project.check("acceptance")
        del project.state["implementation_owner"]
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "Reviewer must differ"):
            project.check("acceptance")

    def test_unresolved_findings_block_acceptance(self):
        project = self.passing()
        project.state["review"]["findings"] = [{"status": "open", "resolution": ""}]
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "unresolved review finding"):
            project.check("acceptance")

    def test_manifest_paths_reject_absolute_parent_and_symlink_escape(self):
        project = self.project()
        outside = self.root.parent / "outside.txt"
        outside.write_text("not in the project")
        (self.root / "escape").symlink_to(self.root.parent, target_is_directory=True)
        for name in (str(outside), "../outside.txt", "a/../code.py", "escape/outside.txt"):
            with self.subTest(name=name), self.assertRaises(MODULE.InvalidHandoff):
                project.path(name)

    def test_symlinked_state_is_rejected_before_reading(self):
        outside = self.root.parent / "outside-state.json"
        outside.write_text(json.dumps(self.state))
        self.state_path.unlink()
        self.state_path.symlink_to(outside)
        with self.assertRaises(MODULE.InvalidHandoff):
            self.project()

    def test_output_paths_cannot_follow_external_symlinks(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        sentinel = outside / "sentinel.txt"
        sentinel.write_text("unchanged")
        project = self.project()
        (self.root / "HANDOFF.md").symlink_to(sentinel)
        with self.assertRaises(MODULE.InvalidHandoff):
            project.handoff()
        self.assertEqual(sentinel.read_text(), "unchanged")
        (self.root / ".workflour/evidence").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(MODULE.InvalidHandoff):
            self.run_test(project, [sys.executable, "-c", "print('must not run')"])
        self.assertEqual(list(outside.iterdir()), [sentinel])

    def test_stale_writer_does_not_erase_other_agents_test_history(self):
        first, second = self.project(), self.project()
        self.run_test(first, [sys.executable, "-c", "print('first')"])
        second.state["next_action"] = "stale edit"
        with self.assertRaisesRegex(MODULE.InvalidHandoff, "changed during this operation"):
            second.save()
        self.assertEqual(len(self.project().state["tests"]), 1)

    def test_simultaneous_writers_do_not_both_overwrite_state(self):
        first, second = self.project(), self.project()
        barrier = threading.Barrier(2)

        def save(project, action):
            project.state["next_action"] = action
            barrier.wait(timeout=5)
            try:
                project.save()
                return "saved"
            except MODULE.InvalidHandoff:
                return "stale"

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(save, first, "first"), pool.submit(save, second, "second")]
            outcomes = [result.result(timeout=5) for result in results]
        self.assertCountEqual(outcomes, ["saved", "stale"])
        self.assertIn(self.project().state["next_action"], ["first", "second"])

    def test_save_rejects_external_temporary_file_or_lock_symlink(self):
        outside = self.root.parent / "outside.txt"
        outside.write_text("unchanged")
        for name in ("handoff.json.tmp", "handoff.lock"):
            with self.subTest(name=name):
                link = self.root / ".workflour" / name
                if link.exists():
                    link.unlink()
                link.symlink_to(outside)
                with self.assertRaises(MODULE.InvalidHandoff):
                    self.project().save()
                self.assertEqual(outside.read_text(), "unchanged")
                link.unlink()

    def test_test_command_that_changes_source_is_not_a_pass(self):
        project = self.project()
        argv = [sys.executable, "-c", "from pathlib import Path; Path('code.py').write_text('answer = 43\\n')"]
        self.assertEqual(self.run_test(project, argv), 0)
        self.assertEqual(project.state["verification"]["status"], "failed")
        self.assertTrue(project.state["tests"][0]["source_changed_during_test"])


if __name__ == "__main__":
    unittest.main()
