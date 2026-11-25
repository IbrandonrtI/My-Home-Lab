"""On the Stats tab a tile left alone at the end of a row stretches over the empty places. Needs Python Playwright and a Chromium browser, and is skipped without them."""
import os
import shutil
import tempfile
import unittest

import helpers

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


def group(cols, ids):
    tiles = "".join('<li id="stat-%s"><div class="service-card" style="height:60px">%s</div></li>' % (i, i) for i in ids)
    return '<div class="services-group"><ul class="services-list" style="display:grid;gap:8px;grid-template-columns:repeat(%d,minmax(0,1fr))">%s</ul></div>' % (cols, tiles)


def page(*groups):
    return ('<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="custom.css"></head><body style="width:1200px"><div id="inner_wrapper">'
            '<div id="layout-groups">' + "".join(groups) + '</div></div><script src="custom.js"></script></body></html>')


@unittest.skipUnless(sync_playwright, "Python Playwright is not installed")
class TileRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="rows-")
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

    def open(self, html):
        with open(os.path.join(self.dir, "p.html"), "w", encoding="utf-8") as f:
            f.write(html)
        ctx = self.browser.new_context(viewport={"width": 1300, "height": 900})
        self.addCleanup(ctx.close)
        pg = ctx.new_page()
        pg.goto("file://" + os.path.join(self.dir, "p.html"))
        pg.wait_for_timeout(700)
        return pg

    def widths(self, pg, n=0):
        return pg.evaluate("n => [...document.querySelectorAll('.services-list')[n].children].map(li => Math.round(li.getBoundingClientRect().width))", n)

    def test_a_fourth_tile_in_three_columns_fills_the_last_row(self):
        w = self.widths(self.open(page(group(3, "abcd"))))
        self.assertEqual(w[0], w[1])
        self.assertAlmostEqual(w[3], w[0] * 3 + 16, delta=2)

    def test_a_third_tile_in_two_columns_fills_the_last_row(self):
        w = self.widths(self.open(page(group(2, "abc"))))
        self.assertAlmostEqual(w[2], w[0] * 2 + 8, delta=2)

    def test_the_fifth_tile_in_three_columns_takes_the_last_two_places(self):
        w = self.widths(self.open(page(group(3, "abcde"))))
        self.assertAlmostEqual(w[4], w[0] * 2 + 8, delta=2)

    def test_a_full_row_is_left_alone(self):
        pg = self.open(page(group(3, "abc"), group(2, "xy")))
        self.assertEqual(len(set(self.widths(pg, 0))), 1)
        self.assertEqual(len(set(self.widths(pg, 1))), 1)

    def test_a_list_without_stats_tiles_is_left_alone(self):
        html = page('<div class="services-group"><ul class="services-list" style="display:grid;grid-template-columns:repeat(3,1fr)">'
                    '<li id="a-card">a</li><li id="b-card">b</li><li id="c-card">c</li><li id="d-card">d</li></ul></div>')
        w = self.widths(self.open(html))
        self.assertEqual(len(set(w)), 1)

    def test_it_follows_a_narrower_window(self):
        pg = self.open(page(group(3, "abcd")))
        pg.evaluate("document.querySelector('.services-list').style.gridTemplateColumns = 'repeat(2, minmax(0, 1fr))'")
        pg.wait_for_timeout(3600)
        w = self.widths(pg)
        self.assertEqual(len(set(w)), 1, "four tiles in two columns need no stretching")


if __name__ == "__main__":
    unittest.main()
