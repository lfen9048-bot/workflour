#!/usr/bin/env python3
"""Live test of managed service survival, crash recovery, and deliberate stop.

Requires an idle running managed installation. Ends with both jobs running.
Only the two workflour-owned launchd labels may be interrupted.
"""

import importlib.util
import hashlib
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("omb_launchd", ROOT / "integrations/openmausbot/launchd/manage.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
MANAGER = MODULE.Manager()


def idle():
    with MANAGER.opener.open(f"http://127.0.0.1:{MANAGER.port}/api/bots?messages=0", timeout=8) as response:
        bots = json.load(response)["bots"]
    if any(b.get("busy") or any(t.get("busy") for t in b.get("tasks", [])) for b in bots):
        raise RuntimeError("A bot is busy; refusing to interrupt services")


def eventually(check, timeout=75):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(1)
    raise TimeoutError("Managed job did not recover within the test deadline")


def command(action):
    result = subprocess.run([str(ROOT / "scripts/omb-public.sh"), action],
                            capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"{action} failed: {result.stdout}{result.stderr}")


def main():
    evidence = ROOT / "tests/evidence" / ("service-lifecycle-" + time.strftime("%Y%m%d-%H%M%S") + ".json")
    report = {"ok": False, "checks": {}}
    stopped = False
    MANAGER.ensure_ownership()
    if not all(MANAGER.loaded(kind) for kind in MODULE.LABELS):
        raise RuntimeError("Start both managed jobs before running this test")
    idle()
    try:
        before = {kind: MANAGER.pid(kind) for kind in MODULE.LABELS}
        hashes = {kind: hashlib.sha256(MANAGER.path(kind).read_bytes()).hexdigest() for kind in MODULE.LABELS}
        command("up")
        report["checks"]["idempotentUp"] = (
            before == {kind: MANAGER.pid(kind) for kind in MODULE.LABELS}
            and hashes == {kind: hashlib.sha256(MANAGER.path(kind).read_bytes()).hexdigest() for kind in MODULE.LABELS})
        print("Repeated up preserved jobs and definitions", flush=True)
        idle()
        old_health = MANAGER.health()
        result = MANAGER.ctl("kill", "SIGKILL", MANAGER.target("serve"))
        if result.returncode:
            raise RuntimeError("Unable to signal the owned server job")
        def recovered_server():
            current = MANAGER.health()
            return current if current and current.get("pid") != old_health.get("pid") else None
        new_health = eventually(recovered_server)
        report["checks"]["serverCrashRecovery"] = MANAGER.pid("serve") != before["serve"]
        report["serverPids"] = [old_health.get("pid"), new_health.get("pid")]
        print("Server recovered after SIGKILL", flush=True)
        idle()
        old_ssh = MANAGER.pid("tunnel")
        result = MANAGER.ctl("kill", "SIGKILL", MANAGER.target("tunnel"))
        if result.returncode:
            raise RuntimeError("Unable to signal the owned tunnel job")
        def recovered_tunnel():
            if MANAGER.pid("tunnel") == old_ssh:
                return False
            return MANAGER.health(True)
        eventually(recovered_tunnel)
        report["checks"]["tunnelCrashRecovery"] = MANAGER.pid("tunnel") != old_ssh
        report["tunnelPids"] = [old_ssh, MANAGER.pid("tunnel")]
        print("Tunnel recovered after SIGKILL", flush=True)
        idle()
        command("down")
        stopped = True
        time.sleep(7)  # Longer than the configured five-second restart throttle.
        report["checks"]["deliberateStopStaysStopped"] = (
            not any(MANAGER.loaded(kind) for kind in MODULE.LABELS)
            and MANAGER.health() is None
            and not any(MANAGER.path(kind).exists() for kind in MODULE.LABELS))
        print("Explicit down remained stopped", flush=True)
        command("up")
        stopped = False
        report["checks"]["restored"] = bool(MANAGER.health() and MANAGER.health(True))
        report["ok"] = all(report["checks"].values())
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        if stopped or not MANAGER.health():
            try:
                command("up")
                report["restoredAfterFailure"] = True
            except Exception as error:
                report["restoreError"] = str(error)
        evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    print("Evidence:", evidence, flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
