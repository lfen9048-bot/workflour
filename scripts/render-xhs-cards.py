#!/usr/bin/env python3
"""Render a small, local-only 3:4 carousel from the writer's cards.json."""
import argparse
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def text(value):
    return html.escape(str(value), quote=True)


def project_file(project, value):
    p = (project / value).resolve(strict=True)
    p.relative_to(project)
    if not p.is_file():
        raise ValueError('Expected a project file')
    return p


def save_output(path, data):
    if path.is_symlink():
        raise ValueError('Refuse symlink output file: ' + path.name)
    fd, temporary = tempfile.mkstemp(prefix='.render-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data if isinstance(data, bytes) else data.encode('utf-8'))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def output_directory(project, value):
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or '..' in relative.parts:
        raise ValueError('Use a project-relative output directory without ".."')
    output = project
    for part in relative.parts:
        output /= part
        if output.is_symlink():
            raise ValueError('Refuse symlink output directory: ' + part)
    output.resolve().relative_to(project)
    output.mkdir(parents=True, exist_ok=True)
    return output


STYLE = '''
*{box-sizing:border-box}body{margin:0;background:#e8e6e1;color:#192a31;font-family:"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif}
.card{position:relative;isolation:isolate;width:1080px;height:1440px;background:#f7f4ec;padding:76px 78px;overflow:hidden;display:flex;flex-direction:column}
.card::before{content:"";position:absolute;top:0;left:0;right:0;height:14px;background:#e87e5a}.eyebrow{font-size:23px;letter-spacing:2px;color:#59716f;font-weight:600;margin:0 0 32px}
.num{position:absolute;top:76px;right:78px;font-size:24px;font-weight:500}.headline{font-size:76px;line-height:1.19;letter-spacing:-2px;font-weight:700;margin:12px 0 38px;max-width:880px;white-space:pre-line}
.deck{font-size:34px;line-height:1.65;color:#4b6063;margin:0 0 36px}.body{font-size:34px;line-height:1.68;white-space:pre-line}.bullets{margin:10px 0 0;padding:0;list-style:none}
.bullets li{padding:23px 0 23px 37px;border-bottom:1px solid #d8ded6;position:relative;line-height:1.5}.bullets li::before{content:"";width:10px;height:10px;background:#e87e5a;position:absolute;left:2px;top:43px}
.footer{margin-top:auto;padding-top:26px;border-top:1px solid #ccd5cc;color:#5e716f;font-size:21px;line-height:1.7;display:flex;justify-content:space-between;gap:24px}.footer span:first-child{max-width:720px}
.art{width:100%;height:575px;object-fit:cover;border-radius:6px;margin:4px 0 32px}.cover .headline{font-size:87px;line-height:1.15;margin-bottom:24px}.cover .deck{font-size:30px;margin-bottom:25px}
.note{background:#e8ece3;border-left:5px solid #8fa293;padding:23px 28px;font-size:27px;line-height:1.65;margin-top:32px}.sources{font-size:23px;line-height:1.7;color:#58716f;overflow-wrap:anywhere;margin-top:26px}
.cover-art{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:-2}.cover-shade{position:absolute;inset:0;z-index:-1;background:linear-gradient(to bottom,#f7f4ec 0%,#f7f4ecf5 24%,#f7f4ec00 49%,#f7f4ec00 70%,#f7f4eceb 90%,#f7f4ec 100%)}
.image-cover .headline{font-size:84px;line-height:1.18;margin-bottom:24px;max-width:840px}.image-cover .deck{font-size:31px;line-height:1.5;max-width:810px;margin-bottom:32px}.cover-details{margin-top:auto;background:#f7f4ecf5;padding:20px 24px;border-radius:6px}.cover-details .body{font-size:28px;line-height:1.5}.cover-details .note{margin-top:18px}.cover-details .sources{margin-top:16px}.image-cover .cover-details+.footer{margin-top:24px}
@media screen{.card{margin:32px auto;box-shadow:0 10px 45px #243f4220}}@media(max-width:1100px){.card{margin:0;box-shadow:none}}
'''


def build(project, data):
    cards = data.get('cards')
    if not isinstance(cards, list) or not 1 <= len(cards) <= 6:
        raise ValueError('cards.json needs 1–6 cards')
    output = []
    for i, card in enumerate(cards, 1):
        if not isinstance(card, dict) or not card.get('title'):
            raise ValueError('Each card needs a title')
        image_cover = card.get('layout') == 'image-cover'
        if image_cover and not card.get('image'):
            raise ValueError('image-cover needs a local project image')
        image = ''
        if card.get('image'):
            p = project_file(project, card['image'])
            image = f'<img class="{"cover-art" if image_cover else "art"}" src="{text(p.as_uri())}" alt="{text(card.get("image_alt", "原创插图"))}">'
        bullets = ''.join(f'<li>{text(s)}</li>' for s in card.get('bullets', []))
        sources = ''.join(f'<div>{text(s)}</div>' for s in card.get('sources', []))
        note = f'<div class="note">{text(card["note"])}</div>' if card.get('note') else ''
        if image_cover:
            details = ''
            if any(card.get(key) for key in ('body', 'bullets', 'note', 'sources')):
                details = f'<div class="cover-details"><div class="body">{text(card.get("body", ""))}<ul class="bullets">{bullets}</ul></div>{note}<div class="sources">{sources}</div></div>'
            output.append(f'''<article class="card image-cover" id="card-{i}">
{image}<div class="cover-shade" aria-hidden="true"></div>
<div class="eyebrow">{text(card.get('kicker', data.get('series', 'AI · 更新笔记')))}</div><div class="num">{i:02d} / {len(cards):02d}</div>
<h1 class="headline">{text(card['title'])}</h1><div class="deck">{text(card.get('subtitle', ''))}</div>{details}
<footer class="footer"><span>{text(card.get('source_label', '依据公开资料整理 · 非亲测'))}</span><span>{text(data.get('as_of', ''))}</span></footer></article>''')
            continue
        output.append(f'''<article class="card {'cover' if image else ''}" id="card-{i}">
<div class="eyebrow">{text(card.get('kicker', data.get('series', 'AI · 更新笔记')))}</div><div class="num">{i:02d} / {len(cards):02d}</div>
<h1 class="headline">{text(card['title'])}</h1><div class="deck">{text(card.get('subtitle', ''))}</div>
{image}<div class="body">{text(card.get('body', ''))}<ul class="bullets">{bullets}</ul></div>{note}
<div class="sources">{sources}</div><footer class="footer"><span>{text(card.get('source_label', '依据公开资料整理 · 非亲测'))}</span><span>{text(data.get('as_of', ''))}</span></footer></article>''')
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>图文草稿预览</title><style>' + STYLE + '</style><body>' + '\n'.join(output) + '</body></html>'


def render(project, input_file, output_dir='output'):
    from playwright.sync_api import sync_playwright
    data = json.loads(project_file(project, input_file).read_text())
    output = output_directory(project, output_dir)
    preview = output / 'preview.html'
    save_output(preview, build(project, data))
    with sync_playwright() as p:
        channel = os.environ.get('XHS_BROWSER_CHANNEL')
        if not channel and sys.platform == 'darwin' and Path('/Applications/Google Chrome.app').exists():
            channel = 'chrome'
        browser = p.chromium.launch(headless=True, **({'channel': channel} if channel else {}))
        context = browser.new_context(viewport={'width': 1080, 'height': 1440}, device_scale_factor=1)
        page = context.new_page()
        # Preview has no remote images, fonts, or scripts.
        page.route('http://**/*', lambda route: route.abort())
        page.route('https://**/*', lambda route: route.abort())
        page.goto(preview.as_uri())
        page.evaluate('document.fonts.ready')
        page.wait_for_function('Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)')
        checks = page.locator('.card').evaluate_all('nodes => nodes.map(n => ({id:n.id,overflow:n.scrollHeight>n.clientHeight+1,bottom:n.querySelector("footer").getBoundingClientRect().bottom-n.getBoundingClientRect().top}))')
        if any(row['overflow'] or row['bottom'] > 1440 for row in checks):
            browser.close()
            raise ValueError('Card content overflows; shorten the copy before rendering')
        files = []
        for i in range(1, len(data['cards']) + 1):
            file = output / f'card-{i:02d}.png'
            # Render each card at the top of its own layout. Scrolling a tall
            # multi-card page can capture unpainted compositor tiles in Chrome.
            page.locator('.card').evaluate_all('(nodes, id) => nodes.forEach(n => n.style.display = n.id === id ? "flex" : "none")', f'card-{i}')
            page.evaluate('window.scrollTo(0, 0)')
            page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
            save_output(file, page.locator(f'#card-{i}').screenshot(animations='disabled'))
            files.append({'path': str(file.relative_to(project)), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest(), 'width': 1080, 'height': 1440})
        context.close()
        browser.close()
    result = {'renderer': 'local_html_template', 'images': files, 'preview': str(preview.relative_to(project)), 'layout_checks': checks}
    save_output(output / 'render-manifest.json', json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--input', default='cards.json')
    parser.add_argument('--output-dir', default='output', help='Project-relative directory for preview, cards, and manifest')
    args = parser.parse_args()
    if importlib.util.find_spec('playwright') is None:
        alternate = Path(os.environ.get('XHS_BROWSER_PYTHON', ROOT / '.tools/browser/bin/python'))
        # A venv's Python is often a symlink to the same binary; its module
        # search path still differs, so do not resolve away the venv here.
        if alternate.is_file() and alternate.absolute() != Path(sys.executable).absolute():
            return subprocess.call([str(alternate), str(Path(__file__).resolve()), *sys.argv[1:]])
        raise ValueError('Playwright missing: install playwright and chromium, or set XHS_BROWSER_PYTHON')
    p = Path(args.project).expanduser()
    if not p.is_absolute():
        raise ValueError('Use an absolute project path')
    print(json.dumps(render(p.resolve(strict=True), args.input, args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit('render-xhs-cards: ' + str(error)) from None
