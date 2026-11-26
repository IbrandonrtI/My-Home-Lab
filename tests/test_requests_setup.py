"""The request apps (Seerr, Radarr, Sonarr, qBittorrent): the folders, the stack file and the linking, run against small fake copies of the four apps' web interfaces.
What the real apps do is not tested here; these check that the installer sends what their documented interfaces ask for."""
import http.server
import json
import os
import re
import threading
import unittest
import urllib.parse
from unittest import mock

import helpers

KEYS = {"radarr": "r" * 32, "sonarr": "s" * 32}


class Fake(http.server.BaseHTTPRequestHandler):
    """One fake app. `state` holds what it was sent and how it should answer."""

    def log_message(self, *args):
        pass

    def reply(self, code, body, headers=None):
        raw = body if isinstance(body, str) else json.dumps(body)
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(raw.encode())))
        self.end_headers()
        self.wfile.write(raw.encode())

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n).decode()

    def do_GET(self):
        self.go("GET")

    def do_POST(self):
        self.go("POST")

    def do_PUT(self):
        self.go("PUT")

    def go(self, method):
        s, path = self.server.state, self.path.split("?")[0]
        raw = self.body()
        s["log"].append((method, self.path, raw, dict(self.headers)))
        app = s["app"]
        if app == "qbittorrent":
            return self.qbit(method, path, raw)
        if app == "seerr":
            return self.seerr(method, path, raw)
        return self.servarr(method, path, raw)

    def qbit(self, method, path, raw):
        s = self.server.state
        if path == "/":
            return self.reply(200, "ok")
        if path == "/api/v2/auth/login":
            f = dict(urllib.parse.parse_qsl(raw))
            if (f["username"], f["password"]) in s["logins"]:
                return self.reply(200, "Ok.", {"Set-Cookie": "SID=abc123; HttpOnly; path=/"})
            return self.reply(200, "Fails.")
        if path == "/api/v2/app/setPreferences" and "SID=abc123" in self.headers.get("Cookie", ""):
            s["prefs"] = json.loads(dict(urllib.parse.parse_qsl(raw))["json"])
            return self.reply(200, "")
        self.reply(403, "")

    def servarr(self, method, path, raw):
        s = self.server.state
        if path == "/ping":
            return self.reply(200, {"status": "OK"})
        if self.headers.get("X-Api-Key") != KEYS[s["app"]]:
            return self.reply(401, {})
        if path.startswith("/api/v3/config/host"):
            if method == "PUT":
                if path != "/api/v3/config/host/1":
                    return self.reply(404, {})
                s["host"] = json.loads(raw)
                return self.reply(202, s["host"])
            return self.reply(200, {"id": 1, "authenticationMethod": "none", "port": 7878})
        if path == "/api/v3/rootfolder":
            if method == "POST":
                s["roots"].append(json.loads(raw))
                return self.reply(201, {})
            return self.reply(200, s["roots"])
        if path == "/api/v3/downloadclient/schema":
            return self.reply(200, [{"implementation": "Deluge", "fields": []}, {"implementation": "QBittorrent", "configContract": "QBittorrentSettings",
                                    "fields": [{"name": n, "value": None} for n in ("host", "port", "useSsl", "username", "password", "movieCategory", "tvCategory")]}])
        if path == "/api/v3/downloadclient":
            if method == "POST":
                s["clients"].append(json.loads(raw))
                return self.reply(201, {})
            return self.reply(200, s["clients"])
        if path == "/api/v3/qualityprofile":
            return self.reply(200, [{"id": 1, "name": "Any"}, {"id": 4, "name": "HD-1080p"}])
        self.reply(404, {})

    def seerr(self, method, path, raw):
        s = self.server.state
        if path == "/api/v1/status":
            return self.reply(200, {"version": "x"})
        if path == "/api/v1/settings/public":
            return self.reply(200, {"initialized": s["initialized"]})
        if path == "/api/v1/auth/jellyfin":
            body = json.loads(raw)
            if s["need_email"] and "email" not in body:
                return self.reply(400, {"message": "NO_EMAIL"})
            s["login"] = body
            return self.reply(200, {"id": 1}, {"Set-Cookie": "connect.sid=sess1; Path=/; HttpOnly"})
        if "connect.sid=sess1" not in self.headers.get("Cookie", ""):
            return self.reply(403, {})
        if path == "/api/v1/settings/jellyfin/library":
            return self.reply(200, [{"id": "lib1", "name": "Movies", "enabled": False}, {"id": "lib2", "name": "Shows", "enabled": False}])
        if path in ("/api/v1/settings/radarr", "/api/v1/settings/sonarr"):
            s.setdefault("services", {})[path.rsplit("/", 1)[1]] = json.loads(raw)
            return self.reply(201, {})
        if path == "/api/v1/settings/initialize":
            s["initialized"] = True
            return self.reply(201, {})
        self.reply(404, {})


