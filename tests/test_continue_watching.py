"""The Continue watching row on the Home tab, drawn from images/watching.json and images/watching-posters.json. Needs Python Playwright and a Chromium browser, and is skipped without them."""
import functools
import http.server
import json
import os
import shutil
import tempfile
import threading
import time
import unittest

import helpers

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

PIXEL = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
PAGE = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="custom.css"></head><body>'
        '<div id="inner_wrapper" style="--lk-side:14px"><div id="layout-groups"><div class="services-group"><ul class="services-list">'
        '<li id="%s-card" class="service"><div class="service-card"><div class="service-title"><a href="http://x.test/">Card</a></div></div></li></ul></div></div></div>'
        '<script src="custom.js"></script></body></html>')
ID1, ID2, ID3 = "a" * 32, "b" * 32, "c" * 32


def data(items=None, age=10, link="https://jf.example.ts.net:1009", user="Brandon", server="d" * 32):
    return {"version": 1, "updated": int(time.time()) - age, "user": user, "link": link, "server": server,
            "items": items if items is not None else [
                {"id": ID1, "title": "Severance", "sub": "S2 E5 - Trojan's Horse", "pct": 20, "left": 40, "poster": "p1"},
                {"id": ID2, "title": "Dune", "sub": "2021", "pct": 55, "left": 125, "poster": "p2"},
                {"id": ID3, "title": "No Picture", "sub": "", "pct": 0, "left": None, "poster": ""}]}


@unittest.skipUnless(sync_playwright, "Python Playwright is not installed")
class ContinueWatching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="cw-")
        os.makedirs(cls.dir + "/images")
        for n in ("custom.css", "custom.js"):
            shutil.copy(os.path.join(helpers.ROOT, "homepage-config", n), cls.dir)
        for name, card in (("home.html", "jellyfin"), ("other.html", "plain")):
            with open(cls.dir + "/" + name, "w") as f:
                f.write(PAGE % card)

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=cls.dir))
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

    def open(self, meta, page="home.html", width=1300, posters=None):
        for name, body in (("watching.json", meta), ("watching-posters.json", {"p1": PIXEL, "p2": PIXEL} if posters is None else posters)):
            path = self.dir + "/images/" + name
            if body is None:
                if os.path.exists(path):
                    os.remove(path)
            else:
                with open(path, "w") as f:
                    json.dump(body, f)
        ctx = self.browser.new_context(viewport={"width": width, "height": 900})
        self.addCleanup(ctx.close)
        pg = ctx.new_page()
        pg.goto("http://127.0.0.1:%d/%s" % (self.srv.server_address[1], page))
        pg.wait_for_timeout(900)
        return pg

    def shown(self, pg):
        return pg.evaluate("(() => { const e = document.getElementById('hl-watching'); return !!e && !e.hidden && e.getBoundingClientRect().height > 0; })()")

    def test_the_row_shows_each_title_with_its_progress(self):
        pg = self.open(data())
        self.assertTrue(self.shown(pg))
        self.assertEqual(pg.eval_on_selector_all("#hl-watching .hl-wt-title", "e => e.map(x => x.textContent)"), ["Severance", "Dune", "No Picture"])
        self.assertEqual(pg.eval_on_selector_all("#hl-watching .hl-wt-bar i", "e => e.map(x => x.style.width)"), ["20%", "55%"])
        self.assertEqual(pg.eval_on_selector_all("#hl-watching .hl-wt-left", "e => e.map(x => x.textContent)"), ["40 min left", "2 h 5 min left"])
        self.assertEqual(pg.eval_on_selector_all("#hl-watching .hl-wt-sub", "e => e.map(x => x.textContent)"), ["S2 E5 - Trojan's Horse", "2021"])
        self.assertIn("Brandon", pg.inner_text("#hl-watching .hl-wt-head"))

    def test_a_title_opens_in_jellyfin_in_a_new_tab(self):
        pg = self.open(data())
        a = pg.locator("#hl-watching a.hl-wt-card").first
        self.assertEqual(a.get_attribute("href"), "https://jf.example.ts.net:1009/web/#/details?id=%s&serverId=%s" % (ID1, "d" * 32))
        self.assertEqual(a.get_attribute("target"), "_blank")
        self.assertIn("noopener", a.get_attribute("rel"))

    def test_posters_are_drawn_and_a_missing_one_gets_a_letter(self):
        pg = self.open(data())
        self.assertEqual(pg.eval_on_selector_all("#hl-watching img", "e => e.length"), 2)
        self.assertEqual(pg.inner_text("#hl-watching .hl-wt-ph"), "N")

    def test_the_row_sits_above_the_services(self):
        pg = self.open(data())
        r = pg.evaluate("[document.getElementById('hl-watching').getBoundingClientRect().bottom, document.getElementById('layout-groups').getBoundingClientRect().top]")
        self.assertLessEqual(r[0], r[1])

    def test_nothing_half_watched_means_no_row(self):
        self.assertFalse(self.shown(self.open(data(items=[]))))

    def test_an_old_file_hides_the_row(self):
        self.assertFalse(self.shown(self.open(data(age=3 * 3600))))

    def test_no_file_means_no_row(self):
        self.assertFalse(self.shown(self.open(None, posters={})))

    def test_other_tabs_do_not_get_the_row(self):
        self.assertFalse(self.shown(self.open(data(), page="other.html")))

    def test_a_link_that_is_not_a_web_address_is_not_used(self):
        pg = self.open(data(link="javascript:alert(1)"))
        self.assertTrue(self.shown(pg))
        self.assertEqual(pg.locator("#hl-watching a").count(), 0)

    def test_a_poster_that_is_not_a_jpeg_picture_is_ignored(self):
        pg = self.open(data(), posters={"p1": "javascript:alert(1)", "p2": "data:text/html;base64,AAAA"})
        self.assertEqual(pg.eval_on_selector_all("#hl-watching img", "e => e.length"), 0)

    def test_text_from_jellyfin_is_shown_as_text(self):
        pg = self.open(data(items=[{"id": ID1, "title": "<img src=x onerror=alert(1)>", "sub": "<b>x</b>", "pct": 5, "left": 3, "poster": ""}]))
        self.assertEqual(pg.locator("#hl-watching b.hl-wt-title").inner_text(), "<img src=x onerror=alert(1)>")
        self.assertEqual(pg.locator("#hl-watching .hl-wt-card img").count(), 0)

    def test_on_a_phone_the_row_scrolls_inside_and_the_page_does_not(self):
        items = [{"id": ID1, "title": "Title %d" % i, "sub": "", "pct": 10, "left": 5, "poster": "p1"} for i in range(10)]
        pg = self.open(data(items=items), width=390)
        r = pg.evaluate("""() => { const row = document.querySelector('#hl-watching .hl-wt-row'); return [document.documentElement.scrollWidth, row.scrollWidth > row.clientWidth,
            document.getElementById('hl-watching').getBoundingClientRect().right]; }""")
        self.assertLessEqual(r[0], 390)
        self.assertTrue(r[1])
        self.assertLessEqual(r[2], 390 - 13)


if __name__ == "__main__":
    unittest.main()
