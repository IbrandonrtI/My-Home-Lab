"""The request apps (Seerr, Radarr, Sonarr, Prowlarr, FlareSolverr, qBittorrent): the folders, the stack file and the linking, run against small fake copies of the apps' web interfaces.
What the real apps do is not tested here; these check that the installer sends what their documented interfaces ask for."""
import http.server
import json
import os
import re
import shutil
import threading
import unittest
import urllib.parse
from unittest import mock

import helpers

KEYS = {"radarr": "r" * 32, "sonarr": "s" * 32, "prowlarr": "p" * 32}


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

    def do_DELETE(self):
        self.go("DELETE")

    def go(self, method):
        s, path = self.server.state, self.path.split("?")[0]
        raw = self.body()
        s["log"].append((method, self.path, raw, dict(self.headers)))
        app = s["app"]
        if app == "qbittorrent":
            return self.qbit(method, path, raw)
        if app == "seerr":
            return self.seerr(method, path, raw)
        if app == "flaresolverr":
            return self.reply(200, {"msg": "FlareSolverr is ready!"})
        return self.servarr(method, path, raw)

    def qbit(self, method, path, raw):
        s = self.server.state
        if path == "/":
            return self.reply(200, "ok")
        if path == "/api/v2/auth/login":
            f = dict(urllib.parse.parse_qsl(raw))
            if s.get("blocked"):
                return self.reply(403, "Your IP address has been banned after too many failed authentication attempts.")
            if (f["username"], f["password"]) in s["logins"]:
                cookie = {"Set-Cookie": "%s; HttpOnly; SameSite=Lax; expires=Thu, 26-Nov-2026 03:57:57 GMT; path=/" % getattr(self.server, "cookie", "QBT_SID_8085=abc123")}
                return self.reply(200, "Ok.", cookie) if getattr(self.server, "old_reply", False) else self.reply(204, "", cookie)
            return self.reply(200, "Fails.")
        if path == "/api/v2/app/setPreferences" and "=abc123" in self.headers.get("Cookie", ""):
            s["prefs"] = json.loads(dict(urllib.parse.parse_qsl(raw))["json"])
            return self.reply(200, "")
        self.reply(403, "")

    def servarr(self, method, path, raw):
        s = self.server.state
        if path == "/ping":
            return self.reply(200, {"status": "OK"})
        if self.headers.get("X-Api-Key") != KEYS[s["app"]]:
            return self.reply(401, {})
        if s["app"] == "prowlarr":
            if not path.startswith("/api/v1/"):
                return self.reply(404, {})
            path = path.replace("/api/v1/", "/api/v3/", 1)
            if path == "/api/v3/applications/schema":
                return self.reply(200, [{"implementation": n, "fields": [{"name": f, "value": None} for f in ("prowlarrUrl", "baseUrl", "apiKey", "syncCategories")]} for n in ("Lidarr", "Radarr", "Sonarr")])
            if path == "/api/v3/applications":
                if method == "POST":
                    s["clients"].append(dict(json.loads(raw), id=len(s["clients"]) + 1))
                    return self.reply(201, {})
                return self.reply(200, s["clients"])
            if path == "/api/v3/tag":
                if method == "POST":
                    if s.get("refuse_tag"):
                        return self.reply(400, [{"errorMessage": "no tags today"}])
                    tag = dict(json.loads(raw), id=len(s.setdefault("tags", [])) + 11)
                    s["tags"].append(tag)
                    return self.reply(201, tag)
                return self.reply(200, s.get("tags", []))
            if path == "/api/v3/indexerproxy/schema":
                return self.reply(200, [{"implementation": "Http", "fields": []}, {"implementation": "FlareSolverr", "configContract": "FlareSolverrSettings",
                                        "fields": [{"name": "host", "value": "http://localhost:8191/"}, {"name": "requestTimeout", "value": 60}], "tags": []}])
            if path == "/api/v3/indexerproxy":
                if method == "POST":
                    if s.get("refuse_proxy") and "forceSave" not in self.path:
                        return self.reply(400, [{"errorMessage": "Unable to connect"}])
                    s.setdefault("proxies", []).append(dict(json.loads(raw), id=len(s.get("proxies", [])) + 1))
                    return self.reply(201, {})
                return self.reply(200, s.get("proxies", []))
            if path.startswith("/api/v3/indexerproxy/") and method == "PUT":
                body = json.loads(raw)
                s["proxies"] = [body if str(p.get("id")) == path.rsplit("/", 1)[1] else p for p in s.get("proxies", [])]
                return self.reply(202, body)
            if path.startswith("/api/v3/applications/") and method == "DELETE":
                s["clients"] = [c for c in s["clients"] if str(c.get("id")) != path.rsplit("/", 1)[1]]
                return self.reply(200, {})
        if path.startswith("/api/v3/config/host"):
            if method == "PUT":
                if path != "/api/v3/config/host/1":
                    return self.reply(404, {})
                s["host"] = json.loads(raw)
                return self.reply(202, s["host"])
            return self.reply(200, {"id": 1, "authenticationMethod": "none", "port": 7878})
        if path == "/api/v3/rootfolder":
            if method == "POST":
                if s.get("refuse_root"):
                    return self.reply(400, [{"propertyName": "Path", "errorMessage": s["refuse_root"]}])
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
            s["logins"].append(body)
            if s.get("refuse_login") or (s.get("refuse_minimal") and "hostname" not in body):
                return self.reply(500, {"message": "Jellyfin said no"})
            s["login"] = body
            return self.reply(200, {"id": 1}, {"Set-Cookie": "connect.sid=sess1; Path=/; HttpOnly"})
        if "connect.sid=sess1" not in self.headers.get("Cookie", ""):
            return self.reply(403, {})
        if path == "/api/v1/settings/jellyfin/library":
            return self.reply(200, [{"id": "lib1", "name": "Movies", "enabled": False}, {"id": "lib2", "name": "Shows", "enabled": False}])
        if path in ("/api/v1/settings/radarr", "/api/v1/settings/sonarr"):
            if method == "GET":
                return self.reply(200, [dict(s.get("services", {})[path.rsplit("/", 1)[1]], id=0)] if path.rsplit("/", 1)[1] in s.get("services", {}) else [])
            s.setdefault("services", {})[path.rsplit("/", 1)[1]] = json.loads(raw)
            return self.reply(201, {})
        if path == "/api/v1/settings/sonarr/0" and method == "DELETE":
            s.get("services", {}).pop("sonarr", None)
            return self.reply(200, {})
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
        self.apps = {"qbittorrent": serve("qbittorrent", logins=[("admin", "temp-pass")]), "radarr": serve("radarr"), "sonarr": serve("sonarr"), "prowlarr": serve("prowlarr"), "flaresolverr": serve("flaresolverr"), "seerr": serve("seerr")}
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
        for app in ("radarr", "sonarr", "prowlarr"):
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
        prowlarr = self.apps["prowlarr"].state
        self.assertEqual((prowlarr["host"]["authenticationMethod"], prowlarr["host"]["username"], prowlarr["host"]["password"]), ("forms", "brandon", "Secret-pass-1"))
        self.assertEqual([c["implementation"] for c in prowlarr["clients"]], ["Radarr", "Sonarr"])
        radarr_app = {f["name"]: f["value"] for f in prowlarr["clients"][0]["fields"]}
        self.assertEqual((radarr_app["prowlarrUrl"], radarr_app["baseUrl"], radarr_app["apiKey"]), ("http://prowlarr:%d" % self.m.PORTS["prowlarr"], "http://radarr:%d" % self.m.PORTS["radarr"], KEYS["radarr"]))
        self.assertEqual(prowlarr["clients"][0]["syncLevel"], "fullSync")
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

    def test_an_older_qbittorrent_answer_works_too(self):
        self.apps["qbittorrent"].cookie = "SID=abc123"
        self.apps["qbittorrent"].old_reply = True
        self.step.run()
        self.assertEqual(self.step.probe(), "done")

    def test_a_blocked_address_is_cleared_by_restarting_qbittorrent(self):
        state = self.apps["qbittorrent"].state
        state["blocked"] = True
        restarts = []

        def docker(*args, **kw):
            if args[0] == "restart":
                restarts.append(args)
                state["blocked"] = False
            return 0, "A temporary password is provided for this session: temp-pass"

        with mock.patch.object(self.m, "docker", docker):
            self.step.run()
        self.assertEqual(len(restarts), 1)
        self.assertEqual(self.step.probe(), "done")

    def test_the_apps_own_words_are_in_the_message_when_a_folder_is_refused(self):
        def refuse(app):
            self.apps[app].state["refuse_root"] = "Folder '/data/movies/' is not writable by user 'abc'"
        refuse("radarr")
        with self.assertRaises(self.m.Abort) as cm:
            self.step.run()
        self.assertIn("is not writable by user 'abc'", str(cm.exception))

    def test_a_part_that_fails_is_reported_and_only_that_part_is_retried(self):
        self.apps["qbittorrent"].state["logins"] = []
        with self.assertRaises(self.m.Abort) as cm:
            self.step.run()
        self.assertIn("qBittorrent", str(cm.exception))
        self.assertEqual(self.step.probe(), "todo")
        self.assertEqual(self.m.State.data["requests_linked"], {"radarr": True, "sonarr": True, "prowlarr": True, "flaresolverr": True, "seerr": True})
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

    def test_a_seerr_that_is_already_set_up_with_both_apps_is_left_alone(self):
        self.apps["seerr"].state["initialized"] = True
        self.apps["seerr"].state["services"] = {"radarr": {"name": "Radarr"}, "sonarr": {"name": "Sonarr"}}
        self.step.run()
        self.assertEqual([r for r in self.apps["seerr"].state["log"] if r[0] == "POST" and "/settings/" in r[1]], [])

    def test_seerr_gets_an_address_for_the_email_when_it_asks(self):
        self.apps["seerr"].state["need_email"] = True
        self.step.run()
        self.assertEqual(self.apps["seerr"].state["login"]["email"], "brandon@localhost")

    def test_an_older_install_without_prowlarr_only_links_prowlarr(self):
        self.m.State.data["requests_linked"] = {"qbittorrent": True, "radarr": True, "sonarr": True, "seerr": True}
        self.assertEqual(self.step.probe(), "todo")
        self.step.run()
        self.assertEqual(self.step.probe(), "done")
        for app in ("radarr", "sonarr", "seerr", "qbittorrent"):
            self.assertEqual([r for r in self.apps[app].state["log"] if r[0] != "GET"], [], app)

    def fs_host(self):
        return "http://flaresolverr:%d/" % self.m.PORTS["flaresolverr"]

    def test_flaresolverr_is_added_to_prowlarr_as_a_proxy_with_its_own_tag(self):
        self.step.run()
        prowlarr = self.apps["prowlarr"].state
        self.assertEqual([t["label"] for t in prowlarr["tags"]], ["flaresolverr"])
        (proxy,) = prowlarr["proxies"]
        fields = {f["name"]: f["value"] for f in proxy["fields"]}
        self.assertEqual((proxy["implementation"], proxy["name"], proxy["tags"], fields["host"], fields["requestTimeout"]),
                         ("FlareSolverr", "FlareSolverr", [prowlarr["tags"][0]["id"]], self.fs_host(), 60))

    def test_no_indexer_is_tagged_or_added(self):
        self.step.run()
        self.assertEqual([r for r in self.apps["prowlarr"].state["log"] if "/indexer" in r[1] and "indexerproxy" not in r[1]], [])

    def test_an_install_without_flaresolverr_only_gets_the_proxy(self):
        self.m.State.data["requests_linked"] = {"qbittorrent": True, "radarr": True, "sonarr": True, "prowlarr": True, "seerr": True}
        self.assertEqual(self.step.probe(), "todo")
        self.step.run()
        self.assertEqual(self.step.probe(), "done")
        for app in ("radarr", "sonarr", "seerr", "qbittorrent"):
            self.assertEqual([r for r in self.apps[app].state["log"] if r[0] != "GET"], [], app)
        self.assertEqual([r[0] + " " + r[1].split("?")[0] for r in self.apps["prowlarr"].state["log"] if r[0] != "GET"], ["POST /api/v1/tag", "POST /api/v1/indexerproxy"])

    def test_a_second_run_adds_no_second_tag_or_proxy(self):
        self.step.run()
        self.m.State.data["requests_linked"] = {}
        self.step.run()
        self.assertEqual(len(self.apps["prowlarr"].state["tags"]), 1)
        self.assertEqual(len(self.apps["prowlarr"].state["proxies"]), 1)

    def test_a_tag_that_is_already_there_is_used_and_not_made_again(self):
        self.apps["prowlarr"].state["tags"] = [{"id": 3, "label": "FlareSolverr"}]
        self.step.run()
        self.assertEqual(len(self.apps["prowlarr"].state["tags"]), 1)
        self.assertEqual(self.apps["prowlarr"].state["proxies"][0]["tags"], [3])

    def test_a_proxy_that_points_somewhere_else_is_pointed_at_the_container(self):
        self.apps["prowlarr"].state["proxies"] = [{"id": 1, "name": "FlareSolverr", "implementation": "FlareSolverr", "tags": [3],
                                                   "fields": [{"name": "host", "value": "http://172.17.0.3:8191/"}, {"name": "requestTimeout", "value": 90}]}]
        self.step.run()
        (proxy,) = self.apps["prowlarr"].state["proxies"]
        self.assertEqual({f["name"]: f["value"] for f in proxy["fields"]}, {"host": self.fs_host(), "requestTimeout": 90})
        self.assertEqual(proxy["tags"], [3])

    def test_a_proxy_that_is_already_right_is_left_alone(self):
        self.apps["prowlarr"].state["tags"] = [{"id": 3, "label": "my-tag"}]
        self.apps["prowlarr"].state["proxies"] = [{"id": 1, "name": "Mine", "implementation": "FlareSolverr", "tags": [3],
                                                   "fields": [{"name": "host", "value": self.fs_host()}]}]
        self.step.run()
        self.assertEqual([r for r in self.apps["prowlarr"].state["log"] if "indexerproxy" in r[1] and r[0] != "GET"], [])
        self.assertEqual(len(self.apps["prowlarr"].state["tags"]), 1)

    def test_prowlarr_saves_the_proxy_anyway_when_its_own_test_of_flaresolverr_fails(self):
        self.apps["prowlarr"].state["refuse_proxy"] = True
        self.step.run()
        self.assertEqual(len(self.apps["prowlarr"].state["proxies"]), 1)
        self.assertEqual(self.step.probe(), "done")

    def test_a_refused_tag_is_reported_by_name_and_the_other_parts_are_kept(self):
        self.apps["prowlarr"].state["refuse_tag"] = True
        with self.assertRaises(self.m.Abort) as cm:
            self.step.run()
        self.assertIn("FlareSolverr", str(cm.exception))
        self.assertEqual(self.step.probe(), "todo")
        self.assertEqual(self.m.State.data["requests_linked"], {"qbittorrent": True, "radarr": True, "sonarr": True, "prowlarr": True, "seerr": True})

    def linked_before_sonarr_came_back(self):
        """An install that was linked while Sonarr was out: Prowlarr and Seerr are set up with Radarr only."""
        self.step.run()
        self.apps["sonarr"].state["log"].clear()
        self.apps["prowlarr"].state["clients"] = [c for c in self.apps["prowlarr"].state["clients"] if c["implementation"] == "Radarr"]
        self.apps["seerr"].state["services"].pop("sonarr")
        self.m.State.data["requests_linked"] = {"qbittorrent": True, "radarr": True, "prowlarr": True, "seerr": True}

    def test_sonarr_is_linked_to_prowlarr_and_seerr_on_an_install_that_already_had_them_set_up(self):
        self.linked_before_sonarr_came_back()
        self.assertEqual(self.step.probe(), "todo")
        self.step.run()
        self.assertEqual(self.step.probe(), "done")
        self.assertEqual([c["implementation"] for c in self.apps["prowlarr"].state["clients"]], ["Radarr", "Sonarr"])
        shows = self.apps["seerr"].state["services"]["sonarr"]
        self.assertEqual((shows["hostname"], shows["apiKey"], shows["activeDirectory"]), ("sonarr", KEYS["sonarr"], "/data/shows"))
        self.assertEqual(self.apps["sonarr"].state["roots"], [{"path": "/data/shows"}])
        self.assertEqual(list(self.apps["seerr"].state["services"]), ["radarr", "sonarr"])

    def test_an_already_set_up_seerr_is_signed_in_to_with_only_the_login(self):
        self.linked_before_sonarr_came_back()
        self.step.run()
        self.assertEqual(sorted(self.apps["seerr"].state["logins"][-1]), ["password", "username"])

    def test_the_full_login_is_tried_when_the_short_one_is_refused(self):
        self.linked_before_sonarr_came_back()
        self.apps["seerr"].state["refuse_minimal"] = True
        self.step.run()
        self.assertIn("sonarr", self.apps["seerr"].state["services"])
        self.assertEqual(self.step.probe(), "done")

    def test_a_seerr_that_refuses_every_login_gets_a_note_and_the_rest_is_finished(self):
        self.linked_before_sonarr_came_back()
        self.apps["seerr"].state["refuse_login"] = True
        warned = []
        with mock.patch.object(self.m, "warn", warned.append):
            self.step.run()
        self.assertEqual(self.step.probe(), "done")
        self.assertEqual([c["implementation"] for c in self.apps["prowlarr"].state["clients"]], ["Radarr", "Sonarr"])
        self.assertNotIn("sonarr", self.apps["seerr"].state["services"])
        self.assertEqual(len(warned), 1)
        self.assertIn("Jellyfin said no", warned[0])
        self.assertIn("Add Sonarr there yourself", warned[0])

    def test_linking_sonarr_again_does_not_add_it_twice(self):
        self.linked_before_sonarr_came_back()
        self.step.run()
        self.m.State.data["requests_linked"] = {"qbittorrent": True, "radarr": True, "prowlarr": True, "seerr": True}
        self.step.run()
        self.assertEqual([c["implementation"] for c in self.apps["prowlarr"].state["clients"]], ["Radarr", "Sonarr"])
        self.assertEqual(len([r for r in self.apps["seerr"].state["log"] if r[0] == "POST" and r[1].endswith("/settings/sonarr")]), 2)  # once in the first setup, once when it came back; not a third time

    def test_folders_that_belong_to_someone_else_are_handed_to_the_lab_user(self):
        m = self.m
        for d in m.LIBRARY_FOLDERS:
            os.makedirs(m.P(d), exist_ok=True)
        with mock.patch.object(m, "FAKE", False), mock.patch.object(m.Ctx, "uid", os.getuid() + 1), mock.patch.object(m, "chown") as chown:
            step = m.BY_ID["requests-folders"]
            self.assertEqual(step.probe(), "todo")
            step.run()
        self.assertEqual({c.args[0] for c in chown.call_args_list} & {m.P(d) for d in m.LIBRARY_FOLDERS}, {m.P(d) for d in m.LIBRARY_FOLDERS})

    def test_a_dry_run_changes_nothing(self):
        with mock.patch.object(self.m.Opt, "dry", True):
            self.step.run()
        self.assertEqual([r for a in self.apps.values() for r in a.state["log"]], [])

    def older_install_with_jdownloader(self):
        """An install made before JDownloader was taken out: its container, its settings folder and the direct folder."""
        m = self.m
        os.makedirs(m.P("/home/brandon/requests/jdownloader"), exist_ok=True)
        open(m.P("/home/brandon/requests/jdownloader/settings"), "w").close()
        shutil.rmtree(m.P("/mnt/storage/downloads/direct"), ignore_errors=True)
        os.makedirs(m.P("/mnt/storage/downloads/direct"), exist_ok=True)
        self.addCleanup(shutil.rmtree, m.P("/mnt/storage/downloads/direct"), True)
        self.addCleanup(shutil.rmtree, m.P("/home/brandon/requests/jdownloader"), True)
        present, removed, forgotten = {"seerr", "radarr", "sonarr", "prowlarr", "jdownloader"}, [], []

        def fake_docker(*args, **kwargs):
            if args[:2] == ("rm", "-f"):
                removed.append(args[2])
                present.discard(args[2])
            return 0, ""

        for patcher in (mock.patch.object(m, "docker", fake_docker), mock.patch.object(m, "containers_all", lambda: set(present)),
                        mock.patch.object(m, "forget_card", forgotten.append)):
            patcher.start()
            self.addCleanup(patcher.stop)
        return removed, forgotten

    def test_jdownloader_is_removed_from_an_older_install_and_the_other_apps_are_not_touched(self):
        removed, forgotten = self.older_install_with_jdownloader()
        step = self.m.BY_ID["requests-retire"]
        self.assertEqual(step.probe(), "todo")
        step.run()
        self.assertEqual(removed, ["jdownloader"])
        self.assertEqual(forgotten, ["jdownloader"])
        self.assertFalse(os.path.exists(self.m.P("/home/brandon/requests/jdownloader")))
        self.assertFalse(os.path.exists(self.m.P("/mnt/storage/downloads/direct")))
        self.assertTrue(os.path.isdir(self.m.P("/home/brandon/requests/radarr")))
        self.assertTrue(os.path.isdir(self.m.P("/home/brandon/requests/sonarr")))
        self.assertEqual(step.probe(), "done")

    def test_a_direct_folder_with_files_in_it_is_kept(self):
        self.older_install_with_jdownloader()
        mine = self.m.P("/mnt/storage/downloads/direct/movie.mkv")
        open(mine, "w").close()
        self.m.BY_ID["requests-retire"].run()
        self.assertTrue(os.path.exists(mine))

    def test_nothing_is_done_when_jdownloader_was_never_there(self):
        with mock.patch.object(self.m, "containers_all", lambda: {"radarr", "sonarr"}):
            self.assertEqual(self.m.BY_ID["requests-retire"].probe(), "done")

    def test_sonarr_is_not_treated_as_a_leftover(self):
        self.assertNotIn("sonarr", self.m.REQUESTS_RETIRED)
        with mock.patch.object(self.m, "containers_all", lambda: {"sonarr"}):
            self.assertEqual(self.m.BY_ID["requests-retire"].probe(), "done")

    def test_a_dry_run_of_the_removal_changes_nothing(self):
        removed, forgotten = self.older_install_with_jdownloader()
        with mock.patch.object(self.m.Opt, "dry", True):
            self.m.BY_ID["requests-retire"].run()
        self.assertEqual((removed, forgotten), ([], []))
        self.assertTrue(os.path.isdir(self.m.P("/home/brandon/requests/jdownloader")))


