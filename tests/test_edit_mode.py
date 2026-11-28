"""Edit mode on the dashboard page, in a real browser: the page script and the real control panel server talk to each other, cards and groups are dragged, and Save writes the
dashboard files. Needs Python Playwright and a Chromium browser, and is skipped without them."""
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

import helpers

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

PASSWORD = "test-password-123"

SERVICES = """- Network & DNS:

    - Tailscale:
        id: tailscale-card
        href: http://192.168.1.5:1
    - AdGuard Home:
        id: adguard-card
        href: http://192.168.1.5:2

- Files & Photos:

    - Immich:
        id: immich-card
        href: http://192.168.1.5:4
    - Nextcloud:
        id: nextcloud-card
        href: http://192.168.1.5:5

- Media & Entertainment:

    - Navidrome:
        id: navidrome-card
        href: http://192.168.1.5:6
    - Jellyfin:
        id: jellyfin-card
        href: http://192.168.1.5:7

- Customize:

    - Control panel:
        id: customize-card
        href: http://192.168.1.5:8
"""

SETTINGS = """title: Home Lab
layout:
  Network & DNS:
    tab: Home
    icon: mdi-lan
  Files & Photos:
    tab: Home
    icon: mdi-folder-multiple-image
  Media & Entertainment:
    tab: Home
    icon: mdi-movie-open
  Customize:
    tab: Customize
    icon: mdi-tune
"""

GROUPS = [("Network & DNS", [("tailscale", "Tailscale"), ("adguard", "AdGuard Home")]),
          ("Files & Photos", [("immich", "Immich"), ("nextcloud", "Nextcloud")]),
          ("Media & Entertainment", [("navidrome", "Navidrome"), ("jellyfin", "Jellyfin")])]


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def page_html():
    out = []
    for name, cards in GROUPS:
        lis = "".join('<li id="%s-card" class="service" data-name="%s"><div class="service-card"><a class="service-title-text" href="http://x.test/%s">%s</a></div></li>' % (i, n, i, n) for i, n in cards)
        out.append('<div class="services-group"><button><h2 class="service-group-name">%s</h2></button><div><ul class="services-list">%s</ul></div></div>' % (name.replace("&", "&amp;"), lis))
    return ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="custom.css"><style>'
            'html,body{height:100%;margin:0}#inner_wrapper{height:100%;overflow:auto;-webkit-backdrop-filter:blur(2px);backdrop-filter:blur(2px)}#layout-groups{display:flex;flex-wrap:wrap;align-items:flex-start;margin:16px}.services-group{flex:1 1 30%;min-width:260px;padding:4px}'
            'ul{list-style:none;padding:0;margin:0}li.service{margin:0 0 8px}.service-card{height:54px;padding:8px}</style></head><body><div id="inner_wrapper">'
            '<div id="tabs"><ul id="myTab"><li><button id="Home-tab" aria-selected="true">Home</button></li><li><button id="Customize-tab" aria-selected="false">Customize</button></li></ul></div>'
            '<div id="layout-groups">' + "".join(out) + '</div><div style="height:1500px"></div></div><script src="custom.js"></script></body></html>')


