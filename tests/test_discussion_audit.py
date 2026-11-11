import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "discussion_audit", Path(__file__).with_name("omb-discussion-audit.py"))
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


class DiscussionAuditTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = Path(self.directory.name) / "runtime.db"
        self.connection = sqlite3.connect(str(self.db))
        self.connection.executescript("""
            CREATE TABLE assignments(id TEXT,root_id TEXT,parent_id TEXT,status TEXT,
              requester_thread_id TEXT,assignee_bot_id TEXT,assignee_thread_id TEXT,
              created_at INTEGER,finished_at INTEGER,json TEXT);
            CREATE TABLE assignment_events(id INTEGER,assignment_id TEXT,at INTEGER,
              kind TEXT,detail TEXT);
            CREATE TABLE inbox(id TEXT,owner_bot_id TEXT,owner_thread_id TEXT,
              owner_run_id TEXT,assignment_id TEXT,kind TEXT,created_at INTEGER,
              delivered_at INTEGER);
        """)
        self.add_row("root", "root", None, "target", "sender", "sender", "target", "work", 2)
        self.add_row("consult", "root", "root", "target", "sender", "reviewer", "child", "consult", 1)
        self.add_row("foreign", "foreign", None, "unrelated", "elsewhere", "elsewhere", "unrelated", "work", 1)
        self.connection.execute("INSERT INTO assignment_events VALUES (1,'root',20,'resume_due','event-secret')")
        self.connection.execute("INSERT INTO inbox VALUES ('inbox','sender','target',NULL,'consult','settled',19,20)")
        self.connection.commit()
        self.connection.close()

    def add_row(self, identifier, root, parent, request_thread, sender, recipient, target_thread, mode, executions):
        data = {"requester": {"kind": "bot_turn", "botId": sender},
                "assignee": {"destination": {"groupId": "group"}},
                "mode": mode, "reply": "resume", "outcome": "done",
                "executions": executions, "restarts": 0, "startedAt": 10,
                "reportedAt": 19, "rework": False,
                "brief": "private-brief-secret", "result": "private-model-result",
                "credentials": "secret-token", "reasoning": "private-reasoning"}
        self.connection.execute("INSERT INTO assignments VALUES (?,?,?,?,?,?,?,?,?,?)",
                                (identifier, root, parent, "completed", request_thread,
                                 recipient, target_thread, 1, 21, json.dumps(data)))

    def test_scoped_projection_drops_content_and_does_not_modify_database(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        report = audit_module.audit(self.db, "target", "sender", "reviewer")
        self.assertEqual([row["id"] for row in report["assignments"]], ["consult", "root"])
        serialized = json.dumps(report)
        for prohibited in ("private-brief-secret", "private-model-result", "secret-token",
                           "private-reasoning", "event-secret", "foreign", "unrelated"):
            self.assertNotIn(prohibited, serialized)
        self.assertTrue(report["checks"]["consult_exactly_one"])
        self.assertTrue(report["checks"]["consult_all_results_delivered"])
        self.assertTrue(report["checks"]["consult_all_parent_turns_resumed"])
        self.assertEqual(before, hashlib.sha256(self.db.read_bytes()).hexdigest())

    def test_no_assignments_is_not_reported_as_success(self):
        report = audit_module.audit(self.db, "unknown")
        self.assertEqual(report["assignments"], [])
        self.assertFalse(report["checks"]["consult_all_completed"])
        self.assertFalse(report["checks"]["work_all_results_delivered"])

    def test_output_cannot_replace_source_or_follow_symlink(self):
        for path in (self.db, Path(str(self.db) + "-wal"), Path(str(self.db) + "-shm")):
            with self.assertRaises(ValueError):
                audit_module.write_artifact(path, {}, self.db)
        link = Path(self.directory.name) / "alias.json"
        link.symlink_to(self.db)
        with self.assertRaises(ValueError):
            audit_module.write_artifact(link, {}, self.db)
        output = Path(self.directory.name) / "audit.json"
        audit_module.write_artifact(output, {"ok": True}, self.db)
        self.assertEqual(json.loads(output.read_text()), {"ok": True})


if __name__ == "__main__":
    unittest.main()
