"""The dashboard on a phone: the gauges sit in one compact panel instead of a stack of tiles, the header fills the width, the tab names fit whole next to the bell and the
status pill, and nothing makes the page scroll sideways. Needs Python Playwright and a Chromium browser, and is skipped without them."""
import os
import shutil
import tempfile
import unittest

import helpers

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


def resource(text, pct=None, label=""):
    bar = '<div class="bar"><div style="width:%s%%"></div></div>' % pct if pct is not None else ""
    return '<div class="widget-container"><div class="information-widget-resource"><span>%s</span>%s</div>%s</div>' % (text, bar, ("<div>%s</div>" % label) if label else "")


HEADER = ('<div id="information-widgets"><div id="widgets-wrap">'
          '<div class="widget-container"><div><div class="information-widget-resource"><span>CPU 4%</span><div class="bar"><div style="width:4%"></div></div></div>'
          '<div class="information-widget-resource"><span>Memory 3.9 GiB free</span><div class="bar"><div style="width:51%"></div></div></div>'
          '<div class="information-widget-resource"><span>44°C</span><div class="bar"><div style="width:44%"></div></div></div></div></div>'
          + resource("861 GB free 1.8 TB total", 52, "Main Pool") + resource("61.7 GB free 931 GB total", 7, "Backup") + resource("↓ 12 kB/s ↑ 3 kB/s", None, "Network")
          + resource("Uptime 8d19h") +
          '<div id="information-widgets-right"><div class="information-widget-datetime"><span>Nov 23, 2026, 5:53 PM</span></div>'
          '<div class="information-widget-openmeteo"><span>New York City, 57.3°F</span></div>'
          '<form class="information-widget-search"><input placeholder="Search"></form></div></div></div>')


def card(cid, name):
    return ('<li id="%s-card" class="service"><div class="service-card"><div class="service-title"><a class="service-title-text" href="http://%s.test/">%s</a>'
            '<div class="site-monitor-status"><div class="bg-emerald-500" style="width:10px;height:10px"></div></div></div></div></li>' % (cid, cid, name))


PAGE = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="custom.css"><style>'
        'body{margin:0}#inner_wrapper{display:flex;flex-direction:column;min-height:100vh;--lk-side:14px;--lk-glass:33,42,64;--lk-glass-a:.85;--lk-line:#34405c;--lk-ink:255,255,255;--lk-accent:94,214,164}'
        '.bar{height:6px}ul{list-style:none;padding:0;margin:0}</style></head><body><div id="inner_wrapper">' + HEADER +
        '<div id="tabs"><ul id="myTab"><li><button id="home-tab" aria-selected="true">Home</button></li><li><button id="stats-tab">Stats</button></li>'
        '<li><button id="links-tab">Links</button></li><li><button id="customize-tab">Customize</button></li></ul></div>'
        '<div id="layout-groups"><div class="services-group"><ul class="services-list">' + card("a", "Alpha") + card("b", "Beta") + '</ul></div></div></div>'
        '<script src="custom.js"></script></body></html>')


@unittest.skipUnless(sync_playwright, "Python Playwright is not installed")
class PhoneLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="phone-")
        for n in ("custom.css", "custom.js"):
            shutil.copy(os.path.join(helpers.ROOT, "homepage-config", n), cls.dir)
        with open(os.path.join(cls.dir, "p.html"), "w", encoding="utf-8") as f:
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

    def open(self, width):
        ctx = self.browser.new_context(viewport={"width": width, "height": 800}, is_mobile=True, has_touch=True)
        self.addCleanup(ctx.close)
        p = ctx.new_page()
        p.goto("file://" + os.path.join(self.dir, "p.html"))
        p.wait_for_timeout(700)
        return p

    def test_gauges_share_one_panel_and_the_old_tiles_are_hidden(self):
        p = self.open(390)
        r = p.evaluate("""() => { const s = document.getElementById('hl-stats'), b = s.getBoundingClientRect(), c = getComputedStyle(s);
            return { cols: c.gridTemplateColumns.split(' ').length, h: b.height, gauges: s.querySelectorAll('.hl-g').length,
              tiles: [...document.querySelectorAll('#widgets-wrap > .widget-container')].filter(e => getComputedStyle(e).display !== 'none').length }; }""")
        self.assertEqual(r["cols"], 2)
        self.assertEqual(r["gauges"], 7)
        self.assertEqual(r["tiles"], 0, "the original tiles stay hidden under the gauges")
        self.assertLess(r["h"], 260, "the gauges take too much of the first screen")

    def test_the_first_service_is_near_the_top(self):
        p = self.open(390)
        top = p.evaluate("document.querySelector('#layout-groups .service').getBoundingClientRect().top")
        self.assertLess(top, 520)

    def test_the_gauges_come_before_the_clock(self):
        p = self.open(390)
        r = p.evaluate("""() => [document.getElementById('hl-stats').getBoundingClientRect().top, document.querySelector('.information-widget-datetime').getBoundingClientRect().top]""")
        self.assertLess(r[0], r[1])

    def test_header_fills_the_width_and_the_page_does_not_scroll_sideways(self):
        for width in (320, 360, 390, 430):
            with self.subTest(width=width):
                p = self.open(width)
                r = p.evaluate("""() => { const h = document.getElementById('widgets-wrap').getBoundingClientRect(); return [h.left, h.right, document.documentElement.scrollWidth]; }""")
                self.assertAlmostEqual(r[0], 14, delta=1)
                self.assertAlmostEqual(r[1], width - 14, delta=1)
                self.assertLessEqual(r[2], width)

    def test_tab_names_fit_whole(self):
        for width in (320, 360, 390, 430):
            with self.subTest(width=width):
                p = self.open(width)
                clipped = p.evaluate("[...document.querySelectorAll('#myTab button')].filter(b => b.scrollWidth > b.clientWidth).map(b => b.textContent)")
                self.assertEqual(clipped, [])
                bar = p.evaluate("(() => { const r = document.getElementById('tabs').getBoundingClientRect(); return [r.left, r.right]; })()")
                self.assertGreaterEqual(bar[0], 0)
                self.assertLessEqual(bar[1], width)


if __name__ == "__main__":
    unittest.main()
