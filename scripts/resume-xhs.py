#!/usr/bin/env python3
"""Inspect XHS recovery and block unsafe native continuation.

status/preview are local, read-only and report native model drift. send is blocked:
OpenMausBot 0.1.143 has no verifiable per-task opt-out from native quota takeover.
"""
import argparse
import json
import os
from pathlib import Path

import xhs_recovery as recovery


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('status', 'preview', 'send'):
        command = commands.add_parser(name)
        command.add_argument('--project', required=True, type=Path)
        if name != 'status':
            command.add_argument('--reason', required=name == 'send', default='继续已授权的原稿机械交付')
    args = parser.parse_args()
    project = recovery.workflow().project_path(args.project)
    if args.command == 'send':
        os.umask(0o077)
        team = recovery.module('provision-xhs-team.py')
        result = recovery.send(team.control.Client(), team.manifest(team.DEFAULT_MANIFEST), project, args.reason)
    else:
        result = recovery.preview(project, reason=getattr(args, 'reason', '继续已授权的原稿机械交付'))
        if args.command == 'status':
            result.pop('prompt')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, StopIteration) as error:
        raise SystemExit('resume-xhs: ' + str(error)) from None
