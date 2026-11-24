def api_drives_job_start(action, body):
    words = job_words(action, body)
    if action == "wipe" and not drive_listed("spare", body.get("id")):
        raise Fail("That drive is not a spare drive, so it cannot be wiped here. The boot drive and the drives in a pool are never wiped.")
    items = [t.split(":")[0] for t in job_ids(body)] if action not in ("wipe", "setup", "bootadd", "appsfix", "moveboot") else ([body.get("id")] if action == "wipe" else ["bootadd"] if action == "bootadd" else ["moveboot"] if action == "moveboot" else ["appsfix"] if action == "appsfix" else [str(t).split(":")[0] for t in (body.get("ids") or [])])
    drives_change_begin()
    with JOB_LOCK:
        JOB.update(id=JOB["id"] + 1, running=True, action=action, lines=[], rc=None, message="", started=int(time.time()), items=items, progress={}, current="", stopping=False)
        jid = JOB["id"]
    threading.Thread(target=job_thread, args=(words,), daemon=True).start()
    return {"ok": True, "job": jid}


def api_drives_job():
    with JOB_LOCK:
        return {"id": JOB["id"], "running": JOB["running"], "action": JOB["action"], "lines": JOB["lines"][-(12 if JOB["running"] else 60):], "rc": JOB["rc"], "message": JOB["message"], "started": JOB["started"], "items": JOB["items"], "progress": JOB["progress"], "current": JOB["current"], "stopping": JOB["stopping"]}


