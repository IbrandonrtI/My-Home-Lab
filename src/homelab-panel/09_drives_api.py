def api_location_save(body):
    """Save the chosen city and time zone."""
    tz = str(body.get("timeZone") or "").strip()
    place = body.get("place")
    tx = Tx("Time zone and city changed")
    text = tx.get(WIDGETS)
    if tz:
        if not ZONE_NAME.match(tz) or tz not in zoneinfo.available_timezones():
            raise Fail("That is not a valid time zone name. Choose one from the list, for example America/New_York.")
        b = widget_block(text, "datetime")
        if not b:
            raise Fail("The dashboard has no clock widget in widgets.yaml, so there is nothing to set.")
        blk = text[b[0]:b[1]]
        if re.search(r"\n\s+timeZone:", blk):
            blk = re.sub(r"(\n\s+timeZone:).*", lambda m: "%s %s" % (m.group(1), tz), blk, count=1)
        else:
            f = re.search(r"\n(\s+)format:[^\n]*", blk)
            blk = (blk[:f.end()] + "\n%s  timeZone: %s" % (f.group(1), tz) + blk[f.end():]) if f else blk.rstrip("\n") + "\n    format:\n      timeZone: %s\n" % tz
        text = text[:b[0]] + blk + text[b[1]:]
    if place:
        try:
            name, lat, lon = str(place["name"]).strip(), float(place["lat"]), float(place["lon"])
        except (KeyError, TypeError, ValueError):
            raise Fail("The city is not valid. Search for it again and choose one from the list.") from None
        if not name or len(name) > 60 or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise Fail("The city is not valid. Search for it again and choose one from the list.")
        b = widget_block(text, "openmeteo")
        if not b:
            raise Fail("The dashboard has no weather widget in widgets.yaml, so there is nothing to set.")
        blk = text[b[0]:b[1]]
        label = name.replace("\\", "").replace('"', "")
        blk = re.sub(r"(\n\s+label:).*", lambda m: '%s "%s"' % (m.group(1), label), blk, count=1)
        blk = re.sub(r"(\n\s+latitude:).*", lambda m: "%s %.4f" % (m.group(1), lat), blk, count=1)
        blk = re.sub(r"(\n\s+longitude:).*", lambda m: "%s %.4f" % (m.group(1), lon), blk, count=1)
        text = text[:b[0]] + blk + text[b[1]:]
    if not tz and not place:
        raise Fail("Nothing to save.")
    tx.put(WIDGETS, text)
    tx.commit()
    return {}


def full_state():
    h = history_last()
    return {"version": VERSION, "look": look_state(), "background": bg_state(), "layout": layout_state(), "services": services_state(), "hlcards": hl_state(), "mythemes": mythemes_state(), "schedule": schedule_state(),
            "links": marks_state(), "linksVersion": marks_version(), "location": location_state(), "paint": paint_state(), "undo": (h[1]["label"] if h else ""), "automatic": sorted(AUTOMATIC), "protected": sorted(PROTECTED)}


DRIVES_GATE = threading.Condition()
DRIVES_STATE = {"readers": 0, "changing": False}
DRIVE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
DRIVE_NAME = re.compile(r"[A-Za-z0-9 .()+,-]{1,40}\Z")
DRIVE_TIMEOUT = {"status": 90, "actions": 90, "setups": 120, "health": 180, "check": 180, "remount": 600, "apps": 60}
DRIVE_WORD = re.compile(r"(ERASE|CONTINUE|REMOVE|KEEP|NOW|RESTORE|START|/dev/[a-z0-9]{1,16}|pool|mirror|snapraid1|snapraid2|zfs-stripe|zfs-mirror|zfs-raidz1|zfs-raidz2|zfs-raidz3|md-raid0|md-raid1|md-raid5|md-raid6|md-raid10)\Z")
JOB_MAX_SECONDS = 8 * 3600
JOB = {"id": 0, "running": False, "action": "", "lines": [], "rc": None, "message": "", "started": 0, "items": [], "progress": {}, "current": "", "stopping": False}
JOB_LOCK = threading.Lock()


