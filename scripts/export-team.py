#!/usr/bin/env python3
"""Export a private, read-only migration snapshot of local OpenMausBot teams.

Uses the native readable backup (POST /api/teams/export, format=backup), GETs,
and a read-only assignment query. Never deletes, imports, stops or patches bots.
Not an executable-session backup: see RESTORE-LIMITS.md in each export.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import urllib.parse
import urllib.request

SCRIPT_ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("record_export", SCRIPT_ROOT / "export-agent-record.py")
record = importlib.util.module_from_spec(spec)
spec.loader.exec_module(record)
TERMINAL = {"completed", "failed", "cancelled"}
SECRET_KEYS = re.compile(r"^(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|authorization|client[_-]?secret|private[_-]?key)$", re.I)
SECRET_FILES = re.compile(r"(^\.env($|\.)|credentials|cookies|auth\.json|sessions\.json|config\.json|id_rsa|id_ed25519|\.pem$|\.key$)", re.I)
MAX_FILE = 50 * 1024 * 1024
BOT_FIELDS = "id threadId name title description soul soulHash notifications color mascotBody mascotExpression mascotFaceColor modelSelection createdAt section cwd autoApprove pinned memoryEnabled approvalMode alwaysAllow chiefOfStaff hidden defaultBot welcomed sidebarHidden playbooks toolScope connectorTools computer browser composio helperModel avatarUrl tasks".split()
TASK_FIELDS = "threadId title createdAt updatedAt cwd openedBy closedBy pinned approvalMode autoApprove alwaysAllow modelSelection followsBotModel busy activity waitingForTeammates".split()


def now():
    return datetime.now(timezone.utc).isoformat()


def clean(value):
    if isinstance(value, str):
        return record.redact(value)
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, dict):
        return {key: "[redacted]" if SECRET_KEYS.fullmatch(key) else clean(item)
                for key, item in value.items()}
    return value


def sha(data):
    return hashlib.sha256(data).hexdigest()


def api(path, body=None):
    if body is not None and (path != "/api/teams/export" or body.get("format") != "backup"):
        raise ValueError("Only the native read-only backup POST is allowed")
    if not path.startswith("/api/") or ".." in path:
        raise ValueError("Invalid local API path")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), record.NoRedirect())
    request = urllib.request.Request("http://127.0.0.1:8799" + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"} if body is not None else {})
    with opener.open(request, timeout=60) as response:
        return json.load(response)


class Export:
    def __init__(self, destination):
        raw = Path(destination).expanduser()
        if raw.is_symlink():
            raise ValueError("Backup destination cannot be a symlink")
        self.root = raw.resolve()
        self.root.mkdir(parents=True, mode=0o700, exist_ok=False)
        os.chmod(self.root, 0o700)
        self.files, self.skipped, self.errors = [], [], []

    def write(self, name, data, source=None, original=None):
        target = self.root / name
        if self.root not in target.resolve().parents:
            raise ValueError("Backup output escaped its directory")
        target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        if isinstance(data, str):
            data = data.encode("utf-8")
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        row = {"path": str(name), "bytes": len(data), "sha256": sha(data)}
        if source is not None:
            row.update(source=str(source), source_sha256=sha(original), redacted=original != data)
        self.files.append(row)
        return target

    def json(self, name, value):
        return self.write(name, json.dumps(clean(value), ensure_ascii=False, indent=2) + "\n")

    def copy(self, source, name, binary=False):
        source = Path(source)
        if source.is_symlink():
            self.skipped.append({"source": str(source), "reason": "symlink: not followed"})
            return
        if not source.is_file():
            return
        if any(SECRET_FILES.search(part) for part in source.parts):
            self.skipped.append({"source": str(source), "reason": "credential/config filename: excluded without reading"})
            return
        if source.stat().st_size > MAX_FILE:
            self.errors.append({"source": str(source), "reason": "exceeds per-file limit"})
            return
        before = source.stat()
        original = source.read_bytes()
        try:
            text = original.decode("utf-8")
            if "\x00" in text:
                raise UnicodeError("binary")
            if source.suffix == ".json":
                data = (json.dumps(clean(json.loads(text)), ensure_ascii=False, indent=2) + "\n").encode()
            elif source.suffix in (".ndjson", ".jsonl"):
                data = ("\n".join(json.dumps(clean(json.loads(line)), ensure_ascii=False) for line in text.splitlines() if line.strip()) + "\n").encode()
            else:
                data = record.redact(text).encode()
        except (UnicodeError, ValueError):
            if not binary:
                self.skipped.append({"source": str(source), "reason": "opaque or malformed text: not copied"})
                return
            data = original  # Opaque attachments/data files stay only in the private backup.
        after = source.stat()
        if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
            self.errors.append({"source": str(source), "reason": "changed while being read"})
        self.write(name, data, source, original)

    def tree(self, source, name, binary=False):
        source = Path(source)
        if source.is_symlink():
            self.skipped.append({"source": str(source), "reason": "symlink root: not followed"})
            return
        if not source.exists():
            return
        for base, dirs, files in os.walk(source, followlinks=False):
            for dirname in list(dirs):
                path = Path(base) / dirname
                if path.is_symlink() or dirname in {".git", "node_modules", ".ssh"}:
                    dirs.remove(dirname)
                    self.skipped.append({"source": str(path), "reason": "symlink/private dependency directory: not followed"})
            for filename in sorted(files):
                path = Path(base) / filename
                self.copy(path, Path(name) / path.relative_to(source), binary=binary)


def assignments(data_dir):
    path = data_dir / "runtime.db"
    with sqlite3.connect(path.resolve(strict=True).as_uri() + "?mode=ro", uri=True, timeout=5) as connection:
        connection.execute("PRAGMA query_only=ON")
        names = "id root_id parent_id status requester_thread_id assignee_bot_id assignee_thread_id created_at finished_at".split()
        # Deliberately never select json: it includes prompts/results and capability information.
        return [dict(zip(names, row)) for row in connection.execute("SELECT " + ",".join(names) + " FROM assignments")]


def stable_view(roster):
    return {bot["id"]: {"busy": bot.get("busy"), "modelSelection": bot.get("modelSelection"),
        "threadId": bot.get("threadId"), "tasks": [
            {key: task.get(key) for key in ("threadId", "updatedAt", "busy", "activity", "modelSelection")}
            for task in bot.get("tasks", [])]} for bot in roster["bots"]}


def attachment_names(value):
    result = set()
    if isinstance(value, str):
        result.update(re.findall(r"/api/attachments/([A-Za-z0-9_.-]+)", value))
        result.update(re.findall(r"/\.openmausbot/attachments/([A-Za-z0-9_.-]+)", value))
    elif isinstance(value, dict):
        for item in value.values():
            result.update(attachment_names(item))
    elif isinstance(value, list):
        for item in value:
            result.update(attachment_names(item))
    return result


def discover_projects(project_root, registry):
    candidates = {Path(row["project"]).resolve(): row for row in registry}
    for base in (project_root / "projects", project_root / "examples"):
        for dirname, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = [name for name in dirs if name not in {".git", "node_modules", "vendor", "templates"}
                       and not (Path(dirname) / name).is_symlink()]
            if Path(dirname).name == ".workflour" and "handoff.json" in files:
                candidates.setdefault(Path(dirname).parent.resolve(), {})
    return candidates


def project_inventory(export, project_root, registry):
    rows = []
    for root, registration in sorted(discover_projects(project_root, registry).items()):
        handoff_file = root / ".workflour/handoff.json"
        if not handoff_file.is_file():
            rows.append({"project": str(root), "error": "registered handoff missing"})
            continue
        handoff = json.loads(handoff_file.read_text())
        ledger_file = root / ".workflour/coordination.json"
        ledger = json.loads(ledger_file.read_text()) if ledger_file.is_file() else {}
        slug = root.name + "-" + sha(str(root).encode())[:10]
        dest = Path("projects") / slug
        for filename in ("handoff.json", "coordination.json", "project.json", "observer-status.json"):
            export.copy(root / ".workflour" / filename, dest / ".workflour" / filename)
        for filename in ("HANDOFF.md", "PROJECT-WORKFLOW.md", "PLAN.md", "ACCEPTANCE.md", "README.md"):
            export.copy(root / filename, dest / filename)
        for directory in ("records", "specs", ".workflour/evidence", ".workflour/coordination-history"):
            export.tree(root / directory, dest / directory, binary=True)
        export.copy(root / "tests/manual-checklist.md", dest / "tests/manual-checklist.md")
        # External source trees remain in place; preserve files explicitly designated as deliverables.
        for filename in handoff.get("code_files", []):
            rel = Path(filename)
            if not rel.is_absolute() and ".." not in rel.parts:
                export.copy(root / rel, dest / "code" / rel, binary=True)
        assignees = sorted({item["bot_id"] for item in ledger.get("assignments", {}).values()
                            if isinstance(item, dict) and item.get("bot_id")})
        rows.append({"project": str(root), "backup": str(dest), "registered": bool(registration),
            "observer_suspended": registration.get("suspended", False),
            "task_id": handoff.get("task_id"), "stage": handoff.get("stage"), "phase": ledger.get("phase"),
            "acceptance": handoff.get("acceptance", {}).get("status"),
            "next_action": handoff.get("next_action"), "coordinator_thread": ledger.get("coordinator_thread"),
            "bot_ids": assignees, "unfinished": handoff.get("stage") != "done"})
    return rows


def export_team(args):
    os.umask(0o077)
    data_dir = Path(args.data_dir).expanduser().resolve(strict=True)
    export = Export(args.out)
    started = now()
    before = api("/api/bots?messages=0")
    native = api("/api/teams/export", {"format": "backup", "name": "Workflour before team rebuild"})
    if native.get("format") != "openmaus.backup" or native.get("version") != 1:
        raise ValueError("Unsupported native backup response")
    export.json("native-readable-backup.json", native)
    export.json("bots-public-settings.json", [{key: bot[key] for key in BOT_FIELDS if key in bot and key != "tasks"}
        | {"tasks": [{key: task[key] for key in TASK_FIELDS if key in task} for task in bot.get("tasks", [])]}
        for bot in before["bots"]])
    export.json("groups-public-settings.json", before.get("groups", []))
    config = api("/api/config")
    export.json("ui-feature-settings.json", {key: config.get(key) for key in ("features", "newBots", "threads", "language")})
    initial_assignments = assignments(data_dir)
    export.json("assignment-status-before.json", initial_assignments)
    registry_file = Path(args.registry).expanduser()
    registry = json.loads(registry_file.read_text()) if registry_file.exists() else []
    export.json("observer-registry.json", registry)
    projects = project_inventory(export, Path(args.project_root).resolve(), registry)
    export.json("projects-inventory.json", projects)
    native_bots = {bot["key"]: bot for bot in native["bots"]}
    coverage, referenced_attachments, all_threads = [], set(), set()
    thread_bots = {task["threadId"]: bot["id"] for bot in before["bots"] for task in bot.get("tasks", [])}
    for kind, records in (("bots", native["bots"]), ("groups", native.get("groups", []))):
        for owner in records:
            for task in owner["tasks"]:
                tid = record.identifier(task["key"])
                if tid in all_threads:
                    continue
                all_threads.add(tid)
                messages = record.read_thread(tid)
                referenced_attachments.update(attachment_names(messages))
                native_ids = {message["id"] for message in task["messages"]}
                public_ids = {message["id"] for message in messages}
                if native_ids != public_ids:
                    export.errors.append({"thread": tid, "reason": "native/public message IDs differ; inspect before deleting",
                        "native_only": len(native_ids - public_ids), "public_only": len(public_ids - native_ids)})
                lines = ["# " + owner["name"] + " · " + task["title"], "", "原始会话 ID：" + tid, ""]
                for message in task["messages"]:
                    lines += ["## " + message["role"] + " · " + message["id"], "", record.redact(message.get("text", "")), ""]
                export.write(Path("chats") / kind / owner["key"] / (tid + ".md"), "\n".join(lines))
                coverage.append({"owner_kind": kind, "owner_id": owner["key"], "thread_id": tid,
                    "native_messages": len(task["messages"]), "public_messages": len(messages),
                    "same_message_ids": native_ids == public_ids})
    expected_bots = {bot["id"] for bot in before["bots"]}
    if expected_bots != set(native_bots):
        export.errors.append({"reason": "native backup does not cover the live Bot roster"})
    for bot in before["bots"]:
        bid = record.identifier(bot["id"])
        expected = {task["threadId"] for task in bot.get("tasks", [])} or {bot["threadId"]}
        actual = {task["key"] for task in native_bots.get(bid, {}).get("tasks", [])}
        if expected != actual:
            export.errors.append({"bot_id": bid, "reason": "native backup does not cover all live tasks"})
        for directory in ("workspaces", "bots", "skill-state"):
            export.tree(data_dir / directory / bid, Path("local-bot-files") / directory / bid, binary=True)
        export.copy(data_dir / "memory-journal" / (bid + ".ndjson"), Path("local-bot-files/memory-journal") / (bid + ".ndjson"))
        referenced_attachments.update(attachment_names(bot.get("avatarUrl")))
    # Uploaded attachment store is separately scoped (no config, provider keys, sessions or logs).
    attachment_files = sorted(path for path in (data_dir / "attachments").glob("*") if path.is_file())
    for source in attachment_files:
        export.copy(source, Path("attachments") / source.name, binary=True)
    present = {path.name for path in attachment_files}
    missing = sorted(referenced_attachments - present)
    if missing:
        export.errors.append({"reason": "referenced attachments are absent from the store", "names": missing})
    export.json("attachment-coverage.json", {"referenced": sorted(referenced_attachments), "copied": sorted(present), "missing": missing})
    after = api("/api/bots?messages=0")
    final_assignments = assignments(data_dir)
    export.json("assignment-status-after.json", final_assignments)
    stable = stable_view(before) == stable_view(after) and initial_assignments == final_assignments
    if not stable:
        export.errors.append({"reason": "live tasks/model settings/assignments changed during export; re-export affected records"})
    active = [row for row in final_assignments if row["status"] not in TERMINAL]
    eligibility = []
    for bot in after["bots"]:
        bid = bot["id"]
        references = [row["project"] for row in projects if row.get("unfinished") and (
            bid in row.get("bot_ids", []) or thread_bots.get(row.get("coordinator_thread")) == bid)]
        reasons = []
        if "defaultBot" in bot and bot["defaultBot"] is not None and bot["defaultBot"] is not False:
            reasons.append("protected default Bot: only sidebarHidden is supported")
        if bid in args.keep_bot_id:
            reasons.append("explicitly retained Bot")
        if bot.get("busy") or any(task.get("busy") for task in bot.get("tasks", [])):
            reasons.append("running task")
        if any(row["assignee_bot_id"] == bid or thread_bots.get(row["requester_thread_id"]) == bid for row in active):
            reasons.append("nonterminal native assignment")
        if export.errors:
            reasons.append("export coverage or consistency errors")
        if references:
            reasons.append("unfinished project references: preserve handoff and retire/rebind observer before deletion")
        eligibility.append({"bot_id": bid, "name": bot["name"], "busy": bool(bot.get("busy")),
            "deletion_eligible_at_snapshot": not reasons, "reasons": reasons, "unfinished_projects": references,
            "task_count": len(bot.get("tasks", []))})
    export.json("deletion-eligibility.json", {"checked_at": now(), "advisory_only": True,
        "requires_fresh_idle_check_before_delete": True, "bots": eligibility})
    limits = """# 恢复范围与限制

