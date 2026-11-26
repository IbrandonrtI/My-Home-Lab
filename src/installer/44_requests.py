# Requests: Seerr (where people ask for a movie or show), Radarr and Sonarr (which keep the lists), Prowlarr (which keeps the indexers for both) and qBittorrent (the download client).
# Installed only by `homelab-setup requests`. No indexers and no download sources are added.

REQUESTS_FOLDERS = ("requests", "requests/seerr", "requests/radarr", "requests/sonarr", "requests/prowlarr", "requests/qbittorrent")
DOWNLOADS_FOLDER = "/mnt/storage/downloads"
SEERR_UID = 1000
REQUESTS_ROOTS = {"radarr": "/data/movies", "sonarr": "/data/shows"}
REQUESTS_LABELS = {"seerr": "Seerr", "radarr": "Radarr", "sonarr": "Sonarr", "prowlarr": "Prowlarr", "qbittorrent": "qBittorrent"}
REQUESTS_PARTS = ("qbittorrent", "radarr", "sonarr", "prowlarr", "seerr")
SERVARR_API = {"prowlarr": "v1"}


def requests_applies():
    return requests_wanted() and BY_ID["stack-jellyfin"].applies()


def requests_page_answers(app):
    path = {"seerr": "/api/v1/status", "radarr": "/ping", "sonarr": "/ping", "prowlarr": "/ping", "qbittorrent": "/"}[app]
    return http("GET", url(app, path), timeout=10)[0] == 200


def requests_all_answer():
    return all(requests_page_answers(a) for a in REQUESTS_PARTS)


@step
class RequestsFolders(Step):
    id, group = "requests-folders", "Services"
    title = "Folders for the request apps, and the downloads folder on the Main pool"
    needs = ("folders",)

    def applies(self):
        return requests_applies()

    def probe(self):
        want = [Ctx.home + "/" + f for f in REQUESTS_FOLDERS] + [DOWNLOADS_FOLDER]
        return "done" if all(os.path.isdir(P(d)) for d in want) else "todo"

    def run(self):
        if Opt.dry:
            out("      would create %s and the folders under %s/requests" % (DOWNLOADS_FOLDER, Ctx.home))
            return
        for f in REQUESTS_FOLDERS:
            path = Ctx.home + "/" + f
            make_folder(P(path))
            chown(P(path), SEERR_UID if f == "requests/seerr" else Ctx.uid, SEERR_UID if f == "requests/seerr" else Ctx.gid)
        make_folder(P(DOWNLOADS_FOLDER))
        chown(P(DOWNLOADS_FOLDER), Ctx.uid, Ctx.gid)


class RequestsStack(StackStep):
    """The five request containers in one stack."""

    def applies(self):
        return requests_applies()

    def detail(self):
        return "Seerr %d, Radarr %d, Sonarr %d, Prowlarr %d, qBittorrent %d" % tuple(PORTS[a] for a in ("seerr", "radarr", "sonarr", "prowlarr", "qbittorrent"))

    def stamp(self):
        return hashlib.md5((stack_text("requests") + "|".join("%s=%s" % kv for kv in stack_env("requests"))).encode()).hexdigest()

    def probe(self):
        return "done" if stack_up("requests") and State.data.get("requests_stack") == self.stamp() else "todo"

    def run(self):
        StackStep.run(self, start_first=State.data.get("requests_stack") == self.stamp())
        if Opt.dry:
            return
        if not wait_for(requests_all_answer, "the request apps to answer", 300, every=5):
            raise Abort("The request apps do not all answer yet. Look at the logs, for example:  docker logs radarr")
        State.data["requests_stack"] = self.stamp()
        State.save()
        if not FAKE and os.path.exists(P("/usr/local/sbin/homelab-cards")):
            run([P("/usr/local/sbin/homelab-cards"), "sync"], timeout=120)


register(RequestsStack("requests", ("portainer-env", "folders", "requests-folders", "stack-jellyfin"),
                       "Requests stack (Seerr, Radarr, Sonarr, Prowlarr and qBittorrent)", 600))


def servarr_key(app):
    """The API key Radarr or Sonarr made for itself, read from its settings file."""
    m = re.search(r"<ApiKey>([^<]+)</ApiKey>", read_file(P("%s/requests/%s/config.xml" % (Ctx.home, app))))
    return m.group(1).strip() if m else ""


def servarr_call(app, method, path, body=None):
    return http(method, url(app, "/api/%s%s" % (SERVARR_API.get(app, "v3"), path)), body=body, headers={"X-Api-Key": servarr_key(app)}, timeout=60)


def qbit_login(user, password):
    """Log in to qBittorrent's web page and return the session header, or None."""
    st, txt, hd = http("POST", url("qbittorrent", "/api/v2/auth/login"), urlform={"username": user, "password": password}, timeout=30, raw=True)
    m = re.search(r"SID=([^;,\s]+)", hd.get("set-cookie", "") or "")
    return {"Cookie": "SID=" + m.group(1)} if st == 200 and m and "Ok" in txt else None


