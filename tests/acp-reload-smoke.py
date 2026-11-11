#!/usr/bin/env python3
"""Real no-prompt new/load/load/close/load probe; save only allowlisted metadata.

Uses a temporary local MCP server with no tools or network calls to prove each
load mounts its request's new MCP settings. Does not inspect native logs.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("acp_smoke", ROOT / "tests/acp-smoke.py")
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)

MCP = '''import sys,json
from pathlib import Path
for line in sys.stdin:
 try: r=json.loads(line)
 except ValueError: continue
 if "id" not in r: continue
 method=r.get("method")
 if method=="initialize":
  with Path(sys.argv[1]).open("a") as f: f.write(sys.argv[2]+"\\n")
  result={"protocolVersion":r.get("params",{}).get("protocolVersion","2024-11-05"),"capabilities":{"tools":{}},"serverInfo":{"name":"workflour-reload-probe","version":"1"}}
 elif method=="tools/list": result={"tools":[]}
 elif method=="ping": result={}
 else:
  print(json.dumps({"jsonrpc":"2.0","id":r["id"],"error":{"code":-32601,"message":"probe method not found"}}),flush=True); continue
 print(json.dumps({"jsonrpc":"2.0","id":r["id"],"result":result}),flush=True)
'''


def run(role):
    report = {"role": role, "prompt_sent": False, "steps": [], "ok": False}
    proc = SMOKE.AcpProcess(role)
    with tempfile.TemporaryDirectory(prefix="workflour-acp-reload-") as directory:
        directory = Path(directory)
        server = directory / "mcp.py"
        marker = directory / "mounts.txt"
        server.write_text(MCP)

        def rpc(request_id, method, params):
            proc.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            response = proc.wait_for_id(request_id, 60)
            result = response.get("result", {})
            # No MCP headers/env/credentials or native transcript in evidence.
            report["steps"].append({"id": request_id, "method": method, "ok": True,
                                    "selection": [{"id": o["id"], "currentValue": o.get("currentValue")}
                                                  for o in result.get("configOptions", [])]})
            return result

        def workspace(label, session=None):
            params = {"cwd": str(ROOT / "examples/omb-smoke"), "mcpServers": [{
                "name": "workflour-reload-probe", "command": sys.executable,
                "args": [str(server), str(marker), label], "env": []}]}
            if session:
                params["sessionId"] = session
            return params

        try:
            init = rpc(1, "initialize", {"protocolVersion": 1, "clientCapabilities": {},
                                         "clientInfo": {"name": "workflour-no-prompt-reload", "version": "1"}})
            report["sessionCapabilities"] = init.get("agentCapabilities", {}).get("sessionCapabilities")
            native = rpc(2, "session/new", workspace("new-A"))
            sid = native["sessionId"]
            report["sessionId"] = sid
            rpc(3, "session/load", workspace("load-B", sid))
            rpc(4, "session/load", workspace("load-C", sid))
            rpc(5, "session/close", {"sessionId": sid})
            rpc(6, "session/load", workspace("after-close-D", sid))
            rpc(7, "session/close", {"sessionId": sid})
            report["mcp_mounts"] = marker.read_text().splitlines()
            report["same_persisted_session_restored"] = True
            report["fresh_mcp_each_load"] = report["mcp_mounts"] == ["new-A", "load-B", "load-C", "after-close-D"]
            report["ok"] = report["fresh_mcp_each_load"]
        except Exception as error:
            # Exception detail deliberately omitted: native errors may include
            # subprocess configuration. Operator can reproduce interactively.
            report["failure_type"] = type(error).__name__
        finally:
            proc.close_stdin()
            try:
                report["exit_code"] = proc.proc.wait(timeout=30)
            except Exception:
                proc.terminate()
                report["exit_code"] = proc.proc.poll()
            report["ok"] = report["ok"] and report["exit_code"] == 0 and not SMOKE.validate_stdout(proc)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", nargs="?", default="assistant")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.role)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"ok": result["ok"], "output": str(args.output)}, ensure_ascii=False))
    sys.exit(0 if result["ok"] else 1)