def drives_problem(rc, text):
    low = text.lower()
    if rc == 127 or "command not found" in low or "no such file" in low:
        return "The drives tool is not installed on this machine, so the Drives tab has nothing to work with."
    if "password is required" in low or "not allowed" in low or "may not run sudo" in low or "no tty present" in low:
        return "The Drives tab is not allowed to use the drives tool yet. On the server, run:  sudo homelab-setup upgrade"
    if rc == 124:
        return "The drives tool took too long. Nothing further was started. Try again shortly."
    lines = [x.strip() for x in text.splitlines() if x.strip() and not x.startswith("WARNING")]
    return " ".join(lines[-3:])[:400] or "The drives tool failed (code %d)." % rc


DRIVES_BUSY_MSG = "A drive change is running right now. This page shows its progress."


def drives_look_begin():
    with DRIVES_GATE:
        if DRIVES_STATE["changing"]:
            raise Fail(DRIVES_BUSY_MSG, 409)
        DRIVES_STATE["readers"] += 1


def drives_look_end():
    with DRIVES_GATE:
        DRIVES_STATE["readers"] -= 1
        DRIVES_GATE.notify_all()


def drives_change_begin(wait=30):
    with DRIVES_GATE:
        if DRIVES_STATE["changing"]:
            raise Fail("Another drive command is running. Try again shortly.", 409)
        DRIVES_STATE["changing"] = True
        if not DRIVES_GATE.wait_for(lambda: DRIVES_STATE["readers"] == 0, timeout=wait):
            DRIVES_STATE["changing"] = False
            DRIVES_GATE.notify_all()
            raise Fail("The drives are still being read. Try again shortly.", 409)


def drives_change_end():
    with DRIVES_GATE:
        DRIVES_STATE["changing"] = False
        DRIVES_GATE.notify_all()


def drives_run(words, timeout, look=False):
    """Run `drives panel WORDS...` and return (returncode, stdout, stderr). Reading commands can run together; a change runs alone."""
    if look:
        drives_look_begin()
    else:
        drives_change_begin()
    try:
        try:
            p = subprocess.run(DRIVES_CMD + ["panel"] + words, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
            return p.returncode, p.stdout or "", p.stderr or ""
        except FileNotFoundError:
            return 127, "", "command not found"
        except subprocess.TimeoutExpired:
            return 124, "", "timed out"
    finally:
        if look:
            drives_look_end()
        else:
            drives_change_end()


def drives_json(action, extra=()):
    rc, out, err = drives_run([action] + list(extra), DRIVE_TIMEOUT[action], look=True)
    try:
        data = json.loads(out)
    except ValueError:
        raise Fail(drives_problem(rc, err or out), 502 if rc != 124 else 504) from None
    if not isinstance(data, dict):
        raise Fail("The drives tool returned a response that the panel cannot read.", 502)
    return data


DRIVES_LAST = {"state": None}
DRIVES_LAST_FILE = os.path.join(STATE_DIR, "drives-last.json")


def drives_last_load():
    if DRIVES_LAST["state"] is None:
        try:
            with open(DRIVES_LAST_FILE) as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("status"), dict):
                DRIVES_LAST["state"] = data
        except (OSError, ValueError):
            pass
    return DRIVES_LAST["state"]


def api_drives_state():
    """Return the pools, drives and last backup, plus what can be renamed or put to sleep. While a change is running the drives are not read, so the last state is returned."""
    try:
        st = drives_json("status")
        ac = drives_json("actions")
    except Fail as e:
        last = drives_last_load() if e.code == 409 and DRIVES_STATE["changing"] else None
        if last is None:
            raise
        return dict(last, stale=True)
    state = {"status": st, "actions": ac}
    DRIVES_LAST["state"] = state
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        tmp = DRIVES_LAST_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f)
        os.replace(tmp, DRIVES_LAST_FILE)
    except OSError:
        pass
    return state


