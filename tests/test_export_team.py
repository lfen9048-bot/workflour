import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("team_export", Path(__file__).parents[1] / "scripts/export-team.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class TeamExportTests(unittest.TestCase):
    def test_credentials_redacted_without_losing_routing_ids(self):
        value = MOD.clean({"api_key": "not-for-export", "access_token": "not-for-export",
                           "bot_id": "abc-123", "threadId": "def-456",
                           "text": "Authorization: Bearer sk-123456789abcdef"})
        self.assertEqual(value["api_key"], "[redacted]")
        self.assertEqual(value["access_token"], "[redacted]")
        self.assertNotIn("sk-123456789abcdef", value["text"])
        self.assertEqual(value["threadId"], "def-456")

    def test_output_refuses_existing_path_and_escape(self):
        with tempfile.TemporaryDirectory() as root:
            export = MOD.Export(Path(root) / "backup")
            with self.assertRaises(FileExistsError):
                MOD.Export(export.root)
            with self.assertRaises(ValueError):
                export.write("../outside.txt", "never")

    def test_private_files_redaction_and_hashes(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "MEMORY.md"
            source.write_text("token=sk-123456789abcdef\nrole: planner\n")
            export = MOD.Export(Path(root) / "backup")
            export.copy(source, "MEMORY.md")
            target = export.root / "MEMORY.md"
            self.assertNotIn("sk-123456789abcdef", target.read_text())
            self.assertEqual(export.root.stat().st_mode & 0o777, 0o700)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(export.files[0]["source_sha256"], MOD.sha(source.read_bytes()))
            self.assertEqual(export.files[0]["sha256"], MOD.sha(target.read_bytes()))

    def test_symlinks_and_credential_files_are_not_read(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "source"
            source.mkdir()
            (source / ".env").write_text("SENSITIVE=never-copy")
            (source / "alias.md").symlink_to(source / ".env")
            export = MOD.Export(Path(root) / "backup")
            export.tree(source, "files")
            self.assertEqual(len(export.files), 0)
            self.assertEqual(len(export.skipped), 2)

    def test_mutation_post_is_rejected_before_http(self):
        with self.assertRaises(ValueError):
            MOD.api("/api/bots/foo", {"hidden": True})
        with self.assertRaises(ValueError):
            MOD.api("/api/teams/export", {"format": "package"})

    def test_attachment_refs_do_not_accept_path_traversal(self):
        refs = MOD.attachment_names({"attachments": [{"url": "/api/attachments/abcd-1234.md"}]})
        self.assertEqual(refs, {"abcd-1234.md"})


if __name__ == "__main__":
    unittest.main()
