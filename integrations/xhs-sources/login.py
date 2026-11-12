#!/usr/bin/env python3
"""User login in a dedicated Chrome profile; save only that platform's session."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request


async def login(wait_seconds, platform):
    os.umask(0o077)
    os.environ['TWS_TELEMETRY'] = '0'
    from playwright.async_api import async_playwright

    home = Path(os.environ.get('WORKFLOUR_XHS_SOURCES_HOME',
                               Path.home() / '.workflour/xhs-sources')).expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    home.chmod(0o700)
    chrome = os.environ.get('XHS_CHROME_BIN') or (
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' if sys.platform == 'darwin'
        else shutil.which('google-chrome') or shutil.which('chromium') or shutil.which('chromium-browser'))
    if not chrome or not Path(chrome).is_file():
        raise RuntimeError('Installed Chrome is required')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    # Start the installed browser normally, without Playwright's launch flags.
    # This private profile never imports cookies from the personal Chrome profile.
    url = 'https://x.com/i/flow/login' if platform == 'x' else 'https://www.youtube.com/'
    process = subprocess.Popen([chrome, '--user-data-dir=' + str(home / (platform + '-browser-manual')),
        '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=' + str(port),
        '--no-first-run', '--no-default-browser-check', url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(40):
        try:
            with opener.open(f'http://127.0.0.1:{port}/json/version', timeout=1) as response:
                json.load(response)
            break
        except OSError:
            await asyncio.sleep(0.5)
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
        context = browser.contexts[0]
        try:
            print(json.dumps({'status': 'waiting_for_user_login', 'platform': platform,
                              'dedicated_profile': True, 'seconds': wait_seconds}), flush=True)
            deadline = time.monotonic() + wait_seconds
            while time.monotonic() < deadline:
                scoped = await context.cookies('https://x.com' if platform == 'x' else 'https://www.youtube.com')
                cookies = {c['name']: c['value'] for c in scoped}
                ready = (cookies.get('auth_token') and cookies.get('ct0')) if platform == 'x' else cookies.get('SAPISID')
                if ready:
                    if platform == 'x':
                        from twscrape import API
                        from twscrape.logger import set_log_level
                        set_log_level('CRITICAL')
                        api = API(str(home / 'x-accounts.db'))
                        await api.pool.add_account_cookies('xhs-research', json.dumps(
                            {name: cookies[name] for name in ('auth_token', 'ct0')}))
                        (home / 'x-accounts.db').chmod(0o600)
                    else:
                        lines = ['# Netscape HTTP Cookie File', '# Dedicated user-authorized YouTube session']
                        for c in scoped:
                            if c['domain'].lstrip('.') != 'youtube.com':
                                continue
                            fields = [c['domain'], 'TRUE' if c['domain'].startswith('.') else 'FALSE',
                                c['path'], 'TRUE' if c['secure'] else 'FALSE',
                                str(max(0, int(c.get('expires', 0)))), c['name'], c['value']]
                            if any('\n' in value or '\t' in value for value in fields):
                                continue
                            lines.append('\t'.join(fields))
                        temporary = home / 'youtube-cookies.tmp'
                        temporary.write_text('\n'.join(lines) + '\n')
                        temporary.chmod(0o600)
                        temporary.replace(home / 'youtube-cookies.txt')
                    print(json.dumps({'status': 'session_saved', 'platform': platform,
                                      'account_slots': 1, 'network_validation': 'pending'}), flush=True)
                    return 0
                await asyncio.sleep(2)
            print(json.dumps({'status': 'login_required', 'reason': 'user_login_timeout'}), flush=True)
            return 3
        finally:
            await browser.close()
            if process.poll() is None:
                process.terminate()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait-seconds', type=int, default=900)
    parser.add_argument('--platform', choices=('x', 'youtube'), default='x')
    args = parser.parse_args()
    if not 30 <= args.wait_seconds <= 1800:
        parser.error('--wait-seconds must be between 30 and 1800')
    try:
        raise SystemExit(asyncio.run(login(args.wait_seconds, args.platform)))
    except (KeyboardInterrupt, Exception) as error:
        print(json.dumps({'status': 'login_required', 'reason': type(error).__name__}))
        raise SystemExit(3)