def serve(app, **extra):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    srv.state = dict({"app": app, "log": [], "roots": [], "clients": [], "initialized": False, "need_email": False, "logins": []}, **extra)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class RequestsSetup(unittest.TestCase):
    def setUp(self):
        self.m = helpers.installer()
        m = self.m
        self.apps = {"qbittorrent": serve("qbittorrent", logins=[("admin", "temp-pass")]), "radarr": serve("radarr"), "sonarr": serve("sonarr"), "seerr": serve("seerr")}
        for srv in self.apps.values():
            self.addCleanup(srv.shutdown)
            self.addCleanup(srv.server_close)
        ports = {a: srv.server_address[1] for a, srv in self.apps.items()}
        for patcher in (mock.patch.dict(m.PORTS, dict(ports, jellyfin=8096)), mock.patch.object(m, "HOST_OVERRIDE", "127.0.0.1"),
                        mock.patch.object(m.State, "data", {}), mock.patch.object(m.State, "save", lambda *a, **k: None),
                        mock.patch.object(m.Runtime, "password", "Secret-pass-1"), mock.patch.object(m.Ctx, "admin", "brandon"),
                        mock.patch.object(m.Ctx, "home", "/home/brandon"), mock.patch.object(m, "docker", lambda *a, **k: (0, "A temporary password is provided for this session: temp-pass"))):
            patcher.start()
            self.addCleanup(patcher.stop)
        for app in ("radarr", "sonarr"):
            folder = m.P("/home/brandon/requests/" + app)
            os.makedirs(folder, exist_ok=True)
            with open(folder + "/config.xml", "w") as f:
                f.write("<Config><ApiKey>%s</ApiKey></Config>" % KEYS[app])
        m.State.data["requests"] = True
        self.step = m.BY_ID["requests-links"]

    def sent(self, app, method, path):
        return [json.loads(r[2]) if r[2].startswith("{") else r[2] for r in self.apps[app].state["log"] if r[0] == method and r[1].split("?")[0] == path]

    def test_every_app_is_linked(self):
        self.assertEqual(self.step.probe(), "todo")
        self.step.run()
        self.assertEqual(self.step.probe(), "done")
        q = self.apps["qbittorrent"].state["prefs"]
        self.assertEqual((q["web_ui_username"], q["web_ui_password"], q["save_path"]), ("brandon", "Secret-pass-1", "/data/downloads"))
        for app, root in (("radarr", "/data/movies"), ("sonarr", "/data/shows")):
            host = self.apps[app].state["host"]
            self.assertEqual((host["authenticationMethod"], host["authenticationRequired"], host["username"], host["password"]), ("forms", "enabled", "brandon", "Secret-pass-1"))
            self.assertEqual(self.apps[app].state["roots"], [{"path": root}])
            fields = {f["name"]: f["value"] for f in self.apps[app].state["clients"][0]["fields"]}
            self.assertEqual((fields["host"], fields["port"], fields["username"], fields["password"]), ("qbittorrent", self.m.PORTS["qbittorrent"], "brandon", "Secret-pass-1"))
            self.assertEqual(self.apps[app].state["clients"][0]["implementation"], "QBittorrent")
        seerr = self.apps["seerr"].state
        self.assertEqual((seerr["login"]["username"], seerr["login"]["password"], seerr["login"]["hostname"], seerr["login"]["port"]), ("brandon", "Secret-pass-1", "127.0.0.1", 8096))
        self.assertIn("enable=lib1,lib2", [r[1] for r in seerr["log"] if "enable=" in r[1]][0])
        movies, shows = seerr["services"]["radarr"], seerr["services"]["sonarr"]
        self.assertEqual((movies["hostname"], movies["port"], movies["apiKey"], movies["activeProfileId"], movies["activeDirectory"], movies["isDefault"]),
                         ("radarr", self.apps["radarr"].server_address[1], KEYS["radarr"], 4, "/data/movies", True))
        self.assertEqual((shows["hostname"], shows["apiKey"], shows["activeDirectory"], shows["enableSeasonFolders"]), ("sonarr", KEYS["sonarr"], "/data/shows", True))
        self.assertTrue(seerr["initialized"])

    def test_seerr_is_asked_to_use_an_address_the_container_can_reach(self):
        self.step.run()
        self.assertEqual(self.apps["seerr"].state["services"]["radarr"]["hostname"], "radarr")
        self.assertEqual(self.apps["radarr"].state["clients"][0]["fields"][0]["value"], "qbittorrent")

    def test_a_part_that_fails_is_reported_and_only_that_part_is_retried(self):
        self.apps["qbittorrent"].state["logins"] = []
        with self.assertRaises(self.m.Abort) as cm:
            self.step.run()
        self.assertIn("qBittorrent", str(cm.exception))
        self.assertEqual(self.step.probe(), "todo")
        self.assertEqual(self.m.State.data["requests_linked"], {"radarr": True, "sonarr": True, "seerr": True})
        self.apps["qbittorrent"].state["logins"] = [("admin", "temp-pass")]
        before = len(self.apps["radarr"].state["log"])
        self.step.run()
        self.assertEqual(len(self.apps["radarr"].state["log"]), before)
        self.assertEqual(self.step.probe(), "done")

    def test_a_second_run_after_a_reset_does_not_add_a_second_download_client(self):
        self.step.run()
        self.m.State.data["requests_linked"] = {}
        self.step.run()
        self.assertEqual(len(self.apps["radarr"].state["clients"]), 1)
        self.assertEqual(len(self.apps["radarr"].state["roots"]), 1)

    def test_the_login_is_accepted_when_qbittorrent_was_already_set(self):
        self.apps["qbittorrent"].state["logins"] = [("brandon", "Secret-pass-1")]
        self.step.run()
        self.assertEqual(self.step.probe(), "done")

    def test_a_seerr_that_is_already_set_up_is_left_alone(self):
        self.apps["seerr"].state["initialized"] = True
        self.step.run()
        self.assertEqual([r for r in self.apps["seerr"].state["log"] if r[0] == "POST"], [])

    def test_seerr_gets_an_address_for_the_email_when_it_asks(self):
        self.apps["seerr"].state["need_email"] = True
        self.step.run()
        self.assertEqual(self.apps["seerr"].state["login"]["email"], "brandon@localhost")

    def test_a_dry_run_changes_nothing(self):
        with mock.patch.object(self.m.Opt, "dry", True):
            self.step.run()
        self.assertEqual([r for a in self.apps.values() for r in a.state["log"]], [])


