#!/usr/bin/env python3
"""Explicitly add the XHS delivery MCP to this workspace's Antigravity config.

This never writes a user/global MCP config and never starts the MCP or a model.
Existing unrelated settings are retained; an occupied server name is a conflict.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SERVER_KEY = 'workflour_xhs_delivery'


def read_config(path):
    if path.is_symlink():
        raise ValueError('Refuse a symlink MCP config')
    if not path.exists():
        return None, {}
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('MCP config must be a regular file')
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError('MCP config exceeds the size limit')

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('MCP config contains duplicate keys')
            result[key] = value
        return result

    def constant(_):
        raise ValueError('MCP config contains a non-finite number')

    config = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(config, dict):
        raise ValueError('MCP config must be an object')
    return raw, config


def configure(root):
    root = Path(root).expanduser().resolve(strict=True)
    if not root.is_dir() or not (root / 'scripts/xhs-delivery-mcp.py').is_file():
        raise ValueError('root must contain scripts/xhs-delivery-mcp.py')
    directory = root / '.agents'
    if directory.is_symlink():
        raise ValueError('Refuse a symlink .agents directory')
    directory.mkdir(exist_ok=True)
    path = directory / 'mcp_config.json'
    raw, config = read_config(path)
    servers = config.setdefault('mcpServers', {})
    if not isinstance(servers, dict):
        raise ValueError('mcpServers must be an object')
    python = shutil.which('python3')
    if not python:
        raise ValueError('python3 is required')
    desired = {
        'command': str(Path(python).absolute()),
        'args': [str(root / 'scripts/xhs-delivery-mcp.py')],
        'timeoutSeconds': 600,
        'tools': {name: {'background': 'off', 'eager': True}
                  for name in ('prepare_delivery', 'confirm_delivery')},
    }
    if SERVER_KEY in servers:
        if servers[SERVER_KEY] != desired:
            raise ValueError('Existing workflour_xhs_delivery configuration conflicts; inspect it before changing it')
        return {'changed': False, 'path': str(path), 'server': SERVER_KEY}
    servers[SERVER_KEY] = desired
    value = (json.dumps(config, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    fd, temporary = tempfile.mkstemp(prefix='.xhs-mcp-', dir=directory)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        current, _ = read_config(path)
        if current != raw:
            raise ValueError('MCP config changed during setup; rerun after reviewing it')
        if raw is None:
            # Unlike replace, link cannot overwrite a concurrently-created file.
            os.link(temporary, path)
        else:
            os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
            os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {'changed': True, 'path': str(path), 'server': SERVER_KEY}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='Workspace root (defaults to this repository)')
    args = parser.parse_args()
    try:
        print(json.dumps(configure(args.root), ensure_ascii=False))
    except (ValueError, OSError) as error:
        raise SystemExit('configure-xhs-delivery: ' + str(error)) from None


if __name__ == '__main__':
    main()
