#!/usr/bin/env python3
"""Run an argv in an initialized project's exact directory; no shell parsing.

Does not change an OpenMausBot thread's native cwd or provide a file sandbox.
"""
import argparse
from pathlib import Path
import subprocess
import sys


def run(project, argv):
    root = Path(project).expanduser().resolve(strict=True)
    if not (root / '.workflour/project.json').is_file():
        raise ValueError('Expected an initialized project with .workflour/project.json')
    if not argv:
        raise ValueError('A command after -- is required')
    return subprocess.run(argv, cwd=root).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.command[1:] if args.command[:1] == ['--'] else args.command
    try:
        return run(args.project, argv)
    except (ValueError, OSError) as exc:
        print(f'Project command: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