def drive_message(out, err, limit=600, problem=False):
    """Turn the drives tool's output into a short message for the page. A finished change is reported by its "Done." line alone."""
    lines = []
    for x in (out + "\n" + err).splitlines():
        x = x.strip()
        if not x or x.startswith(("Starting containers", "Stopping", "WARNING: Not safe to continue now")):
            continue
        if re.fullmatch(r"[-\u2014\u2500=_ ]+", x) or x.startswith(("\u2014", "\u2500")) or "\u2014\u2014" in x:
            continue
        lines.append(x)
    if not problem:
        for x in lines:
            if x.startswith("Done"):
                return x[:limit]
    else:
        errors = [x[len("ERROR:"):].strip() for x in lines if x.startswith("ERROR:")]
        warned = [x[len("WARNING:"):].strip() for x in lines if x.startswith("WARNING:") and "lazy unmount" not in x]
        if errors:
            lines = errors
        elif warned:
            lines = warned
    while len(lines) > 1 and len(" ".join(lines)) > limit:
        lines.pop(0)
    return " ".join(lines)[-limit:]


def drive_listed(kind, ident):
    """True if the drives tool lists this drive under "rename" (drives in a pool) or "spare" (drives that can be set up or wiped). When the list cannot be read the request goes through, because the tool itself still checks everything."""
    try:
        acts = drives_json("actions")
    except Fail:
        return True
    return any(isinstance(x, dict) and x.get("id") == ident for x in acts.get(kind) or [])


def api_drives_do(action, body):
    """Run rename, sleep, wake or remount and return what the drives tool said."""
    words = [action]
    if action in ("rename", "sleep", "wake"):
        ident = body.get("id")
        if not isinstance(ident, str) or not DRIVE_ID.match(ident):
            raise Fail("Choose a drive first.")
        words.append(ident)
    if action == "rename":
        name = body.get("name")
        if not isinstance(name, str):
            raise Fail("Type a name first.")
        name = " ".join(name.split())
        if name != "auto" and not DRIVE_NAME.match(name):
            raise Fail("A name may have up to 40 letters, numbers, spaces and these marks: . ( ) + , -")
        if name != "auto" and (name[0] in " .-" or name[-1] in " .-"):
            raise Fail("A name cannot start or end with a space, a dot or a dash.")
        if not drive_listed("rename", body.get("id")):
            raise Fail("Only a drive that is in the Main or Backup pool can be renamed.")
        words.append(name)
    rc, out, err = drives_run(words, DRIVE_TIMEOUT.get(action, 90))
    msg = drive_message(out, err)
    if rc != 0:
        low = (err + out).lower()
        sudo_no = "password is required" in low or "not allowed" in low or "may not run sudo" in low or "no tty present" in low
        raise Fail(drives_problem(rc, err + out) if rc in (124, 127) or sudo_no or not msg else msg, 409 if rc == 1 and not sudo_no else 502)
    return {"message": msg or "Done."}


DRIVE_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}(:(keep|erase))?\Z")


def job_ids(body):
    ids = body.get("ids")
    if ids is None:
        ids = [body.get("id")]
    if not isinstance(ids, list) or not 1 <= len(ids) <= 8:
        raise Fail("Choose between one and eight drives.")
    out = []
    for t in ids:
        if not isinstance(t, str) or not DRIVE_TOKEN.match(t):
            raise Fail("Choose a drive first.")
        if t.split(":")[0] in [x.split(":")[0] for x in out]:
            raise Fail("A drive cannot be chosen twice.")
        out.append(t)
    each = [":" in t for t in out]
    if any(each) and not all(each):
        raise Fail("Every drive needs its own choice.")
    return out


