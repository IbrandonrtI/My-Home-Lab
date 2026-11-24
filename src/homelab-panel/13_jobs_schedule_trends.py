def read_bytes(p):
    try:
        with open(p, "rb") as f:
            return f.read()
    except OSError:
        return None


JOBSTATUS_FILE = os.path.join(IMAGES, "job-status.json")
MDSTAT = os.environ.get("HLP_MDSTAT") or "/proc/mdstat"
JOBSTATUS_SECS = float(os.environ.get("HLP_JOBSTATUS_SECS") or 5)
DRIVE_TITLES = {"setup": "Building the new drive setup", "add": "Adding a drive", "move": "Moving a drive", "disconnect": "Taking a drive out of its pool", "wipe": "Erasing a drive",
                "bootadd": "Reserving space on the boot drive", "moveboot": "Moving files from the boot drive", "movefolders": "Moving folders to another drive", "appsfix": "Repairing Immich and Nextcloud", "remount": "Repairing the drives"}
UPDATE_TITLES = {"check": "Looking for updates", "containers": "Updating the containers", "containers-now": "Updating the containers", "system": "Updating the system", "restart": "Restarting the machine"}
MD_TITLES = {"resync": "Syncing drive array %s", "recovery": "Rebuilding drive array %s", "reshape": "Resizing drive array %s", "check": "Checking drive array %s"}


def eta_from_pace(pct, started, now):
    """Time left, from how long the job has taken so far. Given only when the percent is high enough for the pace to mean something."""
    if pct is None or not started or pct < 15 or pct >= 99 or now - started < 45:
        return None
    return max(60, int((now - started) * (100 - pct) / pct))


def md_jobs():
    """Drive arrays that are building or checking their redundancy in the background, with the percent and the finish time the system itself reports."""
    jobs, name = [], ""
    for line in read_text(MDSTAT).splitlines():
        m = re.match(r"(md\w+) :", line)
        if m:
            name = m.group(1)
            continue
        m = re.search(r"(resync|recovery|reshape|check)\s*=\s*([\d.]+)%", line)
        if name and m:
            f = re.search(r"finish=([\d.]+)min", line)
            sp = re.search(r"speed=(\d+)K/sec", line)
            jobs.append({"id": "md:" + name, "kind": "array", "title": MD_TITLES[m.group(1)] % name, "step": "Runs in the background. The drives can be used meanwhile." + (" About %d MB/s." % round(int(sp.group(1)) / 1024) if sp else ""),
                         "pct": min(99, int(float(m.group(2)))), "eta": int(float(f.group(1)) * 60) if f else None, "started": 0})
    return jobs


def job_status_jobs():
    now = int(time.time())
    jobs = []
    with UPJOB_LOCK:
        if UPJOB["running"]:
            pct = UPJOB["pct"]
            jobs.append({"id": "update", "kind": "updates", "title": UPDATE_TITLES.get(UPJOB["action"], "Updating"), "step": UPJOB["stage"] or "Working...", "pct": pct, "eta": eta_from_pace(pct, UPJOB["started"], now), "started": UPJOB["started"]})
    with JOB_LOCK:
        if JOB["running"]:
            vals = [JOB["progress"].get(i, {}).get("pct", 0) for i in JOB["items"]] or []
            pct = min(99, int(sum(vals) / len(vals))) if vals and JOB["progress"] else None
            cur = JOB["progress"].get(JOB["current"], {})
            jobs.append({"id": "drives", "kind": "drives", "title": DRIVE_TITLES.get(JOB["action"], "Changing the drives"), "step": cur.get("text") or "Working...", "pct": pct, "eta": eta_from_pace(pct, JOB["started"], now), "started": JOB["started"]})
    with BJOB_LOCK:
        if BJOB["running"]:
            pct = BJOB["pct"]
            jobs.append({"id": "backup", "kind": "backup", "title": {"run": "Running a backup", "dry": "Previewing a backup", "restore": "Restoring files"}.get(BJOB["action"], "Backup"), "step": "Working...", "pct": pct, "eta": eta_from_pace(pct, BJOB["started"], now), "started": BJOB["started"]})
    return jobs + md_jobs()


