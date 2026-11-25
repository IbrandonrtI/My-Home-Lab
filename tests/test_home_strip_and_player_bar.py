"""The small status pill in the tab bar ("13/13", and which services are not answering when you press it) and the music player that starts as a slim bar. Needs Python
Playwright and a Chromium browser, and is skipped without them."""
import os
import shutil
import tempfile
import unittest

import helpers

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


def card(cid, name, state):
    colour = {"up": "bg-emerald-500", "down": "bg-rose-500"}[state]
    return ('<li id="%s-card" class="service"><div class="service-card"><div class="service-title"><a class="service-title-text" href="http://%s.test/">%s</a>'
            '<div class="site-monitor-status"><div class="%s" style="width:10px;height:10px"></div></div></div></div></li>' % (cid, cid, name, colour))


def page(cards, player=False):
    nd = ('<li id="navidrome-card" class="service"><div class="service-card"><div class="service-title"><a href="http://nd.test/">Navidrome</a></div>'
          '<div><iframe src="http://nd.test/" style="height:300px"></iframe></div></div></li>') if player else ""
    return ('<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="custom.css"></head><body><div id="inner_wrapper">'
            '<div id="tabs"><ul id="myTab"><li><button id="home-tab" aria-selected="true">Home</button></li></ul></div>'
            '<div id="layout-groups"><div class="services-group"><ul class="services-list">' + "".join(cards) + nd + '</ul></div></div></div>'
            '<script src="custom.js"></script></body></html>')


@unittest.skipUnless(sync_playwright, "Python Playwright is not installed")
class HomeStripAndPlayerBar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="home-")
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

    def open(self, html, name="p.html"):
        with open(os.path.join(self.dir, name), "w", encoding="utf-8") as f:
            f.write(html)
        ctx = self.browser.new_context(viewport={"width": 1400, "height": 900})
        self.addCleanup(ctx.close)
        page_ = ctx.new_page()
        page_.route("http://**/**", lambda r: r.fulfill(status=200, content_type="text/html", body="<title>x</title>"))
        page_.goto("file://" + os.path.join(self.dir, name))
        page_.wait_for_timeout(600)
        return page_

    def later(self, page_):
        """Pretend the page has been open for a minute, so a red dot is no longer 'still starting'."""
        page_.evaluate("(n => { Date.now = () => n() + 60000; })(Date.now)")

    def poke(self, page_):
        """Homepage changes a dot's class without adding anything, which the page notices on its 3 second tick. A new element makes it look at once."""
        page_.evaluate("document.body.appendChild(document.createElement('i'))")
        page_.wait_for_timeout(300)

    def strip(self, page_):
        return page_.eval_on_selector("#hl-status", "e => e.hidden ? '' : e.textContent")

    def pill(self, page_):
        return page_.eval_on_selector("#hl-status > button", "e => e.textContent.trim()")

    def test_all_services_up(self):
        page_ = self.open(page([card("a", "Alpha", "up"), card("b", "Beta", "up")]))
        self.assertIn("All services are healthy", self.strip(page_))
        self.assertIn("2 of 2 answering", self.strip(page_))
        self.assertEqual(self.pill(page_), "2/2")
        self.assertEqual(page_.evaluate("document.getElementById('hl-status').parentNode.id"), "tabs", "it sits in the tab bar, not above the cards")
        box = page_.eval_on_selector("#hl-status", "e => { const r = e.getBoundingClientRect(); return [r.width, r.height]; }")
        self.assertLess(box[0], 120)
        self.assertLess(box[1], 60)
        self.assertFalse(page_.is_visible("#hl-status .hl-bellpop"), "the details stay closed until it is pressed")
        page_.click("#hl-status > button")
        self.assertTrue(page_.is_visible("#hl-status .hl-bellpop"))
        page_.keyboard.press("Escape")
        self.assertFalse(page_.is_visible("#hl-status .hl-bellpop"))

    def test_a_down_service_is_named_and_the_chip_points_to_its_card(self):
        page_ = self.open(page([card("a", "Alpha", "up"), card("b", "Beta", "down")]))
        self.assertIn("Checking the services", self.strip(page_), "just after the page opens a red dot is not yet an alarm")
        self.assertEqual(self.pill(page_), "…")
        self.later(page_)
        self.poke(page_)
        text = self.strip(page_)
        self.assertIn("1 service is not answering", text)
        self.assertIn("Beta", text)
        self.assertNotIn("Alpha", text)
        self.assertEqual(self.pill(page_), "1 down")
        page_.click("#hl-status > button")
        page_.click("#hl-status .hl-st-chip")
        self.assertTrue(page_.evaluate("document.getElementById('b-card').classList.contains('hl-flash')"))

    def test_the_pill_follows_the_dots_and_hides_without_any(self):
        page_ = self.open(page([card("a", "Alpha", "up"), card("b", "Beta", "up")]))
        self.later(page_)
        page_.evaluate("document.querySelector('#a-card .site-monitor-status div').className = 'bg-rose-500'")
        page_.evaluate("document.querySelector('#b-card .site-monitor-status div').className = 'bg-rose-500'")
        self.poke(page_)
        self.assertIn("2 services are not answering", self.strip(page_))
        self.assertEqual(self.pill(page_), "2 down")
        page_.evaluate("document.querySelectorAll('.site-monitor-status').forEach(e => e.remove())")
        page_.wait_for_timeout(300)
        self.assertEqual(self.strip(page_), "", "a tab without status dots has no pill")

    def test_the_player_starts_as_a_slim_bar_and_remembers_the_choice(self):
        page_ = self.open(page([card("a", "Alpha", "up")], player=True), "player.html")
        page_.wait_for_selector("#navidrome-card .hl-shrink", state="attached")
        self.assertTrue(page_.evaluate("document.documentElement.classList.contains('hl-player-min')"), "slim at first")
        page_.wait_for_timeout(500)
        self.assertEqual(page_.eval_on_selector("#navidrome-card iframe", "e => e.parentElement.getBoundingClientRect().height"), 0)
        page_.click("#navidrome-card .hl-shrink")
        page_.wait_for_timeout(600)
        self.assertFalse(page_.evaluate("document.documentElement.classList.contains('hl-player-min')"), "opened")
        self.assertEqual(page_.evaluate("localStorage.getItem('hl-player-shrunk')"), "0")
        page_.reload()
        page_.wait_for_selector("#navidrome-card .hl-shrink", state="attached")
        self.assertFalse(page_.evaluate("document.documentElement.classList.contains('hl-player-min')"), "the choice is kept")

    def test_pressing_the_slim_bar_opens_the_player(self):
        page_ = self.open(page([card("a", "Alpha", "up")], player=True), "player2.html")
        page_.wait_for_selector("#navidrome-card .hl-shrink", state="attached")
        page_.evaluate("document.querySelector('#navidrome-card .service-title').click()")
        page_.wait_for_timeout(400)
        self.assertFalse(page_.evaluate("document.documentElement.classList.contains('hl-player-min')"))


if __name__ == "__main__":
    unittest.main()
