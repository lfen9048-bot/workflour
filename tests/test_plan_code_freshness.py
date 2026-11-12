"""New plan-code contracts invalidate stale material without upgrading history."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("freshness_fixtures", ROOT / "tests/test_plan_code_workflow.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
checker, ledger = fixtures.checker, fixtures.ledger


class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PlanCodeEvidenceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.project = self.fixture.project
        self.root = self.project.root
        self.project.save()
        self.path = self.root / ".workflour/coordination.json"
        self.state = {"workflow": "plan-code", "workflow_version": 3,
                      "freshness_version": 1, "phase": "plan", "repair_round": 0,
                      "coordinator_thread": "lead-thread", "assignments": {}}
        self.write_ledger()

    def write_ledger(self):
        self.path.write_text(json.dumps(self.state))

    def invoke(self, *args, failure=None, rows=()):
        before = self.path.read_bytes()
        output, error = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["coordinator-workflow.py", "--project", str(self.root),
                         "--actor", "plan-lead", *args]), \
             patch.object(ledger, "workflow_rows", return_value=list(rows)), \
             patch.object(ledger, "sender_idle", return_value=True), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            if failure:
                with self.assertRaises(SystemExit) as caught:
                    ledger.main()
                self.assertEqual(caught.exception.code, 2)
                self.assertIn(failure, error.getvalue())
                self.assertEqual(before, self.path.read_bytes())
            else:
                ledger.main()
        self.state = json.loads(self.path.read_text())

    def lock_plan(self):
        self.invoke("record", "plan", "--evidence", "records/plan.md")
        self.assertEqual(self.state["requirements_snapshot"], self.project.requirements_snapshot())

    def completed(self, phase, role, evidence, suffix=""):
        key = phase + "/" + role + suffix
        self.state["assignments"][key] = {
            "status": "completed", "assignment_id": key, "dispatch_token": "token-" + key,
            "bot_id": role, "thread_id": "worker-" + key,
            "evidence": evidence, "evidence_sha256": checker.digest(self.root / evidence),
            "snapshot": self.project.snapshot()}
        return {"id": key, "status": "completed", "outcome": None,
                "tokens": ["token-" + key], "bot_id": role, "thread_id": "worker-" + key}

    def test_new_init_marks_version_without_inventing_a_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".workflour").mkdir()
            # No project metadata: this isolated CLI test must not register Obsidian.
            process = subprocess.run([sys.executable, str(ROOT / "scripts/coordinator-workflow.py"),
                "--project", str(root), "--actor", "plan-lead", "init", "NEW", "A real request",
                "--workflow", "plan-code", "--thread-id", "lead"], text=True, capture_output=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            state = json.loads((root / ".workflour/coordination.json").read_text())
            self.assertEqual(state["workflow_version"], 3)
            self.assertEqual(state["freshness_version"], 1)
            self.assertNotIn("requirements_snapshot", state)

    def test_plan_check_before_lock_and_implementation_require_lock(self):
        self.assertTrue(self.project.check("plan")["ok"])
        with self.assertRaisesRegex(checker.InvalidHandoff, "Record the final plan"):
            self.project.check("implement")
        self.lock_plan()
        self.assertTrue(self.project.check("acceptance")["ok"])
        self.invoke("advance", "implement")

    def test_new_template_copies_current_checker_and_allows_prelock_checks(self):
        copied = self.root / ".workflour/check.py"
        self.assertEqual(copied.read_bytes(), (ROOT / "scripts/workflow-check.py").read_bytes())
        self.state["phase"] = "research"
        self.write_ledger()
        for stage in ("requirements", "plan"):
            process = subprocess.run([sys.executable, str(copied), "check", "--stage", stage],
                                     cwd=self.root, text=True, capture_output=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertFalse(json.loads(process.stdout)["freshness"]["contract_locked"])

    def test_same_requirement_id_new_criterion_invalidates_acceptance_and_advance(self):
        self.lock_plan()
        self.project.state["requirements"][0]["criterion"] = "Show 99 and persist the filter"
        self.project.save()
        with self.assertRaisesRegex(checker.InvalidHandoff, "Requirements/spec changed"):
            self.project.check("acceptance")
        self.invoke("advance", "implement", failure="Requirements/spec changed")

    def test_spec_or_original_request_change_is_not_hidden_by_unchanged_ids(self):
        self.lock_plan()
        original = self.project.artifact("spec").read_bytes()
        self.project.artifact("spec").write_text("New requirement, same R1")
        with self.assertRaisesRegex(checker.InvalidHandoff, "Requirements/spec changed"):
            self.project.check("acceptance")
        self.project.artifact("spec").write_bytes(original)
        self.project.state["original_request"] = "A different user request"
        with self.assertRaisesRegex(checker.InvalidHandoff, "Requirements/spec changed"):
            self.project.check("acceptance")

    def test_progress_metadata_changes_do_not_change_the_contract(self):
        self.lock_plan()
        self.project.state.update(next_owner="User", next_action="Await user acceptance", stage="acceptance")
        self.project.state["decisions"].append("Current tests and experience complete")
        self.assertTrue(self.project.check("acceptance")["ok"])

    def test_changed_prior_review_report_blocks_final_check_and_cli_advance(self):
        self.lock_plan()
        self.completed("review", "code-review", "records/review.md")
        row = self.completed("experience", "plan-review", "records/experience.json")
        self.state["phase"] = "experience"
        self.write_ledger()
        self.assertTrue(self.project.check("acceptance")["ok"])
        self.project.artifact("review").write_text("Changed after review: changes requested")
        with self.assertRaisesRegex(checker.InvalidHandoff, "review/code-review"):
            self.project.check("acceptance")
        self.invoke("advance", "acceptance", rows=[row], failure="review/code-review")

    def test_old_planning_report_is_still_an_effective_dependency(self):
        self.lock_plan()
        self.state["assignments"]["research/plan-lead"] = {
            "status": "completed", "execution": "local", "evidence": "records/plan-lead.md",
            "evidence_sha256": checker.digest(self.root / "records/plan-lead.md"), "snapshot": {}}
        self.state["repair_round"] = 1
        self.state["phase"] = "implement"
        self.write_ledger()
        (self.root / "records/plan-lead.md").write_text("Replaced old research")
        with self.assertRaisesRegex(checker.InvalidHandoff, "research/plan-lead"):
            self.project.check("implement")

    def test_repair_skips_superseded_reports_and_old_code_snapshots(self):
        self.lock_plan()
        self.completed("review", "code-review", "records/review.md")
        self.state.update(phase="review")
        self.write_ledger()
        self.invoke("rework", "--reason", "Fix actual review findings", "--evidence", "records/review.md")
        (self.root / "app.py").write_text("value = 43\n")
        # Repaired code differs from local-plan/old-review snapshots. A retired
        # report is history, not an active dependency; its old bytes are ignored.
        (self.root / "records/review.md").write_text("Historical round-zero report changed")
        (self.root / "records/implementation-r1.md").write_text("Round-one implementation")
        # A repaired implementation now needs current test evidence before
        # entering review, independently of old report freshness checks.
        with contextlib.redirect_stdout(io.StringIO()):
            self.project.run_test([sys.executable, '-c', 'print(43)'])
        row = self.completed("implement", "code-main", "records/implementation-r1.md", "@1")
        self.write_ledger()
        self.assertTrue(self.project.check("implement")["ok"])
        self.invoke("advance", "review", rows=[row])
        self.assertEqual(self.state["phase"], "review")
        # The same exemption must not apply to this round's report.
        (self.root / "records/implementation-r1.md").write_text("Changed current report")
        with self.assertRaisesRegex(checker.InvalidHandoff, "implement/code-main@1"):
            self.project.check_freshness()

    def test_active_implementation_report_and_missing_report_are_rejected(self):
        self.lock_plan()
        self.completed("implement", "code-main", "records/tasks.md")
        self.write_ledger()
        (self.root / "records/tasks.md").unlink()
        with self.assertRaisesRegex(checker.InvalidHandoff, "implement/code-main"):
            self.project.check_freshness()

    def test_legacy_ledger_stays_legacy_without_historical_backfill(self):
        self.state.update(workflow_version=2)
        self.state.pop("freshness_version")
        self.write_ledger()
        before = self.path.read_bytes()
        self.project.state["requirements"][0]["criterion"] = "Different legacy criterion"
        self.project.artifact("review").write_text("Different legacy report")
        result = self.project.check("acceptance")
        self.assertEqual(result["freshness"]["mode"], "legacy")
        self.assertEqual(before, self.path.read_bytes())
        self.invoke("record", "plan", "--evidence", "records/plan.md")
        self.assertNotIn("requirements_snapshot", self.state)
        self.assertNotIn("freshness_version", self.state)

    def test_missing_or_unknown_version_cannot_downgrade_a_new_ledger(self):
        original = copy.deepcopy(self.state)
        for version, marker in ((3, None), (3, 2), (4, 1), (3.0, 1), (3, True)):
            with self.subTest(version=version, marker=marker):
                self.state = copy.deepcopy(original)
                self.state["workflow_version"] = version
                if marker is None:
                    self.state.pop("freshness_version")
                else:
                    self.state["freshness_version"] = marker
                self.write_ledger()
                with self.assertRaisesRegex(checker.InvalidHandoff, "freshness version"):
                    self.project.check("plan")


if __name__ == "__main__":
    unittest.main()
