#!/usr/bin/env python3
"""OpenMausBot / Harness ACP 协议握手验证（不发 session/prompt）。

对每个角色（coder、doc）分别启动 run-acp-agent.sh，按顺序发送：

  1. initialize
  2. session/new（cwd = examples/omb-smoke）
  3. session/close

然后关闭 stdin，等待进程退出。

判据：
  - initialize 返回成功，protocolVersion 存在
  - session/new 返回非空 sessionId
  - session/close 成功
  - stdout 的每一行非空内容都是合法 JSON-RPC 消息
  - 进程能在关闭 stdin 后自行退出

注意：这不是「离线 / 零副作用」检查。插件仍可能联网刷新目录或认证，
session/new 也可能落盘。

用法：
    python3 tests/acp-smoke.py            # 两个角色都跑
    python3 tests/acp-smoke.py coder      # 只跑一个
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
LAUNCHER = WORKSPACE / "run-acp-agent.sh"
SMOKE_CWD = WORKSPACE / "examples" / "omb-smoke"

COLD_START_TIMEOUT = 180.0   # 首次冷启动允许 180 秒
RESPONSE_TIMEOUT = 30.0      # 启动后每项响应最多 30 秒
EXIT_TIMEOUT = 60.0


class HandshakeError(RuntimeError):
    pass


def redact(text: str) -> str:
    """粗略脱敏：去掉形似凭据的长串，避免把 token 写进日志。"""
    if not text:
        return text
    out = []
    for token in text.split():
        if len(token) > 48 and token.count(".") >= 2:
            out.append("<redacted-token>")
        else:
            out.append(token)
    return " ".join(out)


class AcpProcess:
    def __init__(self, role: str):
        self.role = role
        self.stdout_lines: list[str] = []
        self.stderr_lines: list[str] = []
        self.protocol_errors: list[str] = []
        self._queue: queue.Queue[str | None] = queue.Queue()
        self.proc = subprocess.Popen(
            [str(LAUNCHER), role],
            cwd=str(WORKSPACE),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env={**os.environ},
        )
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()
        self._err = threading.Thread(target=self._read_stderr, daemon=True)
        self._err.start()

    def _read_stdout(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            line = line.rstrip("\n")
            self.stdout_lines.append(line)
            if line.strip():
                self._queue.put(line)
        self._queue.put(None)

    def _read_stderr(self) -> None:
        assert self.proc.stderr is not None
        for line in self.proc.stderr:
            self.stderr_lines.append(line.rstrip("\n"))

    def send(self, message: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def wait_for_id(self, request_id: int, timeout: float) -> dict:
        """读取 stdout，直到出现匹配 id 的响应或超时。"""
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise HandshakeError(
                    f"等待 id={request_id} 的响应超时（{timeout:.0f}s）"
                )
            try:
                line = self._queue.get(timeout=remaining)
            except queue.Empty:
                continue
            if line is None:
                raise HandshakeError(
                    f"进程在响应 id={request_id} 之前关闭了 stdout；"
                    f"stderr 尾部: {redact(chr(10).join(self.stderr_lines[-10:]))}"
                )
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self.protocol_errors.append(f"stdout 非 JSON 行: {line[:200]}")
                continue
            if msg.get("id") == request_id:
                if "error" in msg:
                    raise HandshakeError(
                        f"id={request_id} 返回错误: "
                        f"{redact(json.dumps(msg['error'], ensure_ascii=False))}"
                    )
                return msg

    def close_stdin(self) -> None:
        if self.proc.stdin and not self.proc.stdin.closed:
            self.proc.stdin.close()

    def terminate(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)


def validate_stdout(proc: AcpProcess) -> list[str]:
    """检查 stdout 每一行非空内容都是合法 JSON-RPC 2.0 消息。"""
    problems: list[str] = []
    for line in proc.stdout_lines:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            problems.append(f"非 JSON: {line[:200]}")
            continue
        if not isinstance(msg, dict):
            problems.append(f"不是 JSON 对象: {line[:200]}")
            continue
        if msg.get("jsonrpc") != "2.0":
            problems.append(f"缺少 jsonrpc=2.0: {line[:200]}")
            continue
        if "method" not in msg and "result" not in msg and "error" not in msg:
            problems.append(f"既非请求/通知也非响应: {line[:200]}")
    return problems


def run_role(role: str) -> dict:
    report: dict = {"role": role, "ok": False, "steps": {}, "problems": []}
    print(f"\n=== ACP 握手验证: {role} ===", flush=True)

    proc = AcpProcess(role)
    started = time.monotonic()
    try:
        # 1. initialize
        proc.send({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": 1,
                "clientCapabilities": {},
                "clientInfo": {"name": "workflour-acp-smoke", "version": "0.1.0"},
            },
        })
        init_resp = proc.wait_for_id(1, COLD_START_TIMEOUT)
        cold = time.monotonic() - started
        result = init_resp.get("result", {})
        report["steps"]["initialize"] = {
            "seconds": round(cold, 1),
            "protocolVersion": result.get("protocolVersion"),
            "agentInfo": result.get("agentInfo"),
            "sessionCapabilities": result.get("agentCapabilities", {}).get(
                "sessionCapabilities"
            ),
        }
        print(
            f"  [1/3] initialize OK（{cold:.1f}s，"
            f"protocolVersion={result.get('protocolVersion')}，"
            f"agent={result.get('agentInfo', {}).get('name')}）",
            flush=True,
        )

        # 2. session/new
        proc.send({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "session/new",
            "params": {"cwd": str(SMOKE_CWD), "mcpServers": []},
        })
        new_resp = proc.wait_for_id(2, RESPONSE_TIMEOUT)
        new_result = new_resp.get("result", {})
        session_id = new_result.get("sessionId")
        if not isinstance(session_id, str) or not session_id:
            raise HandshakeError("session/new 未返回有效 sessionId")
        config_options = new_result.get("configOptions")
        report["steps"]["session/new"] = {
            "sessionId": session_id,
            "configOptions": config_options,
        }
        # model 选项可能是分组结构（options[].group + options[].options[]），
        # 展开成扁平列表，并用 currentValue 标出实际选中的路由。
        models: list[dict] = []
        if isinstance(config_options, list):
            for option in config_options:
                if not isinstance(option, dict) or option.get("id") != "model":
                    continue
                current = option.get("currentValue")

                def collect(entries, group=None):
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        nested = entry.get("options")
                        if isinstance(nested, list):
                            collect(nested, entry.get("group") or entry.get("name"))
                            continue
                        models.append({
                            "value": entry.get("value"),
                            "name": entry.get("name"),
                            "group": group,
                            "selected": entry.get("value") == current,
                        })

                collect(option.get("options") or [])
        report["steps"]["session/new"]["models"] = models
        selected = [m for m in models if m["selected"]]
        label = (
            f"{selected[0]['group']} / {selected[0]['value']}"
            if selected else "未声明"
        )
        print(
            f"  [2/3] session/new OK（sessionId={session_id}，当前模型={label}）",
            flush=True,
        )

        # 3. session/close
        proc.send({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "session/close",
            "params": {"sessionId": session_id},
        })
        close_resp = proc.wait_for_id(3, RESPONSE_TIMEOUT)
        report["steps"]["session/close"] = {"result": close_resp.get("result")}
        print("  [3/3] session/close OK", flush=True)

    except HandshakeError as error:
        report["problems"].append(str(error))
        print(f"  [失败] {error}", flush=True)
    except Exception as error:  # noqa: BLE001 - 需要把任何异常都记录成证据
        report["problems"].append(f"{type(error).__name__}: {error}")
        print(f"  [异常] {type(error).__name__}: {error}", flush=True)
    finally:
        # 关闭 stdin，等待自然退出
        proc.close_stdin()
        exit_code = None
        try:
            exit_code = proc.proc.wait(timeout=EXIT_TIMEOUT)
        except subprocess.TimeoutExpired:
            report["problems"].append(f"关闭 stdin 后 {EXIT_TIMEOUT:.0f}s 内未退出")
            proc.terminate()
            exit_code = proc.proc.poll()
        report["exit"] = {"code": exit_code}

    problems = validate_stdout(proc)
    if problems:
        report["problems"].extend(problems)

    report["stdout_line_count"] = len([l for l in proc.stdout_lines if l.strip()])
    report["stderr_tail"] = [redact(l) for l in proc.stderr_lines[-8:]]
    report["ok"] = not report["problems"]

    print(f"  stdout 非空行: {report['stdout_line_count']}，"
          f"退出码: {report['exit']['code']}", flush=True)
    if report["problems"]:
        print(f"  问题: {report['problems']}", flush=True)
    return report


def main() -> int:
    if not SMOKE_CWD.is_dir():
        SMOKE_CWD.mkdir(parents=True, exist_ok=True)
        print(f"已创建测试目录: {SMOKE_CWD}", flush=True)

    roles = sys.argv[1:] or ["coder", "doc"]
    reports = [run_role(role) for role in roles]

    evidence_dir = WORKSPACE / "tests" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = evidence_dir / f"acp-smoke-{stamp}.json"
    out.write_text(
        json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n证据已写入: {out}", flush=True)

    ok = all(r["ok"] for r in reports)
    print("\n=== 结论 ===", flush=True)
    for r in reports:
        print(f"  {r['role']}: {'通过' if r['ok'] else '未通过'}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
