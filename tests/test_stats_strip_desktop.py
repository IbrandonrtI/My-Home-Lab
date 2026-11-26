"""The gauge strip on a wide screen: the Network graph stays inside its own cell and never runs over the line into Uptime, at every width. Needs Python Playwright and a
Chromium browser, and is skipped without them."""
import os
import shutil
import tempfile
import unittest

import helpers
from test_phone_layout import LOGO_PAGE, TRENDS

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

PAGE = (LOGO_PAGE.replace("--hl-logo-src", '--hl-hello: "Home Lab"; --hl-logo-src')
        .replace("861 GB free 1.8 TB total", "1.68 TB free 1.97 TB total").replace("61.7 GB free 931 GB total", "437 GB free 521 GB total")
        .replace("↓ 12 kB/s ↑ 3 kB/s", "↓ 138 kB/s ↑ 59 kB/s").replace("Uptime 8d19h", "Uptime 15h40m")
        .replace('<script src="custom.js">', TRENDS.replace("[1, 5, 2, 8, 3, 9, 4, 6]", "[100000, 500000, 200000, 800000, 300000, 900000, 400000, 600000]") + '<script src="custom.js">'))


@unittest.skipUnless(sync_playwright, "Python Playwright is not installed")
class StatsStripDesktop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="strip-")
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

    def test_the_network_graph_stays_in_its_cell_at_every_wide_width(self):
        for width in (1200, 1300, 1480, 1560, 1700, 1920, 2200):
            with self.subTest(width=width):
                ctx = self.browser.new_context(viewport={"width": width, "height": 400})
                self.addCleanup(ctx.close)
                p = ctx.new_page()
                p.goto("file://" + os.path.join(self.dir, "p.html"))
                p.wait_for_timeout(800)
                r = p.evaluate("""() => { const n = document.querySelector('#hl-stats .hl-g-net'), u = document.querySelector('#hl-stats .hl-g-up'), s = n.querySelector('.hl-gs');
                    if (!s) return null; const c = n.getBoundingClientRect(), g = s.getBoundingClientRect(), k = u.getBoundingClientRect();
                    return { inside: c.right - g.right, apart: k.left - g.right, spill: n.scrollWidth - n.clientWidth }; }""")
                self.assertIsNotNone(r, "the graph is drawn")
                self.assertGreaterEqual(r["inside"], -0.5, "the graph runs past the end of its cell")
                self.assertGreaterEqual(r["apart"], -0.5, "the graph runs into Uptime")
                self.assertLessEqual(r["spill"], 1)


if __name__ == "__main__":
    unittest.main()