def job_status_write(last):
    """Write the running jobs for the dashboard's progress ring (images/job-status.json). `last` is True when the previous write held jobs. Returns True when this one does."""
    jobs = job_status_jobs()
    if not jobs and not last:
        return False
    if os.path.isdir(IMAGES):
        try:
            write_atomic(JOBSTATUS_FILE, json.dumps({"version": 1, "updated": int(time.time()), "jobs": jobs}), 0o644)
        except OSError:
            pass
    return bool(jobs)


def job_status_loop():
    last = True
    while True:
        try:
            last = job_status_write(last)
        except Exception as e:
            sys.stderr.write("job status: %r\n" % (e,))
        time.sleep(JOBSTATUS_SECS)


# ---- Day and night: the server switches the theme at sunrise and sunset ----
SCHEDULE = os.path.join(HP, ".panel-schedule.json")
SCHEDULE_SECS = float(os.environ.get("HLP_SCHEDULE_SECS") or 60)
SCHEDULE_DEFAULT = {"enabled": False, "mode": "sun", "dayAt": "07:00", "nightAt": "19:00", "phase": ""}
TIME_HM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def now_utc():
    t = os.environ.get("HLP_NOW")
    return datetime.datetime.fromtimestamp(float(t), datetime.timezone.utc) if t else datetime.datetime.now(datetime.timezone.utc)


def sun_events(lat, lon, date):
    """Sunrise and sunset of a calendar date at a place, as UTC times (None in polar day or night). Accurate to a few minutes, which is plenty for switching a theme."""
    n = date.timetuple().tm_yday
    lng_hour = lon / 15.0
    base = datetime.datetime(date.year, date.month, date.day, tzinfo=datetime.timezone.utc)
    noon = base + datetime.timedelta(hours=12 - lng_hour)
    out = []
    for rising in (True, False):
        t = n + ((6 if rising else 18) - lng_hour) / 24.0
        m = 0.9856 * t - 3.289
        l = (m + 1.916 * math.sin(math.radians(m)) + 0.020 * math.sin(math.radians(2 * m)) + 282.634) % 360
        ra = math.degrees(math.atan(0.91764 * math.tan(math.radians(l)))) % 360
        ra = (ra + math.floor(l / 90) * 90 - math.floor(ra / 90) * 90) / 15.0
        sin_dec = 0.39782 * math.sin(math.radians(l))
        cos_dec = math.cos(math.asin(sin_dec))
        cos_h = (math.cos(math.radians(90.833)) - sin_dec * math.sin(math.radians(lat))) / (cos_dec * math.cos(math.radians(lat)))
        if cos_h > 1 or cos_h < -1:
            return None
        h = (360 - math.degrees(math.acos(cos_h))) if rising else math.degrees(math.acos(cos_h))
        ut = (h / 15.0 + ra - 0.06571 * t - 6.622 - lng_hour) % 24
        cands = [base + datetime.timedelta(hours=ut + 24 * k) for k in (-1, 0, 1)]
        # The sun rises about 6 hours before local solar noon at the equinox and sets about 6 hours after it. This picks the right one of the three days.
        out.append(min(cands, key=lambda c: abs((c - noon).total_seconds() - (-6 if rising else 6) * 3600)))
    return out[0], out[1]


def hm_minutes(text):
    return int(text[:2]) * 60 + int(text[3:])


def schedule_zone(loc):
    try:
        return zoneinfo.ZoneInfo(loc.get("timeZone")) if loc.get("timeZone") else datetime.datetime.now().astimezone().tzinfo
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return datetime.datetime.now().astimezone().tzinfo


def schedule_phase(sch, loc, now=None):
    """('day' or 'night', (sunrise, sunset) in UTC or None) for the schedule at this moment."""
    now = now or now_utc()
    local = now.astimezone(schedule_zone(loc))
    if sch.get("mode", "sun") == "sun" and loc.get("lat") is not None and loc.get("lon") is not None:
        ev = sun_events(loc["lat"], loc["lon"], local.date())
        if ev:
            return ("day" if ev[0] <= now < ev[1] else "night"), ev
    mins = local.hour * 60 + local.minute
    d, n = hm_minutes(sch.get("dayAt") or "07:00"), hm_minutes(sch.get("nightAt") or "19:00")
    day = (d <= mins < n) if d < n else (mins >= d or mins < n)
    return ("day" if day else "night"), None


def schedule_read():
    try:
        d = json.loads(read(SCHEDULE) or "{}")
    except ValueError:
        d = {}
    return d if isinstance(d, dict) else {}