def api_drives_abort():
    """The Stop button: ask the drives tool to stop the running change at the next safe moment. It does not wait for the change and is not held back by the drive gate."""
    with JOB_LOCK:
        running, action = JOB["running"], JOB["action"]
        copying = any(str(v.get("text", "")).startswith("Copying files") for v in JOB["progress"].values())
    if not running:
        raise Fail("No drive change is running right now.", 409)
    if action == "setup" and not copying:
        raise Fail("A new setup can be stopped only while the files of the Main pool are being copied. Erasing and building the drives cannot be interrupted.", 409)
    if action == "appsfix" and not copying:
        raise Fail("Cancel works while the files are being copied from the backup. Right now nothing is being copied.", 409)
    if action not in ("add", "move", "disconnect", "setup", "appsfix"):
        raise Fail("That cannot be stopped: erasing a drive cannot be interrupted.", 409)
    try:
        p = subprocess.run(DRIVES_CMD + ["panel", "abort"], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise Fail("The drives tool did not respond. Try Stop again.", 504) from None
    except FileNotFoundError:
        raise Fail("The drives tool is not installed.", 502) from None
    msg = drive_message(p.stdout or "", p.stderr or "")
    if p.returncode != 0:
        raise Fail(msg or "The change could not be stopped.", 409)
    with JOB_LOCK:
        JOB["stopping"] = True
    return {"message": msg or "Stopping."}


BACKUP_ID = re.compile(r"[a-z][a-z0-9-]{0,23}\Z")
BACKUP_VERSION = re.compile(r"(current|\d{4}-\d\d-\d\d(_\d{6})?)\Z")
BACKUP_HOST = re.compile(r"[a-z_][a-z0-9_-]{0,31}@[A-Za-z0-9][A-Za-z0-9.-]{0,252}(:[0-9]{1,5})?\Z")
BJOB = {"id": 0, "running": False, "action": "", "task": "", "lines": [], "rc": None, "message": "", "started": 0, "pct": None}
BJOB_LOCK = threading.Lock()
BACKUP_SAVE_KEYS = ("id", "name", "enabled", "source", "exclude", "dest", "schedule", "keep", "skip")


def backup_problem(rc, text):
    low = text.lower()
    if rc == 127 or "command not found" in low or "no such file" in low:
        return "The backup tool is not installed on this machine yet. Run the installer's update (homelab-update) to add it."
    if rc == 124:
        return "The backup tool took too long to respond. Try again shortly."
    if "password is required" in low or "not allowed" in low or "may not run sudo" in low or "no tty present" in low:
        return "The panel is not allowed to run the backup tool yet. Run the installer's update (homelab-update) to add the permission."
    return ""


def backup_run(words, stdin=None, timeout=60):
    try:
        p = subprocess.run(BACKUP_CMD + words, capture_output=True, text=True, timeout=timeout, input=stdin if stdin is not None else None,
                           stdin=None if stdin is not None else subprocess.DEVNULL)
        return p.returncode, p.stdout or "", p.stderr or ""
    except FileNotFoundError:
        return 127, "", "command not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"


def backup_json(words, stdin=None, timeout=60):
    rc, out, err = backup_run(words, stdin, timeout)
    try:
        data = json.loads(out.strip().split("\n")[-1]) if out.strip() else None
    except ValueError:
        data = None
    if isinstance(data, dict) and "error" in data:
        raise Fail(str(data["error"])[:600], 409)
    if rc != 0 or not isinstance(data, dict):
        raise Fail(backup_problem(rc, err + out) or "The backup tool returned a response that the panel cannot read.", 502 if rc != 124 else 504)
    return data


def backup_id(v):
    if not isinstance(v, str) or not BACKUP_ID.match(v):
        raise Fail("Choose a backup task first.")
    return v


def backup_version(v):
    if not isinstance(v, str) or not BACKUP_VERSION.match(v):
        raise Fail("Choose a version first.")
    return v


def backup_rel(v):
    v = "." if v in (None, "", "/") else v
    if not isinstance(v, str) or len(v) > 600 or re.search(r"[\x00-\x1f]", v) or ".." in v.split("/") or v.startswith("-"):
        raise Fail("That path is not allowed.")
    return v


def api_backup_state():
    return backup_json(["state"])


def api_backup_save(body):
    task = {k: body[k] for k in BACKUP_SAVE_KEYS if k in body}
    if "id" in task:
        backup_id(task["id"])
    return backup_json(["save"], json.dumps(task))


def api_backup_task(action, body):
    """Quick backup actions that complete immediately: delete, toggle, sshkey, sshtest and cloud-add."""
    if action == "delete":
        if body.get("data") not in ("keep", "erase"):
            raise Fail("Choose whether to keep or erase the copies already made.")
        return backup_json(["delete", backup_id(body.get("id")), body["data"]], timeout=3700)
    if action == "toggle":
        return backup_json(["toggle", backup_id(body.get("id")), "on" if body.get("enabled") else "off"])
    if action == "sshkey":
        return backup_json(["sshkey"], timeout=90)
    if action == "sshtest":
        host = body.get("host")
        if not isinstance(host, str) or not BACKUP_HOST.match(host):
            raise Fail("The other computer must look like user@name.")
        return backup_json(["sshtest", host], timeout=90)
    if action == "cloud-add":
        keep = {k: body.get(k) for k in ("type", "name", "key_id", "key", "endpoint") if isinstance(body.get(k), str)}
        return backup_json(["cloud-add"], json.dumps(keep))
    raise Fail("Unknown address.", 404)


def api_backup_look(path, query):
    q = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
    if path == "versions":
        return backup_json(["versions", backup_id(q.get("id"))], timeout=120)
    return backup_json(["browse", backup_id(q.get("id")), backup_version(q.get("v")), backup_rel(q.get("rel"))], timeout=180)


DL_TOKENS = {}
DL_LOCK = threading.Lock()


def api_backup_dltoken(body, session):
    """The Download button: create a link that works once, for two minutes and for this session only."""
    mode = body.get("mode")
    if mode not in ("file", "zip"):
        raise Fail("Choose a file or a folder.")
    task, version, rel = backup_id(body.get("id")), backup_version(body.get("v")), backup_rel(body.get("rel"))
    rel = "" if rel == "." else rel
    name = os.path.basename(rel) if rel else "backup"
    if mode == "zip":
        name += ".zip"
    tok = secrets.token_urlsafe(24)
    with DL_LOCK:
        now = time.time()
        for k in [k for k, v in DL_TOKENS.items() if v[0] < now]:
            del DL_TOKENS[k]
        if len(DL_TOKENS) > 200:
            raise Fail("Too many downloads are waiting. Try again shortly.", 429)
        DL_TOKENS[tok] = (now + 120, session, task, version, rel or ".", mode, name)
    return {"url": "/api/backup/download?t=" + tok}


def backup_download(handler, query):
    """Stream one file, or a folder as a .zip, from the backup tool to the browser. The tool reads as root and nothing is kept on the way."""
    t = urllib.parse.parse_qs(query).get("t", [""])[0]
    with DL_LOCK:
        entry = DL_TOKENS.pop(t, None)
    if not entry or entry[0] < time.time() or entry[1] != handler.cookie_token():
        raise Fail("That download link has expired. Press Download again.", 403)
    _, _, task, version, rel, mode, name = entry
    p = subprocess.Popen(BACKUP_CMD + ["stream", task, version, rel, mode], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    try:
        first = p.stdout.read(65536)
        if len(first) < 65536:
            rc = p.wait()
            if rc != 0:
                msg = ""
                try:
                    msg = str(json.loads(first.decode("utf-8", "replace")).get("error", ""))
                except ValueError:
                    pass
                err = (p.stderr.read() or b"").decode("utf-8", "replace")
                raise Fail(msg or backup_problem(rc, err) or "That could not be downloaded.", 409)
        safe = re.sub(r'[^A-Za-z0-9._ ()+,-]', "_", name) or "download"
        handler.send_response(200)
        handler.send_header("Content-Type", "application/zip" if mode == "zip" else "application/octet-stream")
        handler.send_header("Content-Disposition", "attachment; filename=\"%s\"; filename*=UTF-8''%s" % (safe, urllib.parse.quote(name)))
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Connection", "close")
        handler.end_headers()
        handler.close_connection = True
        try:
            handler.wfile.write(first)
            while True:
                chunk = p.stdout.read(1 << 20)
                if not chunk:
                    break
                handler.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
    finally:
        if p.poll() is None:
            p.kill()
        p.wait()
        p.stdout.close()
        p.stderr.close()


def backup_job_thread(words):
    """Run a backup command in the background and keep its output lines for the page."""
    rc = 1
    try:
        try:
            p = subprocess.Popen(BACKUP_CMD + words, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, bufsize=1)
        except FileNotFoundError:
            with BJOB_LOCK:
                BJOB["lines"] = ["command not found"]
            rc = 127
        else:
            timer = threading.Timer(JOB_MAX_SECONDS, p.kill)
            timer.start()
            try:
                for line in p.stdout:
                    line = line.rstrip()
                    if not line:
                        continue
                    m = re.match(r"PROGRESS (\d{1,3})\Z", line)
                    with BJOB_LOCK:
                        if m:
                            BJOB["pct"] = min(100, int(m.group(1)))
                        else:
                            BJOB["lines"] = (BJOB["lines"] + [line[:400]])[-200:]
                rc = p.wait()
            finally:
                timer.cancel()
    finally:
        with BJOB_LOCK:
            text = "\n".join(BJOB["lines"])
            tail = [x for x in BJOB["lines"] if x.strip()]
            BJOB["rc"] = rc
            if rc == 0:
                BJOB["pct"] = 100
            BJOB["message"] = backup_problem(rc, text) or (tail[-1] if tail else ("Done." if rc == 0 else "The backup tool stopped without giving a reason."))
            BJOB["running"] = False


def api_backup_job_start(action, body):
    """Start run, dry or restore in the background, one at a time."""
    tid = backup_id(body.get("id"))
    if action == "restore":
        target = body.get("target")
        if target not in ("folder", "original"):
            raise Fail("Choose where to put the files back.")
        words = ["restore", tid, backup_version(body.get("version")), backup_rel(body.get("rel")), target]
    elif action in ("run", "dry"):
        words = [action, tid]
    else:
        raise Fail("Unknown address.", 404)
    with BJOB_LOCK:
        if BJOB["running"]:
            raise Fail("A backup, preview or restore is running already. Wait until it has finished.", 409)
        BJOB.update(id=BJOB["id"] + 1, running=True, action=action, task=tid, lines=[], rc=None, message="", started=int(time.time()), pct=None)
        jid = BJOB["id"]
    threading.Thread(target=backup_job_thread, args=(words,), daemon=True).start()
    return {"ok": True, "job": jid}


def api_backup_job():
    with BJOB_LOCK:
        return dict(BJOB, lines=BJOB["lines"][-(8 if BJOB["running"] else 40):])


UPDATE_STATE = os.environ.get("HLP_UPDATE_STATE") or "/var/lib/homelab"
REBOOT_FILE = os.environ.get("HLP_REBOOT_FILE") or "/var/run/reboot-required"
UPDATE_STEPS = {
    "check": [["sudo", "-n", "/usr/local/sbin/homelab-update", "check"]],
    "containers": [["sudo", "-n", "/usr/local/sbin/homelab-update", "--yes"]],
    "containers-now": [["sudo", "-n", "/usr/local/sbin/homelab-update", "--yes", "--now"]],
    "system": [["sudo", "-n", "/usr/bin/apt-get", "update"], ["sudo", "-n", "/usr/bin/apt-get", "-y", "upgrade"]],
    "restart": [["sudo", "-n", "/usr/bin/systemctl", "reboot"]],
}
if os.environ.get("HLP_UPDATE_STEPS"):
    UPDATE_STEPS = json.loads(os.environ["HLP_UPDATE_STEPS"])
UPJOB = {"id": 0, "running": False, "action": "", "lines": [], "rc": None, "message": "", "started": 0, "pct": None, "stage": "", "held": ""}
UPJOB_LOCK = threading.Lock()
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


APT_GET = os.environ.get("HLP_APT_GET") or "apt-get"
ALERTS_CMD = os.environ.get("HLP_ALERTS") or "/usr/local/sbin/homelab-alerts"
APT_CACHE = {"at": 0.0, "n": None, "kept": 0}


def apt_waiting():
    if APT_CACHE["n"] is not None and time.time() - APT_CACHE["at"] < 60:
        return APT_CACHE["n"], APT_CACHE["kept"]
    try:
        p = subprocess.run([APT_GET, "-s", "upgrade"], capture_output=True, text=True, timeout=40, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None, 0
    if p.returncode != 0:
        return None, 0
    n = sum(1 for l in p.stdout.splitlines() if l.startswith("Inst "))
    m = re.search(r"(\d+) not upgraded", p.stdout)
    APT_CACHE.update(at=time.time(), n=n, kept=int(m.group(1)) if m else 0)
    return n, APT_CACHE["kept"]


def refresh_alerts():
    try:
        subprocess.run([ALERTS_CMD], capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        pass


ALERTS_REFRESH = {"lock": threading.Lock(), "at": 0.0}
ALERTS_MIN_GAP = float(os.environ.get("HLP_ALERTS_GAP") or 10)


def alerts_refresh_now():
    """Look at everything again for the bell on the dashboard. At most once every few seconds, however often the button is pressed. Returns True when it ran."""
    if not ALERTS_REFRESH["lock"].acquire(blocking=False):
        return False
    try:
        if time.time() - ALERTS_REFRESH["at"] < ALERTS_MIN_GAP:
            return False
        refresh_alerts()
        ALERTS_REFRESH["at"] = time.time()
        return True
    finally:
        ALERTS_REFRESH["lock"].release()