class FlareSolverrByHand(unittest.TestCase):
    """A FlareSolverr container started by hand uses the name and the port the stack needs."""

    def setUp(self):
        self.m = helpers.installer()
        self.calls, self.present, self.project = [], {"flaresolverr", "radarr"}, ""

        def fake_docker(*args, **kw):
            self.calls.append(args)
            if args[0] == "inspect":
                return (0, self.project + "\n") if self.project is not None else (1, "")
            return 0, ""

        for patcher in (mock.patch.object(self.m, "docker", fake_docker), mock.patch.object(self.m, "containers_all", lambda: set(self.present)),
                        mock.patch.object(self.m.State, "data", {"requests": True}), mock.patch.object(self.m.State, "save", lambda *a, **k: None)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_a_container_without_the_stack_label_is_by_hand(self):
        self.assertTrue(self.m.handmade_flaresolverr())

    def test_the_stacks_own_container_is_not(self):
        self.project = "requests"
        self.assertFalse(self.m.handmade_flaresolverr())

    def test_nothing_is_removed_when_there_is_no_such_container_or_it_cannot_be_inspected(self):
        self.present = {"radarr"}
        self.assertFalse(self.m.handmade_flaresolverr())
        self.present, self.project = {"flaresolverr"}, None
        self.assertFalse(self.m.handmade_flaresolverr())

    def run_stack_step(self):
        order = []
        step = self.m.BY_ID["stack-requests"]
        with mock.patch.object(self.m.StackStep, "run", lambda *a, **k: order.append("deploy")), mock.patch.object(self.m, "wait_for", lambda *a, **k: True), \
                mock.patch.object(self.m, "run", lambda cmd, **k: order.append(" ".join(os.path.basename(c) for c in cmd)) or (0, "")):
            self.m.docker = lambda *a, **k: order.append("docker " + " ".join(a)) or ((0, self.project + "\n") if a[0] == "inspect" else (0, ""))
            step.run()
        return order

    def test_it_is_removed_before_the_stack_is_deployed(self):
        order = self.run_stack_step()
        self.assertEqual([o for o in order if o in ("deploy", "docker rm -f flaresolverr")], ["docker rm -f flaresolverr", "deploy"])

    def test_the_stacks_own_container_is_not_removed(self):
        self.project = "requests"
        self.assertNotIn("docker rm -f flaresolverr", self.run_stack_step())

    def test_a_dry_run_removes_nothing(self):
        with mock.patch.object(self.m.Opt, "dry", True):
            self.assertNotIn("docker rm -f flaresolverr", self.run_stack_step())

    def test_the_card_is_allowed_again_once_and_then_made(self):
        home = self.m.P("/usr/local/sbin/homelab-cards")
        os.makedirs(os.path.dirname(home), exist_ok=True)
        open(home, "w").close()
        self.addCleanup(os.remove, home)
        with mock.patch.object(self.m, "FAKE", False):
            first = self.run_stack_step()
            second = self.run_stack_step()
        self.assertEqual([o for o in first if o.startswith("homelab-cards")], ["homelab-cards unignore flaresolverr", "homelab-cards sync"])
        self.assertEqual([o for o in second if o.startswith("homelab-cards")], ["homelab-cards sync"])


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
        self.assertEqual(re.findall(r'PUID: "(\d+)"', text), ["1000"] * 4)

    def test_ports_in_the_stack_file_match_the_installer(self):
        with open(os.path.join(helpers.ROOT, "stacks", "requests.yaml")) as f:
            text = f.read()
        for app in ("seerr", "radarr", "sonarr", "prowlarr", "flaresolverr", "qbittorrent"):
            self.assertIn('"%d:%d"' % (self.m.PORTS[app], self.m.PORTS[app]), text)
        self.assertEqual(self.m.STACKS["requests"][1], ["seerr", "radarr", "sonarr", "prowlarr", "flaresolverr", "qbittorrent"])
        self.assertEqual(self.m.PORTS["flaresolverr"], 8191)
        self.assertNotIn("jdownloader", text)
        self.assertNotIn("jdownloader", self.m.PORTS)

    def test_the_dashboard_card_for_flaresolverr_gets_a_title_a_section_and_a_description(self):
        cards = helpers.load_script("homelab_cards", "scripts/homelab-cards")
        c = {"name": "flaresolverr", "image": "ghcr.io/flaresolverr/flaresolverr:latest", "project": "requests", "ports": [8191], "status": "running",
             "labels": {"org.opencontainers.image.title": "FlareSolverr"}}
        self.assertEqual(cards.guess_section(c), ("Media & Entertainment", True))
        self.assertEqual(cards.display_name(c), "FlareSolverr")
        self.assertEqual(cards.description_of(c, online=False), "Helps Prowlarr open protected indexers")

    def test_the_folders_are_made_once(self):
        step = self.m.BY_ID["requests-folders"]
        self.assertEqual(step.probe(), "todo")
        step.run()
        self.assertEqual(step.probe(), "done")
        self.assertTrue(os.path.isdir(self.m.P("/mnt/storage/downloads")))

    def test_the_steps_only_apply_once_the_person_asks_for_them(self):
        self.m.State.data.pop("requests")
        for sid in ("requests-folders", "stack-requests", "requests-links", "requests-retire"):
            self.assertFalse(self.m.BY_ID[sid].applies(), sid)

    def test_the_command_is_known_everywhere(self):
        with open(os.path.join(helpers.ROOT, "installer", "homelab-setup")) as f:
            text = f.read()
        self.assertIn('elif cmd == "requests"', text)
        self.assertIn('"navilist", "requests", "lastfm"', text)
        self.assertIn("  requests                 set up Seerr", text)


if __name__ == "__main__":
    unittest.main()
