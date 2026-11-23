"""The "Jellyfin look" installer step, run against a small pretend Jellyfin server."""
import http.server
import json
import socketserver
import threading
import unittest
import urllib.parse

import helpers

STATE = {}


def reset(**kw):
    STATE.clear()
    STATE.update(css="", repos=[], plugins={}, pending=[], libs=[], prefs={"CustomPrefs": {"x": "1"}}, log=[], nobuild=False, version="12.4.0")
    STATE.update(kw)


class FakeJellyfin(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, obj=None):
        b = json.dumps(obj).encode() if obj is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"null") if n else None

    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if "Token=" not in (self.headers.get("Authorization") or "") and p != "/System/Info/Public":
            return self.send(401)
        if p == "/System/Info/Public":
            return self.send(200, {"Version": STATE["version"], "StartupWizardCompleted": True})
        if p == "/Plugins":
            return self.send(200, [{"Name": n, "Status": st} for n, st in STATE["plugins"].items()])
        if p == "/Repositories":
            return self.send(200, STATE["repos"])
        if p == "/Packages":
            return self.send(200, [{"name": "File Transformation", "guid": "g1"}, {"name": "Media Bar", "guid": "g2"}, {"name": "Other", "guid": "g3"}])
        if p == "/System/Configuration/branding":
            return self.send(200, {"LoginDisclaimer": "", "CustomCss": STATE["css"], "SplashscreenEnabled": False})
        if p == "/Library/VirtualFolders":
            return self.send(200, STATE["libs"])
        if p == "/Users":
            return self.send(200, [{"Name": "Brandon", "Id": "u1"}])
        if p.startswith("/DisplayPreferences/"):
            return self.send(200, STATE["prefs"])
        self.send(404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        p, q, b = u.path, urllib.parse.parse_qs(u.query), self.body()
        STATE["log"].append(p)
        if p == "/Repositories":
            STATE["repos"] = b
            return self.send(204)
        if p.startswith("/Packages/Installed/"):
            if STATE["nobuild"]:
                return self.send(404)
            STATE["pending"].append(urllib.parse.unquote(p.rsplit("/", 1)[1]))
            return self.send(204)
        if p == "/System/Restart":
            for n in STATE["pending"]:
                STATE["plugins"][n] = "Active"
            STATE["pending"] = []
            return self.send(204)
        if p == "/System/Configuration/branding":
            STATE["css"] = b["CustomCss"]
            return self.send(204)
        if p == "/Library/VirtualFolders":
            STATE["libs"].append({"Name": q["name"][0], "Locations": q["paths"], "CollectionType": q["collectionType"][0]})
            return self.send(204)
        if p.startswith("/DisplayPreferences/"):
            STATE["prefs"] = b
            return self.send(204)
        self.send(404)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class JellyfinLookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = helpers.installer()
        cls.srv = Server(("127.0.0.1", 0), FakeJellyfin)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.m.PORTS["jellyfin"] = cls.srv.server_address[1]
        cls.m.Ctx.admin = "Brandon"
        cls.m.State.data.setdefault("notes", {})
        cls.m.State.data.setdefault("ran", {})
        cls.step = cls.m.BY_ID["jellyfin-look"]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        reset()
        self.m.State.data.pop("jellyfin_look", None)
        self.m.Secrets.vals["JELLYFIN_HOMEPAGE_KEY"] = "key123"
        self.m.Opt.dry = False

    def test_step_is_optional_and_waits_for_the_widget(self):
        self.assertTrue(self.step.optional)
        self.assertEqual(self.step.needs, ("w-jellyfin",))
        self.assertEqual(self.step.probe(), "todo")

    def test_fresh_server_gets_everything(self):
        self.step.run()
        self.assertEqual(STATE["plugins"], {"File Transformation": "Active", "Media Bar": "Active"})
        installs = [p for p in STATE["log"] if p.startswith("/Packages")]
        self.assertEqual(installs, ["/Packages/Installed/File%20Transformation", "/Packages/Installed/Media%20Bar"], "File Transformation must come first")
        self.assertEqual([r["Url"] for r in STATE["repos"]], [self.m.JELLYFIN_PLUGIN_REPO[1]])
        self.assertEqual(STATE["log"].count("/System/Restart"), 1)
        libs = sorted((x["Name"], x["CollectionType"], x["Locations"][0]) for x in STATE["libs"])
        self.assertEqual(libs, [("Movies", "movies", "/media/movies"), ("Shows", "tvshows", "/media/shows")])
        self.assertEqual(STATE["prefs"]["CustomPrefs"], {"x": "1", "enableBackdrops": "true", "detailsBanner": "true"})
        self.assertEqual((self.step.probe(), self.step.detail()), ("done", ""))

    def test_theme_has_slideshow_and_the_dashboard_box_rule_last(self):
        self.step.run()
        css = STATE["css"]
        self.assertIn("colors/jellyflix.css", css)
        self.assertIn("slideshow.css", css)
        self.assertEqual(css.count("@import"), 9)
        self.assertGreater(css.index("@media"), css.rindex("@import"), "an @import must come before any other rule or Jellyfin ignores it")
        self.assertTrue(css.rstrip().endswith("--slideshow-height: 0px; } }"))

    def test_running_again_changes_nothing(self):
        self.step.run()
        before = len(STATE["log"])
        self.m.State.data.pop("jellyfin_look")
        self.step.run()
        again = STATE["log"][before:]
        self.assertEqual([p for p in again if p in ("/Repositories", "/System/Restart", "/Library/VirtualFolders") or p.startswith("/Packages")], [])
        self.assertEqual(len(STATE["libs"]), 2)
        self.assertNotIn("/System/Configuration/branding", again, "a theme that is already there is not written again")

    def test_own_css_is_never_replaced(self):
        reset(css="body { color: red }")
        self.step.run()
        self.assertEqual(STATE["css"], "body { color: red }")

    def test_no_plugin_build_leaves_the_slideshow_out_and_retries_after_an_update(self):
        reset(nobuild=True)
        self.step.run()
        self.assertEqual(STATE["log"].count("/System/Restart"), 0)
        self.assertNotIn("slideshow.css", STATE["css"])
        self.assertEqual(STATE["css"].count("@import"), 8)
        self.assertNotIn("@media", STATE["css"])
        self.assertEqual(self.step.probe(), "done")
        self.assertIn("not available", self.step.detail())
        STATE["version"] = "12.5.0"
        self.assertEqual(self.step.probe(), "todo")

    def test_missing_key_stops_with_advice(self):
        self.m.Secrets.vals["JELLYFIN_HOMEPAGE_KEY"] = ""
        with self.assertRaises(self.m.Abort) as ctx:
            self.step.run()
        self.assertIn("key", str(ctx.exception).lower())

    def test_dry_run_touches_nothing(self):
        self.m.Opt.dry = True
        try:
            self.step.run()
        finally:
            self.m.Opt.dry = False
        self.assertEqual(STATE["log"], [])


if __name__ == "__main__":
    unittest.main()