class RequestsFilesAndCommand(unittest.TestCase):
    def setUp(self):
        self.m = helpers.installer()
        patcher = mock.patch.object(self.m.State, "data", {"requests": True})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.m.Ctx.home = "/home/test"
        self.m.Ctx.uid = self.m.Ctx.gid = 1000

    def test_the_stack_file_has_this_machines_values(self):
        text = self.m.stack_text("requests")
        self.assertNotIn("your-username", text)
        self.assertIn("/home/test/requests/radarr:/config", text)
        self.assertEqual(re.findall(r'PUID: "(\d+)"', text), ["1000"] * 3)

    def test_ports_in_the_stack_file_match_the_installer(self):
        with open(os.path.join(helpers.ROOT, "stacks", "requests.yaml")) as f:
            text = f.read()
        for app in ("seerr", "radarr", "sonarr", "qbittorrent"):
            self.assertIn('"%d:%d"' % (self.m.PORTS[app], self.m.PORTS[app]), text)
        self.assertEqual(self.m.STACKS["requests"][1], ["seerr", "radarr", "sonarr", "qbittorrent"])

    def test_the_folders_are_made_once(self):
        step = self.m.BY_ID["requests-folders"]
        self.assertEqual(step.probe(), "todo")
        step.run()
        self.assertEqual(step.probe(), "done")
        self.assertTrue(os.path.isdir(self.m.P("/mnt/storage/downloads")))

    def test_the_steps_only_apply_once_the_person_asks_for_them(self):
        self.m.State.data.pop("requests")
        for sid in ("requests-folders", "stack-requests", "requests-links"):
            self.assertFalse(self.m.BY_ID[sid].applies(), sid)

    def test_the_command_is_known_everywhere(self):
        with open(os.path.join(helpers.ROOT, "installer", "homelab-setup")) as f:
            text = f.read()
        self.assertIn('elif cmd == "requests"', text)
        self.assertIn('"navilist", "requests", "lastfm"', text)
        self.assertIn("  requests                 set up Seerr", text)


if __name__ == "__main__":
    unittest.main()
