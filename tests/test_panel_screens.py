"""The Customize panel's screens, in a real browser against the real panel server: Upload and Backups have tabs of their own, the Look screen shows one
section at a time under a menu that stays in view, and cards say whether a change needs Save. Needs Python Playwright and a Chromium browser, and is
skipped without them."""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

import helpers

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

PASSWORD = "test-password-123"


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@unittest.skipUnless(sync_playwright, "Python Playwright is not installed")
class PanelScreens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="hlp-screens-")
        hp = os.path.join(cls.dir, "homepage-config")
        shutil.copytree(os.path.join(helpers.ROOT, "homepage-config"), hp, ignore=shutil.ignore_patterns("images", "__pycache__"))
        cls.port = free_port()
        env = dict(os.environ, HLP_HOME=cls.dir, HOMELAB_HOMEPAGE_DIR=hp, HLP_STATE=os.path.join(cls.dir, "state"), HLP_UI=os.path.join(helpers.ROOT, "panel", "ui"),
                   HLP_PORT=str(cls.port), HLP_NO_DOCKER="1", HLP_COOKIE_PLAIN="1", HLP_SHIPPED=os.devnull,
                   HLP_DRIVES=os.path.join(helpers.ROOT, "scripts", "drives"))
        os.makedirs(env["HLP_STATE"], exist_ok=True)
        script = os.path.join(helpers.ROOT, "scripts", "homelab-panel")
        subprocess.run([sys.executable, script, "set-password", "--stdin"], input=PASSWORD + "\n", text=True, env=env, check=True, capture_output=True)
        cls.server = subprocess.Popen([sys.executable, script, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/api/session" % cls.port, timeout=1).read()
                break
            except OSError:
                time.sleep(0.2)
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception as e:
            cls.tearDownClass()
            raise unittest.SkipTest("no Chromium browser: %s" % e) from e

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "browser", None):
            cls.browser.close()
        if getattr(cls, "pw", None):
            cls.pw.stop()
        cls.server.terminate()
        cls.server.wait(10)
        shutil.rmtree(cls.dir, True)

    def open(self, view, width=1300):
        page = self.browser.new_context(viewport={"width": width, "height": 800}).new_page()
        self.addCleanup(page.context.close)
        self.errors = []
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        base = "http://127.0.0.1:%d/" % self.port
        page.goto(base + "#" + view)
        page.fill("input[type=password]", PASSWORD)
        page.keyboard.press("Enter")
        page.wait_for_selector("nav.tabs", timeout=10000)
        page.goto(base + "#" + view)
        page.reload()
        page.wait_for_selector("nav.tabs")
        return page

    def tabs(self, page):
        return page.locator("nav.tabs button").all_inner_texts()

    def test_upload_and_backups_have_their_own_tabs(self):
        page = self.open("drives")
        self.assertEqual(self.tabs(page), ["Look", "Layout", "Cards", "Drives", "Upload", "Backups", "Updates"])
        page.wait_for_timeout(800)
        heads = page.locator("h2").all_inner_texts()
        self.assertFalse([t for t in heads if t.startswith("Upload") or t.startswith("Backups")], "the Drives tab no longer holds them: %s" % heads)
        page.get_by_role("tab", name="Upload").click()
        page.wait_for_selector("h2:has-text('Upload')")
        page.get_by_role("tab", name="Backups").click()
        page.wait_for_selector("h2:has-text('Backups')")
        self.assertEqual(page.evaluate("location.hash"), "#backups")
        self.assertEqual(self.errors, [])

    def test_screens_that_act_at_once_have_no_save_or_undo(self):
        page = self.open("upload")
        names = page.locator("header.top button").all_inner_texts()
        self.assertNotIn("Save", names)
        self.assertNotIn("Undo", names)
        page.get_by_role("tab", name="Look").click()
        names = page.locator("header.top button").all_inner_texts()
        self.assertIn("Save", names)
        self.assertIn("Undo", names)

    def test_look_shows_one_section_at_a_time(self):
        page = self.open("look")
        menu = page.locator("nav.lookmenu button").all_inner_texts()
        self.assertEqual(menu, ["Themes", "Colors", "Shape", "Background", "Motion and Icons", "Names and Place", "Card Colors"])
        visible = lambda: page.locator("section.lookpane:visible").evaluate_all("els => els.map(e => e.id)")
        self.assertEqual(visible(), ["look-themes"])
        page.get_by_role("button", name="Colors", exact=True).click()
        self.assertEqual(visible(), ["look-colors"])
        page.get_by_role("button", name="Names and Place").click()
        self.assertEqual(visible(), ["look-names"])
        self.assertTrue(page.locator("#look-names >> text=Time Zone and City").count())
        page.reload()
        page.wait_for_selector("nav.lookmenu")
        self.assertEqual(visible(), ["look-names"], "the section is remembered")

    def test_a_changed_slider_survives_switching_sections(self):
        page = self.open("look")
        page.get_by_role("button", name="Shape", exact=True).click()
        page.locator("#look-shape input[type=range]").first.fill("5")
        self.assertTrue(page.locator("header.top .state.dirty").count(), "the change is waiting for Save")
        page.get_by_role("button", name="Themes", exact=True).click()
        page.get_by_role("button", name="Shape", exact=True).click()
        self.assertEqual(page.locator("#look-shape input[type=range]").first.input_value(), "5")

    def test_the_menu_and_preview_stay_in_view_while_scrolling(self):
        page = self.open("look")
        page.get_by_role("button", name="Colors", exact=True).click()
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(300)
        for sel in ("nav.lookmenu", "#mock"):
            box = page.locator(sel).bounding_box()
            self.assertIsNotNone(box)
            self.assertGreaterEqual(box["y"], 0, sel)
            self.assertLess(box["y"], 200, sel)

    def test_on_a_phone_the_menu_scrolls_with_the_page(self):
        page = self.open("look", width=390)
        self.assertEqual(page.locator(".stickytop .substrip").count(), 0)
        self.assertEqual(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), True)

    def test_cards_say_whether_a_change_needs_save(self):
        page = self.open("look")
        head = lambda name: page.locator("h2:has-text('%s') .stag" % name).first.inner_text()
        self.assertEqual(head("Themes"), "Needs Save")
        self.assertEqual(head("Day and Night"), "Saves Now")
        page.get_by_role("button", name="Names and Place").click()
        self.assertEqual(page.locator("summary:has-text('Time Zone and City') .stag").inner_text(), "Saves Now")
        self.assertEqual(page.locator("summary:has-text('Names and Logo') .stag").inner_text(), "Needs Save")

    def test_top_of_the_page_can_show_the_name_the_logo_both_or_neither(self):
        page = self.open("look")
        page.get_by_role("button", name="Names and Place").click()
        page.locator("summary:has-text('Names and Logo')").click()
        name = page.get_by_role("checkbox", name="Show the name at the top of the page")
        logo = page.get_by_role("checkbox", name="Show the logo at the top of the page")
        self.assertTrue(name.is_checked())
        self.assertTrue(logo.is_disabled(), "with no logo chosen there is nothing to show")
        page.locator("summary:has-text('Choose a Logo')").click()
        page.locator(".logo-tile").first.click()
        page.wait_for_timeout(400)
        self.assertTrue(name.is_checked() and logo.is_checked())
        page.get_by_role("textbox", name="Name at the top of the page").fill("Brandon  Lab")
        self.assertEqual(page.evaluate("lookW.helloName"), "Brandon Lab")
        name.uncheck()
        self.assertEqual(page.evaluate("lookW.hello"), False)
        self.assertTrue(page.get_by_role("textbox", name="Name at the top of the page").is_disabled())
        self.assertFalse(page.evaluate("!!lookW.logo.off"), "only the logo is left")
        logo.uncheck()
        self.assertTrue(page.evaluate("lookW.logo.off"))
        self.assertTrue(page.evaluate("!!lookW.logo.src"), "the picture is kept")
        name.check()
        logo.check()
        self.assertTrue(page.evaluate("lookW.hello !== false && !lookW.logo.off"))
        self.assertEqual(page.locator(".logo-switch").count(), 0)
        self.assertEqual(self.errors, [])

    def test_no_built_in_label_is_left(self):
        page = self.open("look")
        page.get_by_role("button", name="Names and Place").click()
        page.locator("summary:has-text('Names and Logo')").click()
        page.locator("summary:has-text('Choose a Logo')").click()
        text = page.locator("#look-names").inner_text()
        self.assertNotIn("built-in", text.lower())
        self.assertIn("Ready-Made Logos", text)


if __name__ == "__main__":
    unittest.main()
