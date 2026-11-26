"""The Downloaders dropdown on the Home tab: one row that opens and closes the download apps under it. It starts closed and remembers the last choice in the browser. Tested on a plain page with the real stylesheet and script, not on a real Homepage. Needs Python Playwright and a Chromium browser, and is skipped without them."""
import functools
import http.server
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

APPS = ("seerr", "radarr", "sonarr", "prowlarr", "qbittorrent", "metube", "downtify")
PLAYERS = ("navidrome", "jellyfin", "watching")
PAGE = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="custom.css"></head><body>'
        '<div id="inner_wrapper" style="--lk-side:14px"><div id="layout-groups"><div class="services-group"><ul class="services-list">%s</ul></div></div></div>'
        '<script src="custom.js"></script></body></html>')


def card(name):
    return ('<li id="%s-card" class="service"><div class="service-card"><div class="service-title"><a href="http://x.test/%s">%s</a></div></div></li>' % (name, name, name))


def page(*names):
    return PAGE % "".join(card(n) for n in names)


@unittest.skipUnless(sync_playwright, "Python Playwright is not installed")
class DownloadersDropdown(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="dl-")
        for n in ("custom.css", "custom.js"):
            shutil.copy(os.path.join(helpers.ROOT, "homepage-config", n), cls.dir)
        pages = {"home.html": PLAYERS + ("downloaders",) + APPS + ("adguard",),
                 "nohead.html": PLAYERS + APPS,
                 "noapps.html": PLAYERS + ("downloaders", "adguard"),
                 "one.html": PLAYERS + ("downloaders", "metube", "adguard"),
                 "other.html": ("downloaders", "adguard", "navidrome", "seerr")}
        for name, cards in pages.items():
            with open(cls.dir + "/" + name, "w") as f:
                f.write(page(*cards))
        below = "".join("<div class='services-group'><ul class='services-list'>%s</ul></div>" % "".join("<li id='g%dx%d-card' class='service' style='height:90px'>x</li>" % (g, i) for i in range(12)) for g in range(4))
        with open(cls.dir + "/tall.html", "w") as f:
            f.write(page(*(PLAYERS + ("downloaders",) + APPS)).replace("</ul></div></div></div>", "</ul></div>" + below + "</div></div>")
                    .replace("</head>", "<style>#navidrome-card, #jellyfin-card { min-height: 700px; } .services-group:first-child { overflow-anchor: none; }</style></head>"))

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

    def open(self, name="home.html", width=1300, ctx=None, init=None):
        if ctx is None:
            ctx = self.browser.new_context(viewport={"width": width, "height": 900})
            self.addCleanup(ctx.close)
        pg = ctx.new_page()
        if init:
            pg.add_init_script(init)
        pg.goto("http://127.0.0.1:%d/%s" % (self.srv.server_address[1], name))
        pg.wait_for_timeout(700)
        return pg

    def shown(self, pg, name):
        return pg.evaluate("(() => { const e = document.getElementById('%s-card'); return !!e && getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().height > 0; })()" % name)

    def apps_shown(self, pg):
        return [a for a in APPS if self.shown(pg, a)]

    def test_it_starts_closed_with_the_apps_hidden(self):
        pg = self.open()
        self.assertEqual(self.apps_shown(pg), [])
        self.assertTrue(self.shown(pg, "downloaders"))
        self.assertEqual(pg.inner_text("#hl-downloaders"), "Downloaders\n7 apps")
        self.assertEqual(pg.get_attribute("#hl-downloaders", "aria-expanded"), "false")

    def test_a_click_opens_it_and_another_click_closes_it(self):
        pg = self.open()
        pg.click("#hl-downloaders")
        self.assertEqual(self.apps_shown(pg), list(APPS))
        self.assertEqual(pg.get_attribute("#hl-downloaders", "aria-expanded"), "true")
        pg.click("#hl-downloaders")
        self.assertEqual(self.apps_shown(pg), [])

    def test_opening_and_closing_keep_the_row_where_it_is_and_move_what_is_below(self):
        """The media group is made a poor anchor for the browser's scroll anchoring here, which is what made the page jump on a real dashboard."""
        pg = self.open("tall.html", width=2560)
        pg.set_viewport_size({"width": 2560, "height": 1247})
        top = pg.evaluate("document.getElementById('hl-downloaders').getBoundingClientRect().top + scrollY")
        for at in (0.3, 0.6):
            with self.subTest(at=at):
                pg.evaluate("window.scrollTo(0, %f)" % (top - 1247 * at))
                pg.wait_for_timeout(300)
                before = pg.evaluate("[scrollY, document.getElementById('hl-downloaders').getBoundingClientRect().top, document.querySelector('#g0x0-card').getBoundingClientRect().top]")
                pg.click("#hl-downloaders")
                pg.wait_for_timeout(500)
                opened = pg.evaluate("[scrollY, document.getElementById('hl-downloaders').getBoundingClientRect().top, document.querySelector('#g0x0-card').getBoundingClientRect().top]")
                self.assertEqual(opened[:2], before[:2])
                self.assertGreater(opened[2], before[2] + 100)
                pg.click("#hl-downloaders")
                pg.wait_for_timeout(500)
                self.assertEqual(pg.evaluate("[scrollY, document.getElementById('hl-downloaders').getBoundingClientRect().top]"), before[:2])

    def test_the_keyboard_works_too(self):
        pg = self.open()
        pg.focus("#hl-downloaders")
        pg.keyboard.press("Enter")
        self.assertEqual(self.apps_shown(pg), list(APPS))
        pg.keyboard.press("Space")
        self.assertEqual(self.apps_shown(pg), [])

    def test_the_last_choice_is_remembered_when_the_page_is_opened_again(self):
        ctx = self.browser.new_context(viewport={"width": 1300, "height": 900})
        self.addCleanup(ctx.close)
        pg = self.open(ctx=ctx)
        pg.click("#hl-downloaders")
        pg.close()
        self.assertEqual(self.apps_shown(self.open(ctx=ctx)), list(APPS))
        pg = self.open(ctx=ctx)
        pg.click("#hl-downloaders")
        pg.close()
        self.assertEqual(self.apps_shown(self.open(ctx=ctx)), [])

    def test_the_row_and_the_apps_sit_under_the_players_in_order(self):
        for width in (1300, 390):
            with self.subTest(width=width):
                pg = self.open(width=width)
                pg.click("#hl-downloaders")
                pg.wait_for_timeout(400)
                order = pg.evaluate("[...document.querySelectorAll('.services-list > li')].filter(l => getComputedStyle(l).display !== 'none')"
                                    ".sort((a, b) => Math.round(a.getBoundingClientRect().top / 8) - Math.round(b.getBoundingClientRect().top / 8) || a.getBoundingClientRect().left - b.getBoundingClientRect().left).map(l => l.id.replace('-card', ''))")
                self.assertEqual(order, ["navidrome", "jellyfin", "downloaders"] + list(APPS) + ["adguard"])  # Continue Watching is hidden here: there is nothing half-watched in this page

    def test_the_row_is_as_wide_as_the_list_it_is_in(self):
        for width in (1300, 390):
            with self.subTest(width=width):
                pg = self.open(width=width)
                r = pg.evaluate("""() => { const e = document.getElementById('downloaders-card').getBoundingClientRect(), u = document.getElementById('downloaders-card').parentNode,
                    b = u.getBoundingClientRect(), c = getComputedStyle(u); return [e.left - (b.left + parseFloat(c.paddingLeft)), (b.right - parseFloat(c.paddingRight)) - e.right]; }""")
                self.assertLessEqual(abs(r[0]), 1)
                self.assertLessEqual(abs(r[1]), 1)

    def test_other_cards_are_not_touched_by_the_dropdown(self):
        pg = self.open()
        self.assertTrue(self.shown(pg, "adguard"))
        self.assertTrue(self.shown(pg, "navidrome"))

    def test_the_cards_own_text_is_hidden_behind_the_row(self):
        pg = self.open()
        self.assertEqual(pg.evaluate("getComputedStyle(document.querySelector('#downloaders-card .service-card')).display"), "none")

    def test_without_the_row_the_apps_stay_visible(self):
        pg = self.open("nohead.html")
        self.assertEqual(self.apps_shown(pg), list(APPS))
        self.assertEqual(pg.evaluate("document.querySelectorAll('#hl-downloaders').length"), 0)

    def test_removing_the_row_brings_the_apps_back(self):
        pg = self.open()
        self.assertEqual(self.apps_shown(pg), [])
        pg.evaluate("document.getElementById('downloaders-card').remove()")
        pg.wait_for_timeout(500)
        self.assertEqual(self.apps_shown(pg), list(APPS))

    def test_a_row_with_no_apps_next_to_it_is_hidden(self):
        pg = self.open("noapps.html")
        self.assertFalse(self.shown(pg, "downloaders"))

    def test_the_count_says_one_app_when_there_is_one(self):
        pg = self.open("one.html")
        self.assertEqual(pg.inner_text("#hl-downloaders"), "Downloaders\n1 app")

    def test_an_app_in_a_different_list_than_the_row_is_left_alone(self):
        pg = self.open("home.html")
        pg.evaluate("""() => { const g = document.createElement('div'); g.className = 'services-group'; g.innerHTML = '<ul class="services-list"><li id="seerr-card" class="service">x</li></ul>';
            document.getElementById('seerr-card').remove(); document.getElementById('layout-groups').appendChild(g); }""")
        pg.wait_for_timeout(500)
        self.assertEqual(pg.evaluate("document.getElementById('seerr-card').className.includes('hl-dl-shut')"), False)

    def test_the_row_is_drawn_once_when_the_page_is_updated(self):
        pg = self.open()
        pg.evaluate("document.getElementById('adguard-card').remove()")
        pg.wait_for_timeout(500)
        self.assertEqual(pg.evaluate("document.querySelectorAll('#hl-downloaders').length"), 1)
        pg.evaluate("document.getElementById('hl-downloaders').remove()")
        pg.wait_for_timeout(3500)
        self.assertEqual(pg.evaluate("document.querySelectorAll('#hl-downloaders').length"), 1)

    def test_it_still_works_when_the_browser_cannot_keep_the_choice(self):
        pg = self.open(init="Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } });")
        self.assertEqual(self.apps_shown(pg), [])
        pg.click("#hl-downloaders")
        self.assertEqual(self.apps_shown(pg), list(APPS))
        pg.wait_for_timeout(3500)
        self.assertEqual(self.apps_shown(pg), list(APPS))

    def test_the_row_is_not_offered_in_quick_launch_or_search(self):
        pg = self.open()
        pg.evaluate("localStorage.setItem('hl-visits', JSON.stringify({'downloaders-card': 50}))")
        pg.reload()
        pg.wait_for_timeout(700)
        self.assertEqual(pg.evaluate("document.querySelectorAll('#hl-dock a[href*=\"downloaders\"]').length"), 0)


if __name__ == "__main__":
    unittest.main()