def schedule_write(sch):
    write_atomic(SCHEDULE, json.dumps(sch, indent=1, sort_keys=True), 0o644)


def schedule_package(raw, what):
    """Check what the page sends for the day or the night: the theme (one of the built-in ones), its look and its picture sliders."""
    if not isinstance(raw, dict):
        raise Fail("Choose the %s theme first." % what)
    t = next((x for x in LOOK_THEMES if x["id"] == raw.get("theme")), None)
    if not t:
        raise Fail("The %s theme must be one of the built-in themes." % what)
    sliders = raw.get("bg") if isinstance(raw.get("bg"), dict) else {}
    sliders = {k: sliders[k] for k in ("blur", "saturate", "brightness", "opacity") if k in sliders}
    bg_numbers(sliders, "")
    look = look_clean(raw.get("look"))
    for k in PERSONAL_KEYS:
        look.pop(k, None)
    return {"theme": t["id"], "look": look, "bg": sliders}


def schedule_apply(sch, phase):
    pkg = sch.get(phase)
    if not isinstance(pkg, dict):
        return False
    with LOCK:
        cur = look_get()
        new = dict(look_clean(pkg.get("look") or {}))
        for k in PERSONAL_KEYS:
            if k in cur:
                new[k] = cur[k]
        new["theme"] = pkg["theme"]
        tx = Tx("Day and night: the %s theme" % phase)
        tx.put(CSS, css_with_look(tx.get(CSS), look_clean(new)))
        t = next((x for x in LOOK_THEMES if x["id"] == pkg["theme"]), None)
        if t and t.get("background"):
            have = theme_file(t["id"])
            tx.put(SETTINGS, bg_numbers(pkg.get("bg") or {}, bg_set(tx.get(SETTINGS), "image", "/images/" + have if have else t["background"]["url"])))
        return tx.commit()


def schedule_tick(force=False):
    with LOCK:
        sch = schedule_read()
        if not sch.get("enabled") or not isinstance(sch.get("day"), dict) or not isinstance(sch.get("night"), dict):
            return False
        phase, _ = schedule_phase(sch, location_state(False))
        if phase == sch.get("phase") and not force:
            return False
        schedule_apply(sch, phase)
        sch["phase"] = phase
        sch["applied"] = int(time.time())
        schedule_write(sch)
        return True


def schedule_loop():
    while True:
        try:
            schedule_tick()
        except Exception as e:
            sys.stderr.write("day and night: %r\n" % (e,))
        time.sleep(SCHEDULE_SECS)


def local_hm(dt, loc):
    return dt.astimezone(schedule_zone(loc)).strftime("%H:%M")


def schedule_state():
    sch = schedule_read()
    loc = location_state(False)
    out = {k: sch.get(k, v) for k, v in SCHEDULE_DEFAULT.items()}
    out["dayTheme"] = (sch.get("day") or {}).get("theme", "")
    out["nightTheme"] = (sch.get("night") or {}).get("theme", "")
    out["city"] = loc.get("city") or ""
    out["hasPlace"] = loc.get("lat") is not None and loc.get("lon") is not None
    out["timeZone"] = loc.get("timeZone") or ""
    now = now_utc()
    phase, ev = schedule_phase(sch, loc, now)
    out["now"] = phase
    out["sunrise"] = local_hm(ev[0], loc) if ev else ""
    out["sunset"] = local_hm(ev[1], loc) if ev else ""
    return out


def api_schedule(body):
    op = body.get("op")
    sch = schedule_read()
    if op == "off":
        sch["enabled"] = False
        schedule_write(sch)
        return {}
    if op != "save":
        raise Fail("That request is not understood.")
    mode = body.get("mode")
    if mode not in ("sun", "fixed"):
        raise Fail("Choose sunrise and sunset, or fixed times.")
    day_at, night_at = body.get("dayAt") or SCHEDULE_DEFAULT["dayAt"], body.get("nightAt") or SCHEDULE_DEFAULT["nightAt"]
    if not (isinstance(day_at, str) and TIME_HM.match(day_at) and isinstance(night_at, str) and TIME_HM.match(night_at)):
        raise Fail("The times must look like 07:00 and 19:30.")
    if day_at == night_at:
        raise Fail("The day and night times cannot be the same.")
    loc = location_state(False)
    if mode == "sun" and (loc.get("lat") is None or loc.get("lon") is None):
        raise Fail("Sunrise and sunset need a city. Choose one on the Location screen first, or use fixed times.")
    sch.update({"enabled": True, "mode": mode, "dayAt": day_at, "nightAt": night_at, "phase": "",
                "day": schedule_package(body.get("day"), "day"), "night": schedule_package(body.get("night"), "night")})
    schedule_write(sch)
    schedule_tick(True)
    return {}