def qbit_temp_password():
    rc, txt = docker("logs", "--tail", "400", "qbittorrent", timeout=60)
    found = re.findall(r"temporary password[^:\n]*:\s*(\S+)", txt or "", re.I)
    return found[-1] if found else ""


def setup_qbittorrent(pw):
    """Give qBittorrent the shared admin login and make /data/downloads its folder. Returns None when it worked, else a short reason."""
    session = qbit_login(Ctx.admin, pw)
    if session is None:
        temp = qbit_temp_password()
        session = qbit_login("admin", temp) if temp else None
    if session is None:
        return "its web page did not accept the first-start password"
    prefs = {"web_ui_username": Ctx.admin, "web_ui_password": pw, "save_path": "/data/downloads",
             "web_ui_host_header_validation_enabled": False}
    st, _, _ = http("POST", url("qbittorrent", "/api/v2/app/setPreferences"), urlform={"json": json.dumps(prefs)}, headers=session, timeout=30)
    return None if st == 200 else "it refused the settings (HTTP %s)" % st


def servarr_login(app, pw):
    """Give Radarr, Sonarr or Prowlarr a login with the shared admin password. Returns None when it worked, else a short reason."""
    host = servarr_call(app, "GET", "/config/host")
    if host[0] != 200 or not isinstance(host[1], dict):
        return "it did not answer with its API key (HTTP %s)" % host[0]
    cur = host[1]
    cur.update({"authenticationMethod": "forms", "authenticationRequired": "enabled", "username": Ctx.admin, "password": pw, "passwordConfirmation": pw})
    st = servarr_call(app, "PUT", "/config/host/%s" % cur.get("id", 1), cur)[0]
    return None if st in (200, 202) else "it refused the login settings (HTTP %s)" % st


def setup_servarr(app, pw):
    """Radarr or Sonarr: a login with the shared admin password, a root folder, and qBittorrent as the download client."""
    why = servarr_login(app, pw)
    if why:
        return why
    roots = servarr_call(app, "GET", "/rootfolder")[1]
    if not any(isinstance(r, dict) and r.get("path", "").rstrip("/") == REQUESTS_ROOTS[app] for r in roots or []):
        st = servarr_call(app, "POST", "/rootfolder", {"path": REQUESTS_ROOTS[app]})[0]
        if st not in (200, 201):
            return "it did not accept the folder %s (HTTP %s)" % (REQUESTS_ROOTS[app], st)
    clients = servarr_call(app, "GET", "/downloadclient")[1]
    if any(isinstance(c, dict) and c.get("implementation") == "QBittorrent" for c in clients or []):
        return None
    schema = [s for s in servarr_call(app, "GET", "/downloadclient/schema")[1] or [] if isinstance(s, dict) and s.get("implementation") == "QBittorrent"]
    if not schema:
        return "it has no qBittorrent download client"
    client = schema[0]
    values = {"host": "qbittorrent", "port": PORTS["qbittorrent"], "useSsl": False, "username": Ctx.admin, "password": pw,
              "movieCategory": "radarr", "tvCategory": "sonarr"}
    for f in client.get("fields", []):
        if f.get("name") in values:
            f["value"] = values[f["name"]]
    client.update({"name": "qBittorrent", "enable": True})
    st = servarr_call(app, "POST", "/downloadclient", client)[0]
    if st not in (200, 201):
        st = http("POST", url(app, "/api/v3/downloadclient?forceSave=true"), body=client, headers={"X-Api-Key": servarr_key(app)}, timeout=60)[0]
        return None if st in (200, 201) else "it did not accept qBittorrent as its download client (HTTP %s)" % st
    return None


def setup_prowlarr(pw):
    """Prowlarr: a login with the shared admin password, and Radarr and Sonarr as the apps it sends its indexers to. It adds no indexers."""
    why = servarr_login("prowlarr", pw)
    if why:
        return why
    have = {a.get("implementation") for a in servarr_call("prowlarr", "GET", "/applications")[1] or [] if isinstance(a, dict)}
    schema = {s.get("implementation"): s for s in servarr_call("prowlarr", "GET", "/applications/schema")[1] or [] if isinstance(s, dict)}
    for app in ("radarr", "sonarr"):
        name = app.capitalize()
        if name in have:
            continue
        entry = schema.get(name)
        if not entry:
            return "it has no %s application" % name
        values = {"prowlarrUrl": "http://prowlarr:%d" % PORTS["prowlarr"], "baseUrl": "http://%s:%d" % (app, PORTS[app]), "apiKey": servarr_key(app)}
        for f in entry.get("fields", []):
            if f.get("name") in values:
                f["value"] = values[f["name"]]
        entry.update({"name": name, "syncLevel": "fullSync"})
        if servarr_call("prowlarr", "POST", "/applications", entry)[0] not in (200, 201):
            st = http("POST", url("prowlarr", "/api/v1/applications?forceSave=true"), body=entry, headers={"X-Api-Key": servarr_key("prowlarr")}, timeout=60)[0]
            if st not in (200, 201):
                return "it did not accept %s (HTTP %s)" % (name, st)
    return None


