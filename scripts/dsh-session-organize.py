#!/usr/bin/env python3
"""Read DSH metadata and prepare a reversible, workflow-scoped UI action manifest.

Never edits DSH storage. Apply the listed actions through DSH's own UI/API.
Python 3.14's standard zstd reader is required for native compressed logs.
"""
import argparse
import json
import os
import subprocess
import shutil
import urllib.request
import re
from datetime import datetime
from pathlib import Path


WORKSPACES = {
    ".": "工作流 · 搭建与总控",
    "examples/omb-smoke": "工作流 · 接入验证",
    "examples/workflow-demo": "工作流 · 阶段接力演练",
    "examples/discussion-demo": "工作流 · Bot讨论演练",
    "examples/code-team-demo": "工作流 · Code Team演练",
    "examples/coordinator-demo": "工作流 · 总控验证",
    "examples/model-control-demo": "工作流 · 模型切换验证",
}
ROLE_NAMES = {"kimi": "Kimi规划", "deepseek": "DeepSeek", "glm-plan": "GLM规划", "glm-review": "GLM审核"}


def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def atomic_new_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def role_mapping(project):
    mapping = {}
    for path in sorted((project / "tests/evidence").glob("code-team-*/model-audit.json")):
        data = read_json(path, [])
        if not isinstance(data, list):
            continue
        for row in data:
            if row.get("role") in ROLE_NAMES and row.get("sessionId"):
                mapping[row["sessionId"]] = {"role": ROLE_NAMES[row["role"]], "source": str(path.relative_to(project)), "thread_id": row.get("thread")}
    return mapping


def summarize_log(path, allowed_cwds):
    from compression import zstd
    with zstd.open(path, "rt") as stream:
        first = stream.readline(2_000_001)
        if len(first) > 2_000_000:
            raise ValueError("Oversized header")
        header = json.loads(first)
        raw_cwd = header.get("cwd")
        cwd = str(Path(raw_cwd).resolve()) if isinstance(raw_cwd, str) and Path(raw_cwd).is_absolute() else None
        if header.get("type") != "session" or cwd not in allowed_cwds:
            return None
        result = {"session_id": header["id"], "cwd": cwd, "created_at": header.get("createdAt"), "title": "", "title_source": None, "role_name": None, "open_turn": False, "completed_turn": False, "delegation_depth": header.get("delegationDepth", 0)}
        for line in stream:
            event = json.loads(line)
            kind = event.get("type")
            if kind == "session/title":
                title = event.get("data", {}).get("title")
                if isinstance(title, str):
                    result["title"] = title
                    result["title_source"] = event.get("data", {}).get("source", {}).get("kind")
            elif kind == "agent/inbox/spliced" and result["role_name"] is None:
                for message in event.get("data", {}).get("inserted", []):
                    content = message.get("content", "")
                    text = content if isinstance(content, str) else "\n".join(block.get("text", "") for block in content if isinstance(block, dict)) if isinstance(content, list) else ""
                    role = re.match(r"You are ([^,\n]{1,60}), (?:a personal|a shared|a) bot in OpenMausBot\.", text)
                    if role:
                        result["role_name"] = role[1]
            elif kind == "turn/start":
                result["open_turn"] = True
            elif kind == "turn/end":
                result["open_turn"] = False
                result["completed_turn"] = True
        return result


def inventory(home, project):
    home, project = home.resolve(), project.resolve()
    allowed = {str((project / relative).resolve()): title for relative, title in WORKSPACES.items() if (project / relative).is_dir()}
    state = read_json(home / "storages/workspace.json", {"global": {}, "tables": {"workspaces": {}}})
    workspaces = state.get("tables", {}).get("workspaces", {})
    roles = role_mapping(project)
    actions, records, skipped = [], [], []
    for cwd, title in allowed.items():
        existing = next(((key, value) for key, value in workspaces.items() if value.get("path") == cwd), None)
        actions.append({"kind": "workspace", "cwd": cwd, "workspace_id": existing[0] if existing else None, "before_title": existing[1].get("title") if existing else None, "after_title": title, "operation": "rename" if existing else "create"})
    for folder in sorted((home / "sessions").glob("*")):
        if not folder.is_dir():
            continue
        for native in sorted(folder.glob("*/session.v4.jsonl.zstd")):
            try:
                record = summarize_log(native, allowed)
            except (ValueError, OSError, KeyError) as error:
                skipped.append({"reason": type(error).__name__, "note": "Unreadable header/log; no private path or content exported"})
                continue
            if not record:
                continue
            record["native_directory"] = str(native.parent)
            record["archived"] = record["session_id"] in state.get("global", {}).get("archivedSessionIds", [])
            record["locked_or_active_requires_live_check"] = True
            records.append(record)
            mapped = roles.get(record["session_id"])
            if not mapped and record["role_name"] and record["title"].startswith("You are ") and record["title_source"] != "user":
                mapped = {"role": record["role_name"], "source": "native first-human OpenMausBot role", "thread_id": None}
            if mapped and not record["open_turn"] and record["title_source"] != "user":
                suffix = mapped["thread_id"][:8] if mapped.get("thread_id") else record["session_id"][:8]
                task = "CODE-TEAM-001" if mapped["source"].endswith("model-audit.json") else allowed[record["cwd"]].removeprefix("工作流 · ")
                actions.append({"kind": "session", "operation": "rename", "session_id": record["session_id"], "cwd": record["cwd"], "before_title": record["title"], "after_title": f"[{mapped['role']}] {task} · {suffix}", "source": mapped["source"], "before_archived": record["archived"], "requires_idle_check": True})
    return {"schema_version": 1, "project_root": str(project), "dsh_home": str(home), "status": "planned_not_applied", "scope": "Exact workflow project directories only; no cwd rewrites or storage edits", "workspaces": actions[:len(allowed)], "sessions": records, "actions": actions, "skipped": skipped, "notes": ["Workspace registration and rename are native DSH operations.", "Historical membership needs native attachSession; ordinary restart does not rerun first-use bootstrap.", "Apply only after checking session identity and idle state in native UI/API.", "Unattributed sessions and CAPTURE in temporary folders are excluded until provenance is verified."]}


