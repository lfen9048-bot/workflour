import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import io
from unittest.mock import patch
from compression import zstd

spec = importlib.util.spec_from_file_location("organize", Path(__file__).resolve().parents[1] / "scripts/dsh-session-organize.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class OrganizeTests(unittest.TestCase):
    def test_capture_requires_verified_bot_prompt_and_completed_turn(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project, home = root / "project", root / "home"
            project.mkdir()
            for sid, owner, complete in [("good", "Coder", True), ("foreign", "Another Bot", True), ("busy", "Coder", False)]:
                folder = home / "sessions" / "temporary" / sid
                folder.mkdir(parents=True)
                cache = home / "storages/session_projcache/sessions" / (sid + ".json")
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps({"record": {"rows": {"title": {"val": "You are the CAPTURE step"}}}}))
                events = [{"type": "session", "id": sid, "cwd": "/tmp/omb-acp-memory-abc123"}, {"type": "turn/start"}, {"type": "agent/inbox/spliced", "data": {"inserted": [{"content": f"You are the CAPTURE step of a memory system for an assistant named {owner}. You have no tools. Private text must not be exported."}]}}]
                if complete:
                    events.append({"type": "turn/end"})
                with zstd.open(folder / "session.v4.jsonl.zstd", "wt") as stream:
                    stream.write("\n".join(map(json.dumps, events)) + "\n")
            class Opener:
                def open(self, *args, **kwargs):
                    return io.StringIO(json.dumps({"bots": [{"id": "owned", "name": "Coder", "cwd": str(project)}]}))
            manifest = mod.inventory(home, project)
            with patch.object(mod.urllib.request, "build_opener", return_value=Opener()):
                result = mod.add_verified_captures(manifest, ["Coder"])
            self.assertEqual([s["session_id"] for s in result["sessions"]], ["good"])
            self.assertNotIn("Private text", json.dumps(result))
            self.assertEqual(result["actions"][-1]["operation"], "rename_archive")

    def test_scope_and_durable_title_without_exporting_messages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            home = root / "home"
            for sid, cwd in [("mine", str(project)), ("other", "/another-project")]:
                folder = home / "sessions" / "directory" / sid
                folder.mkdir(parents=True)
                with zstd.open(folder / "session.v4.jsonl.zstd", "wt") as f:
                    for row in [{"type": "session", "id": sid, "cwd": cwd}, {"type": "message", "data": {"secret": "never-export"}}, {"type": "session/title", "data": {"title": "Original title"}}, {"type": "turn/start"}, {"type": "turn/end"}]:
                        f.write(json.dumps(row) + "\n")
            before = {str(p): p.read_bytes() for p in home.rglob("*") if p.is_file()}
            result = mod.inventory(home, project)
            self.assertEqual([r["session_id"] for r in result["sessions"]], ["mine"])
            self.assertEqual(result["sessions"][0]["title"], "Original title")
            self.assertNotIn("never-export", json.dumps(result))
            self.assertEqual(before, {str(p): p.read_bytes() for p in home.rglob("*") if p.is_file()})

    def test_undo_does_not_delete_sessions_and_preserves_blank_titles(self):
        result = mod.undo_manifest({"actions": [{"kind": "workspace", "before_title": None}, {"kind": "session", "before_title": "", "session_id": "x"}]})
        self.assertEqual(result["actions"][0]["operation"], "manual_restore_required")
        self.assertEqual(result["actions"][1]["operation"], "remove_registration_only")

    def test_output_is_private_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            mod.atomic_new_json(path, {"original": True})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                mod.atomic_new_json(path, {})
            self.assertEqual(json.loads(path.read_text()), {"original": True})