@unittest.skipUnless(sync_playwright, "Python Playwright is not installed")
class EditMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="hl-edit-")
        hp = os.path.join(cls.dir, "homepage-config")
        shutil.copytree(os.path.join(helpers.ROOT, "homepage-config"), hp, ignore=shutil.ignore_patterns("images", "__pycache__"))
        cls.services = os.path.join(hp, "services.yaml")
        cls.settings = os.path.join(hp, "settings.yaml")
        cls.web = os.path.join(cls.dir, "web")
        os.makedirs(cls.web)
        for n in ("custom.css", "custom.js"):
            shutil.copy(os.path.join(helpers.ROOT, "homepage-config", n), cls.web)
        with open(os.path.join(cls.web, "index.html"), "w", encoding="utf-8") as f:
            f.write(page_html())
        cls.panel_port, cls.web_port = free_port(), free_port()
        cls.reset()
        env = dict(os.environ, HLP_HOME=cls.dir, HOMELAB_HOMEPAGE_DIR=hp, HLP_STATE=os.path.join(cls.dir, "state"), HLP_UI=os.path.join(helpers.ROOT, "panel", "ui"),
                   HLP_PORT=str(cls.panel_port), HLP_NO_DOCKER="1", HLP_COOKIE_PLAIN="1", HLP_SHIPPED=os.devnull, HLP_DRIVES=os.path.join(helpers.ROOT, "scripts", "drives"),
                   HLP_FRAME="http://127.0.0.1:%d" % cls.web_port)
        os.makedirs(env["HLP_STATE"], exist_ok=True)
        script = os.path.join(helpers.ROOT, "scripts", "homelab-panel")
        subprocess.run([sys.executable, script, "set-password", "--stdin"], input=PASSWORD + "\n", text=True, env=env, check=True, capture_output=True)
        cls.server = subprocess.Popen([sys.executable, script, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/api/session" % cls.panel_port, timeout=1).read()
                break
            except OSError:
                time.sleep(0.2)
        services = json.dumps([{"name": "Customize", "services": [{"name": "Control panel", "id": "customize-card", "widgets": [{"type": "iframe", "src": "http://127.0.0.1:%d/" % cls.panel_port}]}]}])

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=cls.web, **k)

            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path.startswith("/api/services"):
                    body = services.encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                super().do_GET()

        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", cls.web_port), Quiet)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
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
        if getattr(cls, "httpd", None):
            cls.httpd.shutdown()
        cls.server.terminate()
        cls.server.wait(10)
        shutil.rmtree(cls.dir, True)

    @classmethod
    def reset(cls):
        for path, text in ((cls.services, SERVICES), (cls.settings, SETTINGS)):
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)

    def setUp(self):
        self.reset()
        self.errors = []

    def open(self, width=1200):
        ctx = self.browser.new_context(viewport={"width": width, "height": 900})
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.goto("http://127.0.0.1:%d/index.html" % self.web_port)
        page.wait_for_selector("#hl-editbar", state="attached")
        return page

    def btn(self, page, name):
        return page.locator("#hl-editbar").get_by_role("button", name=name, exact=True)

    def edit(self, page):
        self.btn(page, "Edit").click()
        frame = page.frame_locator("#hl-edit-bridge")
        frame.locator("input[type=password]").fill(PASSWORD)
        frame.locator("input[type=password]").press("Enter")
        page.wait_for_selector("html.hl-editing", timeout=15000)
        page.evaluate("document.getElementById('inner_wrapper').scrollTop = 0")

    def file_cards(self):
        with open(self.services, encoding="utf-8") as f:
            text = f.read()
        out, cur = {}, None
        for line in text.split("\n"):
            if line.startswith("- "):
                cur = line[2:].rstrip(":")
                out[cur] = []
            elif line.startswith("    - ") and cur:
                out[cur].append(line[6:].rstrip(":"))
        return out

    def file_groups(self):
        with open(self.settings, encoding="utf-8") as f:
            return [line.strip()[:-1] for line in f if line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(":")]

    def centre(self, page, selector):
        box = page.locator(selector).first.bounding_box()
        return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

    def drag(self, page, src, dst, grip=False):
        x, y = self.centre(page, src)
        page.mouse.move(x, y)
        page.mouse.down()
        tx, ty = self.centre(page, dst)
        page.mouse.move(x + 8, y + 8, steps=3)
        page.mouse.move(tx, ty, steps=14)
        page.mouse.up()

    def test_the_edit_button_is_there_on_a_desktop_and_gone_on_a_phone(self):
        page = self.open(1200)
        self.assertTrue(page.locator("#hl-editbar").is_visible())
        self.assertEqual(page.locator("#hl-editbar button:visible").all_inner_texts(), ["Edit"])
        page.set_viewport_size({"width": 600, "height": 900})
        self.assertFalse(page.locator("#hl-editbar").is_visible())

    def where(self, page):
        return page.evaluate("""() => { const b = document.getElementById('hl-editbar').getBoundingClientRect(), w = document.getElementById('inner_wrapper');
            return { top: b.top, right: b.right, bottom: b.bottom, width: window.innerWidth, height: window.innerHeight, scroll: w.scrollTop, host: document.getElementById('hl-editbar').parentNode.tagName }; }""")

    def assert_bottom_right(self, page, note):
        at = self.where(page)
        self.assertEqual(at["host"], "BODY", note)
        self.assertTrue(at["height"] - 40 < at["bottom"] <= at["height"], "%s: %s" % (note, at))
        self.assertTrue(at["width"] - 40 < at["right"] <= at["width"], "%s: %s" % (note, at))

    def test_the_edit_button_stays_in_the_bottom_right_corner_while_the_page_scrolls(self):
        page = self.open()
        for top in (0, 400, 1e6):
            page.evaluate("t => { document.getElementById('inner_wrapper').scrollTop = t; }", top)
            self.assert_bottom_right(page, "button, scrolled to %s" % top)

    def test_while_editing_the_bar_stays_in_the_bottom_right_corner_wherever_the_page_is_scrolled(self):
        page = self.open()
        self.edit(page)
        for top in (0, 300, 1e6):
            page.evaluate("t => { document.getElementById('inner_wrapper').scrollTop = t; }", top)
            self.assert_bottom_right(page, "bar, scrolled to %s" % top)

    def test_dragging_near_the_bottom_edge_scrolls_the_page(self):
        page = self.open()
        self.edit(page)
        x, y = self.centre(page, "#tailscale-card")
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 8, y + 8, steps=3)
        page.mouse.move(x, 880, steps=6)
        for _ in range(12):
            page.mouse.move(x, 884)
        page.mouse.up()
        self.assertGreater(self.where(page)["scroll"], 100)

    def test_jellyfin_and_navidrome_can_swap_places_while_their_frames_are_on_the_page(self):
        page = self.open(1400)
        page.evaluate("""() => { for (const id of ['navidrome-card', 'jellyfin-card']) { const c = document.getElementById(id).querySelector('.service-card'), d = document.createElement('div');
            d.innerHTML = '<iframe src="/index.html#x" style="height:200px;width:100%"></iframe>'; c.appendChild(d); } }""")
        self.edit(page)
        self.assertGreater(page.locator("#hl-jf-frame iframe").count(), 0, "the Jellyfin library is open over its card, as it is on the real page")
        self.drag(page, "#navidrome-card", "#jellyfin-card")
        self.assertEqual(page.locator(".services-group:has(#navidrome-card) li.service").evaluate_all("els => els.map(e => e.getAttribute('data-name'))"), ["Jellyfin", "Navidrome"])
        self.btn(page, "Save").click()
        for _ in range(60):
            if self.file_cards()["Media & Entertainment"] == ["Jellyfin", "Navidrome"]:
                break
            time.sleep(0.2)
        self.assertEqual(self.file_cards()["Media & Entertainment"], ["Jellyfin", "Navidrome"])
        self.assertEqual(self.errors, [])

    def test_the_edit_button_appears_when_homepage_draws_the_groups_after_the_script_ran(self):
        page = self.open()
        html = page.evaluate("(() => { const b = document.getElementById('layout-groups'); const h = b.innerHTML; b.innerHTML = ''; return h; })()")
        page.wait_for_function("document.getElementById('hl-editbar').hidden === false ? false : true")
        self.assertFalse(page.locator("#hl-editbar").is_visible())
        page.evaluate("h => { document.getElementById('layout-groups').innerHTML = h; }", html)
        self.btn(page, "Edit").wait_for(state="visible", timeout=5000)

    def test_logging_in_starts_edit_mode_and_only_cards_that_can_move_get_a_handle(self):
        page = self.open()
        self.edit(page)
        self.assertEqual(page.locator("#hl-editbar button:visible").all_inner_texts(), ["Save", "Cancel"])
        self.assertTrue(self.btn(page, "Save").is_disabled())
        self.assertEqual(page.locator("li.service .hl-cgrip").count(), 6)
        self.assertEqual(page.locator(".services-group > .hl-ggrip").count(), 2, "the group with Navidrome stays at the top and has no handle")
        self.assertEqual(self.errors, [])

    def test_a_card_dragged_into_another_group_is_saved_there(self):
        page = self.open()
        self.edit(page)
        self.drag(page, "#tailscale-card", "#nextcloud-card")
        self.assertEqual(page.locator(".services-group:has(#immich-card) li.service").evaluate_all("els => els.map(e => e.getAttribute('data-name'))"), ["Immich", "Tailscale", "Nextcloud"])
        self.assertTrue(self.btn(page, "Save").is_enabled())
        before = self.file_cards()
        self.assertEqual(before["Network & DNS"], ["Tailscale", "AdGuard Home"])
        self.btn(page, "Save").click()
        for _ in range(60):
            if self.file_cards() != before:
                break
            time.sleep(0.2)
        self.assertEqual(self.file_cards()["Network & DNS"], ["AdGuard Home"])
        self.assertEqual(self.file_cards()["Files & Photos"], ["Immich", "Tailscale", "Nextcloud"])
        self.btn(page, "Edit").wait_for(state="visible", timeout=10000)
        self.assertEqual(self.errors, [])

    def test_a_group_dragged_past_another_changes_the_order_on_its_tab(self):
        page = self.open()
        self.edit(page)
        self.drag(page, ".services-group:has(#tailscale-card) > .hl-ggrip", ".services-group:has(#nextcloud-card) li.service >> nth=1")
        self.btn(page, "Save").click()
        for _ in range(60):
            if self.file_groups()[0] != "Network & DNS":
                break
            time.sleep(0.2)
        self.assertEqual(self.file_groups(), ["Files & Photos", "Network & DNS", "Media & Entertainment", "Customize"])

    def test_the_arrow_keys_move_a_card_and_cancel_leaves_the_files_alone(self):
        page = self.open()
        self.edit(page)
        page.focus("#tailscale-card .hl-cgrip")
        page.keyboard.press("ArrowDown")
        self.assertEqual(page.locator(".services-group:has(#tailscale-card) li.service").evaluate_all("els => els.map(e => e.getAttribute('data-name'))"), ["AdGuard Home", "Tailscale"])
        self.assertTrue(self.btn(page, "Save").is_enabled())
        self.btn(page, "Cancel").click()
        self.assertEqual(page.locator("#hl-editbar button:visible").all_inner_texts(), ["Save", "Discard changes?"])
        self.btn(page, "Discard changes?").click()
        self.btn(page, "Edit").wait_for(state="visible", timeout=10000)
        self.assertEqual(self.file_cards()["Network & DNS"], ["Tailscale", "AdGuard Home"])

    def test_a_click_on_a_card_does_not_open_it_in_edit_mode(self):
        page = self.open()
        self.edit(page)
        page.click("#tailscale-card a", force=True)
        page.wait_for_timeout(500)
        self.assertTrue(page.url.endswith("/index.html"))
        self.assertEqual(len(page.context.pages), 1)

    def test_the_panel_copy_ignores_messages_when_it_is_not_inside_the_dashboard(self):
        ctx = self.browser.new_context()
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.goto("http://127.0.0.1:%d/?only=edit" % self.panel_port)
        page.wait_for_selector("input[type=password]")
        got = page.evaluate("""() => new Promise(resolve => {
            let seen = null;
            window.addEventListener("message", e => { if (e.data && e.data.type === "edit-reply") seen = e.data; });
            window.postMessage({ hle: 1, id: 1, op: "state" }, "*");
            setTimeout(() => resolve(seen), 800);
        })""")
        self.assertIsNone(got)


if __name__ == "__main__":
    unittest.main()
