def api_updates_state(fresh=False):
    if fresh:
        APT_CACHE["n"] = None
    lines = read_text(os.path.join(UPDATE_STATE, "image-updates")).splitlines()
    first = lines[0].strip() if lines else ""
    stacks = []
    for l in lines[1:]:
        if l.strip():
            parts = l.split(None, 1)
            stacks.append({"name": parts[0], "detail": parts[1] if len(parts) > 1 else ""})
    apt = read_text(os.path.join(UPDATE_STATE, "apt")).strip().split("|")
    system = int(apt[0]) if apt and apt[0].isdigit() else None
    live, kept = apt_waiting()
    if live is not None:
        system = live
    return {"checked": int(first) if first.isdigit() else 0, "containers": stacks, "system": system, "kept_back": kept, "restart": os.path.exists(REBOOT_FILE),
            "now": int(time.time()), "job": api_updates_job()}


def api_updates_job():
    with UPJOB_LOCK:
        return dict(UPJOB, lines=UPJOB["lines"][-(10 if UPJOB["running"] else 60):])


def upd_progress(action, st, line):
    """Work out how far an update has got from the lines the update tools print (one line at a time, colors removed) for the Updates tab's progress bar. `st` is the memory of one job."""
    def done(pct, text):
        pct = None if pct is None else max(st.get("pct", 0), min(99, int(round(pct))))
        if pct is not None:
            st["pct"] = pct
        return pct, text
    if action in ("containers", "containers-now"):
        m = re.search(r"Step (\d) of 4", line)
        if m:
            st["step"] = int(m.group(1))
            if st["step"] == 1:
                return done(3, "Step 1 of 4: checking for new versions")
            if st["step"] == 2:
                return done(10, "Step 2 of 4: downloading the new images")
            if st["step"] == 3:
                return done(52, "Step 3 of 4: checking that no upload is running")
            return done(55, "Step 4 of 4: updating the services one at a time")
        step = st.get("step", 0)
        m = re.search(r"(\d+) image\(s\) to download", line)
        if m and step == 2:
            st["images"] = int(m.group(1))
            st["got"] = 0
            return done(10, "Step 2 of 4: downloading the new images (0 of %d)" % st["images"])
        if step == 2 and re.match(r" {6}\S ", line):
            st["got"] = st.get("got", 0) + 1
            total = st.get("images") or 0
            if total:
                return done(10 + 40 * min(st["got"], total) / total, "Step 2 of 4: downloading the new images (%d of %d)" % (min(st["got"], total), total))
            return done(10 + 40 * (1 - 1 / (1 + st["got"])), "Step 2 of 4: downloading the new images (%d done)" % st["got"])
        m = re.search(r"(\d+) stack\(s\) to update", line)
        if m and step == 4:
            st["total_stacks"] = int(m.group(1))
            return done(55, "Step 4 of 4: updating %d service%s one after the other" % (st["total_stacks"], "" if st["total_stacks"] == 1 else "s"))
        if step == 4:
            total = st.get("total_stacks") or 0
            m = re.match(r" {3}(\d+) {2}(\S+)", line)
            if m:
                st["cur"], st["name"], st["frac"] = int(m.group(1)), m.group(2), 0.0
            cur, name = st.get("cur", 0), st.get("name", "")
            stage = None
            if "Quick database dump" in line:
                stage = (0.15, "making a quick database dump")
            elif "Updating the stack through Portainer" in line or "Recreating Portainer" in line:
                stage = (0.35, "installing the new version")
            elif "Waiting for the containers to come back" in line:
                stage = (0.65, "waiting for the containers to come back")
            elif "is updated and running" in line or "left as it is" in line:
                stage = (1.0, "finished")
            if m:
                stage = (0.0, "starting")
            if stage is not None and cur:
                st["frac"] = max(st.get("frac", 0), stage[0])
                what = "Step 4 of 4: %s%s: %s" % (name, " (%d of %d)" % (cur, total) if total else "", stage[1])
                return done(55 + 45 * ((cur - 1) + st["frac"]) / total if total else 55 + 40 * (1 - 1 / (1 + cur - 1 + st["frac"])), what)
        return None
    if action == "system":
        if line.startswith("$ "):
            if "update" in line.split():
                st["phase"] = "list"
                return done(2, "Step 1 of 2: updating the package list")
            if "upgrade" in line.split():
                st["phase"] = "pkgs"
                st.setdefault("total", APT_CACHE["n"] or 0)
                return done(10, "Step 2 of 2: installing packages" + (" (%d)" % st["total"] if st["total"] else ""))
            return None
        m = re.search(r"(\d+) upgraded, (\d+) newly installed", line)
        if m:
            st["total"] = int(m.group(1)) + int(m.group(2))
            if st["total"] == 0:
                return done(95, "Step 2 of 2: nothing to install")
            return done(10, "Step 2 of 2: installing %d package%s" % (st["total"], "" if st["total"] == 1 else "s"))
        if st.get("phase") == "list":
            st["lists"] = st.get("lists", 0) + 1
            return done(2 + min(7, st["lists"] // 2), "Step 1 of 2: updating the package list") if re.match(r"(Hit|Get|Ign):", line) else None
        if st.get("phase") == "pkgs":
            kind = "dl" if re.match(r"Get:\d+ ", line) else "un" if line.startswith("Unpacking ") else "set" if line.startswith("Setting up ") else ""
            if not kind:
                if line.startswith("Processing triggers"):
                    return done(max(st.get("pct", 0), 96), "Step 2 of 2: finishing up")
                return None
            st[kind] = st.get(kind, 0) + 1
            total = st.get("total") or 0
            if not total:
                n = st.get("dl", 0) + st.get("un", 0) + st.get("set", 0)
                return done(10 + 85 * (1 - 1 / (1 + n / 20.0)), "Step 2 of 2: installing packages (%d steps done)" % n)
            n = min(st.get("dl", 0), total) + min(st.get("un", 0), total) + min(st.get("set", 0), total)
            word = {"dl": "downloading", "un": "unpacking", "set": "setting up"}[kind]
            return done(10 + 86 * n / (3.0 * total), "Step 2 of 2: %s package %d of %d" % (word, min(st[kind], total), total))
    return None


def held_reason(lines):
    """When the update tool holds the update back ("Not now: <reason>"), return (reason, message for the person); otherwise None."""
    for line in lines:
        m = re.search(r"Not now: (.+)", line)
        if not m:
            continue
        early = "Stopped before" in m.group(1)
        reason = re.split(r"\. Stopped before", m.group(1))[0].strip().rstrip(".")
        if early:
            return reason, "The update stopped early because %s. The services updated so far are done; the rest are still waiting. Try again when it has finished." % reason
        return reason, "Nothing was updated because %s. Try again when it has finished, or choose Update Anyway." % reason
    return None


def updates_job_thread(action):
    """Run the steps of an update action in the background and keep their output for the Updates tab."""
    rc = 1
    mem = {}
    try:
        for cmd in UPDATE_STEPS[action]:
            with UPJOB_LOCK:
                head = "$ " + " ".join(cmd[2:] if cmd[:2] == ["sudo", "-n"] else cmd)
                UPJOB["lines"] = (UPJOB["lines"] + [head])[-300:]
                got = upd_progress(action, mem, head)
                if got:
                    UPJOB["pct"], UPJOB["stage"] = got
            try:
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, bufsize=1)
            except FileNotFoundError:
                with UPJOB_LOCK:
                    UPJOB["lines"].append("command not found")
                rc = 127
                break
            timer = threading.Timer(JOB_MAX_SECONDS, p.kill)
            timer.start()
            try:
                for line in p.stdout:
                    line = ANSI.sub("", line).rstrip()
                    if line.strip():
                        with UPJOB_LOCK:
                            UPJOB["lines"] = (UPJOB["lines"] + [line[:400]])[-300:]
                            got = upd_progress(action, mem, line[:400])
                            if got:
                                UPJOB["pct"], UPJOB["stage"] = got
                rc = p.wait()
            finally:
                timer.cancel()
            if rc != 0:
                break
    finally:
        APT_CACHE["n"] = None
        if action != "restart":
            refresh_alerts()
        with UPJOB_LOCK:
            tail = [x for x in UPJOB["lines"] if x.strip() and not x.startswith("$ ")]
            text = "\n".join(UPJOB["lines"])
            UPJOB["rc"] = rc
            if rc == 0 and UPJOB["pct"] is not None:
                UPJOB["pct"], UPJOB["stage"] = 100, "Done"
            held = held_reason(UPJOB["lines"]) if action in ("containers", "containers-now") and rc == 0 else None
            if held:
                UPJOB["rc"], UPJOB["held"] = 75, held[0]
                UPJOB["message"] = held[1]
            elif rc == 0:
                UPJOB["message"] = tail[-1] if tail else "Done."
            elif "a password is required" in text or "not allowed to execute" in text or "sudo:" in text:
                UPJOB["message"] = "The panel does not have permission to run that yet. Run the installer's update (homelab-update) to add the permission."
            elif rc == 127:
                UPJOB["message"] = "That tool is not installed on this machine."
            else:
                UPJOB["message"] = tail[-1] if tail else "It stopped without giving a reason."
            UPJOB["running"] = False


def api_updates_start(body):
    action = body.get("what")
    if action not in UPDATE_STEPS:
        raise Fail("Choose what to update.")
    if action == "restart" and body.get("confirm") is not True:
        raise Fail("Confirm the restart first.")
    with UPJOB_LOCK:
        if UPJOB["running"]:
            raise Fail("An update is already running. Wait until it has finished.", 409)
        UPJOB.update(id=UPJOB["id"] + 1, running=True, action=action, lines=[], rc=None, message="", started=int(time.time()), pct=None, stage="", held="")
        jid = UPJOB["id"]
    threading.Thread(target=updates_job_thread, args=(action,), daemon=True).start()
    return {"ok": True, "job": jid}


IMMICH_URL = (os.environ.get("HLP_IMMICH_URL") or "http://127.0.0.1:2283").rstrip("/")
UPLOAD_FILE = os.path.join(STATE_DIR, "uploads.json")
PHOTO_MAX = 20 * 1024 ** 3
SONG_MAX = 2 * 1024 ** 3
PHOTO_EXT = {"jpg", "jpeg", "png", "gif", "webp", "heic", "heif", "avif", "tif", "tiff", "bmp", "jxl", "dng", "arw", "cr2", "cr3", "nef", "nrw", "orf", "raf", "rw2", "pef", "srw",
             "mp4", "mov", "m4v", "avi", "mkv", "webm", "3gp", "mpg", "mpeg", "mts", "m2ts", "wmv", "flv"}
SONG_EXT = {"mp3", "flac", "m4a", "aac", "ogg", "oga", "opus", "wav", "wma", "alac", "aiff", "aif", "ape", "wv", "mka"}
IMMICH_KEY = re.compile(r"[A-Za-z0-9_-]{16,200}\Z")
MUSIC_CACHE = {"at": 0.0, "dir": ""}
UPLOAD_CHUNK = 1 << 20


def uploads_cfg():
    try:
        with open(UPLOAD_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def uploads_save(cfg):
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    tmp = UPLOAD_FILE + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    os.replace(tmp, UPLOAD_FILE)


def music_dir():
    """Return the folder Navidrome plays from: HLP_MUSIC_DIR, else the folder the Navidrome container has as /music, else the installer's note, else /mnt/storage/music."""
    forced = os.environ.get("HLP_MUSIC_DIR")
    if forced:
        return forced
    if time.time() - MUSIC_CACHE["at"] < 60:
        return MUSIC_CACHE["dir"]
    found = ""
    if not NO_DOCKER:
        try:
            r = subprocess.run(["docker", "inspect", "navidrome", "--format", '{{range .Mounts}}{{if eq .Destination "/music"}}{{.Source}}{{end}}{{end}}'],
                               capture_output=True, text=True, timeout=10)
            found = r.stdout.strip() if r.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            found = ""
    if not found:
        try:
            with open("/var/lib/homelab/music-dir", encoding="utf-8") as f:
                found = f.read().strip()
        except OSError:
            found = ""
    MUSIC_CACHE.update(at=time.time(), dir=found or "/mnt/storage/music")
    return MUSIC_CACHE["dir"]


def immich_call(method, path, key, timeout=5):
    u = urllib.parse.urlparse(IMMICH_URL)
    try:
        c = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=timeout)
        c.request(method, path, headers={"x-api-key": key, "Accept": "application/json"} if key else {"Accept": "application/json"})
        r = c.getresponse()
        raw = r.read(1 << 20)
        c.close()
    except (OSError, http.client.HTTPException):
        return 0, None
    try:
        return r.status, json.loads(raw)
    except ValueError:
        return r.status, None


def api_upload_state():
    key = uploads_cfg().get("immich_key", "")
    up = immich_call("GET", "/api/server/ping", "", timeout=3)[0] == 200
    d = music_dir()
    ok = os.path.isdir(d)
    writable = ok and os.access(d, os.W_OK | os.X_OK)
    try:
        free = shutil.disk_usage(d).free if ok else None
    except OSError:
        free = None
    return {"immich": {"configured": bool(key), "up": up}, "music": {"dir": d, "exists": ok, "writable": writable, "free": free, "user": getpass.getuser()},
            "limits": {"photo": PHOTO_MAX, "song": SONG_MAX}, "photo_ext": sorted(PHOTO_EXT), "song_ext": sorted(SONG_EXT)}


def api_upload_key(body):
    """Keep the Immich API key, or forget it when empty. A key that Immich rejects is not kept."""
    key = body.get("key")
    if not isinstance(key, str):
        raise Fail("Paste the key first.")
    key = key.strip()
    if not key:
        cfg = uploads_cfg()
        cfg.pop("immich_key", None)
        uploads_save(cfg)
        return {"configured": False, "message": "The Immich key was forgotten."}
    if not IMMICH_KEY.match(key):
        raise Fail("That does not look like an Immich API key (letters and numbers, at least 16).")
    st, js = immich_call("GET", "/api/users/me", key)
    if st == 0:
        raise Fail("Immich is not responding, so the key could not be checked. Check that Immich is running.", 502)
    if st == 401:
        raise Fail("Immich rejected that key. Check that the whole key was copied.", 409)
    if st not in (200, 403):
        raise Fail("Immich returned an unexpected response (code %d)." % st, 502)
    cfg = uploads_cfg()
    cfg["immich_key"] = key
    uploads_save(cfg)
    who = js.get("name") or js.get("email") if isinstance(js, dict) else ""
    return {"configured": True, "message": "The key works" + (" (account: %s)." % who if who else ".")}


def upload_name(raw, allowed):
    name = re.sub(r"[\x00-\x1f\x7f]", "", (raw or "").replace("\\", "/").split("/")[-1]).strip().lstrip(".").strip()
    if not name or len(name) > 255:
        raise Fail("That file has no usable name.", 400)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in allowed:
        raise Fail("That file type is not accepted (.%s)." % ext if ext else "That file has no extension such as .mp3 or .jpg.", 415)
    return name


def upload_drain(handler, n):
    left = min(n, 64 * 1024 * 1024)
    while left > 0:
        b = handler.rfile.read(min(left, UPLOAD_CHUNK))
        if not b:
            break
        left -= len(b)
    handler.close_connection = True


def api_upload_stream(handler, kind, q):
    """Receive an uploaded photo or song from the page and pass it on."""
    n = handler.content_length()
    try:
        if n <= 0:
            raise Fail("The file is empty.", 400)
        one = lambda k: (q.get(k) or [""])[0]  # noqa: E731
        if kind == "photo":
            name = upload_name(one("name"), PHOTO_EXT)
            if n > PHOTO_MAX:
                raise Fail("That file is larger than 20 GB.", 413)
            key = uploads_cfg().get("immich_key", "")
            if not key:
                raise Fail("Paste your Immich key first.", 409)
        else:
            name = upload_name(one("name"), SONG_EXT)
            if n > SONG_MAX:
                raise Fail("That song is larger than 2 GB.", 413)
    except Fail:
        upload_drain(handler, n)
        raise
    try:
        return upload_photo(handler, name, n, one("mtime"), key) if kind == "photo" else upload_song(handler, name, n)
    except Fail:
        handler.close_connection = True
        raise


