"""Neutral fixture operator. Writes observed states/screenshots, no pass/fail oracle."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "evidence"


def snapshot(page):
    return page.evaluate("""() => {
      const rect = s => {const r=document.querySelector(s).getBoundingClientRect();
        return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom};};
      return {status:document.querySelector('#status').textContent,
        input:document.querySelector('#name').value,draft:localStorage.getItem('draft'),
        focus:document.activeElement.id,viewport:{width:innerWidth,height:innerHeight},
        scrollWidth:document.documentElement.scrollWidth,scrollY:scrollY,
        lastNote:rect('#last-note'),footer:rect('footer')};
    }""")


def main():
    OUT.mkdir(exist_ok=True)
    report = {"environment_prepared_by": "maintainer", "pages": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        try:
            for filename in ("one.html", "two.html"):
                context = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
                context.route("http://**", lambda route: route.abort())
                context.route("https://**", lambda route: route.abort())
                try:
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda exc: errors.append(str(exc)))
                    page.goto((ROOT / filename).as_uri())
                    page.evaluate("localStorage.clear()")
                    steps = {"initial": snapshot(page)}
                    page.locator("#name").fill("陈一")
                    page.locator("#name").focus()
                    page.keyboard.press("Tab")
                    steps["before_keyboard"] = snapshot(page)
                    page.keyboard.press("Enter")
                    steps["after_keyboard"] = snapshot(page)
                    page.screenshot(path=str(OUT / f"{Path(filename).stem}-keyboard.png"))
                    page.locator("#save").click()
                    steps["after_click"] = snapshot(page)
                    page.locator("#name").fill("陈二")
                    page.locator("#cancel").click()
                    steps["after_cancel"] = snapshot(page)
                    page.locator("#fail").check()
                    page.locator("#save").click()
                    steps["after_failure"] = snapshot(page)
                    page.evaluate("window.scrollTo(0,document.documentElement.scrollHeight)")
                    steps["bottom"] = snapshot(page)
                    page.screenshot(path=str(OUT / f"{Path(filename).stem}-bottom.png"))
                    report["pages"][filename] = {"steps": steps, "page_errors": errors}
                finally:
                    context.close()
        finally:
            browser.close()
    target = OUT / "browser-state.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
