#!/usr/bin/env python3
"""Real OpenMausBot restart test: recover a value seen only in a tool result.

Runs against an idle existing Coder or Doc, restarts the managed local service,
and checks both the answer and the underlying Harness session ID. No credentials
are exported and no production source files are changed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def api(path: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        "http://127.0.0.1:8799" + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with OPENER.open(request, timeout=15) as response:
        return json.load(response)


def fleet() -> list[dict]:
    return api("/api/bots?messages=0")["bots"]


def require_idle() -> None:
    busy = [bot["name"] for bot in fleet() if bot.get("busy")]
    if busy:
        raise RuntimeError("Refusing to restart while bots are busy: " + ", ".join(busy))


def send(bot: dict, text: str) -> list[dict]:
    thread = bot["threadId"]
    send_id = uuid.uuid4().hex
    receipt = api(
        f"/api/bots/{bot['id']}/messages",
        {"text": text, "threadId": thread, "sendId": send_id},
    )
    request_id = receipt.get("message", {}).get("id")
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        time.sleep(1)
        page = api(f"/api/threads/{thread}/messages?limit=200")["messages"]
        starts = [
            i for i, message in enumerate(page)
            if message.get("id") == request_id or message.get("sendId") == send_id
        ]
        if not starts:
            continue
        messages = page[starts[-1]:]
        current = next(item for item in fleet() if item["id"] == bot["id"])
        pending = [m for m in messages if m.get("card", {}).get("requestType") == "permission"
                   and not m["card"].get("answered") and not m["card"].get("dismissed")]
        if pending:
            api(f"/api/bots/{bot['id']}/interrupt", {"threadId": thread})
            raise RuntimeError("Test stopped at a permission card; no permission was auto-approved")
        if not current.get("busy") and any(m.get("role") == "bot" for m in messages):
            return messages
    api(f"/api/bots/{bot['id']}/interrupt", {"threadId": thread})
    raise TimeoutError("Model turn did not finish in 240 seconds; test turn interrupted")


def answer(messages: list[dict]) -> str:
    return "\n".join(
        m.get("text", "") for m in messages
        if m.get("role") == "bot" and m.get("kind") == "text"
    )


def native_requests(bot: dict, offset: int) -> list[dict]:
    path = Path.home() / ".openmausbot/native" / (bot["threadId"] + ".ndjson")
    records = []
    with path.open("rb") as source:
        source.seek(offset)
        for line in source:
            try:
                record = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            msg = record.get("msg", {})
            if msg.get("method") in ("session/new", "session/load", "session/resume", "session/prompt"):
                records.append({"method": msg["method"], "sessionId": msg.get("params", {}).get("sessionId")})
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("Coder", "Doc"), default="Coder", nargs="?")
    args = parser.parse_args()
    require_idle()
    bot = next(item for item in fleet() if item["name"] == args.role)
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + args.role.lower()
    evidence = ROOT / "tests/evidence" / ("native-recovery-" + run_id)
    evidence.mkdir(parents=True)
    fixture_dir = Path(bot["cwd"]) / ".recovery-verification"
    fixture_dir.mkdir(exist_ok=True)
    fixture = fixture_dir / (run_id + ".json")
    marker = "TOOL-" + uuid.uuid4().hex
    fixture.write_text(json.dumps({"marker": marker}) + "\n")
    native = Path.home() / ".openmausbot/native" / (bot["threadId"] + ".ndjson")
    offset = native.stat().st_size if native.exists() else 0
    report = {"role": args.role, "threadId": bot["threadId"], "fixture": str(fixture), "ok": False}
    try:
        print(f"{args.role}: reading fresh fixture using a tool", flush=True)
        first = send(bot, f"重启恢复验证：请实际读取 {fixture}。不要把其中的 marker 值写进聊天回复、MEMORY 或其他文件，不要修改文件。读取后只回复 READY。")
        (evidence / "before-turn.json").write_text(json.dumps(first, ensure_ascii=False, indent=2))
        if marker in answer(first):
            raise RuntimeError("Marker appeared in the chat reply; this would not test tool-only recovery")
        if not any(m.get("tool", {}).get("itemId") and m["tool"].get("ok") is True for m in first):
            raise RuntimeError("No successfully completed tool call was observed")
        requests_before = native_requests(bot, offset)
        before_ids = [r["sessionId"] for r in requests_before if r["method"] == "session/prompt"]
        if not before_ids:
            raise RuntimeError("Could not identify the actual native Harness session")
        report["nativeSessionBefore"] = before_ids[-1]
        offset_after = native.stat().st_size
        require_idle()
        print(f"{args.role}: restarting managed service", flush=True)
        restart = subprocess.run([str(ROOT / "scripts/omb-public.sh"), "restart"],
                                 capture_output=True, text=True, timeout=120)
        report["restartExit"] = restart.returncode
        report["restartOutput"] = restart.stdout + restart.stderr
        if restart.returncode:
            raise RuntimeError("Service restart failed; inspect restartOutput")
        print(f"{args.role}: recalling without tools", flush=True)
        second = send(bot, "重启后的验证：不要调用任何工具，不读写文件或 MEMORY。只回复你上一轮实际从验证文件中读到的 marker 原值；不知道就回答不知道，不要猜。")
        (evidence / "after-turn.json").write_text(json.dumps(second, ensure_ascii=False, indent=2))
        requests_after = native_requests(bot, offset_after)
        after_ids = [r["sessionId"] for r in requests_after if r["method"] == "session/prompt"]
        report["nativeSessionAfter"] = after_ids[-1] if after_ids else None
        report["nativeRequestsAfter"] = requests_after
        report["correctToolOnlyRecall"] = marker in answer(second)
        report["noToolsAfterRestart"] = not any(m.get("tool", {}).get("itemId") for m in second)
        report["sameNativeSession"] = report["nativeSessionBefore"] == report["nativeSessionAfter"]
        report["ok"] = all(report[k] for k in ("correctToolOnlyRecall", "noToolsAfterRestart", "sameNativeSession"))
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        (evidence / "fixture.json").write_text(fixture.read_text())
        fixture.unlink()
        try:
            fixture_dir.rmdir()
        except OSError:
            pass
        (evidence / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    print("Evidence:", evidence, flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
