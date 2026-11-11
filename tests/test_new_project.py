"""Safety and integration checks for the reusable project initializer."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("new_project", ROOT / "scripts/new-project.py")
assert spec is not None and spec.loader is not None
initializer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(initializer)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NewProjectTest(unittest.TestCase):
    def test_code_team_initialization_is_opt_in_and_pending(self):
        with tempfile.TemporaryDirectory() as temp:
            target = initializer.create_project(Path(temp) / "team", workflow="code-team")
            state = json.loads((target / ".workflour/handoff.json").read_text())
            self.assertEqual(state["workflow"], {"kind": "code-team", "docs_required": False})
            self.assertEqual(state["planning"]["status"], "pending")
            self.assertEqual(state["owner"], "Code Team · 总控")
            self.assertNotIn("Codex 当前窗口协调", (target/"PROJECT-WORKFLOW.md").read_text())
            self.assertEqual(state["work_items"], [])
            self.assertEqual(state["review"]["reviewer"], "GLM Reviewer")
            self.assertEqual(state["acceptance"]["status"], "pending")

    def test_created_project_is_self_contained_and_preserves_upstream(self):
        baseline = [
            ROOT / "run-agent.sh",
            ROOT / "setup-agents.sh",
            ROOT / "agents/agent-coder/cordis.patch.yml",
            ROOT / "agents/agent-doc/cordis.patch.yml",
        ]
        profiles = Path.home() / ".dsh/profiles"
        baseline.extend(
            path for path in (
                profiles / "omb-coder/cordis.patch.yml",
                profiles / "omb-doc/cordis.patch.yml",
            ) if path.exists()
        )
        # Legacy headless profiles contain local account-pool choices and are
        # deliberately absent from a clean repository checkout. When present
        # locally, still prove project initialization leaves them untouched.
        before = {path: sha256(path) for path in baseline if path.exists()}
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "新的 项目"
            result = initializer.create_project(target, name="中文项目")
            self.assertEqual(result, target)
            self.assertIn("中文项目", (target / "README.md").read_text())
            self.assertFalse((target / ".git").exists())
            self.assertFalse((target / ".dsh").exists())
            self.assertFalse((target / ".agents").exists())
            self.assertFalse((target / ".specify/feature.json").exists())
            self.assertFalse((target / "specs").exists())
            manifest = json.loads((target / ".workflour/vendor/spec-kit/source.json").read_text())
            self.assertEqual(manifest["version"], "1.3.2")
            self.assertEqual(len(manifest["files"]), 20)
            for filename, expected in manifest["files"].items():
                self.assertEqual(sha256(target / filename), expected, filename)
            self.assertIn("MIT License", (target / ".workflour/vendor/spec-kit/LICENSE").read_text())
            self.assertEqual(sha256(target / ".workflour/check.py"), sha256(ROOT / "scripts/workflow-check.py"))
            self.assertTrue((target / ".specify/scripts/bash/create-new-feature.sh").stat().st_mode & 0o111)
            help_run = subprocess.run(
                [sys.executable, str(target / ".workflour/check.py"), "--help"],
                capture_output=True,
                text=True,
                check=False,
                cwd=temp,
            )
            self.assertEqual(help_run.returncode, 0, help_run.stderr)
            pending_run = subprocess.run(
                [sys.executable, str(target / ".workflour/check.py"), "check"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(pending_run.returncode, 0)
        self.assertEqual(before, {path: sha256(path) for path in before})

    def test_nonempty_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "existing"
            target.mkdir()
            sentinel = target / "README.md"
            sentinel.write_bytes(b"user content\x00\xff")
            with self.assertRaises(initializer.ProjectInitError):
                initializer.create_project(target)
            self.assertEqual(sentinel.read_bytes(), b"user content\x00\xff")
            self.assertEqual([path.name for path in target.iterdir()], ["README.md"])

    def test_existing_empty_directory_can_be_initialized_once(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "empty"
            target.mkdir()
            initializer.create_project(target)
            before = {str(path.relative_to(target)): sha256(path) for path in target.rglob("*") if path.is_file()}
            with self.assertRaises(initializer.ProjectInitError):
                initializer.create_project(target)
            after = {str(path.relative_to(target)): sha256(path) for path in target.rglob("*") if path.is_file()}
            self.assertEqual(before, after)

    def test_destination_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as temp:
            real = Path(temp) / "real"
            real.mkdir()
            linked = Path(temp) / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaises(initializer.ProjectInitError):
                initializer.create_project(linked)
            self.assertEqual(list(real.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
