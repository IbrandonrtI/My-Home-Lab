DOCKER_FILE = os.path.join(IMAGES, "docker-trends.json")
DOCKER_SECS = float(os.environ.get("HLP_DOCKER_SECS") or 60)
DOCKER_POINTS = 60
DOCKER_TOP = 8
_MEM_UNITS = {"b": 1, "kb": 1000, "mb": 1000 ** 2, "gb": 1000 ** 3, "tb": 1000 ** 4,
              "kib": 1024, "mib": 1024 ** 2, "gib": 1024 ** 3, "tib": 1024 ** 4}


def docker_bytes(text):
    """'1.5GiB' or '312kB' as a number of bytes; 0 when it is not a size."""
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([A-Za-z]+)\s*", str(text or ""))
    if not m or m.group(2).lower() not in _MEM_UNITS:
        return 0
    return int(float(m.group(1)) * _MEM_UNITS[m.group(2).lower()])


def docker_parse(raw, cores):
    """The output of `docker stats --no-stream --format '{{json .}}'` as {name: (cpu % of the whole machine, memory bytes)}."""
    out = {}
    for line in (raw or "").splitlines():
        try:
            d = json.loads(line)
            name = re.sub(r"[^A-Za-z0-9_.-]", "", str(d.get("Name") or ""))[:40]
            cpu = float(str(d.get("CPUPerc") or "0").rstrip("% ") or 0) / max(1, cores)
            mem = docker_bytes(str(d.get("MemUsage") or "").split("/")[0])
        except (ValueError, TypeError, AttributeError):
            continue
        if name:
            out[name] = (round(max(0.0, cpu), 2), mem)
    return out


def docker_push(full, sample, now):
    """Add one reading to the full history {t, names, cpu, mem}, in place. A container that was not running counts as 0."""
    n = len(full["t"])
    full["t"] = (full["t"] + [int(now)])[-DOCKER_POINTS:]
    for name in sample:
        if name not in full["names"]:
            full["names"].append(name)
    for name in full["names"]:
        cur = sample.get(name, (0.0, 0))
        for series, val in ((full["cpu"], cur[0]), (full["mem"], cur[1])):
            old = series.get(name) or []
            series[name] = ([0] * (n - len(old)) + old + [val])[-DOCKER_POINTS:]
    for name in [x for x in full["names"] if not any(full["cpu"][x]) and not any(full["mem"][x])]:
        full["names"].remove(name)
        del full["cpu"][name], full["mem"][name]


def docker_summary(full, now, cores=1):
    """What the charts need. Each chart ranks the containers by its own number (processor or memory), names the busiest and adds the rest together as 'other'. The members of 'other' are kept too, so the page can say what is in it."""
    t = full["t"]
    out = {"version": 2, "step": DOCKER_SECS, "updated": int(now), "cores": cores, "t": t, "charts": {}}
    for key in ("cpu", "mem"):
        rank = sorted(full["names"], key=lambda x: -sum(full[key][x]))
        keep, rest = rank[:DOCKER_TOP], rank[DOCKER_TOP:]
        chart = {"names": list(keep), "series": {x: full[key][x] for x in keep}, "rest": {x: full[key][x] for x in rest}}
        if rest:
            chart["names"].append("other")
            total = [sum(full[key][x][i] for x in rest) for i in range(len(t))]
            chart["series"]["other"] = [round(v, 2) for v in total] if key == "cpu" else total
        out["charts"][key] = chart
    return out


def docker_loop():
    """Every minute: how much processor and memory each container uses, for the charts on the Stats tab."""
    cores = os.cpu_count() or 1
    full = {"t": [], "names": [], "cpu": {}, "mem": {}}
    while True:
        try:
            r = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{json .}}"],
                               capture_output=True, text=True, timeout=45, stdin=subprocess.DEVNULL)
            sample = docker_parse(r.stdout, cores) if r.returncode == 0 else {}
            if sample:
                now = time.time()
                docker_push(full, sample, now)
                if os.path.isdir(IMAGES):
                    write_atomic(DOCKER_FILE, json.dumps(docker_summary(full, now, cores), separators=(",", ":")), 0o644)
        except Exception as e:
            sys.stderr.write("docker stats: %r\n" % (e,))
        time.sleep(DOCKER_SECS)