def job_words(action, body):
    """Build the exact words of a drive change (add, wipe, disconnect, move) and check them before the drives tool is asked to do anything."""
    typed = body.get("typed", [])
    if not isinstance(typed, list) or len(typed) > 20 or not all(isinstance(w, str) and DRIVE_WORD.match(w) for w in typed):
        raise Fail("A confirmation word is not allowed.")

    def pick(key, allowed):
        v = body.get(key)
        if v not in allowed:
            raise Fail("Choose %s first." % key)
        return v
    if action == "moveboot":
        return ["moveboot"]
    if action == "appsfix":
        return ["appsfix", pick("mode", ("restore", "fresh"))] + typed
    if action == "bootadd":
        units = body.get("units")
        if not isinstance(units, int) or isinstance(units, bool) or not 1 <= units <= 999999:
            raise Fail("Choose a size first.")
        return ["bootadd", pick("role", ("main", "backup")), str(units)] + typed
    if action == "setup":
        name, ids = body.get("setup"), body.get("ids")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9-]{3,12}", name):
            raise Fail("Choose a setup first.")
        if not isinstance(ids, list) or not 1 <= len(ids) <= 16 or not all(isinstance(t, str) and DRIVE_TOKEN.match(t) for t in ids) or len({t.split(":")[0] for t in ids}) != len(ids):
            raise Fail("Choose the drives for the setup.")
        return ["setup", name, ",".join(ids)] + typed
    if action == "wipe":
        ident = body.get("id")
        if not isinstance(ident, str) or not DRIVE_ID.match(ident):
            raise Fail("Choose a drive first.")
        words = ["wipe", ident, pick("mode", ("empty", "format"))]
        return words + typed
    ids = job_ids(body)
    lst = ",".join(ids)
    each = ":" in ids[0]
    if action == "add":
        words = ["add", lst, pick("role", ("main", "backup")), "each" if each else pick("mode", ("keep", "erase"))]
    elif action == "disconnect":
        words = ["disconnect", lst, pick("copy", ("yes", "no"))]
    elif action == "move":
        words = ["move", lst, "each" if each else pick("keep", ("keep", "erase")), pick("copy", ("yes", "no"))]
    else:
        raise Fail("Unknown address.", 404)
    return words + typed


def job_progress(line):
    m = re.match(r"PROGRESS (\S+) (\d{1,3}) ?(.*)\Z", line)
    if not m:
        return False
    item, pct, text = m.group(1), min(100, int(m.group(2))), m.group(3)[:80]
    prog = JOB["progress"]
    JOB["current"] = item
    old = prog.get(item, {"pct": 0})
    prog[item] = {"pct": max(old["pct"], pct), "text": text}
    return True


def job_thread(words):
    """Run one drive change and keep its progress lines for the page. Holds the drive gate, so a change runs alone, until it ends."""
    rc, tail = 1, []
    try:
        try:
            p = subprocess.Popen(DRIVES_CMD + ["panel"] + words, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, bufsize=1)
        except FileNotFoundError:
            with JOB_LOCK:
                JOB["lines"] = ["command not found"]
            rc = 127
        else:
            timer = threading.Timer(JOB_MAX_SECONDS, p.kill)
            timer.start()
            try:
                for line in p.stdout:
                    line = line.rstrip()
                    if line:
                        with JOB_LOCK:
                            if not job_progress(line):
                                JOB["lines"] = (JOB["lines"] + [line])[-300:]
                rc = p.wait()
            finally:
                timer.cancel()
        with JOB_LOCK:
            tail = list(JOB["lines"])
    finally:
        text = "\n".join(tail)
        low = text.lower()
        sudo_no = "password is required" in low or "may not run sudo" in low or "no tty present" in low
        with JOB_LOCK:
            JOB["rc"] = rc
            if rc == 0:
                for it in JOB["items"]:
                    JOB["progress"][it] = {"pct": 100, "text": "Done"}
            JOB["message"] = drives_problem(rc, text) if rc in (124, 127) or sudo_no else (tail[-1] if rc == 4 and tail else drive_message(text, "", 1500, problem=(rc != 0)))
            JOB["running"] = False
            JOB["stopping"] = False
            drives_change_end()