def add_verified_captures(manifest, bot_names):
    from compression import zstd
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    fleet = json.load(opener.open("http://127.0.0.1:8799/api/bots?messages=0", timeout=5))
    root = manifest["project_root"]
    verified = {}
    for name in bot_names:
        bots = [bot for bot in fleet.get("bots", []) if bot.get("name") == name]
        if len(bots) != 1:
            raise ValueError("CAPTURE Bot name is absent or ambiguous")
        bot = bots[0]
        cwd = str(Path(bot.get("cwd", "/")).resolve())
        if cwd != root and not cwd.startswith(root + os.sep):
            raise ValueError("CAPTURE Bot does not belong to this workflow")
        verified[name] = bot["id"]
    home = Path(manifest["dsh_home"])
    for cache in sorted((home / "storages/session_projcache/sessions").glob("*.json")):
        record = read_json(cache, {}).get("record", {})
        if not str(record.get("rows", {}).get("title", {}).get("val", "")).startswith("You are the CAPTURE step"):
            continue
        for native in (home / "sessions").glob(f"*/{cache.stem}/session.v4.jsonl.zstd"):
            with zstd.open(native, "rt") as stream:
                header = json.loads(stream.readline())
                if not re.fullmatch(r"omb-acp-memory-[A-Za-z0-9]+", Path(header.get("cwd", "")).name):
                    continue
                owner = None
                for line in stream:
                    event = json.loads(line)
                    if event.get("type") != "agent/inbox/spliced":
                        continue
                    for message in event.get("data", {}).get("inserted", []):
                        content = message.get("content", "")
                        text = content if isinstance(content, str) else "\n".join(block.get("text", "") for block in content if isinstance(block, dict)) if isinstance(content, list) else ""
                        match = re.match(r"You are the CAPTURE step of a memory system for an assistant named (.+?)\. You have no tools\.", text)
                        if match and match[1] in verified:
                            owner = match[1]
                    break
            if not owner:
                continue
            summary = summarize_log(native, {str(Path(header["cwd"]).resolve())})
            if not summary or summary["open_turn"] or not summary["completed_turn"]:
                manifest["skipped"].append({"session_id": header["id"], "reason": "CAPTURE not confirmed completed"})
                continue
            summary.update({"auxiliary_capture": True, "source_kind": "OpenMausBot memory-capture", "bot_id": verified[owner], "bot_name": owner})
            manifest["sessions"].append(summary)
            manifest["actions"].append({"kind": "session", "operation": "rename_archive", "session_id": summary["session_id"], "cwd": summary["cwd"], "before_title": summary["title"], "after_title": f"[系统·记忆整理] {owner} · {summary['session_id'][:8]}", "before_archived": summary["session_id"] in read_json(home / "storages/workspace.json", {}).get("global", {}).get("archivedSessionIds", []), "requires_idle_check": True})
    return manifest


