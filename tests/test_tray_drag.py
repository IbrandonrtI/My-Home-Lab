"""Quick launch icons: a row of the edit list can be dragged to a new place. Needs Python Playwright and a Chromium browser, and is skipped without them."""
import json
import os
import shutil
import tempfile
import unittest

import helpers

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

PAGE = ('<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="custom.css"></head><body><div id="inner_wrapper"><div id="widgets-wrap"></div>'
        '<div id="tabs"><ul id="myTab"><li><button id="home-tab" aria-selected="true">Home</button></li></ul></div><div id="layout-groups"></div></div>'
        '<script src="custom.js"></script></body></html>')


@unittest.skipUnless(sync_playwright, "Python Playwright is not installed")
class TrayDragTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="tray-")
        for n in ("custom.css", "custom.js"):
            shutil.copy(os.path.join(helpers.ROOT, "homepage-config", n), cls.dir)
        with open(os.path.join(cls.dir, "page.html"), "w", encoding="utf-8") as f:
            f.write(PAGE)
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception as e:
            cls.pw.stop()
            shutil.rmtree(cls.dir, True)
            raise unittest.SkipTest("no Chromium browser: %s" % e) from e

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        shutil.rmtree(cls.dir, True)

    def open_menu(self):
        page = self.browser.new_page(viewport={"width": 1300, "height": 700})
        self.addCleanup(page.close)
        items = [{"n": n, "h": "https://%s.example.com/" % n.lower(), "i": None} for n in ("Alpha", "Bravo", "Charlie", "Delta")]
        page.add_init_script("localStorage.setItem('hl-tray', %s)" % json.dumps(json.dumps({"items": items})))
        page.goto("file://" + os.path.join(self.dir, "page.html"))
        page.wait_for_selector("#hl-tray-menu > button", state="attached")
        page.click("#hl-tray-menu > button")
        page.wait_for_selector("#hl-tray-menu .hl-trow")
        return page

    def names(self, page):
        return page.eval_on_selector_all("#hl-tray-menu .hl-trow .hl-tname", "e => e.map(x => x.textContent)")

    def saved(self, page):
        return [i["n"] for i in json.loads(page.evaluate("localStorage.getItem('hl-tray')"))["items"]]

    def drag(self, page, row, x_offset, to_row_float):
        rows = page.query_selector_all("#hl-tray-menu .hl-trow")
        box = rows[row].bounding_box()
        x, y = box["x"] + x_offset, box["y"] + box["height"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x, y + box["height"] * to_row_float / 2, steps=4)
        page.mouse.move(x, y + box["height"] * to_row_float, steps=4)
        page.mouse.up()

    def test_dragging_the_grip_moves_the_icon_and_saves_it(self):
        page = self.open_menu()
        self.drag(page, 0, 12, 2)
        self.assertEqual(self.names(page), ["Bravo", "Charlie", "Alpha", "Delta"])
        self.assertEqual(self.saved(page), ["Bravo", "Charlie", "Alpha", "Delta"])

    def test_dragging_up_works_from_the_name(self):
        page = self.open_menu()
        self.drag(page, 3, 110, -3)
        self.assertEqual(self.names(page), ["Delta", "Alpha", "Bravo", "Charlie"])

    def test_a_tiny_movement_changes_nothing(self):
        page = self.open_menu()
        self.drag(page, 1, 110, 0.05)
        self.assertEqual(self.names(page), ["Alpha", "Bravo", "Charlie", "Delta"])

    def test_the_arrow_keys_on_the_grip_move_the_icon_and_keep_the_focus(self):
        page = self.open_menu()
        page.focus("#hl-tray-menu .hl-trow:nth-child(1) .hl-tgrip")
        page.keyboard.press("ArrowDown")
        self.assertEqual(self.names(page), ["Bravo", "Alpha", "Charlie", "Delta"])
        self.assertEqual(self.saved(page), ["Bravo", "Alpha", "Charlie", "Delta"])
        self.assertTrue(page.evaluate("document.activeElement.classList.contains('hl-tgrip')"))

    def test_there_are_no_move_buttons_in_the_rows(self):
        page = self.open_menu()
        self.assertEqual(page.locator("#hl-tray-menu .hl-trow .hl-tbtn").count(), 4)  # only the remove buttons

if __name__ == "__main__":
    unittest.main()