本目录是私有迁移备份，目录 0700、文件 0600。没有执行删除、停止、导入、改模型或改权限。

- native-readable-backup.json 可通过原生团队备份导入；恢复文字、角色和记忆，但会创建新的 Bot、会话和消息 ID。
- 原生导入不恢复原 ACP session/resumeCursors，不恢复委派运行树、待审批请求、旧模型选择或权限；例行任务导入后禁用。
- bots-public-settings.json 另外保留原模型/档位、权限、职责、目录和任务设置，供人工核对，不能直接当 PATCH 请求批量回放。
- chats/ 是可读聊天；不包括隐藏推理、完整工具参数/结果或原生运行日志。不是无损会话存档。
- local-bot-files/ 保留有限 Bot 文件、工作区、记忆、skill-state；文本做尽力凭据脱敏。二进制附件/数据库仅私有保留，不保证可独立恢复。
- attachments/ 补存原生导出缺少的本地上传附件。无法自动识别图像或二进制内容中的秘密；不要公开整个目录。
- projects/ 仅存交接、计划/审核记录、证据和 handoff 指定代码，不是全项目备份；实际项目代码目录原地保留。
- 没有读取/复制 config.json、sessions.json、provider 凭据、浏览器配置、密钥或全量消息数据库。全局安装的 skills、DSH 配置与 DSH 原生会话不在本备份中。
- checksums.sha256 校验本备份文件；manifest.json 逐文件记录源与输出哈希以及脱敏情况。
- 运行期间若数据变化、附件缺失或消息覆盖不符，manifest.complete=false，不可据此删除原 Bot。删除前必须再次核查空闲和未结束项目。
- 不把“待用户验收”改成完成。旧项目如仍指向旧 Bot/thread，需另行保存交接并调整观察器引用。

