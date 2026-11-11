import os
import sys
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

PROJECT_DIR = Path("/Users/a1/Documents/a/workflour/examples/plan-code-web-demo").resolve()
INDEX_HTML = PROJECT_DIR / "index.html"
FILE_URL = f"file://{INDEX_HTML}"

def run_tests():
    print(f"Starting Playwright automated test suite on: {FILE_URL}")
    assert INDEX_HTML.exists(), f"index.html does not exist at {INDEX_HTML}"

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)

        # -------------------------------------------------------------
        # Test 1: Desktop basic flow & REQ-001 / REQ-002 / REQ-003
        # -------------------------------------------------------------
        print("\n--- Test 1: Desktop basic flow & REQ-001, 002, 003 ---")
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(FILE_URL)

        # 1.1 Initial state
        expect(page.locator("h1")).to_have_text("今日三件事")
        expect(page.locator("#counter-badge")).to_have_text("已完成 0 件 / 共 0 件")
        expect(page.locator("#empty-state")).to_be_visible()
        expect(page.locator("#todo-list")).to_be_hidden()
        print("  ✓ Initial state verified: empty state visible, counter 0/0")

        # 1.2 Empty and pure whitespace input validation (REQ-002)
        page.fill("#todo-input", "")
        page.click("#add-btn")
        expect(page.locator("#status-banner")).to_be_visible()
        expect(page.locator("#status-banner")).to_contain_text("事项内容不能为空")
        expect(page.locator("#counter-badge")).to_have_text("已完成 0 件 / 共 0 件")

        page.fill("#todo-input", "   \t  \u3000 ")
        page.click("#add-btn")
        expect(page.locator("#status-banner")).to_be_visible()
        expect(page.locator("#status-banner")).to_contain_text("事项内容不能为空")
        expect(page.locator("#counter-badge")).to_have_text("已完成 0 件 / 共 0 件")
        print("  ✓ Empty & whitespace validation verified")

        # 1.3 Add 3 valid items (REQ-002)
        page.fill("#todo-input", "第一件事：需求梳理与设计")
        page.click("#add-btn")
        expect(page.locator("#status-banner")).to_be_hidden()
        expect(page.locator("#counter-badge")).to_have_text("已完成 0 件 / 共 1 件")
        expect(page.locator(".todo-item")).to_have_count(1)

        page.fill("#todo-input", "第二件事：实现核心功能与UI")
        page.keyboard.press("Enter")
        expect(page.locator("#counter-badge")).to_have_text("已完成 0 件 / 共 2 件")
        expect(page.locator(".todo-item")).to_have_count(2)

        page.fill("#todo-input", "第三件事：编写自动化测试与文档")
        page.click("#add-btn")
        expect(page.locator("#counter-badge")).to_have_text("已完成 0 件 / 共 3 件")
        expect(page.locator(".todo-item")).to_have_count(3)
        print("  ✓ 3 items added successfully; Enter & Click both work")

        # 1.4 Max limit 3 items rejection (Click and Enter) (REQ-002, M-2, M-3)
        page.fill("#todo-input", "第四件事：多余的任务")
        page.click("#add-btn")
        expect(page.locator("#status-banner")).to_be_visible()
        expect(page.locator("#status-banner")).to_contain_text("今日最多保留 3 件事")
        expect(page.locator("#status-banner")).to_contain_text("包含已完成")
        expect(page.locator("#status-banner")).to_contain_text("请先删除一件不需要的事项")
        banner_text = page.locator("#status-banner").inner_text()
        assert "先完成或删除" not in banner_text, f"Misleading guide still present: {banner_text}"
        assert "先完成" not in banner_text, f"Misleading guide still present: {banner_text}"
        expect(page.locator(".todo-item")).to_have_count(3)
        # Input value should remain and focus should be in input
        expect(page.locator("#todo-input")).to_have_value("第四件事：多余的任务")
        focused_id = page.evaluate("() => document.activeElement.id")
        assert focused_id == "todo-input", f"Expected focus on todo-input, got {focused_id}"

        # Try Enter submit on 4th item
        page.keyboard.press("Enter")
        expect(page.locator("#status-banner")).to_be_visible()
        expect(page.locator("#status-banner")).to_contain_text("今日最多保留 3 件事")
        expect(page.locator(".todo-item")).to_have_count(3)
        print("  ✓ Max limit 3 items enforced via click and enter; banner clear, input preserved & focused")

        # 1.5 Toggle completion (REQ-003)
        checkboxes = page.locator(".todo-checkbox")
        checkboxes.nth(0).click()
        expect(page.locator("#counter-badge")).to_have_text("已完成 1 件 / 共 3 件")
        expect(page.locator(".todo-item").nth(0)).to_have_class("todo-item completed")

        checkboxes.nth(1).click()
        expect(page.locator("#counter-badge")).to_have_text("已完成 2 件 / 共 3 件")

        checkboxes.nth(2).click()
        expect(page.locator("#counter-badge")).to_have_text("已完成 3 件 / 共 3 件")
        expect(page.locator("#counter-badge")).to_have_class("counter-badge all-completed")

        # Uncheck second item
        checkboxes.nth(1).click()
        expect(page.locator("#counter-badge")).to_have_text("已完成 2 件 / 共 3 件")
        expect(page.locator("#counter-badge")).not_to_have_class("counter-badge all-completed")
        print("  ✓ Toggle complete/incomplete & counter accurate, all-completed style verified")

        # 1.6 Delete item (REQ-003)
        delete_btns = page.locator(".btn-delete")
        delete_btns.nth(1).click() # Delete second item
        expect(page.locator(".todo-item")).to_have_count(2)
        expect(page.locator("#counter-badge")).to_have_text("已完成 2 件 / 共 2 件")
        print("  ✓ Delete item verified")
        context.close()

        # -------------------------------------------------------------
        # Test 2: Persistence & Storage Error Recovery (REQ-004, M-1)
        # -------------------------------------------------------------
        print("\n--- Test 2: Persistence & Storage Error Recovery (REQ-004, M-1) ---")
        context2 = browser.new_context(viewport={"width": 1280, "height": 900})
        page2 = context2.new_page()
        page2.goto(FILE_URL)

        # Clear and add known items
        page2.evaluate("() => localStorage.clear()")
        page2.reload()
        expect(page2.locator(".todo-item")).to_have_count(0)

        page2.fill("#todo-input", "保存测试项 1")
        page2.click("#add-btn")
        page2.fill("#todo-input", "保存测试项 2")
        page2.click("#add-btn")
        page2.locator(".todo-checkbox").nth(0).click()

        # Check storage content
        stored_raw = page2.evaluate("() => localStorage.getItem('wfweb001.todo.v1')")
        assert stored_raw is not None, "localStorage wfweb001.todo.v1 should exist"
        stored_data = json.loads(stored_raw)
        assert len(stored_data) == 2
        assert stored_data[0]["completed"] is True
        assert stored_data[1]["completed"] is False

        # Reload page and verify restored state
        page2.reload()
        expect(page2.locator(".todo-item")).to_have_count(2)
        expect(page2.locator(".todo-item").nth(0)).to_have_class("todo-item completed")
        expect(page2.locator(".item-text").nth(0)).to_have_text("保存测试项 1")
        expect(page2.locator(".item-text").nth(1)).to_have_text("保存测试项 2")
        expect(page2.locator("#counter-badge")).to_have_text("已完成 1 件 / 共 2 件")
        print("  ✓ Refresh persistence verified with exact text & status")

        # Test corrupt JSON recovery
        page2.evaluate("() => localStorage.setItem('wfweb001.todo.v1', '{corrupt-json-data')")
        page2.reload()
        expect(page2.locator("#status-banner")).to_be_visible()
        expect(page2.locator("#status-banner")).to_contain_text("读取本地存储失败")
        expect(page2.locator(".todo-item")).to_have_count(0)
        expect(page2.locator("#empty-state")).to_be_visible()
        print("  ✓ Corrupt localStorage gracefully caught and recovered to empty state")
        context2.close()

        # -------------------------------------------------------------
        # Test 3: Responsive & 375px mobile viewport checks (REQ-005, M-2)
        # -------------------------------------------------------------
        print("\n--- Test 3: Responsive & 375px mobile viewport checks (REQ-005, M-2) ---")
        mobile_ctx = browser.new_context(viewport={"width": 375, "height": 812})
        page_m = mobile_ctx.new_page()
        page_m.goto(FILE_URL)

        # Clear storage
        page_m.evaluate("() => localStorage.clear()")
        page_m.reload()

        # Add items including long continuous unbroken string
        page_m.fill("#todo-input", "短任务一：快速检查")
        page_m.click("#add-btn")

        long_string = "超长连续英文字符无断点测试_Supercalifragilisticexpialidocious_1234567890_ABCDEFGHIJKLMN"
        page_m.fill("#todo-input", long_string)
        page_m.click("#add-btn")

        page_m.fill("#todo-input", "短任务三：确认收尾")
        page_m.click("#add-btn")

        # Check overflow metrics
        metrics = page_m.evaluate("""() => {
            return {
                innerWidth: window.innerWidth,
                visualViewportWidth: window.visualViewport ? window.visualViewport.width : window.innerWidth,
                scrollWidth: document.documentElement.scrollWidth,
                bodyScrollWidth: document.body.scrollWidth,
                containerScrollWidth: document.querySelector('.container').scrollWidth
            };
        }""")
        print(f"  Mobile 375px metrics: {metrics}")
        assert metrics["scrollWidth"] <= 375, f"Horizontal overflow detected! scrollWidth: {metrics['scrollWidth']}"
        assert metrics["bodyScrollWidth"] <= 375, f"Body overflow detected! bodyScrollWidth: {metrics['bodyScrollWidth']}"

        # Check touch target size for delete buttons (>= 44px)
        btn_box = page_m.locator(".btn-delete").nth(0).bounding_box()
        assert btn_box["height"] >= 44, f"Delete button height {btn_box['height']} is less than 44px"
        assert btn_box["width"] >= 44, f"Delete button width {btn_box['width']} is less than 44px"
        print(f"  ✓ Touch target size verified: {btn_box['width']}x{btn_box['height']} >= 44px")

        # Check alignment: checkbox top vs text top (flex-start baseline alignment)
        cb_box = page_m.locator(".todo-checkbox").nth(1).bounding_box()
        text_box = page_m.locator(".item-text").nth(1).bounding_box()
        diff = abs(cb_box["y"] - text_box["y"])
        print(f"  Checkbox y: {cb_box['y']}, Text y: {text_box['y']}, diff: {diff}")
        assert diff <= 8, f"Checkbox and first line text vertical alignment gap too large: {diff}"
        print("  ✓ Checkbox aligned with first line of multiline text")
        mobile_ctx.close()

        # -------------------------------------------------------------
        # Test 4: Keyboard navigation & Focus management (REQ-006, M-3, M-4)
        # -------------------------------------------------------------
        print("\n--- Test 4: Keyboard navigation & Focus management (REQ-006, M-3, M-4) ---")
        kb_ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page_kb = kb_ctx.new_page()
        page_kb.goto(FILE_URL)
        page_kb.evaluate("() => localStorage.clear()")
        page_kb.reload()

        # Add 3 items
        for i in range(1, 4):
            page_kb.fill("#todo-input", f"待办任务 {i}")
            page_kb.click("#add-btn")

        # 4.1 Tab to first checkbox and toggle with Space
        page_kb.locator("#todo-input").focus()
        page_kb.keyboard.press("Tab") # to Add button
        expect(page_kb.locator("#add-btn")).to_be_focused()

        page_kb.keyboard.press("Tab") # to first checkbox
        expect(page_kb.locator(".todo-checkbox").nth(0)).to_be_focused()

        # Press Space to toggle
        page_kb.keyboard.press("Space")
        expect(page_kb.locator(".todo-item").nth(0)).to_have_class("todo-item completed")
        # Verify focus stays on the checkbox after Space toggle!
        expect(page_kb.locator(".todo-checkbox").nth(0)).to_be_focused()
        print("  ✓ Space toggles checkbox and preserves focus on checkbox")

        # 4.2 Delete middle item (Item 2) and verify focus moves to next delete button (Item 3)
        page_kb.locator(".btn-delete").nth(1).focus()
        expect(page_kb.locator(".btn-delete").nth(1)).to_be_focused()
        page_kb.keyboard.press("Enter")

        # Wait for frame & check focus: should be on delete button of the new 2nd item (originally item 3)
        page_kb.wait_for_timeout(100)
        expect(page_kb.locator(".todo-item")).to_have_count(2)
        active_el = page_kb.evaluate("""() => {
            const el = document.activeElement;
            return {
                tagName: el.tagName,
                className: el.className,
                ariaLabel: el.getAttribute('aria-label')
            };
        }""")
        print(f"  Active element after deleting middle item: {active_el}")
        assert "btn-delete" in active_el["className"]
        assert "待办任务 3" in active_el["ariaLabel"]
        print("  ✓ Focus transferred to next item's delete button")

        # 4.3 Delete last item (now Item 2) and verify focus falls back to previous delete button (Item 1)
        page_kb.keyboard.press("Enter") # deletes item 3
        page_kb.wait_for_timeout(100)
        expect(page_kb.locator(".todo-item")).to_have_count(1)
        active_el2 = page_kb.evaluate("""() => {
            const el = document.activeElement;
            return {
                tagName: el.tagName,
                className: el.className,
                ariaLabel: el.getAttribute('aria-label')
            };
        }""")
        print(f"  Active element after deleting last item: {active_el2}")
        assert "btn-delete" in active_el2["className"]
        assert "待办任务 1" in active_el2["ariaLabel"]
        print("  ✓ Focus transferred to previous item's delete button when deleting last")

        # 4.4 Delete only remaining item and verify focus returns to input
        page_kb.keyboard.press("Enter") # deletes item 1
        page_kb.wait_for_timeout(100)
        expect(page_kb.locator(".todo-item")).to_have_count(0)
        expect(page_kb.locator("#todo-input")).to_be_focused()
        print("  ✓ Focus transferred back to todo-input when list becomes empty")

        kb_ctx.close()

        # -------------------------------------------------------------
        # Test 5: Regression suite for F-1 & F-2 (Error Banner Retention & Blank Text Filtering)
        # -------------------------------------------------------------
        print("\n--- Test 5: Regression suite for F-1 & F-2 ---")
        reg_ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page_reg = reg_ctx.new_page()
        page_reg.goto(FILE_URL)

        # 5.1 F-1 on Add: Storage setItem throws error
        page_reg.evaluate("() => localStorage.clear()")
        page_reg.reload()
        page_reg.evaluate("""() => {
            window.__origSetItem = Storage.prototype.setItem;
            Storage.prototype.setItem = function(k, v) {
                throw new DOMException('QuotaExceededError');
            };
        }""")
        page_reg.fill("#todo-input", "写入异常测试项（添加）")
        page_reg.click("#add-btn")
        expect(page_reg.locator(".todo-item")).to_have_count(1)
        expect(page_reg.locator("#status-banner")).to_be_visible()
        expect(page_reg.locator("#status-banner")).to_have_class("status-banner visible error")
        expect(page_reg.locator("#status-banner")).to_contain_text("本地存储写入失败")
        print("  ✓ F-1: Error banner visible and preserved after storage write failure on add")

        # Typing in input should clear the banner
        page_reg.fill("#todo-input", "再次输入文字")
        expect(page_reg.locator("#status-banner")).to_be_hidden()
        print("  ✓ Status banner clears when user starts new input")

        # 5.2 F-1 on Delete: Storage setItem throws error
        # Restore storage first and add an item normally
        page_reg.evaluate("() => { Storage.prototype.setItem = window.__origSetItem; localStorage.clear(); }")
        page_reg.reload()
        page_reg.fill("#todo-input", "待删除测试项")
        page_reg.click("#add-btn")
        expect(page_reg.locator(".todo-item")).to_have_count(1)
        expect(page_reg.locator("#status-banner")).to_be_hidden()

        # Break setItem and delete the item
        page_reg.evaluate("""() => {
            window.__origSetItem = Storage.prototype.setItem;
            Storage.prototype.setItem = function() { throw new DOMException('QuotaExceededError'); };
        }""")
        page_reg.locator(".btn-delete").nth(0).click()
        expect(page_reg.locator(".todo-item")).to_have_count(0)
        expect(page_reg.locator("#status-banner")).to_be_visible()
        expect(page_reg.locator("#status-banner")).to_have_class("status-banner visible error")
        expect(page_reg.locator("#status-banner")).to_contain_text("本地存储写入失败")
        print("  ✓ F-1: Error banner visible and preserved after storage write failure on delete")

        # Restore storage and verify next successful write clears previous error
        page_reg.evaluate("() => { Storage.prototype.setItem = window.__origSetItem; }")
        page_reg.fill("#todo-input", "恢复正常后添加的事项")
        page_reg.click("#add-btn")
        expect(page_reg.locator(".todo-item")).to_have_count(1)
        expect(page_reg.locator("#status-banner")).to_be_hidden()
        print("  ✓ F-1: Successful storage write clears old error banner without residue")

        # 5.3 F-1 on Toggle: Storage setItem throws error
        page_reg.evaluate("""() => {
            window.__origSetItem = Storage.prototype.setItem;
            Storage.prototype.setItem = function() { throw new DOMException('QuotaExceededError'); };
        }""")
        page_reg.locator(".todo-checkbox").nth(0).click()
        expect(page_reg.locator(".todo-item").nth(0)).to_have_class("todo-item completed")
        expect(page_reg.locator("#status-banner")).to_be_visible()
        expect(page_reg.locator("#status-banner")).to_have_class("status-banner visible error")
        expect(page_reg.locator("#status-banner")).to_contain_text("本地存储写入失败")

        # Restore and toggle again (success)
        page_reg.evaluate("() => { Storage.prototype.setItem = window.__origSetItem; }")
        page_reg.locator(".todo-checkbox").nth(0).click()
        expect(page_reg.locator(".todo-item").nth(0)).not_to_have_class("todo-item completed")
        expect(page_reg.locator("#status-banner")).to_be_hidden()
        print("  ✓ F-1: Toggle error retained on failure, cleared on successful save")

        # 5.4 F-2: Blank text malformed storage items discarded and do not occupy quota
        malformed_data = [
            {"id": "b1", "text": "   ", "completed": False},
            {"id": "b2", "text": "\t\u3000 ", "completed": False},
            {"id": "valid1", "text": "有效存储项", "completed": False}
        ]
        page_reg.evaluate("(val) => localStorage.setItem('wfweb001.todo.v1', JSON.stringify(val))", malformed_data)
        page_reg.reload()

        # Should only render the valid item
        expect(page_reg.locator(".todo-item")).to_have_count(1)
        expect(page_reg.locator(".item-text").nth(0)).to_have_text("有效存储项")
        expect(page_reg.locator("#counter-badge")).to_have_text("已完成 0 件 / 共 1 件")

        # Adding 2 more valid items should succeed and reach 3 items total
        page_reg.fill("#todo-input", "后续任务二")
        page_reg.click("#add-btn")
        page_reg.fill("#todo-input", "后续任务三")
        page_reg.click("#add-btn")
        expect(page_reg.locator(".todo-item")).to_have_count(3)
        expect(page_reg.locator("#counter-badge")).to_have_text("已完成 0 件 / 共 3 件")

        # Trying to add 4th item should be rejected (quota 3 verified)
        page_reg.fill("#todo-input", "第四个任务应被拒绝")
        page_reg.click("#add-btn")
        expect(page_reg.locator("#status-banner")).to_be_visible()
        expect(page_reg.locator("#status-banner")).to_contain_text("今日最多保留 3 件事")
        expect(page_reg.locator("#status-banner")).to_contain_text("请先删除一件不需要的事项")
        expect(page_reg.locator(".todo-item")).to_have_count(3)
        print("  ✓ F-2: Malformed blank items discarded on load, quota not occupied, capacity correctly 3")

        # 5.5 Maintainer check / F-3: Completed items still count towards 3-item limit; rejection guides deletion
        page_reg.evaluate("() => localStorage.clear()")
        page_reg.reload()
        for i in range(1, 4):
            page_reg.fill("#todo-input", f"事项 {i}")
            page_reg.click("#add-btn")
        expect(page_reg.locator(".todo-item")).to_have_count(3)
        expect(page_reg.locator("#counter-badge")).to_have_text("已完成 0 件 / 共 3 件")

        # Complete item 1
        page_reg.locator(".todo-checkbox").nth(0).click()
        expect(page_reg.locator(".todo-item").nth(0)).to_have_class("todo-item completed")
        expect(page_reg.locator("#counter-badge")).to_have_text("已完成 1 件 / 共 3 件")

        # Attempt to add 4th item via click
        page_reg.fill("#todo-input", "第四件事尝试添加")
        page_reg.click("#add-btn")

        # Verify 4th item is rejected: count remains 3, completed remains 1
        expect(page_reg.locator(".todo-item")).to_have_count(3)
        expect(page_reg.locator("#counter-badge")).to_have_text("已完成 1 件 / 共 3 件")
        expect(page_reg.locator("#status-banner")).to_be_visible()
        expect(page_reg.locator("#status-banner")).to_contain_text("今日最多保留 3 件事")
        expect(page_reg.locator("#status-banner")).to_contain_text("包含已完成")
        expect(page_reg.locator("#status-banner")).to_contain_text("请先删除一件不需要的事项")
        reg_banner = page_reg.locator("#status-banner").inner_text()
        assert "先完成或删除" not in reg_banner, f"Banner contains misleading '先完成或删除': {reg_banner}"
        assert "先完成" not in reg_banner, f"Banner contains misleading '先完成': {reg_banner}"

        # Input value and focus retained
        expect(page_reg.locator("#todo-input")).to_have_value("第四件事尝试添加")
        active_id = page_reg.evaluate("() => document.activeElement.id")
        assert active_id == "todo-input", f"Expected focus on todo-input, got {active_id}"

        # Attempt to add via Enter
        page_reg.keyboard.press("Enter")
        expect(page_reg.locator(".todo-item")).to_have_count(3)
        expect(page_reg.locator("#counter-badge")).to_have_text("已完成 1 件 / 共 3 件")
        expect(page_reg.locator("#status-banner")).to_be_visible()
        expect(page_reg.locator("#status-banner")).to_contain_text("包含已完成")
        print("  ✓ F-3: Completed items still count towards 3-item limit; rejection guides deletion, not completion")

        reg_ctx.close()
        browser.close()

    print("\n==========================================")
    print("ALL TESTS PASSED SUCCESSFULLY! (100% pass)")
    print("==========================================")

if __name__ == "__main__":
    run_tests()
