#!/usr/bin/env python3
"""Prepare actual cards synchronously; confirm only after reading the images."""
import argparse
import json
from xhs_delivery import DeliveryCancelled, prepare, confirm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'confirm'):
        command = commands.add_parser(name)
        command.add_argument('--project', required=True)
        if name == 'prepare':
            group = command.add_mutually_exclusive_group()
            group.add_argument('--image-prompt-file')
            group.add_argument('--existing-image-evidence')
        else:
            command.add_argument('--reviewed-image', action='append', required=True)
    args = parser.parse_args()
    value = (prepare(args.project, args.image_prompt_file, args.existing_image_evidence)
             if args.command == 'prepare' else confirm(args.project, args.reviewed_image))
    print(json.dumps(value, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except DeliveryCancelled:
        raise SystemExit('xhs-deliver: cancelled; inspect delivery/receipt.json, do not repeat generation')
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit('xhs-deliver: ' + str(error)) from None
