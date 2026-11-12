#!/usr/bin/env python3
"""Prepare and verify a native dispatch. This tool never sends a Bot message."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

import dispatch_intents as dispatch


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--actor', required=True, choices=['plan-lead'])
    p.add_argument('phase'); p.add_argument('role')
    p.add_argument('--message-file', type=Path, required=True)
    p.add_argument('--title'); p.add_argument('--done-when')
    p.add_argument('--supplement', action='store_true')
    p.add_argument('--reason'); p.add_argument('--evidence')
    p.add_argument('--require-image', action='store_true')
    for action in ('preflight', 'begin', 'finish', 'requirements'):
        sub.add_parser(action)
    args = parser.parse_args(argv)
    try:
        if args.action == 'prepare':
            value = dispatch.prepare(args.project, args.phase, args.role, args.message_file.read_text(),
                                     title=args.title, done_when=args.done_when, supplement=args.supplement,
                                     reason=args.reason, evidence=args.evidence, require_image=args.require_image)
            result = {k: value[k] for k in ('id', 'state', 'native_arguments', 'required_capabilities')}
            result['instruction'] = 'Pass native_arguments unchanged to coordinate_bots only when state is prepared; all other states require receipt inspection.'
        else:
            raw = sys.stdin.read(128_001)
            if len(raw) > 128_000: raise ValueError('Dispatch input too large')
            data = json.loads(raw)
            if args.action == 'requirements':
                result = dispatch.requirements_for_binding(data)
            elif args.action == 'finish':
                result = dispatch.finish(data['intent_id'], data['binding'])
            else:
                result = getattr(dispatch, args.action)(data['arguments'], data['binding'])
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get('ok', True) else 1
    except (OSError, ValueError, KeyError, sqlite3.Error) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