def undo_manifest(manifest):
    actions = []
    for action in reversed(manifest["actions"]):
        if action["kind"] == "workspace":
            actions.append({**action, "operation": "rename" if action["before_title"] is not None else "remove_registration_only", "after_title": action["before_title"]})
        elif action["kind"] == "session":
            if not action["before_title"]:
                actions.append({**action, "operation": "manual_restore_required", "reason": "DSH has no supported title deletion API; original blank title is preserved here"})
            else:
                actions.append({**action, "after_title": action["before_title"]})
    return {"schema_version": 1, "status": "undo_instructions_not_applied", "actions": actions, "note": "Use official DSH UI/API; never remove project files or native session logs."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["scan", "undo-manifest", "apply", "undo", "install-desktop"])
    parser.add_argument("--home", type=Path, default=Path.home() / ".dsh")
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--receipt", type=Path, help="Native apply receipt used by undo")
    parser.add_argument("--baseline", type=Path, help="Original workspace baseline used by undo")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--desktop-stopped", action="store_true")
    parser.add_argument("--service-stopped", action="store_true", help="Explicit maintenance window: OMB must be unreachable and no ACP worker processes may remain")
    parser.add_argument("--capture-bots", help="Comma-separated unique workflow Bot names; validates provenance before adding completed CAPTURE sessions")
    args = parser.parse_args()
    if args.command == "install-desktop":
        if not args.desktop_stopped:
            parser.error("Close the idle native desktop before installing the single-writer grouping plugin")
        patch = args.home / "profiles/desktop/cordis.patch.yml"
        text = patch.read_text()
        if "id: workflour-workspace-autogroup" in text:
            atomic_new_json(args.out, {"status": "already_installed"})
            return
        backup = args.home / "backups" / ("workflour-autogroup-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        backup.mkdir(parents=True, mode=0o700)
        shutil.copyfile(patch, backup / "cordis.patch.yml")
        (backup / "cordis.patch.yml").chmod(0o600)
        plugin = Path(__file__).resolve().parents[1] / "integrations/openmausbot/session-title/autogroup.mjs"
        addition = f"\n# Workflour desktop-only session grouping; ACP workers only enqueue metadata.\n- insert:\n    - id: workflour-workspace-autogroup\n      name: {json.dumps(str(plugin))}\n"
        temp = patch.with_suffix(".workflour-tmp")
        with open(temp, "x", encoding="utf-8", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
            stream.write(text + addition)
        os.replace(temp, patch)
        atomic_new_json(args.out, {"status": "desktop_plugin_installed", "backup": str(backup), "plugin": str(plugin)})
        print(json.dumps({"status": "desktop_plugin_installed", "backup": str(backup)}, ensure_ascii=False))
        return
    if args.command in {"apply", "undo"}:
        if not args.manifest or not args.desktop_stopped:
            parser.error("apply requires --manifest and --desktop-stopped after closing the idle native desktop")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        if args.service_stopped:
            try:
                opener.open("http://127.0.0.1:8799/api/health", timeout=2)
            except OSError:
                pass
            else:
                parser.error("--service-stopped requires OpenMausBot to be stopped")
            processes = subprocess.run(["ps", "-axo", "command="], capture_output=True, text=True, check=True).stdout.splitlines()
            if any(re.match(r"^\S*(?:python3|Python)\s+.*acp-resume-bridge\.py", line.strip()) or ("DeepSeek Harness" in line and re.search(r"--profile\s+omb-", line)) for line in processes):
                parser.error("ACP workers still exist; maintenance has not started")
        else:
            with opener.open("http://127.0.0.1:8799/api/bots?messages=0", timeout=5) as response:
                fleet = json.load(response)
            if any(bot.get("busy") for bot in fleet.get("bots", [])):
                parser.error("OpenMausBot has running workers; wait for idle before maintenance")
        manifest = read_json(args.manifest, {})
        home = Path(manifest["dsh_home"])
        backup = home / "backups" / ("workflour-organize-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        backup.mkdir(parents=True, mode=0o700)
        shutil.copyfile(home / "storages/workspace.json", backup / "workspace.json")
        (backup / "workspace.json").chmod(0o600)
        shutil.copyfile(args.manifest, backup / "manifest.json")
        (backup / "manifest.json").chmod(0o600)
        host = Path(__file__).with_name("dsh-session-organize-host.mjs")
        binary = "/Applications/DeepSeek Harness.app/Contents/MacOS/DeepSeek Harness"
        command = [binary, "--expose-internals", str(host), "--manifest", str(args.manifest.resolve()), "--out", str(args.out.resolve()), "--apply", "--desktop-stopped"]
        if args.command == "undo":
            if not args.receipt or not args.baseline:
                parser.error("undo requires --receipt and --baseline")
            command += ["--undo", "--receipt", str(args.receipt.resolve()), "--baseline", str(args.baseline.resolve())]
        completed = subprocess.run(command, capture_output=True, text=True, env={**os.environ, "ELECTRON_RUN_AS_NODE": "1", "DSH_HOME": str(home)}, timeout=180)
        # Native startup diagnostics can contain authenticated URLs. Never export
        # their stdout/stderr into project evidence or the chat.
        if completed.returncode or not args.out.exists():
            raise SystemExit("Native maintenance failed; backup retained at " + str(backup))
        print(json.dumps({"status": "native_maintenance_finished", "backup": str(backup), "output": str(args.out)}, ensure_ascii=False))
        return
    if args.command == "undo-manifest":
        if not args.manifest:
            parser.error("--manifest is required")
        data = undo_manifest(read_json(args.manifest, {}))
    else:
        data = inventory(args.home, args.project)
        if args.capture_bots:
            data = add_verified_captures(data, [name.strip() for name in args.capture_bots.split(",") if name.strip()])
    atomic_new_json(args.out, data)
    print(json.dumps({"status": data["status"], "actions": len(data["actions"]), "output": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
