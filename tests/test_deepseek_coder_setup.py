"""Exercise selective setup with dummy data, without starting Harness or models."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "integrations/openmausbot/setup.sh"


class DeepSeekCoderSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.dsh = self.base / "dsh"
        self.omb = self.base / "omb"
        (self.dsh / "profiles/desktop/node_modules").mkdir(parents=True)
        self.doc = self.dsh / "profiles/omb-doc/cordis.patch.yml"
        self.doc.parent.mkdir()
        self.doc.write_text("# preserved doc\n- id: dsh-connect-workbuddy\n  config:\n    marker: dummy-initial\n")
        self.coder = self.dsh / "profiles/omb-coder/cordis.patch.yml"
        self.coder.parent.mkdir()
        self.coder.write_text("# preserved glm\n")
        self.omb.mkdir()
        self.config = self.omb / "config.json"
        self.initial = {"unrelated": {"keep": True}, "instances": {
            "omb-coder": {"driver": "customAcp", "config": {"cli": "original-coder"}},
            "agy-gemini": {"driver": "customAcp", "config": {"cli": "original-gemini"}},
        }}
        self.config.write_text(json.dumps(self.initial))

    def run_setup(self, *args):
        result = subprocess.run(["bash", str(SETUP), *args], cwd=ROOT,
                                env={**os.environ, "DSH_HOME": str(self.dsh), "OMB_DATA_DIR": str(self.omb)},
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_selective_setup_preserves_existing_roles_and_account_state(self):
        before = {p: p.read_bytes() for p in (self.doc, self.coder)}
        self.run_setup("--only", "deepseek-coder")
        profile = self.dsh / "profiles/omb-deepseek-coder"
        patch = profile / "cordis.patch.yml"
        self.assertIn("model: deepseek-v4.1-flash", patch.read_text())
        self.assertIn("marker: dummy-initial", patch.read_text())
        self.assertIn("agents/deepseek-coder/skills", patch.read_text())
        self.assertNotIn("agents/agent-doc/skills", patch.read_text())
        self.assertEqual(patch.stat().st_mode & 0o777, 0o600)
        self.assertEqual((profile / "node_modules").resolve(), (self.dsh / "profiles/desktop/node_modules").resolve())
        state = json.loads(self.config.read_text())
        for key, value in self.initial["instances"].items():
            self.assertEqual(state["instances"][key], value)
        self.assertEqual(state["unrelated"], self.initial["unrelated"])
        self.assertEqual(state["instances"]["omb-deepseek-coder"]["config"]["cli"],
                         str(ROOT / "run-acp-agent.sh") + " deepseek-coder")
        patch.write_text(patch.read_text().replace("dummy-initial", "dummy-updated"))
        self.run_setup("--only", "deepseek-coder")
        self.assertIn("marker: dummy-updated", patch.read_text())
        self.assertEqual(len(json.loads(self.config.read_text())["instances"]), 3)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_planning_and_review_profiles_are_independent_and_idempotent(self):
        before = {p: p.read_bytes() for p in (self.doc, self.coder)}
        roles = {"kimi-planner": "kimi-k3.1-pro", "glm-planner": "glm-5.3", "glm-reviewer": "glm-5.3",
                 "coordinator": "deepseek-v4.1-flash", "assistant": "deepseek-v4.1-flash"}
        for role, model in roles.items():
            with self.subTest(role=role):
                self.run_setup("--only", role)
                profile = self.dsh / f"profiles/omb-{role}"
                patch = profile / "cordis.patch.yml"
                text = patch.read_text()
                self.assertIn(f"model: {model}\n", text)
                self.assertIn(f"agents/{role}/skills", text)
                self.assertIn("provider: workbuddy", text)
                self.assertEqual(patch.stat().st_mode & 0o777, 0o600)
                patch.write_text(text.replace("dummy-initial", f"dummy-{role}"))
                self.run_setup("--only", role)
                self.assertIn(f"marker: dummy-{role}", patch.read_text())
                self.assertEqual(patch.read_text().count("- id: dsh-connect-workbuddy"), 1)
                cfg = json.loads(self.config.read_text())
                self.assertEqual(cfg["instances"][f"omb-{role}"]["config"]["cli"], str(ROOT / "run-acp-agent.sh") + " " + role)
        self.assertEqual(len(json.loads(self.config.read_text())["instances"]), 7)
        for p, content in before.items():
            self.assertEqual(p.read_bytes(), content)
        cfg = json.loads(self.config.read_text())
        for key, value in self.initial["instances"].items():
            self.assertEqual(cfg["instances"][key], value)

    def test_invalid_selection_exits_before_creating_files(self):
        fresh = self.base / "not-created"
        result = subprocess.run(["bash", str(SETUP), "--only", "unknown"], cwd=ROOT,
                                env={**os.environ, "DSH_HOME": str(fresh), "OMB_DATA_DIR": str(fresh)},
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(fresh.exists())

    def test_default_setup_retains_original_scope(self):
        self.coder.write_text("- id: dsh-connect-workbuddy\n  config:\n    marker: dummy-coder\n")
        self.run_setup()
        self.assertIn("model: glm-5.3-flash", self.coder.read_text())
        self.assertIn("marker: dummy-coder", self.coder.read_text())
        self.assertIn("model: deepseek-v4.1-flash", self.doc.read_text())
        self.assertIn("marker: dummy-initial", self.doc.read_text())
        self.assertFalse((self.dsh / "profiles/omb-deepseek-coder").exists())
        self.assertNotIn("omb-deepseek-coder", json.loads(self.config.read_text())["instances"])


if __name__ == "__main__":
    unittest.main()
