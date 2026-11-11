#!/usr/bin/env python3
"""Create a project from the pinned, agent-neutral collaboration template.

This command copies files only. It never starts an agent or changes a profile.
Git initialization is opt-in and does not commit, publish, or add a remote.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


TOOLKIT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = TOOLKIT_ROOT / "templates" / "project"
CHECKER_SOURCE = TOOLKIT_ROOT / "scripts" / "workflow-check.py"


class ProjectInitError(RuntimeError):
    """Initialization could not proceed without overwriting existing work."""


def _target_path(value: str | Path) -> Path:
    # Do not resolve the final component: a destination symlink must be refused.
    return Path(os.path.abspath(os.path.expanduser(str(value))))


def _check_destination(target: Path) -> None:
    if target.is_symlink():
        raise ProjectInitError(f"目标是符号链接，未写入：{target}")
    if target.exists():
        if not target.is_dir():
            raise ProjectInitError(f"目标已存在且不是目录，未写入：{target}")
        if any(target.iterdir()):
            raise ProjectInitError(f"目标目录不是空目录，未覆盖任何文件：{target}")


def _copy_file(source: Path, destination: Path, project_name: str) -> None:
    # Exclusive creation also protects a target that changed after preflight.
    if source.suffix == ".md" and ".specify" not in source.parts:
        content = source.read_text(encoding="utf-8").replace(
            "{{PROJECT_NAME}}", project_name
        ).replace("{{TOOLKIT_ROOT}}", str(TOOLKIT_ROOT))
        with destination.open("x", encoding="utf-8", newline="") as stream:
            stream.write(content)
    else:
        with source.open("rb") as incoming, destination.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
    shutil.copymode(source, destination)


def create_project(
    destination: str | Path,
    *,
    name: str | None = None,
    git: bool = False,
    workflow: str = "manual",
) -> Path:
    if workflow not in ("manual", "code-team", "plan-code"):
        raise ProjectInitError("未知工作流")
    target = _target_path(destination)
    project_name = name if name is not None else target.name
    if not project_name.strip() or any(ord(character) < 32 for character in project_name):
        raise ProjectInitError("项目名称不能为空或包含控制字符")
    _check_destination(target)
    if not TEMPLATE_ROOT.is_dir() or not CHECKER_SOURCE.is_file():
        raise ProjectInitError("工作流工具包不完整：缺少项目模板或 scripts/workflow-check.py")

    entries = sorted(TEMPLATE_ROOT.rglob("*"), key=lambda path: path.parts)
    if any(path.is_symlink() for path in entries):
        raise ProjectInitError("模板含符号链接，未创建项目")
    if git and shutil.which("git") is None:
        raise ProjectInitError("未找到 Git；可不带 --git 创建项目")

    # All reads and source checks finish before creating the destination.
    if not target.exists():
        target.mkdir(parents=True, exist_ok=False)
    else:
        _check_destination(target)
    try:
        for source in entries:
            output = target / source.relative_to(TEMPLATE_ROOT)
            if source.is_dir():
                output.mkdir(exist_ok=False)
            elif source.is_file():
                _copy_file(source, output, project_name)
        checker = target / ".workflour" / "check.py"
        with CHECKER_SOURCE.open("rb") as incoming, checker.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
        checker.chmod(0o755)
        if workflow == "code-team":
            state_path = target / ".workflour/handoff.json"
            state = json.loads(state_path.read_text())
            state.update({
                "workflow": {"kind": "code-team", "docs_required": False},
                "owner": "Code Team · 总控", "next_owner": "Kimi", "implementation_owner": "Antigravity",
                "planning": {"status": "pending", "participants": ["Kimi", "DeepSeek", "GLM Planner"],
                             "contributions": [], "discussion_rounds": 0, "max_rounds": 2,
                             "discussion_required": True, "discussion_version": 1},
                "work_items": [],
            })
            state["review"]["reviewer"] = "GLM Reviewer"
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        if workflow == 'plan-code':
            state_path = target / '.workflour/handoff.json'
            state = json.loads(state_path.read_text())
            state.update({
                'workflow': {'kind': 'plan-code', 'version': 2, 'docs_required': False},
                'owner': 'plan-lead', 'next_owner': 'plan-lead', 'implementation_owner': 'code-main',
                'original_request': '', 'assumptions': [], 'product_surface': 'web',
                'planning': {'status': 'pending', 'participants': ['plan-lead', 'plan-review'],
                             'contributions': [], 'discussion_rounds': 0, 'max_rounds': 2, 'sources': []},
                'work_items': [],
                'next_action': 'Plan 负责人保留用户原话，调研并形成初案，再交独立方案评审',
            })
            state['review']['reviewer'] = 'code-review'
            state['artifacts']['experience'] = ''
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
            # Copy a focused flow rather than presenting old teams as current instructions.
            overlay = TOOLKIT_ROOT / 'templates/plan-code'
            # These are newly copied manual prompts, not user files.
            shutil.rmtree(target / '.workflour/prompts')
            for source in sorted(overlay.rglob('*')):
                if source.is_symlink():
                    raise ProjectInitError('plan-code 模板含符号链接')
                if source.is_file():
                    output = target / source.relative_to(overlay)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    if output.exists():
                        output.unlink()  # Only files just created by this initializer.
                    _copy_file(source, output, project_name)
            (target / '.workflour/templates/handoff.json').write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
        metadata = {
            "schema_version": 1,
            "project_name": project_name,
            "template": "workflour-" + workflow + "-project",
            "spec_kit_version": "1.3.2",
            "spec_kit_commit": "55264c2f2f2d1146f02abc543cb913dcdf1f9342",
            "git_requested": git,
            "workflow": workflow,
            "coordinator": "plan-lead" if workflow == "plan-code" else ("Code Team · 总控" if workflow == "code-team" else "Coordinator"),
        }
        with (target / ".workflour" / "project.json").open("x", encoding="utf-8") as stream:
            json.dump(metadata, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except OSError as error:
        # Leave reviewable partial output. Never recursively remove a directory
        # another process may have started using while this command was running.
        raise ProjectInitError(f"初始化未完成，已写文件保留在 {target}：{error}") from error

    if git:
        completed = subprocess.run(
            ["git", "-C", str(target), "init"],
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode:
            raise ProjectInitError(
                f"项目文件已创建，但 Git 初始化失败：{completed.stderr.strip()}"
            )
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="在新目录或空目录创建多 Agent 协作项目")
    parser.add_argument("destination", help="目标项目目录，必须不存在或为空")
    parser.add_argument("--name", help="项目显示名称，默认使用目录名称")
    parser.add_argument("--git", action="store_true", help="显式启用本地 git init；不提交、不推送")
    parser.add_argument("--workflow", choices=("manual", "code-team", "plan-code"), default="manual")
    parser.add_argument("--json", action="store_true", help="输出机器可读结果")
    args = parser.parse_args(argv)
    try:
        target = create_project(args.destination, name=args.name, git=args.git, workflow=args.workflow)
    except (ProjectInitError, OSError) as error:
        print(f"初始化失败：{error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"project": str(target), "workflow": str(target / "PROJECT-WORKFLOW.md")}, ensure_ascii=False))
    else:
        print(f"项目模板已创建：{target}")
        print(f"下一步：阅读 {target / 'PROJECT-WORKFLOW.md'}，填写需求与验收条件。")
        print("没有启动 Agent、调用模型或修改已有 profiles。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
