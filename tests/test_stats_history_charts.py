"""The temperature and Jellyfin added-per-day charts on the Stats tab, drawn from images/history.json. Needs Python Playwright and a Chromium browser, and is skipped without them."""
import functools
import http.server
import json
import os
import shutil
import tempfile
import threading
import unittest

import helpers

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

PAGE = ('<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="custom.css"></head><body><div id="inner_wrapper">'
        '<div id="layout-groups"><div class="services-group"><ul class="services-list"><li id="stat-one" class="service"><div class="service-card">x</div></li></ul></div></div></div>'
        '<script src="custom.js"></script></body></html>')
HOME_PAGE = PAGE.replace("stat-one", "plain-one")


def history(days=3, readings=40):
    t0 = 1795600000
    t = [t0 + i * 900 for i in range(readings)]
    act = []
    for i in range(14):
        on = i >= 14 - days
        act.append({"day": "2026-11-%02d" % (12 + i), "movies": 1 if on else None, "shows": 0 if on else None, "episodes": 5 if on else None})
    return {"version": 1, "updated": t[-1], "step": 900, "t": t, "cpu": [50 + (i % 7) for i in range(readings)],
            "drives": {"Storage": [36] * readings, "Backup": [None] * 10 + [31] * (readings - 10)},
            "days": {"2026-11-25": {"movies": 50, "shows": 9, "episodes": 300}}, "activity": act}


@unittest.skipUnless(sync_playwright, "Python Playwright is not installed")
class HistoryCharts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="hist-")
        os.makedirs(cls.dir + "/images")
        for n in ("custom.css", "custom.js"):
            shutil.copy(os.path.join(helpers.ROOT, "homepage-config", n), cls.dir)
        with open(cls.dir + "/p.html", "w") as f:
            f.write(PAGE)
        with open(cls.dir + "/home.html", "w") as f:
            f.write(HOME_PAGE)
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        handler = functools.partial(Quiet, directory=cls.dir)
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception as e:
            cls.srv.shutdown()
            cls.pw.stop()
            shutil.rmtree(cls.dir, True)
            raise unittest.SkipTest("no Chromium browser: %s" % e) from e

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.srv.shutdown()
        cls.srv.server_close()
        shutil.rmtree(cls.dir, True)

    def open(self, data, name="p.html"):
        path = self.dir + "/images/history.json"
        if data is None:
            if os.path.exists(path):
                os.remove(path)
        else:
            with open(path, "w") as f:
                json.dump(data, f)
        ctx = self.browser.new_context(viewport={"width": 1400, "height": 1000})
        self.addCleanup(ctx.close)
        pg = ctx.new_page()
        pg.goto("http://127.0.0.1:%d/%s" % (self.srv.server_address[1], name))
        pg.wait_for_selector("#hl-history", state="attached")
        pg.wait_for_timeout(700)
        return pg

    def titles(self, pg):
        return pg.eval_on_selector_all("#hl-history .hl-dk-head b", "els => els.map(e => e.textContent)")

    def test_a_line_chart_and_a_bar_chart(self):
        pg = self.open(history())
        self.assertEqual(self.titles(pg), ["Temperature", "Jellyfin added per day"])
        # CPU plus the two drives; a drive with a gap in front still draws.
        self.assertEqual(pg.eval_on_selector_all("#hl-history .hl-dk-card:nth-child(1) svg path:not(.hl-dk-grid)", "e => e.length"), 3)
        self.assertGreater(pg.eval_on_selector_all("#hl-history .hl-dk-card:nth-child(2) svg rect", "e => e.length"), 0)
        self.assertIn("CPU", pg.inner_text("#hl-history .hl-dk-card:nth-child(1) .hl-hx-key"))
        self.assertIn("Storage", pg.inner_text("#hl-history .hl-dk-card:nth-child(1) .hl-hx-key"))

    def test_it_sits_before_the_docker_charts_and_the_cards(self):
        pg = self.open(history())
        order = pg.evaluate("[...document.getElementById('hl-history').parentNode.children].map(e => e.id).filter(Boolean)")
        self.assertLess(order.index("hl-history"), order.index("layout-groups"))
        if "hl-docker" in order:
            self.assertEqual(order.index("hl-history") + 1, order.index("hl-docker"))
            self.assertEqual(order.index("hl-docker") + 1, order.index("layout-groups"))

    def test_added_per_day_waits_for_two_days_of_totals(self):
        pg = self.open(history(days=0))
        card = pg.inner_text("#hl-history .hl-dk-card:nth-child(2)")
        self.assertIn("Jellyfin added per day", card)
        self.assertIn("two days", card)
        self.assertEqual(pg.eval_on_selector_all("#hl-history .hl-dk-card:nth-child(2) svg", "e => e.length"), 0)

    def test_without_jellyfin_there_is_no_added_chart(self):
        data = history()
        data["days"] = {}
        pg = self.open(data)
        self.assertEqual(self.titles(pg), ["Temperature"])

    def test_no_readings_yet_says_it_is_collecting(self):
        pg = self.open({"version": 1, "updated": 0, "step": 900, "t": [], "cpu": [], "drives": {}, "days": {}, "activity": []})
        self.assertEqual(self.titles(pg), ["Temperature"])
        self.assertIn("Collecting data", pg.inner_text("#hl-history"))

    def test_a_missing_file_shows_a_note_and_the_page_still_works(self):
        pg = self.open(None)
        pg.wait_for_timeout(300)
        self.assertIn("No history yet", pg.inner_text("#hl-history"))
        self.assertTrue(pg.is_visible("#layout-groups"))

    def test_hover_shows_the_values(self):
        pg = self.open(history())
        box = pg.eval_on_selector("#hl-history .hl-dk-card:nth-child(1) .hl-dk-plot", "e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
        pg.mouse.move(box[0] + box[2] * 0.5, box[1] + box[3] * 0.5)
        pg.wait_for_timeout(200)
        tip = pg.inner_text("#hl-history .hl-dk-card:nth-child(1) .hl-dk-tip")
        self.assertIn("CPU", tip)
        self.assertIn("°C", tip)
        self.assertIn("Storage", tip)

    def test_not_shown_outside_the_stats_tab(self):
        ctx = self.browser.new_context(viewport={"width": 1400, "height": 1000})
        self.addCleanup(ctx.close)
        pg = ctx.new_page()
        pg.goto("http://127.0.0.1:%d/home.html" % self.srv.server_address[1])
        pg.wait_for_timeout(900)
        self.assertEqual(pg.evaluate("!!document.getElementById('hl-history')"), False)

    def test_no_chart_runs_past_the_card_on_a_phone(self):
        ctx = self.browser.new_context(viewport={"width": 390, "height": 900})
        self.addCleanup(ctx.close)
        with open(self.dir + "/images/history.json", "w") as f:
            json.dump(history(), f)
        pg = ctx.new_page()
        pg.goto("http://127.0.0.1:%d/p.html" % self.srv.server_address[1])
        pg.wait_for_selector("#hl-history .hl-dk-card")
        self.assertLessEqual(pg.evaluate("document.documentElement.scrollWidth"), 391)


if __name__ == "__main__":
    unittest.main()
