import importlib.util
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("bot_model", Path(__file__).resolve().parents[1] / "scripts/bot-model.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeClient:
    def __init__(self):
        self.writes = []
        self.instances = [
            {"instanceId": "dsh-a", "cli": "/repo/run-acp-agent.sh coder", "models": {"options": [{"id": "dsh-model", "variants": [{"id": "high"}]}]}},
            {"instanceId": "dsh-b", "cli": "/repo/run-acp-agent.sh reviewer", "models": {"options": [{"id": "second", "variants": [{"id": "low"}]}]}},
            {"instanceId": "agy", "cli": "/repo/run-agy-agent.sh", "models": {"options": [{"id": "gemini", "variants": [{"id": "high"}]}]}},
        ]
        self.bot = {"id": "bot", "name": "Reviewer", "modelSelection": {"instanceId": "dsh-a", "model": "dsh-model"},
                    "tasks": [{"threadId": "old", "title": "Old task"}, {"threadId": "history"}]}
        self.fail_pin_once = False
        self.fail_recovery = False

    def call(self, method, path, body=None):
        if method == "GET":
            return copy.deepcopy({"instances": self.instances} if path == "/api/instances" else {"bots": [self.bot]})
        self.writes.append((method, path, body))
        if method == "POST":
            self.bot["tasks"].append({"threadId": "new"})
            return {"task": {"threadId": "new"}}
        if path.endswith("/model"):
            if self.fail_recovery:
                raise module.ControlError("Service unavailable during recovery")
            self.bot["modelSelection"] = copy.deepcopy(body)
        else:
            thread = path.rsplit("/", 1)[-1]
            if thread == "history" and self.fail_pin_once:
                self.fail_pin_once = False
                raise module.ControlError("Pin rejected")
            if body.get("updateBotDefault"):
                self.bot["modelSelection"] = copy.deepcopy(body["modelSelection"])
            task = next(t for t in self.bot["tasks"] if t["threadId"] == thread)
            task["modelSelection"] = copy.deepcopy(body["modelSelection"])
        return {}


class ModelControlTests(unittest.TestCase):
    def test_invalid_model_or_thinking_does_not_mutate(self):
        client = FakeClient()
        for model, thinking in [("missing", None), ("gemini", "max")]:
            with self.assertRaises(module.ControlError):
                module.switch(client, "bot", "old", "agy", model, thinking)
        self.assertEqual(client.writes, [])

    def test_same_runtime_only_changes_selected_task(self):
        client = FakeClient()
        result = module.switch(client, "bot", "old", "dsh-b", "second", "low")
        self.assertFalse(result["cross_runtime"])
        self.assertEqual(len(client.writes), 1)
        self.assertEqual(client.writes[0][1], "/api/bots/bot/tasks/old")
        self.assertFalse(client.writes[0][2]["updateBotDefault"])

    def test_cross_runtime_requires_project_before_new_task(self):
        client = FakeClient()
        with self.assertRaises(module.ControlError):
            module.switch(client, "bot", "old", "agy", "gemini")
        self.assertEqual(client.writes, [])

    def test_cross_runtime_creates_fresh_task_and_role_handoff(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "AGENTS.md").write_text("Project rules")
            result = module.switch(client, "bot", "old", "agy", "gemini", "high", project=root, role="Independent reviewer")
            self.assertTrue(result["cross_runtime"])
            self.assertEqual(result["thread_id"], "new")
            self.assertEqual(client.writes[0][2]["approvalMode"], "ask")
            self.assertFalse(client.writes[0][2]["select"])
            self.assertIn("Independent reviewer", Path(result["handoff"]).read_text())
            self.assertEqual(Path(result["handoff"]).stat().st_mode & 0o777, 0o600)
            self.assertNotIn("/tasks/old", [write[1] for write in client.writes])

    def test_explicit_default_preserves_other_conversations(self):
        client = FakeClient()
        original = copy.deepcopy(client.bot["modelSelection"])
        with tempfile.TemporaryDirectory() as temp, patch.object(module, "RECOVERY_DIR", Path(temp)):
            module.switch(client, "bot", "old", "dsh-b", "second", make_default=True)
        self.assertTrue(client.writes[0][2]["updateBotDefault"])
        self.assertEqual(client.writes[1][1], "/api/bots/bot/tasks/history")
        self.assertEqual(client.writes[1][2]["modelSelection"], original)
        client = FakeClient()
        client.bot["tasks"][1]["busy"] = True
        with self.assertRaises(module.ControlError):
            module.switch(client, "bot", "old", "dsh-b", "second", make_default=True)
        self.assertFalse(client.writes)

    def test_pin_failure_rolls_back_default_and_all_old_tasks(self):
        client = FakeClient()
        original = copy.deepcopy(client.bot["modelSelection"])
        client.fail_pin_once = True
        with tempfile.TemporaryDirectory() as temp, patch.object(module, "RECOVERY_DIR", Path(temp)):
            with self.assertRaisesRegex(module.ControlError, "original model settings restored"):
                module.switch(client, "bot", "old", "dsh-b", "second", make_default=True)
            journal = json.loads(next(Path(temp).glob("*.json")).read_text())
            self.assertEqual(journal["status"], "rolled_back")
        self.assertEqual(client.bot["modelSelection"], original)
        self.assertTrue(all(t["modelSelection"] == original for t in client.bot["tasks"]))

    def test_recovery_failure_keeps_journal_and_explicit_recover_works(self):
        client = FakeClient()
        original = copy.deepcopy(client.bot["modelSelection"])
        client.fail_pin_once = client.fail_recovery = True
        with tempfile.TemporaryDirectory() as temp, patch.object(module, "RECOVERY_DIR", Path(temp)):
            with self.assertRaisesRegex(module.ControlError, "recover --file"):
                module.switch(client, "bot", "old", "dsh-b", "second", make_default=True)
            path = next(Path(temp).glob("*.json"))
            self.assertEqual(json.loads(path.read_text())["status"], "recovery_required")
            client.fail_recovery = False
            self.assertTrue(module.recover(client, path)["recovered"])
            self.assertEqual(client.bot["modelSelection"], original)

    def test_widget_is_read_only_and_deduplicates_dsh_profiles(self):
        client = FakeClient()
        # Both DSH roles offer the same catalog; keep the Bot's own profile.
        client.instances[1]["models"] = copy.deepcopy(client.instances[0]["models"])
        result = module.widget(client, "bot", "old")
        form = result["widget"]["children"][0]
        field = form["children"][0]
        choices = [json.loads(o["value"]) for o in field["options"]]
        self.assertIn(["dsh-a", "dsh-model"], choices)
        self.assertNotIn(["dsh-b", "dsh-model"], choices)
        self.assertTrue(field["required"])
        self.assertFalse(field["allowOther"])
        self.assertEqual(client.writes, [])

    def test_widget_defaults_to_task_scope_and_only_real_levels(self):
        client = FakeClient()
        result = module.widget(client, "bot", "old", json.dumps(["agy", "gemini"]), "/project")
        fields = result["widget"]["children"][0]["children"]
        thinking = next(f for f in fields if f.get("name") == "thinking")
        self.assertEqual(thinking["options"], [{"label": "high", "value": "high"}])
        self.assertEqual(next(f for f in fields if f.get("name") == "scope")["defaultValue"], "task")
        self.assertEqual(next(f for f in fields if f.get("name") == "project")["defaultValue"], "/project")
        self.assertEqual(client.writes, [])

    def test_agy_uses_new_assistant_profile_with_legacy_fallback(self):
        client = FakeClient()
        legacy = copy.deepcopy(client.instances[0])
        legacy["instanceId"] = "omb-assistant"
        fresh = copy.deepcopy(legacy)
        fresh["instanceId"] = "omb-wf-assistant"
        client.instances += [legacy, fresh]
        choices = [json.loads(o["value"]) for o in module.model_choices(client.instances, "agy")]
        self.assertIn(["omb-wf-assistant", "dsh-model"], choices)
        self.assertNotIn(["omb-assistant", "dsh-model"], choices)
        choices = [json.loads(o["value"]) for o in module.model_choices(client.instances[:-1], "agy")]
        self.assertIn(["omb-assistant", "dsh-model"], choices)

    def test_temporary_agy_task_keeps_bot_default_dsh_role_catalog(self):
        client = FakeClient()
        fresh = copy.deepcopy(client.instances[0])
        fresh["instanceId"] = "omb-wf-assistant"
        client.instances.append(fresh)
        client.bot["tasks"][0]["modelSelection"] = {"instanceId": "agy", "model": "gemini"}
        result = module.widget(client, "bot", "old")
        choices = [json.loads(o["value"]) for o in result["widget"]["children"][0]["children"][0]["options"]]
        self.assertIn(["dsh-a", "dsh-model"], choices)
        self.assertNotIn(["omb-wf-assistant", "dsh-model"], choices)
        self.assertEqual(client.writes, [])

    def test_same_runtime_profile_precedes_bot_default_and_neutral(self):
        client = FakeClient()
        client.instances[1]["models"] = copy.deepcopy(client.instances[0]["models"])
        choices = [json.loads(o["value"]) for o in module.model_choices(client.instances, "dsh-b", "dsh-a")]
        self.assertIn(["dsh-b", "dsh-model"], choices)
        self.assertNotIn(["dsh-a", "dsh-model"], choices)

    def test_model_without_thinking_controls_and_unknown_model(self):
        client = FakeClient()
        client.instances[-1]["models"]["options"][0].pop("variants")
        result = module.widget(client, "bot", "old", json.dumps(["agy", "gemini"]))
        self.assertFalse(any(f.get("name") == "thinking" for f in result["widget"]["children"][0]["children"]))
        with self.assertRaises(module.ControlError):
            module.widget(client, "bot", "old", json.dumps(["agy", "unadvertised"]))
        self.assertEqual(client.writes, [])


if __name__ == "__main__":
    unittest.main()
