import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("agent_record_export", Path(__file__).resolve().parents[1] / "scripts/export-agent-record.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExportTests(unittest.TestCase):
    def test_only_visible_whitelisted_fields_are_exported(self):
        secret = "never-export-this-token"
        messages = [
            {"id": "one", "role": "user", "kind": "text", "text": 'token="visible-secret"; do task', "raw": secret},
            {"id": "two", "role": "bot", "kind": "activity", "text": secret,
             "tool": {"name": "read_file", "ok": True, "input": secret, "output": secret}},
            {"id": "three", "role": "bot", "kind": "reasoning", "text": secret},
            {"id": "four", "role": "bot", "kind": "text", "text": "Finished", "reasoning": secret},
            {"id": "five", "role": "bot", "kind": "options", "card": {"secret": secret}},
            {"id": "six", "role": "bot", "kind": "text", "channel": "analysis", "text": secret},
            {"id": "seven", "role": "bot", "kind": "text", "hidden": True, "text": secret},
        ]
        text = module.render(messages, "thread-1", "coder")
        self.assertNotIn(secret, text)
        self.assertNotIn("visible-secret", text)
        self.assertIn("Finished", text)
        self.assertIn("read_file", text)
        self.assertNotIn("three", text)

    def test_redacts_common_credentials(self):
        text = module.redact('Authorization: Bearer abc.def.ghi\napi_key=secret123&foo=1\nsk-abcdefgh1234')
        for secret in ('abc.def.ghi', 'secret123', 'sk-abcdefgh1234'):
            self.assertNotIn(secret, text)

    def test_output_is_exclusive_and_project_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"
            root.mkdir()
            out = module.write_record(root, "records/coder/conversation.md", "safe")
            self.assertEqual(out.read_text(), "safe")
            with self.assertRaises(FileExistsError):
                module.write_record(root, out, "overwrite")
            with self.assertRaises(ValueError):
                module.write_record(root, "../outside.md", "escape")
            (root / "linked").symlink_to(Path(temp), target_is_directory=True)
            with self.assertRaises(ValueError):
                module.write_record(root, "linked/outside.md", "escape")


if __name__ == "__main__":
    unittest.main()
