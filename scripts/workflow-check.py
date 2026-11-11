#!/usr/bin/env python3
"""Small evidence and handoff checks for a manually coordinated Spec Kit project.

No model dispatch, automatic stage advancement, or inferred user approval.
Copied to each project's .workflour/check.py by new-project.py.
Checks establish material consistency, not human identity or test completeness.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

STAGES = ("requirements", "plan", "implement", "review", "verify", "docs", "acceptance", "done", "experience")


class InvalidHandoff(ValueError):
    pass


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def validate_experience(root, record, snapshot, requirement_ids=None, surface="web"):
    """Check browser evidence identity/freshness, not whether its observations are true."""
    root = Path(root).resolve()
    if not isinstance(record, dict) or record.get('status') != 'passed':
        raise InvalidHandoff('Actual product experience is failed, blocked or missing')
    if record.get('reviewer') != 'plan-review' or record.get('snapshot') != snapshot:
        raise InvalidHandoff('Experience must be independently checked against the current snapshot')
    if surface not in ('web', 'cli') or record.get('surface', 'web') != surface:
        raise InvalidHandoff('Experience surface must match the project product_surface')
    required = ('browser', 'url', 'at') if surface == 'web' else ('at',)
    if not all(isinstance(record.get(k), str) and record[k].strip() for k in required):
        raise InvalidHandoff('Experience needs the real browser/command and observation time')
    if surface == 'cli':
        command = record.get('command')
        if (not isinstance(command, list) or not command or any(not isinstance(arg, str) for arg in command)
                or type(record.get('exit_code')) is not int or record['exit_code'] != 0):
            raise InvalidHandoff('CLI experience needs the actual command and successful exit code')
    def checked_file(item):
        if not isinstance(item, dict):
            raise InvalidHandoff('Browser evidence must identify a file and SHA256')
        raw = Path(item.get('path', ''))
        if raw.is_absolute() or '..' in raw.parts:
            raise InvalidHandoff('Browser evidence must stay inside the project')
        file = (root / raw).resolve()
        if root not in file.parents or not file.is_file() or not file.stat().st_size:
            raise InvalidHandoff('Browser evidence file is missing or empty')
        if digest(file) != item.get('sha256'):
            raise InvalidHandoff('Browser evidence has changed')
        return file
    checked_file(record.get('interaction_log'))
    if surface == 'web':
        shots = record.get('screenshots')
        if not isinstance(shots, list) or len(shots) < 2:
            raise InvalidHandoff('Keep both desktop and mobile browser screenshots')
        viewports = set()
        for shot in shots:
            file = checked_file(shot)
            dimensions = shot.get('viewport', {})
            width, height = dimensions.get('width'), dimensions.get('height')
            if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
                raise InvalidHandoff('Screenshot viewport dimensions are required')
            viewports.add('mobile' if width <= 600 else 'desktop')
            header = file.read_bytes()[:12]
            if not (header.startswith(b'\x89PNG\r\n\x1a\n') or header.startswith(b'\xff\xd8\xff')
                    or (header[:4] == b'RIFF' and header[8:12] == b'WEBP')):
                raise InvalidHandoff('Screenshot evidence is not a supported image')
        if viewports != {'desktop', 'mobile'}:
            raise InvalidHandoff('Keep desktop and mobile viewports')
    checks = record.get('checks')
    if not isinstance(checks, list) or not checks:
        raise InvalidHandoff('Record actual actions and observed results')
    for check in checks:
        if (not isinstance(check, dict) or check.get('passed') is not True
                or not all(isinstance(check.get(k), str) and check[k].strip()
                           for k in ('requirement', 'action', 'observed'))):
            raise InvalidHandoff('Every experience check needs a requirement, action and successful observation')
    if requirement_ids and not set(requirement_ids).issubset({c['requirement'] for c in checks}):
        raise InvalidHandoff('Experience checks must cover every user acceptance criterion')
    return record


class Project:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.state_path = self.path(".workflour/handoff.json")
        self.state = json.loads(self.state_path.read_text())
        if not isinstance(self.state, dict):
            raise InvalidHandoff("handoff.json must contain an object")
        self.loaded_state_hash = digest(self.state_path)

    def path(self, value):
        if not isinstance(value, str) or not value.strip():
            raise InvalidHandoff("A project-relative file path is required")
        raw = Path(value)
        if raw.is_absolute() or ".." in raw.parts:
            raise InvalidHandoff("Paths must stay inside the project: " + value)
        target = (self.root / raw).resolve()
        if target == self.root or self.root not in target.parents:
            raise InvalidHandoff("Path escapes the project: " + value)
        return target

    def save(self):
        # Serialize compare-and-replace as well as detecting stale readers.
        # A concurrent Agent must reload instead of erasing earlier evidence.
        with self.path(".workflour/handoff.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.state_path = self.path(".workflour/handoff.json")
            if digest(self.state_path) != self.loaded_state_hash:
                raise InvalidHandoff("Handoff changed during this operation; reload before saving")
            temp = self.path(".workflour/handoff.json.tmp")
            temp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2) + "\n")
            temp.replace(self.state_path)
            self.loaded_state_hash = digest(self.state_path)

    def snapshot(self, names=None):
        names = self.state.get("code_files", []) if names is None else names
        if (not isinstance(names, list) or any(not isinstance(name, str) for name in names)
                or len(names) != len(set(names))):
            raise InvalidHandoff("code_files must be a list without duplicates")
        result = {}
        for name in names:
            path = self.path(name)
            if path.exists() and not path.is_file():
                raise InvalidHandoff("Code snapshot entries must be files")
            result[name] = digest(path)
        return result

    def artifact(self, name):
        path = self.path(self.state.get("artifacts", {}).get(name, ""))
        if not path.is_file() or not path.read_text().strip():
            raise InvalidHandoff("Missing or empty artifact: " + name)
        return path

    def latest_tests(self, snapshot):
        latest = {}
        records = self.state.get("tests", [])
        if not isinstance(records, list):
            raise InvalidHandoff("tests must be a list")
        for test in records:
            if not isinstance(test, dict):
                raise InvalidHandoff("Each test record must be an object")
            argv = test.get("argv")
            if not isinstance(argv, list) or not argv or any(not isinstance(arg, str) for arg in argv):
                raise InvalidHandoff("Each test record needs an argv list of strings")
            if test.get("snapshot") == snapshot:
                latest[tuple(argv)] = test
        return list(latest.values())

    def check(self, stage=None):
        state = self.state
        stage = stage or state.get("stage")
        if stage not in STAGES:
            raise InvalidHandoff("Unknown stage: " + str(stage))
        level = 5 if stage == "experience" else STAGES.index(stage)
        workflow = state.get("workflow", {})
        if not isinstance(workflow, dict):
            raise InvalidHandoff("workflow must be an object")
        if workflow.get("kind") not in (None, "manual", "code-team", "plan-code"):
            raise InvalidHandoff("Unknown workflow kind")
        plan_code = workflow.get("kind") == "plan-code"
        team_mode = workflow.get("kind") in ("code-team", "plan-code")
        if stage == "experience" and not plan_code:
            raise InvalidHandoff("experience is a plan-code stage")
        docs_required = workflow.get("docs_required", True)
        if type(docs_required) is not bool:
            raise InvalidHandoff("docs_required must be boolean")
        if stage == "docs" and not docs_required:
            raise InvalidHandoff("docs is disabled; proceed from verify to acceptance")
        if state.get("schema_version") != 1:
            raise InvalidHandoff("Expected schema_version 1")
        if not state.get("task_id") or state["task_id"] == "unassigned":
            raise InvalidHandoff("Assign task_id before starting")
        for key in ("owner", "next_owner", "next_action"):
            if not isinstance(state.get(key), str) or not state[key].strip():
                raise InvalidHandoff("Missing handoff field: " + key)
        if state.get("blockers"):
            raise InvalidHandoff("Unresolved blockers remain")
        requirements = state.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            raise InvalidHandoff("At least one requirement with an acceptance criterion is required")
        ids = set()
        for requirement in requirements:
            if not requirement.get("id") or not requirement.get("criterion"):
                raise InvalidHandoff("Each requirement needs id and criterion")
            if requirement["id"] in ids:
                raise InvalidHandoff("Duplicate requirement id")
            ids.add(requirement["id"])
        self.artifact("spec")
        if plan_code:
            if state.get('owner') != 'plan-lead':
                raise InvalidHandoff('Plan lead remains the sole shared-state owner')
            if not isinstance(state.get('original_request'), str) or not state['original_request'].strip():
                raise InvalidHandoff('Keep the original user request, separate from team assumptions')
            if not isinstance(state.get('assumptions'), list):
                raise InvalidHandoff('Keep team assumptions as a separate list')
        if level >= 1:
            self.artifact("plan")
            self.artifact("tasks")
        implementers = [state.get("implementation_owner", "Coder")]
        if team_mode and level >= 1:
            planning = state.get("planning", {})
            if not isinstance(planning, dict):
                raise InvalidHandoff("planning must be an object")
            participants = planning.get("participants", [])
            participant_count = 2 if plan_code else 3
            if (not isinstance(participants, list) or len(participants) != participant_count
                    or any(not isinstance(p, str) or not p.strip() for p in participants)
                    or len({p.strip().casefold() for p in participants}) != participant_count):
                raise InvalidHandoff(f"planning needs {participant_count} distinct participants")
            rounds = planning.get("discussion_rounds")
            if planning.get("status") != "settled" or type(rounds) is not int or not 0 <= rounds <= 2:
                raise InvalidHandoff("Planning must settle within two discussion rounds")
            contributions = planning.get("contributions", [])
            if (not isinstance(contributions, list) or len(contributions) != participant_count
                    or any(not isinstance(c, dict) or not isinstance(c.get("owner"), str) for c in contributions)
                    or {c.get("owner") for c in contributions} != set(participants)):
                raise InvalidHandoff("Each planner needs an independent contribution")
            paths = []
            for contribution in contributions:
                path = self.path(contribution.get("record", ""))
                if not path.is_file() or not path.read_text().strip():
                    raise InvalidHandoff("Missing planning contribution record")
                paths.append(path)
            if len(set(paths)) != participant_count:
                raise InvalidHandoff("Planning contribution records must be separate")
            if plan_code:
                if set(participants) != {'plan-lead', 'plan-review'} or rounds < 1:
                    raise InvalidHandoff('Plan lead draft needs an independent plan review before finalization')
                sources = planning.get('sources')
                if not isinstance(sources, list) or not sources:
                    raise InvalidHandoff('Record researched sources and their effect on the plan')
                for source in sources:
                    if (not isinstance(source, dict) or not isinstance(source.get('url'), str)
                            or not source['url'].startswith(('https://', 'http://'))
                            or not source.get('title') or not source.get('decision')):
                        raise InvalidHandoff('Each source needs a URL, title and relevant plan decision')
            items = state.get("work_items", [])
            if not isinstance(items, list) or not items:
                raise InvalidHandoff("Assign work_items before coding")
            ownership, task_ids = {}, set()
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("owner"), str) or not item["owner"].strip():
                    raise InvalidHandoff("Each work item needs an owner")
                if not isinstance(item.get("id"), str) or not item["id"] or item["id"] in task_ids:
                    raise InvalidHandoff("Work item IDs must be distinct")
                task_ids.add(item["id"])
                if plan_code and item['owner'] not in ('code-main', 'code-helper'):
                    raise InvalidHandoff('Coding belongs to code-main or an explicit independent code-helper subtask')
                if plan_code and item['owner'] == 'code-helper' and not item.get('independent_reason'):
                    raise InvalidHandoff('Helper work needs an independent subtask reason')
                implementers.append(item["owner"])
                files = item.get("files")
                if plan_code and level < 2 and item["owner"] == "code-main" and files in (None, []):
                    files = []  # Main coder chooses implementation structure; the lead records actual files afterward.
                elif not isinstance(files, list) or not files:
                    raise InvalidHandoff("Each work item needs exact file ownership")
                for name in files:
                    path = self.path(name)
                    if path in ownership:
                        raise InvalidHandoff("Overlapping work-item file ownership: " + name)
                    ownership[path] = item["owner"]
                if item.get("status") not in ("pending", "running", "completed"):
                    raise InvalidHandoff("Invalid work item status")
                if level >= 2 and item["status"] != "completed":
                    raise InvalidHandoff("Implementation work items are incomplete")
            if level >= 2 and any(self.path(name) not in ownership for name in state.get("code_files", [])):
                raise InvalidHandoff("Every code_file needs a work-item owner")
            if level >= 2 and set(ownership) != {self.path(name) for name in state.get("code_files", [])}:
                raise InvalidHandoff("Every work-item file must be included in code_files snapshots")
        current = self.snapshot()
        if level >= 2:
            if not current:
                raise InvalidHandoff("List implementation, tests and dependency files in code_files")
            for name in state.get("changed_files", []):
                self.path(name)
            baseline = state.get("baseline", {})
            if set(baseline) != set(current):
                raise InvalidHandoff("baseline must cover every code_file; use null for newly added files")
        if level >= 3:
            self.artifact("review")
            review = state.get("review", {})
            if review.get("status") != "passed" or not review.get("reviewer"):
                raise InvalidHandoff("Independent review has not passed")
            implementation_owner = state.get("implementation_owner", "Coder")
            reviewer = review["reviewer"]
            if plan_code and (reviewer != 'code-review' or implementation_owner != 'code-main'):
                raise InvalidHandoff('Keep code-main implementation and code-review independent technical roles')
            if (not isinstance(implementation_owner, str) or not implementation_owner.strip()
                    or not isinstance(reviewer, str) or not reviewer.strip()):
                raise InvalidHandoff("Implementation owner and reviewer must name roles")
            if reviewer.strip().casefold() in {owner.strip().casefold() for owner in implementers}:
                raise InvalidHandoff("Reviewer must differ from implementation_owner")
            if review.get("snapshot") != current:
                raise InvalidHandoff("Code changed after review; request a new review")
            for finding in review.get("findings", []):
                if finding.get("status") not in ("verified", "waived") or not finding.get("resolution"):
                    raise InvalidHandoff("An unresolved review finding remains")
        if level >= 4:
            self.artifact("verification")
            verification = state.get("verification", {})
            if verification.get("status") != "passed" or verification.get("snapshot") != current:
                raise InvalidHandoff("Current code has not passed verification")
            tests = self.latest_tests(current)
            if not tests or any(type(t.get("exit_code")) is not int or t["exit_code"] != 0
                                or t.get("source_changed_during_test") for t in tests):
                raise InvalidHandoff("Current snapshot has a missing or failing test command")
            # Failed runs stay in the audit trail, including their original
            # evidence. A later successful rerun supersedes their result only.
            for test in state.get("tests", []):
                path = self.path(test.get("evidence", ""))
                if not path.is_file() or digest(path) != test.get("evidence_sha256"):
                    raise InvalidHandoff("Test evidence is missing or has changed")
        if plan_code and level >= 5:
            record = json.loads(self.artifact('experience').read_text())
            validate_experience(self.root, record, current, ids, state.get("product_surface", "web"))
        if level >= 5 and docs_required:
            self.artifact("docs")
        if level >= 6:
            self.artifact("acceptance")
        if level >= 7:
            acceptance = state.get("acceptance", {})
            if acceptance.get("status") != "accepted" or any(not acceptance.get(k) for k in ("source", "quote", "at")):
                raise InvalidHandoff("Explicit user acceptance has not been recorded")
            if acceptance.get("snapshot") != current:
                raise InvalidHandoff("User acceptance must refer to the current code snapshot")
        return {"ok": True, "stage_checked": stage, "task_id": state["task_id"],
                "code_snapshot": current, "meaning": "Evidence consistency only; not proof of human authorization or complete test coverage"}

    def run_test(self, argv, detached=False, files=None):
        if argv and argv[0] == "--":
            argv = argv[1:]
        if not argv:
            raise InvalidHandoff("Supply an executable and arguments after test --")
        if files is not None and not detached:
            raise InvalidHandoff("Explicit --files are only for detached worker tests")
        current = self.snapshot(files)
        if not current:
            raise InvalidHandoff("Set code_files or pass --files before recording tests")
        path = None if detached else self.artifact_path("verification")
        evidence = self.path(".workflour/evidence/" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8] + ".txt")
        evidence.parent.mkdir(parents=True, exist_ok=True)
        print("Running:", json.dumps(argv, ensure_ascii=False), flush=True)
        try:
            result = subprocess.run(argv, cwd=self.root, capture_output=True, text=True, timeout=300)
            code, stdout, stderr = result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired as error:
            code, stdout, stderr = 124, str(error.stdout or ""), str(error.stderr or "") + "\nTimed out after 300 seconds"
        except OSError as error:
            code, stdout, stderr = 127, "", str(error)
        after = self.snapshot(files)
        evidence.write_text("argv: " + json.dumps(argv, ensure_ascii=False) + "\nexit_code: " + str(code) + "\nstdout:\n" + stdout + "\nstderr:\n" + stderr)
        record = {"argv": argv, "exit_code": code, "evidence": str(evidence.relative_to(self.root)),
                  "evidence_sha256": digest(evidence), "snapshot": current,
                  "at": datetime.now(timezone.utc).isoformat(), "source_changed_during_test": current != after}
        if detached:
            record_file = evidence.with_suffix('.json')
            record_file.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
            print(json.dumps({'test_record': str(record_file.relative_to(self.root)), **record}, ensure_ascii=False, indent=2))
            return code if code >= 0 else 128 - code
        self.state.setdefault("tests", []).append(record)
        latest = self.latest_tests(after)
        passed = current == after and bool(latest) and all(t.get("exit_code") == 0 and not t.get("source_changed_during_test") for t in latest)
        self.state["verification"] = {"status": "passed" if passed else "failed", "snapshot": after}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Verification\n\nGenerated from actual commands; verify coverage against the specification.\n\n" +
                        "\n".join("- " + json.dumps(t["argv"], ensure_ascii=False) + " → exit " + str(t["exit_code"]) + " ([evidence](../../" + t["evidence"] + "))" for t in self.state["tests"]) + "\n")
        self.save()
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return code if code >= 0 else 128 - code

    def import_test(self, name):
        record = json.loads(self.path(name).read_text())
        if not isinstance(record, dict) or not isinstance(record.get('argv'), list) or not record['argv']:
            raise InvalidHandoff('Invalid detached test record')
        evidence = self.path(record.get('evidence', ''))
        if not evidence.is_file() or digest(evidence) != record.get('evidence_sha256'):
            raise InvalidHandoff('Detached test evidence missing or changed')
        header = evidence.read_text().splitlines()[:2]
        expected_header = ['argv: ' + json.dumps(record['argv'], ensure_ascii=False), 'exit_code: ' + str(record.get('exit_code'))]
        if header != expected_header:
            raise InvalidHandoff('Detached test metadata disagrees with its captured command/output')
        if record.get('snapshot') != self.snapshot() or record.get('source_changed_during_test'):
            raise InvalidHandoff('Detached test is stale; run against the current code')
        if type(record.get('exit_code')) is not int:
            raise InvalidHandoff('Detached test exit code missing')
        if any(t.get('evidence') == record['evidence'] for t in self.state.get('tests', [])):
            raise InvalidHandoff('Test record already imported')
        self.state.setdefault('tests', []).append(record)
        current = self.snapshot()
        latest = self.latest_tests(current)
        passed = bool(latest) and all(t.get('exit_code') == 0 and not t.get('source_changed_during_test') for t in latest)
        self.state['verification'] = {'status': 'passed' if passed else 'failed', 'snapshot': current}
        self.save()
        return {'imported': name, 'verification': self.state['verification']}

    def artifact_path(self, key):
        return self.path(self.state.get("artifacts", {}).get(key, ""))

    def handoff(self):
        state = self.state
        lines = ["# Task handoff", "", "Regenerated from .workflour/handoff.json. Read files before continuing.", ""]
        for key in ("task_id", "stage", "owner", "next_owner", "next_action"):
            lines.append(f"- {key}: {state.get(key, '')}")
        lines += ["", "## Artifacts", ""]
        lines += [f"- {key}: {value}" for key, value in state.get("artifacts", {}).items() if value]
        lines += ["", "## Decisions", ""] + ["- " + str(value) for value in state.get("decisions", [])]
        if state.get("workflow", {}).get("kind") in ("code-team", "plan-code"):
            lines += ["", "## Team work items", ""]
            lines += [f"- {item.get('id')}: {item.get('owner')} / {item.get('status')} / {', '.join(item.get('files', []))}" for item in state.get("work_items", [])]
            lines += ["", "## Planning records", ""]
            lines += [f"- {c.get('owner')}: {c.get('record')}" for c in state.get("planning", {}).get("contributions", [])]
        lines += ["", "## Blockers", ""] + ["- " + str(value) for value in state.get("blockers", [])]
        lines += ["", "## Current code snapshot", "", "```json", json.dumps(self.snapshot(), indent=2), "```", "",
                  "Review and verification become stale if these files change. See JSON for test records and findings.", ""]
        path = self.path("HANDOFF.md")
        path.write_text("\n".join(lines))
        print(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--actor", help="Shared-state writer role; not identity authentication")
    sub = parser.add_subparsers(dest="action", required=True)
    check = sub.add_parser("check")
    check.add_argument("--stage", choices=STAGES)
    sub.add_parser("snapshot")
    test = sub.add_parser("test")
    test.add_argument("--detached", action="store_true", help="Write evidence without changing shared handoff; default for plan-code")
    test.add_argument("--files", action="append", help="Repeat for every actual code/test/dependency file in a detached snapshot")
    test.add_argument("argv", nargs=argparse.REMAINDER)
    p = sub.add_parser("import-test"); p.add_argument("record")
    sub.add_parser("handoff")
    args = parser.parse_args()
    try:
        project = Project(args.project)
        plan_code = project.state.get("workflow", {}).get("kind") == "plan-code"
        if plan_code and args.action in ("import-test", "handoff") and args.actor != "plan-lead":
            raise InvalidHandoff("Shared-state updates belong to plan-lead")
        if args.action == "check":
            print(json.dumps(project.check(args.stage), ensure_ascii=False, indent=2))
        elif args.action == "snapshot":
            print(json.dumps(project.snapshot(), ensure_ascii=False, indent=2))
        elif args.action == "test":
            return project.run_test(args.argv, detached=args.detached or plan_code, files=args.files)
        elif args.action == "import-test":
            print(json.dumps(project.import_test(args.record), ensure_ascii=False, indent=2))
        else:
            project.handoff()
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("workflow-check: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