def profile_for(app):
    """The quality profile Seerr should use: the first one that mentions 1080p, else the first."""
    profiles = [p for p in servarr_call(app, "GET", "/qualityprofile")[1] or [] if isinstance(p, dict) and "id" in p]
    best = next((p for p in profiles if "1080" in str(p.get("name", ""))), profiles[0] if profiles else None)
    return (best["id"], str(best.get("name", ""))) if best else (None, "")


def seerr_call(method, path, session, body=None):
    return http(method, url("seerr", "/api/v1" + path), body=body, headers=session, timeout=60)


def setup_seerr(pw):
    """Seerr: sign in with the Jellyfin admin login, switch on the Jellyfin libraries, and link Radarr and Sonarr. Returns None when it worked, else a short reason."""
    pub = http("GET", url("seerr", "/api/v1/settings/public"), timeout=20)[1]
    if isinstance(pub, dict) and pub.get("initialized"):
        return None
    login = {"username": Ctx.admin, "password": pw, "hostname": svc_host(), "port": PORTS["jellyfin"], "useSsl": False, "urlBase": "", "serverType": 2}
    st, js, hd = http("POST", url("seerr", "/api/v1/auth/jellyfin"), body=login, timeout=60)
    if st == 400 and "email" in json.dumps(js).lower():
        login["email"] = "%s@localhost" % Ctx.admin
        st, js, hd = http("POST", url("seerr", "/api/v1/auth/jellyfin"), body=login, timeout=60)
    m = re.search(r"connect\.sid=([^;,\s]+)", hd.get("set-cookie", "") or "")
    if st != 200 or not m:
        return "it could not sign in to Jellyfin with the admin login (HTTP %s)" % st
    session = {"Cookie": "connect.sid=" + m.group(1)}
    libs = seerr_call("GET", "/settings/jellyfin/library?sync=true", session)[1]
    ids = [str(x["id"]) for x in libs if isinstance(x, dict) and "id" in x] if isinstance(libs, list) else []
    if ids:
        seerr_call("GET", "/settings/jellyfin/library?enable=" + ",".join(ids), session)
    for app, extra in (("radarr", {"minimumAvailability": "released"}), ("sonarr", {"enableSeasonFolders": True})):
        pid, pname = profile_for(app)
        if pid is None:
            return "%s has no quality profile to use" % app.capitalize()
        body = {"name": app.capitalize(), "hostname": app, "port": PORTS[app], "apiKey": servarr_key(app), "useSsl": False, "baseUrl": "",
                "activeProfileId": pid, "activeProfileName": pname, "activeDirectory": REQUESTS_ROOTS[app], "is4k": False, "isDefault": True,
                "syncEnabled": False, "preventSearch": False, "externalUrl": ""}
        body.update(extra)
        if seerr_call("POST", "/settings/" + app, session, body)[0] not in (200, 201):
            return "it did not accept %s" % app.capitalize()
    st = seerr_call("POST", "/settings/initialize", session, {})[0]
    return None if st in (200, 201) else "it did not finish its first-time setup (HTTP %s)" % st


@step
class RequestsLinks(Step):
    id, group = "requests-links", "Services"
    title = "Link the request apps to each other and to Jellyfin (the admin login, folders, download client and Prowlarr)"
    needs = ("stack-requests", "w-jellyfin")

    def applies(self):
        return requests_applies()

    def probe(self):
        done = State.data.get("requests_linked") or {}
        return "done" if all(done.get(a) for a in REQUESTS_PARTS) else "todo"

    def run(self):
        if Opt.dry:
            out("      would set the admin login in each app, add the folders and qBittorrent to Radarr and Sonarr, link Prowlarr to both, and link Seerr to Jellyfin, Radarr and Sonarr")
            return
        pw = need_password("to set the login of the request apps")
        done = State.data.setdefault("requests_linked", {})
        todo = {"qbittorrent": lambda: setup_qbittorrent(pw), "radarr": lambda: setup_servarr("radarr", pw), "sonarr": lambda: setup_servarr("sonarr", pw),
                "prowlarr": lambda: setup_prowlarr(pw), "seerr": lambda: setup_seerr(pw)}
        problems = []
        for app in REQUESTS_PARTS:
            if done.get(app):
                continue
            try:
                why = todo[app]()
            except Abort:
                raise
            except Exception as e:
                why = "something went wrong (%s)" % e
            if why:
                problems.append((app, why))
            else:
                done[app] = True
                State.save()
        if problems:
            names = REQUESTS_LABELS
            raise Abort("Not everything was linked: %s. Run `sudo homelab-setup refresh` to try again; the parts that worked are kept." %
                        "; ".join("%s: %s" % (names[a], w) for a, w in problems))