# ---- Short history of CPU, memory, network and temperature, for the small graphs in the header ----
TRENDS_FILE = os.path.join(IMAGES, "trends.json")
TRENDS_SECS = float(os.environ.get("HLP_TRENDS_SECS") or 30)
TRENDS_POINTS = 120
PROC = os.environ.get("HLP_PROC") or "/proc"
SYS = os.environ.get("HLP_SYS") or "/sys"
TRENDS_SERIES = ("cpu", "mem", "rx", "tx", "temp")


def proc_cpu():
    with open(os.path.join(PROC, "stat")) as f:
        v = [int(x) for x in f.readline().split()[1:9]]
    return sum(v) - v[3] - v[4], sum(v)


def proc_mem():
    d = {}
    with open(os.path.join(PROC, "meminfo")) as f:
        for line in f:
            k, _, rest = line.partition(":")
            if k in ("MemTotal", "MemAvailable"):
                d[k] = int(rest.split()[0])
    return 100.0 * (d["MemTotal"] - d["MemAvailable"]) / d["MemTotal"]


def proc_net():
    rx = tx = 0
    with open(os.path.join(PROC, "net", "dev")) as f:
        for line in f.readlines()[2:]:
            name, _, rest = line.partition(":")
            name = name.strip()
            if not rest or name == "lo" or name.startswith(("docker", "veth", "br-", "virbr", "tailscale", "wg", "tun", "zt")):
                continue
            c = rest.split()
            rx += int(c[0])
            tx += int(c[8])
    return rx, tx


def sys_temp():
    best = None
    for pat in ("class/hwmon/hwmon*/temp*_input", "class/thermal/thermal_zone*/temp"):
        for p in glob.glob(os.path.join(SYS, pat)):
            try:
                with open(p) as f:
                    c = int(f.read().strip()) / 1000.0
            except (OSError, ValueError):
                continue
            if 1 < c < 130 and (best is None or c > best):
                best = c
        if best is not None:
            break
    return best


def trends_load():
    try:
        d = json.loads(read(TRENDS_FILE) or "{}")
    except ValueError:
        d = {}
    if not isinstance(d, dict) or time.time() - (d.get("updated") or 0) > 600:
        return {k: [] for k in TRENDS_SERIES}
    return {k: [x for x in (d.get(k) or []) if x is None or isinstance(x, (int, float))][-TRENDS_POINTS:] for k in TRENDS_SERIES}


def trends_loop():
    data = trends_load()
    prev_cpu = prev_net = prev_t = None
    while True:
        try:
            now = time.time()
            cpu = proc_cpu()
            net = proc_net()
            row = {"mem": round(proc_mem(), 1), "temp": None, "cpu": None, "rx": None, "tx": None}
            t = sys_temp()
            row["temp"] = round(t, 1) if t is not None else None
            if prev_cpu and cpu[1] > prev_cpu[1]:
                row["cpu"] = round(100.0 * (cpu[0] - prev_cpu[0]) / (cpu[1] - prev_cpu[1]), 1)
            if prev_net and now > prev_t:
                row["rx"] = max(0, int((net[0] - prev_net[0]) / (now - prev_t)))
                row["tx"] = max(0, int((net[1] - prev_net[1]) / (now - prev_t)))
            prev_cpu, prev_net, prev_t = cpu, net, now
            if row["cpu"] is not None:
                for k in TRENDS_SERIES:
                    data[k] = (data[k] + [row[k]])[-TRENDS_POINTS:]
                if os.path.isdir(IMAGES):
                    write_atomic(TRENDS_FILE, json.dumps(dict(data, version=1, updated=int(now), step=TRENDS_SECS), separators=(",", ":")), 0o644)
        except Exception as e:
            sys.stderr.write("trends: %r\n" % (e,))
        time.sleep(TRENDS_SECS)


