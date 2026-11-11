#!/usr/bin/env python3
"""Read only OMB coordination metadata; never export message or model content.

Example:
  python3 tests/omb-discussion-audit.py --thread-id THREAD --out audit.json

No requests are sent to bots or services. The only write is the requested JSON
artifact. The SQLite connection is read-only and selects individual metadata
fields rather than fetching assignment JSON, event detail, briefs or results.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile


ASSIGNMENTS_SQL = """
WITH roots AS (
  SELECT DISTINCT root_id FROM assignments
  WHERE requester_thread_id = ? OR assignee_thread_id = ?
)
SELECT id, root_id, parent_id, status, requester_thread_id,
       assignee_bot_id, assignee_thread_id, created_at, finished_at,
       json_extract(json, '$.requester.kind') AS requester_kind,
       json_extract(json, '$.requester.botId') AS requester_bot_id,
       json_extract(json, '$.assignee.destination.groupId') AS group_id,
       json_extract(json, '$.mode') AS mode,
       json_extract(json, '$.reply') AS reply,
       json_extract(json, '$.outcome') AS outcome,
       json_extract(json, '$.executions') AS executions,
       json_extract(json, '$.restarts') AS restarts,
       json_extract(json, '$.startedAt') AS started_at,
       json_extract(json, '$.reportedAt') AS reported_at,
       json_extract(json, '$.rework') AS rework
FROM assignments WHERE root_id IN (SELECT root_id FROM roots)
ORDER BY created_at, id
"""


def identifier(value):
    if not re.fullmatch(r"[\w-]{1,128}", value, flags=re.ASCII):
        raise argparse.ArgumentTypeError("expected a thread or bot identifier")
    return value


def audit(db_path, thread_id, sender_id=None, recipient_id=None):
    db_path = Path(db_path).expanduser().resolve(strict=True)
    if not db_path.is_file():
        raise ValueError("runtime database must be a regular file")
    connection = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")  # One consistent read snapshot, including WAL.
        rows = [dict(row) for row in connection.execute(
            ASSIGNMENTS_SQL, (thread_id, thread_id))]
        for row in rows:
            row["events"] = [dict(item) for item in connection.execute(
                "SELECT id,assignment_id,at,kind FROM assignment_events "
                "WHERE assignment_id=? ORDER BY id", (row["id"],))]
            row["inbox"] = [dict(item) for item in connection.execute(
                "SELECT id,owner_bot_id,owner_thread_id,owner_run_id,"
                "assignment_id,kind,created_at,delivered_at FROM inbox "
                "WHERE assignment_id=? ORDER BY created_at,id", (row["id"],))]
    finally:
        connection.close()

    by_id = {row["id"]: row for row in rows}
    children = [row for row in rows if row["parent_id"] is not None
                and (sender_id is None or row["requester_bot_id"] == sender_id)
                and (recipient_id is None or row["assignee_bot_id"] == recipient_id)]
    checks = {"related_assignment_count": len(rows)}
    for label, mode in (("consult", "consult"), ("work", "work")):
        matches = [row for row in children if row["mode"] == mode]
        checks[label + "_assignment_count"] = len(matches)
        checks[label + "_exactly_one"] = len(matches) == 1
        checks[label + "_all_completed"] = bool(matches) and all(
            row["status"] == "completed" for row in matches)
        checks[label + "_all_executed_once"] = bool(matches) and all(
            row["executions"] == 1 and row["restarts"] == 0 for row in matches)
        checks[label + "_all_results_delivered"] = bool(matches) and all(
            row["reply"] == "resume" and any(
                item["owner_bot_id"] == row["requester_bot_id"]
                and item["owner_thread_id"] == row["requester_thread_id"]
                and item["delivered_at"] is not None for item in row["inbox"])
            for row in matches)
        checks[label + "_all_parent_turns_resumed"] = bool(matches) and all(
            (by_id.get(row["parent_id"], {}).get("executions") or 0) >= 2
            and any(event["kind"] == "resume_due" for event in
                    by_id.get(row["parent_id"], {}).get("events", []))
            for row in matches)
    return {
        "schema_version": 2,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "OpenMausBot runtime.db; SQLite mode=ro, metadata projection only",
        "thread_id": thread_id,
        "sender_id_filter": sender_id,
        "recipient_id_filter": recipient_id,
        "checks": checks,
        "assignments": rows,
        "scope": "Only assignment trees related to the supplied thread. No briefs, "
                 "results, event detail, native requests, credentials or model reasoning. "
                 "Work-mode metadata alone does not establish what the work did.",
    }


def write_artifact(path, data, db_path):
    path = Path(path).expanduser()
    if path.is_symlink():
        raise ValueError("output must not be a symbolic link")
    path = path.absolute()
    source = Path(db_path).expanduser().resolve()
    if path.resolve() in (source, Path(str(source) + "-wal"), Path(str(source) + "-shm")):
        raise ValueError("output must not replace the source database or its journal")
    if path.exists() and not path.is_file():
        raise ValueError("output must be a regular file")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".discussion-audit-", delete=False) as handle:
            temporary = handle.name
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thread-id", type=identifier, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path.home() / ".openmausbot")
    parser.add_argument("--sender-id", type=identifier)
    parser.add_argument("--recipient-id", type=identifier)
    args = parser.parse_args(argv)
    db_path = args.data_dir / "runtime.db"
    try:
        data = audit(db_path, args.thread_id, args.sender_id, args.recipient_id)
        write_artifact(args.out, data, db_path)
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.exit(1, "Audit failed: " + str(error) + "\n")
    print(json.dumps({"out": str(args.out.absolute()), "checks": data["checks"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
