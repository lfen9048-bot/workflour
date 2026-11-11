#!/usr/bin/env python3
"""Export one explicitly selected OMB thread's public text and tool metadata.

No native trace, tool arguments/results, approval cards, or reasoning is read.
Credential-pattern redaction is best effort, not a guarantee for arbitrary
secrets embedded in visible prose. Inspect the result before wider sharing.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request


def identifier(value):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise ValueError("Expected an explicit thread/role identifier")
    return value


def redact(value):
    if not isinstance(value, str):
        return ""
    value = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----", "[redacted private key]", value)
    value = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [redacted]", value)
    value = re.sub(r"\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{8,}", "[redacted credential]", value)
    value = re.sub(r'''(?i)(["']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|secret|authorization)["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s&,;]+)''', r"\1[redacted]", value)
    return value


def render(messages, thread_id, role):
    identifier(thread_id)
    identifier(role)
    lines = [f"# {role}：独立会话记录", "", f"- thread_id: {thread_id}",
             f"- 导出时间: {datetime.now(timezone.utc).isoformat()}",
             "- 来源: 本机 OpenMausBot 可见消息；非 native trace。", 
             "- 仅导出普通文本及工具名称/状态；不包含工具参数、结果、审批卡和隐藏推理。", ""]
    for message in messages:
        if not isinstance(message, dict):
            continue
        if (message.get("hidden") is True or message.get("visible") is False
                or message.get("channel") in ("analysis", "reasoning")
                or message.get("visibility") in ("hidden", "internal")):
            continue
        kind, speaker = message.get("kind"), message.get("role")
        if speaker not in ("user", "bot", "assistant"):
            continue
        if kind == "text":
            body = redact(message.get("text"))
        elif kind == "activity" and isinstance(message.get("tool"), dict):
            tool = message["tool"]
            name = redact(tool.get("name"))[:160]
            status = "成功" if tool.get("ok") is True else "失败" if tool.get("ok") is False else "未标明"
            body = f"工具：{name}；状态：{status}" if name else ""
        else:
            continue
        if not body.strip():
            continue
        mid = message.get("id", "")
        try:
            mid = identifier(mid)
        except (ValueError, TypeError):
            mid = "unavailable"
        lines += [f"## {speaker} · {mid}", "", body, ""]
    return "\n".join(lines)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Loopback export refuses redirects")


def read_thread(thread_id):
    identifier(thread_id)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    messages, seen, before = [], set(), None
    for _ in range(500):
        query = {"limit": 200}
        if before:
            query["before"] = before
        url = f"http://127.0.0.1:8799/api/threads/{thread_id}/messages?" + urllib.parse.urlencode(query)
        with opener.open(url, timeout=15) as response:
            page = json.load(response)
        batch = page.get("messages")
        if not isinstance(batch, list):
            raise ValueError("Unexpected messages response")
        messages = batch + messages
        if not page.get("hasMore"):
            return messages
        if not batch:
            raise ValueError("Empty page with more messages")
        before = identifier(batch[0].get("id", ""))
        if before in seen:
            raise ValueError("Repeated pagination cursor")
        seen.add(before)
    raise ValueError("Thread exceeds bounded export; no partial record written")


def write_record(project, output, content):
    root = Path(project).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Project must be a directory")
    raw = Path(output).expanduser()
    if not raw.is_absolute():
        raw = root / raw
    if raw.is_symlink():
        raise ValueError("Output cannot be a symlink")
    target = raw.resolve()
    if root not in target.parents or target.suffix != ".md":
        raise ValueError("Output must be a Markdown file inside project")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(content)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True, help="Project-relative or absolute .md path; must not exist")
    args = parser.parse_args()
    try:
        identifier(args.role)
        messages = read_thread(args.thread_id)
        output = write_record(args.project, args.out, render(messages, args.thread_id, args.role))
        print(json.dumps({"output": str(output), "thread_id": args.thread_id, "source_message_count": len(messages)}))
    except (ValueError, OSError, TypeError) as error:
        parser.exit(1, f"Export failed: {type(error).__name__}\n")


if __name__ == "__main__":
    main()
