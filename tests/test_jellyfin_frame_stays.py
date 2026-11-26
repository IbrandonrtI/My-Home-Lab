"""The Jellyfin library shown in its dashboard card keeps running when the dashboard switches tabs. Homepage removes the card when another tab is opened and
builds it again on the way back, so the frame lives outside the card and is only laid over a slot in it. Needs Python Playwright and a Chromium browser, and
is skipped without them."""
import os
import shutil
import tempfile
import unittest

import helpers

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

CARD = ('<li id="jellyfin-card" class="service"><div class="service-card"><div class="service-title"><a href="http://jf.test/">Jellyfin</a></div>'
        '<div class="service-block"><div class="service-block-value">19</div><div class="service-block-label">Movies</div></div></div></li>')
PAGE = ('<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="custom.css"></head><body><div id="inner_wrapper">'
        '<div id="tabs"><ul id="myTab"><li><button id="home-tab" aria-selected="true">Home</button></li></ul></div>'
        '<div id="layout-groups"><div class="services-group"><ul class="services-list">' + CARD + '</ul></div></div></div>'
        '<script src="custom.js"></script></body></html>')
FRAME = "<!doctype html><title>jellyfin</title><body style='background:#123'>jellyfin</body>"


@unittest.skipUnless(sync_playwright, "Python Playwright is not installed")
class JellyfinFrameStays(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="jf-")
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

    def open(self):
        page = self.browser.new_page(viewport={"width": 1400, "height": 900})
        self.addCleanup(page.close)
        loads = []

        def serve(route):
            loads.append(route.request.url)
            route.fulfill(status=200, content_type="text/html", body=FRAME)

        page.route("http://jf.test/**", serve)
        page.goto("file://" + os.path.join(self.dir, "page.html"))
        page.wait_for_selector("#hl-jf-frame iframe", state="attached")
        page.wait_for_timeout(900)
        return page, loads

    def test_the_library_is_not_loaded_again_when_the_tab_changes(self):
        page, loads = self.open()
        self.assertEqual(len(loads), 1)
        page.evaluate("window.__frame = document.querySelector('#hl-jf-frame iframe'); window.__card = document.getElementById('jellyfin-card')")
        slot = page.eval_on_selector("#hl-jf-slot", "e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
        frame = page.eval_on_selector("#hl-jf-frame", "e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
        for a, b in zip(slot, frame):
            self.assertAlmostEqual(a, b, delta=2, msg="the frame lies over the slot in the card")
        self.assertGreater(slot[3], 300)

        # another tab: Homepage takes the card out of the page
        page.evaluate("window.__card.remove()")
        page.wait_for_timeout(900)
        self.assertTrue(page.evaluate("document.getElementById('hl-jf-frame').classList.contains('hl-away')"), "the frame is moved out of sight")
        self.assertTrue(page.evaluate("document.querySelector('#hl-jf-frame iframe') === window.__frame"), "the same frame is still in the page")

        # and back to the home tab: a new card
        page.evaluate("document.querySelector('.services-list').appendChild(window.__card.cloneNode(true))")
        page.wait_for_timeout(1200)
        self.assertFalse(page.evaluate("document.getElementById('hl-jf-frame').classList.contains('hl-away')"), "the frame is shown again")
        self.assertTrue(page.evaluate("document.querySelector('#hl-jf-frame iframe') === window.__frame"), "it is the same frame, not a new one")
        slot = page.eval_on_selector("#hl-jf-slot", "e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
        frame = page.eval_on_selector("#hl-jf-frame", "e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
        for a, b in zip(slot, frame):
            self.assertAlmostEqual(a, b, delta=2)
        self.assertEqual(len(loads), 1, "Jellyfin was loaded once and not again")

    def test_closing_the_library_ends_the_frame(self):
        page, loads = self.open()
        page.click("#jellyfin-card .hl-jf-toggle")
        page.wait_for_timeout(700)
        self.assertEqual(page.locator("#hl-jf-frame").count(), 0)
        self.assertFalse(page.evaluate("document.documentElement.classList.contains('hl-jf-side')"))


    def test_the_frame_goes_the_moment_the_card_does(self):
        """Not on the next half-second check: with that check switched off, the page itself must hide the frame when the card is taken out."""
        page = self.browser.new_page(viewport={"width": 1400, "height": 900})
        self.addCleanup(page.close)
        page.add_init_script("window.setInterval = function () { return 0; };")
        page.route("http://jf.test/**", lambda route: route.fulfill(status=200, content_type="text/html", body=FRAME))
        page.goto("file://" + os.path.join(self.dir, "page.html"))
        page.wait_for_selector("#hl-jf-frame iframe", state="attached")
        page.wait_for_timeout(400)
        page.evaluate("document.getElementById('jellyfin-card').remove()")
        page.wait_for_timeout(150)
        self.assertTrue(page.evaluate("document.getElementById('hl-jf-frame').classList.contains('hl-away')"))

if __name__ == "__main__":
    unittest.main()