实现依据：OpenMausBot 0.1.143 server/routes/teams.js 的 format=backup 分支，server/team-backup.js。
相关官方文档：https://docs.openmausbot.com/docs/troubleshooting/logs
"""
    export.write("RESTORE-LIMITS.md", limits)
    manifest = {"format": "workflour.private-team-export", "version": 1, "started_at": started, "finished_at": now(),
        "complete": not export.errors, "stable_live_snapshot": stable, "bot_count": len(native["bots"]),
        "group_count": len(native.get("groups", [])), "thread_count": len(all_threads),
        "message_count": sum(row["native_messages"] for row in coverage), "project_count": len(projects),
        "active_assignments": len(active), "thread_coverage": coverage, "files": list(export.files),
        "skipped": export.skipped, "errors": export.errors}
    export.json("manifest.json", manifest)
    export.write("checksums.sha256", "".join(row["sha256"] + "  " + row["path"] + "\n" for row in export.files))
    # Verify bytes after writing, not just hashes computed before a write.
    if any(sha((export.root / row["path"]).read_bytes()) != row["sha256"] for row in export.files):
        raise ValueError("Backup checksum verification failed")
    return {"output": str(export.root), "complete": manifest["complete"],
        "bots": manifest["bot_count"], "threads": manifest["thread_count"], "messages": manifest["message_count"],
        "projects": len(projects), "files": len(export.files), "errors": len(export.errors), "skipped": len(export.skipped)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="New private destination; existing paths are never overwritten")
    parser.add_argument("--data-dir", default=str(Path.home() / ".openmausbot"))
    parser.add_argument("--project-root", default=str(SCRIPT_ROOT.parent))
    parser.add_argument("--registry", default=str(Path.home() / ".workflour/observer/projects.json"))
    parser.add_argument("--keep-bot-id", action="append", default=[])
    args = parser.parse_args()
    try:
        result = export_team(args)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["complete"] else 2
    except (ValueError, OSError, TypeError, KeyError, sqlite3.Error) as error:
        print("Export failed: " + type(error).__name__ + "; original data was not modified; partial destination retained", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