def cmd_serve():
    ThreadingHTTPServer.request_queue_size = 64
    srv = ThreadingHTTPServer((BIND, PORT), Handler)
    srv.daemon_threads = True
    threading.Thread(target=job_status_loop, daemon=True).start()
    threading.Thread(target=look_regen_safe, daemon=True).start()
    threading.Thread(target=trends_loop, daemon=True).start()
    if not NO_DOCKER:
        threading.Thread(target=docker_loop, daemon=True).start()
    threading.Thread(target=schedule_loop, daemon=True).start()
    if not NO_DOCKER:
        threading.Thread(target=prefetch_theme_pictures, daemon=True).start()
    sys.stderr.write("homelab-panel %s listening on http://%s:%d (files in %s)\n" % (VERSION, BIND, PORT, HP))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def cmd_set_password(args):
    if "--stdin" in args:
        pw = sys.stdin.readline().rstrip("\n")
    else:
        pw = getpass.getpass("New password for the control panel (at least 10 characters): ")
        if getpass.getpass("Type it again: ") != pw:
            print("The two entries do not match. Nothing was changed.", file=sys.stderr)
            return 1
    try:
        set_password(pw)
    except Fail as e:
        print(str(e), file=sys.stderr)
        return 1
    print("The control panel password is set. All active sessions have been logged out.")
    return 0


def cmd_status():
    print("homelab-panel %s" % VERSION)
    print("  password:       %s" % ("set" if os.path.exists(PASSFILE) else "Not set (run: homelab panel password)"))
    print("  listens on:     http://%s:%d" % (BIND, PORT))
    print("  dashboard files: %s" % HP)
    print("  page files:     %s" % UI_DIR)
    return 0


def store_theme_pictures(check=False, timeout=20):
    """Store the picture of every theme in the images folder. Returns (new, missing). With check=True nothing is downloaded."""
    os.makedirs(IMAGES, exist_ok=True)
    new = missing = 0
    for t in LOOK_THEMES:
        if not t.get("background") or theme_file(t["id"]):
            continue
        data = None if check else theme_download(t, timeout)
        ext = sniff_image(data) if data else None
        if not ext:
            missing += 1
            continue
        path = os.path.join(IMAGES, "theme-%s%s%s" % (t["id"], THEME_PIC_REV, ext))
        with open(path, "wb") as f:
            f.write(data)
        os.chmod(path, 0o644)
        new += 1
    return new, missing


def cmd_theme_pictures(args):
    """Store the picture of every theme in the images folder. Homepage serves a picture only if it was there when Homepage started, so having them all in place
    means choosing a theme later never needs a restart. With --check nothing is downloaded: the answer is the exit status (0 = all stored)."""
    new, missing = store_theme_pictures("--check" in args)
    print("new %d missing %d" % (new, missing))
    return 1 if missing else 0


def prefetch_theme_pictures():
    """A little after the panel starts, fetch any theme picture that is not stored yet and restart Homepage once if there were any, so that choosing a theme
    never has to. It tries once per start."""
    time.sleep(20)
    try:
        new, _missing = store_theme_pictures()
    except OSError:
        return
    if new:
        restart_homepage()


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "help"
    if cmd == "theme-pictures":
        return cmd_theme_pictures(argv[2:])
    if cmd == "serve":
        cmd_serve()
        return 0
    if cmd == "set-password":
        return cmd_set_password(argv[2:])
    if cmd == "status":
        return cmd_status()
    if cmd == "version":
        print(VERSION)
        return 0
    print(__doc__)
    return 0 if cmd in ("help", "-h", "--help") else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
