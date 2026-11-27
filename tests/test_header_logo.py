"""The logo and the name at the top left of the page: both together, only one, or neither, at every width. The logo used to sit inside the tile of gauges, which the
gauge strip hides, so it vanished. Needs Python Playwright and a Chromium browser, and is skipped without them."""
import os
import shutil
import tempfile
import unittest

import helpers

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

DOT = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


def page(hello='"Brandon"', logo=True):
    style = "--hl-hello: %s;" % hello
    if logo:
        style += ' --hl-logo-src: "%s";' % DOT
    res = ('<div class="widget-container"><div style="display:flex">'
           '<div class="information-widget-resource"><svg width="16" height="16"></svg><div>CPU 12%</div></div>'
           '<div class="information-widget-resource"><svg width="16" height="16"></svg><div>3.1 GB free</div></div>'
           '<div class="information-widget-resource"><svg width="16" height="16"></svg><div>41 °C</div></div>'
           '<div class="information-widget-resource"><svg width="16" height="16"></svg><div>Uptime 3d</div></div></div><div>HomeLab</div></div>')
    return ('<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="custom.css"></head><body><div id="inner_wrapper" style=\'' + style + '\'>'
            '<div id="information-widgets"><div id="widgets-wrap">' + res + '<div id="information-widgets-right"><div class="information-widget-datetime">Mon 12:00</div></div></div></div>'
            '<div id="tabs"><ul id="myTab"><li><button id="home-tab" aria-selected="true">Home</button></li></ul></div><div id="layout-groups"></div></div>'
            '<script src="custom.js"></script></body></html>')


@unittest.skipUnless(sync_playwright, "Python Playwright is not installed")
class HeaderLogoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="hlogo-")
        for n in ("custom.css", "custom.js"):
            shutil.copy(os.path.join(helpers.ROOT, "homepage-config", n), cls.dir)
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

    def open(self, html, width):
        with open(os.path.join(self.dir, "p.html"), "w", encoding="utf-8") as f:
            f.write(html)
        ctx = self.browser.new_context(viewport={"width": width, "height": 900})
        self.addCleanup(ctx.close)
        p = ctx.new_page()
        p.goto("file://" + os.path.join(self.dir, "p.html"))
        p.wait_for_timeout(700)
        return p

    def box(self, p, sel):
        return p.evaluate("""s => { const e = document.querySelector(s); if (!e || e.hidden) return null; const r = e.getBoundingClientRect(), c = getComputedStyle(e);
            return r.width > 0 && r.height > 0 && c.display !== 'none' && c.visibility !== 'hidden' ? [r.left, r.top, r.right, r.bottom] : null; }""", sel)

    def test_logo_and_name_show_side_by_side_at_every_width(self):
        for width in (1700, 1300, 900):
            with self.subTest(width=width):
                p = self.open(page(), width)
                logo, name = self.box(p, "#hl-logo img"), self.box(p, "#hl-hello")
                self.assertTrue(logo, "the logo is not visible")
                self.assertTrue(name, "the name is not visible")
                self.assertLessEqual(logo[2], width)
                self.assertGreaterEqual(logo[0], 0)
                self.assertTrue(logo[2] <= name[0] + 1 or logo[3] <= name[1] + 1, "the logo and the name overlap: %s %s" % (logo, name))

    def test_a_thin_line_separates_the_logo_from_what_follows(self):
        """On a wide screen the logo is followed by a separator line with room on both sides; below 1181 pixels the logo is the top of the gauge panel and the line runs under it instead."""
        line = "(() => { const c = getComputedStyle(document.getElementById('hl-logo'), '::after'); return [c.content, c.display, c.width]; })()"
        for hello in ('"Brandon"', '"off"'):
            for width in (1700, 1300):
                with self.subTest(width=width, hello=hello):
                    p = self.open(page(hello=hello), width)
                    content, display, w = p.evaluate(line)
                    self.assertEqual((content, display, w), ('""', "block", "1px"))
                    logo = self.box(p, "#hl-logo")
                    sel = "#hl-hello" if hello != '"off"' else "#hl-stats .hl-g"
                    nxt = p.evaluate("""s => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return [r.left + parseFloat(getComputedStyle(e).paddingLeft), r.top, r.bottom]; }""", sel)
                    if nxt and nxt[1] < logo[3]:
                        self.assertGreaterEqual(nxt[0] - logo[2], 10, "too little room after the line")
                    img = self.box(p, "#hl-logo img")
                    self.assertGreaterEqual(logo[2] - img[2], 12, "too little room before the line")
        p = self.open(page(), 900)
        under = p.evaluate("(() => { const c = getComputedStyle(document.getElementById('hl-logo'), '::after'); return [c.display, c.height]; })()")
        self.assertEqual(under, ["block", "1px"])
        self.assertNotEqual(p.evaluate(line)[2], "1px", "the line runs along the bottom, not down the side")

    def test_phone_shows_the_logo(self):
        """The name is left out on a phone by design; the logo stays."""
        p = self.open(page(), 420)
        logo = self.box(p, "#hl-logo img")
        self.assertTrue(logo)
        self.assertTrue(0 <= logo[0] and logo[2] <= 420)

    def test_gauge_strip_is_on_and_still_shows_the_logo(self):
        p = self.open(page(), 1700)
        self.assertTrue(p.evaluate("document.getElementById('widgets-wrap').classList.contains('hl-stats-on')"))
        logo, name = self.box(p, "#hl-logo img"), self.box(p, "#hl-hello")
        self.assertTrue(logo and name)
        self.assertLess(logo[0], name[0], "the logo should be left of the name")

    def test_only_the_logo(self):
        for width in (1700, 900):
            with self.subTest(width=width):
                p = self.open(page(hello='"off"'), width)
                self.assertTrue(self.box(p, "#hl-logo img"))
                self.assertIsNone(self.box(p, "#hl-hello"))

    def test_only_the_name(self):
        for width in (1700, 900):
            with self.subTest(width=width):
                p = self.open(page(logo=False), width)
                self.assertIsNone(self.box(p, "#hl-logo"))
                self.assertTrue(self.box(p, "#hl-hello"))

    def test_neither(self):
        p = self.open(page(hello='"off"', logo=False), 1700)
        self.assertIsNone(self.box(p, "#hl-logo"))
        self.assertIsNone(self.box(p, "#hl-hello"))


if __name__ == "__main__":
    unittest.main()
