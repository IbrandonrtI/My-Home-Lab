"""The request apps (Seerr, Radarr, Sonarr, qBittorrent): the folders, the stack file and the linking, run against small fake copies of the four apps' web interfaces.
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
                    s["clients"].append(json.loads(raw))
                    return self.reply(201, {})
                return self.reply(200, s["clients"])
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
        self.apps = {"qbittorrent": serve("qbittorrent", logins=[("admin", "temp-pass")]), "radarr": serve("radarr"), "sonarr": serve("sonarr"), "prowlarr": serve("prowlarr"), "seerr": serve("seerr")}
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
        self.assertEqual(self.m.State.data["requests_linked"], {"radarr": True, "sonarr": True, "prowlarr": True, "seerr": True})
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

    def test_an_older_install_without_prowlarr_only_links_prowlarr(self):
        self.m.State.data["requests_linked"] = {"qbittorrent": True, "radarr": True, "sonarr": True, "seerr": True}
        self.assertEqual(self.step.probe(), "todo")
        self.step.run()
        self.assertEqual(self.step.probe(), "done")
        for app in ("radarr", "sonarr", "seerr", "qbittorrent"):
            self.assertEqual([r for r in self.apps[app].state["log"] if r[0] != "GET"], [], app)

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
        for app in ("seerr", "radarr", "sonarr", "prowlarr", "qbittorrent", "jdownloader"):
            self.assertIn('"%d:%d"' % (self.m.PORTS[app], self.m.PORTS[app]), text)
        self.assertEqual(self.m.STACKS["requests"][1], ["seerr", "radarr", "sonarr", "prowlarr", "qbittorrent", "jdownloader"])

    def test_jdownloader_saves_into_its_own_folder_on_the_main_pool(self):
        text = self.m.stack_text("requests")
        self.assertIn("jlesage/jdownloader-2", text)
        self.assertIn("/mnt/storage/downloads/direct:/output", text)
        self.assertIn("/mnt/storage/movies:/movies", text)
        self.assertIn("/mnt/storage/shows:/shows", text)
        self.assertIn("/home/test/requests/jdownloader:/config", text)
        self.assertEqual(self.m.DIRECT_FOLDER, self.m.DOWNLOADS_FOLDER + "/direct")
        self.assertIn("jdownloader", self.m.REQUESTS_APPS)
        self.assertNotIn("jdownloader", self.m.REQUESTS_PARTS)

    def test_the_direct_folder_is_made_and_an_older_install_gets_it_too(self):
        for d in ("/mnt/storage/downloads", "/home/test/requests"):
            self.addCleanup(shutil.rmtree, self.m.P(d), True)
        step = self.m.BY_ID["requests-folders"]
        step.run()
        self.assertTrue(os.path.isdir(self.m.P("/mnt/storage/downloads/direct")))
        self.assertTrue(os.path.isdir(self.m.P("/home/test/requests/jdownloader")))
        os.rmdir(self.m.P("/mnt/storage/downloads/direct"))
        self.assertEqual(step.probe(), "todo")
        step.run()
        self.assertEqual(step.probe(), "done")

    def test_the_stack_waits_for_jdownloader_and_the_status_lists_it(self):
        asked = []
        with mock.patch.object(self.m, "requests_page_answers", lambda app: asked.append(app) or True):
            self.assertTrue(self.m.requests_all_answer())
        self.assertIn("jdownloader", asked)
        shown = []
        with mock.patch.object(self.m, "out", shown.append), mock.patch.object(self.m, "containers_running", lambda: {"jdownloader"}), \
                mock.patch.object(self.m, "url", lambda app, path="": "http://x/" + app):
            self.m.requests_status()
        line = [s for s in shown if "JDownloader" in s]
        self.assertEqual(len(line), 1)
        self.assertIn("running", line[0])
        self.assertNotIn("not linked", line[0])

    def test_the_folders_are_made_once(self):
        step = self.m.BY_ID["requests-folders"]
        self.assertEqual(step.probe(), "todo")
        step.run()
        self.assertEqual(step.probe(), "done")
        self.assertTrue(os.path.isdir(self.m.P("/mnt/storage/downloads")))

    def test_jdownloader_gets_a_card_in_the_media_section(self):
        cards = helpers.load_script("homelab_cards", "scripts/homelab-cards", {"HOMELAB_CARDS_OFFLINE": "1"})
        c = {"image": "jlesage/jdownloader-2:latest", "name": "jdownloader", "project": "requests", "labels": {"org.opencontainers.image.title": "JDownloader"}}
        self.assertEqual(cards.guess_section(c), ("Media & Entertainment", True))
        self.assertEqual(cards.display_name(c), "JDownloader")
        self.assertIn("jdownloader", cards.KNOWN_DESCRIPTIONS)

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
