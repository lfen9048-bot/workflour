"""Offline browser regression for the native settings page transition contract.

Run with .tools/browser/bin/python; no service, profile, credentials or network.
"""
from pathlib import Path
import unittest

try:
    from playwright.sync_api import sync_playwright, expect
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "integrations/openmausbot/workbench"

# The 0.1.143 settings dialog retains its scroll container during page changes.
# React removes native page children, leaving externally inserted siblings alive.
NATIVE_SHEET = """<!doctype html><html lang="zh-CN"><body>
<div data-settings-sheet data-settings-look="simple">
  <div role="dialog" aria-labelledby="app-settings-title">
    <header><h2 id="app-settings-title">设置</h2></header>
    <div data-settings-scroll>
      <section data-settings-block="engines"><h3>引擎</h3></section>
    </div>
  </div>
</div></body></html>"""


@unittest.skipIf(sync_playwright is None, "Use .tools/browser/bin/python for browser regression")
class WorkbenchNavigationTests(unittest.TestCase):
    def test_model_guide_is_removed_on_native_page_change_and_returns_once(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            try:
                context = browser.new_context(viewport={"width": 375, "height": 812})
                context.route("**/*", lambda route: route.abort())
                page = context.new_page()
                page.set_content(NATIVE_SHEET)
                page.add_style_tag(path=str(OVERLAY / "workbench.css"))
                page.add_script_tag(path=str(OVERLAY / "workbench.js"))
                guide = page.locator("[data-workflour-model-guide]")
                engines = page.locator('[data-settings-block="engines"]')
                toggle = page.get_by_role("button", name="高级设置", exact=True)
                expect(guide).to_have_count(1)
                expect(guide).to_be_visible()
                expect(engines).to_be_hidden()

                # Emulate native React unmounting its own page, not the overlay.
                page.evaluate("""() => {
                  document.querySelector('[data-settings-block="engines"]').remove();
                  const appearance = document.createElement('section');
                  appearance.dataset.settingsBlock = 'appearance';
                  appearance.innerHTML = '<h3>外观</h3>';
                  document.querySelector('[data-settings-scroll]').append(appearance);
                }""")
                expect(guide).to_have_count(0)
                expect(page.get_by_role("heading", name="外观", exact=True)).to_be_visible()
                expect(toggle).to_have_count(1)

                page.evaluate("""() => {
                  document.querySelector('[data-settings-block="appearance"]').remove();
                  const engines = document.createElement('section');
                  engines.dataset.settingsBlock = 'engines';
                  engines.innerHTML = '<h3>引擎</h3>';
                  document.querySelector('[data-settings-scroll]').append(engines);
                }""")
                expect(guide).to_have_count(1)
                expect(guide).to_be_visible()
                expect(engines).to_be_hidden()
                toggle.click()
                expect(guide).to_be_hidden()
                expect(engines).to_be_visible()
                toggle.click()
                expect(guide).to_be_visible()
                expect(engines).to_be_hidden()
                expect(toggle).to_have_count(1)
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
