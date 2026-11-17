def ensure_root():
    if FAKE or os.geteuid() == 0:
        return
    if not have("sudo"):
        raise SystemExit("homelab-setup must run as root, and sudo is not installed.")
    words = ["sudo", "-E"]
    if os.environ.get("TS_AUTHKEY_FILE"):
        words += ["env", "TS_AUTHKEY_FILE=" + os.path.abspath(os.environ["TS_AUTHKEY_FILE"])]
    os.execvp("sudo", words + [sys.executable] + sys.argv)


def homepage_file_problems():
    """The dashboard shows no cards or no look when one of its files is missing, empty or not valid YAML, and nothing else complains. One line per problem."""
    found = []
    if not os.path.isdir(P(hp_dir())):
        return found
    try:
        import yaml
    except ImportError:
        yaml = None
    for f in ("settings.yaml", "services.yaml", "bookmarks.yaml", "widgets.yaml", "custom.css"):
        path = hp_path(f)
        if not os.path.exists(path):
            found.append("%s is missing" % f)
        elif not os.path.getsize(path):
            found.append("%s is empty" % f)
        elif yaml and f.endswith(".yaml"):
            try:
                with open(path, encoding="utf-8") as fh:
                    yaml.safe_load(fh)
            except (yaml.YAMLError, UnicodeDecodeError, OSError):
                found.append("%s is not valid YAML, so Homepage cannot read it" % f)
        elif not os.access(path, os.R_OK):
            found.append("%s cannot be read" % f)
    return found


def remember_repo():
    """Save where the downloaded copy of the lab is, but never a folder that is not one (an installed installer sits in /usr/local)."""
    if looks_like_repo(Ctx.repo) or Opt.repo:
        State.data["repo"] = Ctx.repo


# One-time actions of a first install. A lab that already runs has had them; running them again would upgrade every package or put the shipped layout back.
ONE_TIME_STEPS = ("apt-update", "apt-upgrade", "homepage-tabs", "homepage-stats", "homepage-calendar", "homepage-customize", "homepage-clock", "speedtest-first")
SALVAGE_ANSWERS = ("admin", "email", "lan", "tz", "tz_found", "adguard", "lvm_grow", "ts_token_asked")


def salvage_state_text(body):
    """The readable parts of a damaged state file: answers and finished one-time actions written as plain "name": "value" pairs."""
    found = {"answers": {}, "ran": {}}
    for key in SALVAGE_ANSWERS:
        m = re.search(r'"%s"\s*:\s*"([^"\\]*)"' % re.escape(key), body)
        if m:
            found["answers"][key] = m.group(1)
    m = re.search(r'"ran"\s*:\s*\{([^{}]*)(?:\}|$)', body)
    if m:
        for k, v in re.findall(r'"([A-Za-z0-9_-]+)"\s*:\s*"([^"\\]*)"', m.group(1)):
            found["ran"][k] = v
    m = re.search(r'"weather"\s*:\s*\{([^{}]*)\}', body)
    if m:
        w = dict(re.findall(r'"([a-z]+)"\s*:\s*"([^"\\]*)"', m.group(1)))
        w.update({k: float(v) for k, v in re.findall(r'"(lat|lon)"\s*:\s*(-?[0-9.]+)', m.group(1))})
        if w.get("name"):
            found["answers"]["weather"] = w
    return found


def newest_damaged_copy():
    folder = os.path.dirname(STATE_FILE)
    try:
        names = sorted(f for f in os.listdir(folder) if f.startswith(os.path.basename(STATE_FILE) + ".damaged-"))
    except OSError:
        return ""
    return os.path.join(folder, names[-1]) if names else ""


def read_back_answers():
    """The admin name and e-mail address as they are written in the logins of Homepage's widgets (AdGuard Home: the admin name; Beszel: the e-mail)."""
    found = {}
    try:
        import yaml
        data = yaml.safe_load(read_file(hp_path("services.yaml")) or "")
    except Exception:  # no yaml module, or a file that is not valid yaml
        return found

    def walk(node):
        if isinstance(node, dict):
            kind, user = node.get("type"), node.get("username")
            if isinstance(user, str) and user.strip():
                if kind == "adguard":
                    found.setdefault("admin", user.strip())
                elif kind == "beszel" and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", user.strip()):
                    found.setdefault("email", user.strip())
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(data)
    return found


def gather_rebuild_answers():
    """The answers a rebuilt state file would hold, from the damaged copy when it is readable and then from what is installed, and the finished one-time actions
    of that copy. Nothing is written."""
    a = {}
    copy = newest_damaged_copy()
    salvaged = salvage_state_text(read_file(copy)) if copy else {"answers": {}, "ran": {}}
    for k, v in salvaged["answers"].items():
        a.setdefault(k, v)
    for k, v in read_back_answers().items():
        if not a.get(k):
            a[k] = v
    if "adguard" not in a:
        names = containers_all()
        a["adguard"] = "yes" if any(c in names for c in STACKS["adguard"][1]) else "no"
    return a, salvaged


def has_weather_widget():
    return bool(re.search(r"openmeteo:", read_file(hp_path("widgets.yaml"))))


def rebuild_state_from_machine():
    """`refresh --force-existing`: write a new state file for a lab that already runs. Answers come from the damaged copy when it is readable, then from what
    is installed; only what cannot be found is asked. One-time first-install actions count as done, so the rebuild does not upgrade every package or put
    the shipped dashboard layout back."""
    a = State.data["answers"]
    found, salvaged = gather_rebuild_answers()
    for k, v in found.items():
        a.setdefault(k, v)
    missing = [k for k in ("admin", "email") if not a.get(k)]
    if missing:
        if not interactive():
            raise Abort("The %s could not be read back from this machine and no terminal is open to ask for it. Run `sudo homelab-setup refresh --force-existing` in a terminal." % " and ".join(
                "admin name" if k == "admin" else "email address" for k in missing))
        out("")
        say("Some answers could not be read back from this machine, so they are asked once more:")
        if "admin" in missing:
            a["admin"] = ask("Admin name for every service", Ctx.user.capitalize())
        if "email" in missing:
            a["email"] = ask("Email address (login for Immich, Beszel and Speedtest Tracker)", "")
            while not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", a["email"]):
                a["email"] = ask("That is not a valid email address. Enter it again", "")
    Ctx.detect()
    a.setdefault("lan", Ctx.lan)
    if Ctx.tz:
        a.setdefault("tz", Ctx.tz)
    remember_repo()
    stamp = time.strftime("%F %T")
    for k, v in salvaged["ran"].items():
        State.data["ran"].setdefault(k, v)
    for k in ONE_TIME_STEPS:
        State.data["ran"].setdefault(k, stamp)
    if not State.data.get("weather_set") and has_weather_widget():
        w = a.get("weather")
        State.data["weather_set"] = w["name"] if isinstance(w, dict) and w.get("name") else "kept"
    State.mark("install-started")
    kept = [k for k in a if a.get(k)]
    say("Answers kept or read back: %s." % (", ".join(sorted(kept)) or "none"))


def preview_rebuild():
    """The dry run of `refresh --force-existing`: what the rebuild would keep, ask for and mark as done."""
    found, salvaged = gather_rebuild_answers()
    out("")
    say("It would keep or read back these answers: %s." % (", ".join(sorted(k for k in found if found.get(k))) or "none"))
    still = [("admin name" if k == "admin" else "email address") for k in ("admin", "email") if not found.get(k)]
    if still:
        say("It would ask for: %s." % " and ".join(still))
    say("It would count these first-install actions as done, so they are not repeated: %s." % ", ".join(ONE_TIME_STEPS))
    say("Then it would check every step again and repair what is missing. Nothing was changed. The step count is only known after a real run.")


def damaged_state_seen():
    """True when this run found a state file it could not read."""
    return Mode.state_damaged


def load_all():
    State.load()
    Mode.state_damaged = State.damaged
    if State.damaged:
        kept = State.keep_damaged()
        warn("The setup state file %s is damaged and cannot be read. %sAnswers you gave earlier may have to be given again. To build a new one from what is installed: sudo homelab-setup refresh --force-existing." % (
            STATE_FILE, ("A copy was kept as %s. " % kept) if kept else "It is kept under a new name (.damaged-<date>) before a new one is written. "))
    Secrets.load()
    Ctx.detect()
    apply_adopted_ports()
    Mode.existing = is_existing()
    State.readonly = Mode.existing and not Opt.force_existing
    if not State.readonly and not Opt.dry:
        clean_stale_temp_files()


def password_warning():
    out("")
    warn("One password is used for every admin login (Portainer, %sBeszel, Immich, Nextcloud, FileBrowser, "
         "Speedtest Tracker). If one service leaks it, all of them are exposed. Homepage's configuration file also stores "
         "some of these logins in plain text. Use a long password that is not used anywhere else and keep it in a password "
         "manager." % ("AdGuard Home, " if adguard_wanted() else ""))


def auto_location(a):
    if a.get("tz") and a.get("weather"):
        return
    found = ip_location()
    if found:
        if not a.get("tz") and found["tz"]:
            a["tz"] = found["tz"]
            a["tz_found"] = found["tz"]
        if not a.get("weather"):
            a["weather"] = {k: found[k] for k in ("name", "region", "country", "lat", "lon")}
        good("Detected automatically: %s, time zone %s (change it any time on the Look tab of Customize)" % (
            ", ".join(x for x in (found["name"], found["region"], found["country"]) if x), a.get("tz") or Ctx.tz))
    else:
        a.setdefault("tz", Ctx.tz)
        warn("The location lookup did not answer, so the machine's time zone (%s) is used and the weather card shows New York. "
             "Change both on the Look tab of Customize." % a["tz"])


LVM_EXPLAIN = ("The Ubuntu Server installer creates a small system volume (about 100 GB) and leaves the rest of the drive unused. "
               "Using that space enlarges the system volume. Nothing is erased and nothing moves: files stay as they "
               "are, and it is done while the machine runs. It is needed to use part of this drive as a pool "
               "later (sudo drives bootsection). A volume is easy to grow but difficult to shrink.")


def lvm_question(info):
    out("")
    say("This machine's system volume is %s, but its drive has another %s that nothing uses." %
        (pretty_size(info["size"]), pretty_size(info["free"])))
    say(LVM_EXPLAIN)
    return yesno("Add the unused space to the system volume?", True)


def ask_grow_boot_volume(a):
    if "lvm_grow" in a:
        return
    info = root_lvm_info()
    if not info or info["free"] < LVM_MIN_FREE:
        return
    a["lvm_grow"] = "yes" if lvm_question(info) else "no"
    State.save()


def grow_boot_volume():
    info = root_lvm_info()
    if not info or info["free"] < LVM_MIN_FREE:
        return False
    out("")
    rule("Using the unused space of the drive")
    say("Growing the system volume from %s by %s ..." % (pretty_size(info["size"]), pretty_size(info["free"])))
    rc, text = act(["lvextend", "-r", "-l", "+100%FREE", info["src"]], timeout=900)
    if rc != 0:
        warn("The system volume could not be enlarged, so nothing was changed. Reason:\n      %s\n"
             "      To try again later, run:  sudo homelab-setup growdisk" % "\n      ".join(text.strip().splitlines()[-4:]))
        return False
    if not Opt.dry:
        good("The system volume has been enlarged.")
        State.data["answers"]["lvm_grow"] = "done"
        State.save()
    return True


def cmd_growdisk():
    info = root_lvm_info()
    if not info or info["free"] < LVM_MIN_FREE:
        out("")
        say("Nothing to do: the system volume already uses its whole drive, or it is not an LVM volume with room to grow.")
        return
    if not lvm_question(info):
        say("Nothing was changed.")
        return
    grow_boot_volume()


def is_ipv4(text):
    return bool(re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", text)) and all(int(x) <= 255 for x in text.split("."))


def ask_tailscale_token(a):
    """Optionally ask for the Tailscale access token used by the Homepage Tailscale card. Pressing Enter skips it; it can be added later with `fill`."""
    if a.get("ts_token_asked") or Secrets.get("TAILSCALE_API_TOKEN") or Opt.yes or Opt.dry:
        return
    if FAKE:
        if os.environ.get("HLS_ASK_TS") != "1":
            return
    elif not interactive():
        return
    out("")
    say("This machine is now connected to Tailscale. The Tailscale card on your dashboard needs an access token from your Tailscale account. "
        "It takes a minute to create, and the installer then fills in the card automatically. "
        "Open https://login.tailscale.com/admin/settings/keys, press Generate access token, copy it and paste it here. "
        "Press Enter to skip. The token is used only for that card and can be added later with:  sudo homelab-setup fill")
    tok = ask_secret("Tailscale access token (starts with tskey-api-, Enter to skip)").strip()
    a["ts_token_asked"] = "yes"
    State.save()
    if not tok:
        return
    if not re.fullmatch(r"tskey-[A-Za-z0-9_-]{10,}", tok):
        warn("That does not look like a Tailscale access token (it starts with tskey-api-), so it was skipped. You can add it later with:  sudo homelab-setup fill")
        return
    Secrets.set("TAILSCALE_API_TOKEN", tok)
    good("Saved. The Tailscale card is filled in after the machine has joined your Tailscale network.")


def ask_answers():
    """Ask the questions at the start of an install: admin name, email, LAN address and password. Time zone and city are detected automatically."""
    a = State.data["answers"]
    out("")
    say("A few answers are needed first. They stay on this machine and only fill in its configuration files.")
    out("")
    a["admin"] = ask("Admin name for every service", a.get("admin") or Ctx.user.capitalize())
    a["email"] = ask("Email address (login for Immich, Beszel and Speedtest Tracker)", a.get("email", ""))
    while not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", a["email"]):
        a["email"] = ask("That is not a valid email address. Enter it again", "")
    auto_location(a)
    a["lan"] = ask("This machine's LAN address (reserve it in the router so that it does not change)", a.get("lan") or Ctx.lan)
    while not is_ipv4(a["lan"].strip()):
        a["lan"] = ask("That is not an address like 192.168.1.20. Enter it again", "")
    a["lan"] = a["lan"].strip()
    if "adguard" not in a and "adguard" in adopted():
        a["adguard"] = "yes"
    if "adguard" not in a:
        out("")
        say("AdGuard Home blocks ads and trackers for every device on your network by acting as the network's DNS server. To do "
            "that it takes port 53 from this machine's built-in DNS resolver, and each device must then be pointed at it. It can be "
            "skipped now and added later with:  sudo homelab-setup adguard")
        a["adguard"] = "yes" if yesno("Install AdGuard Home?", True) else "no"
    State.save()
    Ctx.detect()
    if not Runtime.password:
        password_warning()
        out("")
        for _ in range(3):
            p1 = ask_secret("Choose the admin password (12 or more letters and digits; it is not saved)")
            problem = password_problem(p1)
            if problem:
                warn(problem)
                continue
            if ask_secret("Type it again") != p1:
                warn("The two entries did not match.")
                continue
            Runtime.password = p1
            break
        else:
            raise Abort("No valid password was entered.")


def preflight():
    out("")
    if OsSupported().probe() != "done":
        raise Abort(OsSupported().help())
    good("Operating system: %s" % Ctx.os_name)
    if not Ctx.lan:
        raise Abort("Could not detect this machine's network address. Connect it to the network and try again.")
    good("Network address: %s" % Ctx.lan)
    try:
        socket.getaddrinfo("download.docker.com", 443)
        good("Internet reachable")
    except OSError:
        if not FAKE:
            raise Abort("No internet access (download.docker.com did not resolve). Check the network and try again.") from None
    free = shutil.disk_usage(P("/") if os.path.isdir(P("/")) else "/").free / 1073741824.0
    if free < 20:
        warn("Only %.0f GB free on the boot drive. The services need about 20 GB (more with photos)." % free)
    else:
        good("Free space on the boot drive: %.0f GB" % free)


def show_secret_values():
    out("")
    for k in sorted(Secrets.vals):
        out("   %-28s %s" % (k, Secrets.vals[k]))
    out("")


def final_report(res, background=False):
    Live.close()
    done, total = counts(res)
    failed = [s for s in STEPS if res[s.id].state == "failed"]
    rule("Install finished")
    good("Finished in %s. %d of %d steps are done." % (fmt_time(Live.elapsed_total()), done, total))
    if background:
        say_background_start(res)
    if failed:
        bad("%d step(s) failed: %s. `sudo homelab-setup refresh` tries them again." % (
            len(failed), "; ".join(s.title for s in failed[:3]) + (" ..." if len(failed) > 3 else "")))
    if adopted():
        say("Left as they are, because you already ran them: %s." % ", ".join(ADOPT_LABELS[n] for n in adopted()))
    Secrets.load()
    if Secrets.vals:
        say("Generated passwords and keys are kept in %s (root only). Show them any time with:  sudo homelab-setup secrets" % SECRET_FILE.replace(ROOT, ""))
    offer_drive_wizard()
    show_checklist(res, "Setup")
    next_step_section(res)
    show_dashboard_links()


def show_dashboard_links():
    """Print where to open the dashboard (Homepage): the address on this network and the one over Tailscale."""
    Ctx.refresh_tailscale()
    if not Ctx.lan and not HOST_OVERRIDE:
        Ctx.lan = detect_lan()
    rule("Open the dashboard")
    if svc_host() == "127.0.0.1":
        # Another device cannot use 127.0.0.1, and Homepage refuses that name, so the fallback shown is localhost.
        out("  Homepage, on this network:   this machine's network address is not known yet (open it on this machine at %s)" % mark(url("homepage").replace("127.0.0.1", "localhost")))
    else:
        out("  Homepage, on this network:   %s" % mark(url("homepage")))
    if Ctx.fqdn:
        out("  Homepage, over Tailscale:    %s" % mark("https://%s:%d" % (Ctx.fqdn, SERVE[0][0])))
        out("  %sThe Tailscale address works from your other devices, not from this machine itself.%s" % (D, N))
    else:
        out("  Homepage, over Tailscale:    available once this machine has joined your Tailscale network")
    out("")


def offer_drive_wizard():
    if FAKE or Opt.yes or Opt.dry or not interactive() or State.data.get("wizard_offered"):
        return
    drives = P("/usr/local/sbin/drives")
    if not os.path.exists(drives) or os.path.ismount(P("/mnt/storage")):
        return
    State.data["wizard_offered"] = time.strftime("%F %T")
    State.save()
    rule("Your drives")
    say("Next, the drive wizard inspects the connected drives and suggests a setup. "
        "An empty drive is formatted only after a yes. A drive that holds files is changed only after its plan is shown and ERASE is typed. The wizard can be run again at any time:\n$ sudo drives wizard")
    try:
        subprocess.call([drives, "wizard", "--first-run"])
    except OSError as e:
        warn("Could not start the drive wizard (%s). Run it later:  sudo drives wizard" % e)


SERVICE_LABELS = [("homepage", "Homepage"), ("portainer", "Portainer"), ("adguard", "AdGuard Home"), ("beszel", "Beszel"),
                  ("netdata", "Netdata"), ("speedtest", "Speedtest Tracker"), ("filebrowser", "FileBrowser"),
                  ("immich", "Immich"), ("nextcloud", "Nextcloud")]


def navidrome_wanted():
    return BY_ID["stack-navidrome"].applies()


def added_services():
    """List the services added after the install (Navidrome and every card made with `homelab-cards`) as (label, container, local port, Tailscale port or 0), sorted by label."""
    found = {}
    try:
        managed = json.loads(read_file(PROGRESS_DIR + "/cards.json") or "{}").get("managed", {})
        for container, m in managed.items():
            if m.get("hostport"):
                label = NAVIDROME_TITLE if container == "navidrome" else (m.get("name") or container)
                found[container] = (label, container, int(m["hostport"]), int(m.get("serve") or 0))
    except (ValueError, AttributeError, TypeError):
        pass
    if navidrome_wanted() and "navidrome" not in found:
        found["navidrome"] = ("Navidrome", "navidrome", PORTS["navidrome"], 0)
    if "navidrome" in found:
        found["navidrome"] = ("Navidrome",) + found["navidrome"][1:]
    if audiomuse_wanted() and navidrome_wanted() and "audiomuse-flask" not in found:
        found["audiomuse-flask"] = ("AudioMuse-AI", "audiomuse-flask", PORTS["audiomuse"], 0)
    if "audiomuse-flask" in found:
        found["audiomuse-flask"] = ("AudioMuse-AI",) + found["audiomuse-flask"][1:]
    if navilist_wanted() and navidrome_wanted() and "navilist" not in found:
        found["navilist"] = ("naviList", "navilist", PORTS["navilist"], 0)
    if "navilist" in found:
        found["navilist"] = ("naviList",) + found["navilist"][1:]
    return sorted(found.values(), key=lambda x: x[0].lower())


def young_containers():
    """True when a container started less than three minutes ago or Docker still lists one as starting."""
    rc, txt = docker("ps", "--format", "{{.Status}}", timeout=20)
    if rc != 0:
        return False
    for line in txt.splitlines():
        if "health: starting" in line or re.match(r"Up (Less than a second|a second|\d+ seconds?|About a minute|[12] minutes?)\b", line):
            return True
    return False


class PageWait:
    left = 60.0


def page_answers(link):
    """True when the page answers. A page of a container that only just started gets up to a minute (shared by all pages) to wake up."""
    while True:
        if 0 < http("GET", link, timeout=10)[0] < 500:
            return True
        if PageWait.left <= 0 or not young_containers():
            return False
        time.sleep(5)
        PageWait.left -= 5


def system_check():
    """Check the running system and report whether everything is up. Returns the number of problems found."""
    rule("System check")
    problems = []
    own = adopted()
    names = ["portainer"] + [c for n in STACK_ORDER if n not in own for c in STACKS[n][1] if n != "adguard" or adguard_wanted()]
    if navidrome_wanted():
        names.append("navidrome")
    if audiomuse_wanted() and navidrome_wanted():
        names += [c for c in STACKS["audiomuse"][1] if c != "audiomuse-worker" or not State.data.get("audiomuse_paused")]
    if navilist_wanted() and navidrome_wanted():
        names += STACKS["navilist"][1]
    names = [c for c in names if not any(c in STACKS[n][1] for n in own)] + adopted_names()
    up = containers_running()
    missing = [c for c in names if c not in up]
    if missing:
        bad("Containers: %d of %d running. Not running: %s" % (len(names) - len(missing), len(names), ", ".join(missing)))
        problems.append("containers")
    else:
        good("Containers: %d of %d running" % (len(names), len(names)))
    Ctx.refresh_tailscale()
    if Ctx.fqdn:
        good("Tailscale: connected as %s" % Ctx.fqdn)
    else:
        bad("Tailscale: not connected")
        problems.append("tailscale")
    resolv = read_file(P("/etc/resolv.conf"))
    if "nameserver" in resolv and "100.100.100.100" not in resolv:
        good("DNS: this machine uses its router (Tailscale does not manage DNS)")
    else:
        bad("DNS: /etc/resolv.conf is empty or points at Tailscale (100.100.100.100). Run `sudo homelab-setup refresh`.")
        problems.append("dns")
    if panel_applies():
        for unit, label in (("homelab-panel", "The control panel"), ("homelab-terminal", "The web terminal")):
            if not os.path.exists(P("/etc/systemd/system/%s.service" % unit)):
                continue
            if run(["systemctl", "is-active", unit])[1].strip() == "active":
                good("%s is running" % label)
            else:
                bad("%s is not running. Start it with: sudo systemctl start %s" % (label, unit))
                problems.append(unit)
    broken = homepage_file_problems()
    if broken:
        for text in broken:
            bad("Homepage files: %s (control panel > Customize > Undo, or: sudo homelab-restore-configs)" % text)
        problems.append("homepage-files")
    elif os.path.isdir(P(hp_dir())):
        good("Homepage files: all there, not empty and readable")
    out("")
    out("  %sServices on the local network%s" % (B, N))
    for key, label in SERVICE_LABELS:
        if key == "adguard" and not adguard_wanted():
            continue
        if page_answers(url(key)):
            out("  %s%s%s %-18s %s" % (G, S_OK, N, label, mark(url(key))))
        else:
            out("  %s%s%s %-18s %s  (no answer)" % (R, S_BAD, N, label, mark(url(key))))
            problems.append(key)
    extras = added_services()
    if extras:
        out("")
        out("  %sOther services%s" % (B, N))
        for label, container, port, _ in extras:
            link = "http://%s:%d" % (svc_host(), port)
            if page_answers(link):
                out("  %s%s%s %-18s %s" % (G, S_OK, N, label, mark(link)))
            elif container in ("navidrome", "audiomuse-flask", "navilist") and (
                    container == "navidrome" or (container == "audiomuse-flask" and audiomuse_wanted()) or (container == "navilist" and navilist_wanted())):
                out("  %s%s%s %-18s %s  (no answer)" % (R, S_BAD, N, label, mark(link)))
                problems.append(container)
            elif container in up:
                out("  %s%s%s %-18s %s  (the container runs but the page does not answer: sudo docker logs --tail 30 %s)" % (R, S_BAD, N, label, mark(link), container))
                problems.append(container)
            else:
                out("  %s%s%s %-18s %s  (not running: sudo docker start %s)" % (Y, S_WAIT, N, label, mark(link), container))
    if Ctx.fqdn:
        out("")
        out("  %sServices over Tailscale%s %s(use these from other devices; a machine cannot open its own Tailscale addresses)%s" % (B, N, D, N))
        for port, key in serve_items():
            label = dict(SERVICE_LABELS)[key]
            out("    %-18s %s" % (label, mark("https://%s:%d" % (Ctx.fqdn, port))))
        for label, _, _, port in extras:
            if port:
                out("    %-18s %s" % (label, mark("https://%s:%d" % (Ctx.fqdn, port))))
    out("")
    if problems:
        say("%d problem(s) found. Run:\n$ sudo homelab-setup refresh" % len(problems))
    else:
        good("Everything is up and running. Open Homepage: %s" % mark(url("homepage")))
    out("")
    return len(problems)


def next_step_section(res):
    """Print the last section of the output: the next command to run, or the system check when everything is done."""
    if Mode.existing:
        return
    done, total = counts(res)
    if done >= total:
        system_check()
        return
    rule("Next step")
    nxt = pick_next(res)
    if nxt is None:
        say("The remaining steps are waiting for earlier ones. Run:\n$ sudo homelab-setup refresh")
        out("")
        return
    out("  %s%s%s" % (B, nxt.title, N))
    r = res[nxt.id]
    if r.state == "failed" and r.detail:
        for l in wrap("Last attempt failed: " + r.detail, 4):
            out("%s%s%s" % (R, l, N))
    if nxt.kind == "auto":
        say("This step runs automatically. Run:\n$ sudo homelab-setup refresh", 4)
    else:
        say(nxt.help(), 4)
        out("")
        say("%d of %d steps are done. After each step, check progress with:\n$ sudo homelab-setup refresh" % (done, total))
    out("")


def cmd_verify():
    load_all()
    if Mode.existing and not Opt.force_existing:
        say("This machine already runs the lab. The system check is for machines set up by the installer.")
        return 0
    # The exit code is 1 when the check found problems, so a script or a scheduled job can use it.
    return 1 if system_check() else 0


def sync_shown_count(res):
    """Make the count on the login screen and the dashboard equal to the list that was just shown. The login screen's file is written only when the numbers
    changed (or removed when everything is done), so reading the list again and again changes nothing."""
    if Opt.dry or State.readonly:
        return
    done, total = counts(res)
    try:
        if done >= total:
            if os.path.exists(PROGRESS_FILE):
                os.remove(PROGRESS_FILE)
        elif read_file(PROGRESS_FILE).strip().split("|")[:2] != [str(done), str(total)]:
            os.makedirs(PROGRESS_DIR, exist_ok=True)
            write_file(PROGRESS_FILE, "%d|%d|%d\n" % (done, total, int(time.time())), 0o644)
    except OSError:
        pass
    sync_dashboard_status(res)


def cmd_checklist():
    load_all()
    res = evaluate()
    if Mode.existing and not damaged_state_seen():
        say("This machine already runs the lab (set up by hand). The installer only reads it and changes nothing.")
    elif Mode.existing:
        say("The installer's state file was damaged, so it only reads this machine for now and changes nothing. The step counts below can be wrong until a new state file is built from what is installed: sudo homelab-setup refresh --force-existing")
    show_checklist(res, show_all=Opt.all)
    next_step_section(res)
    sync_shown_count(res)  # so that `homelab` and the dashboard show the same count as this list


DURING_INSTALL = ("tailscale-login", "tailscale-https")

GROUP_BLURB = {
    "System": "updates, helper programs and Docker",
    "Tailscale": "the private network that reaches the lab from anywhere",
    "Network": "keeps DNS working and frees port 53 for AdGuard Home (if you chose it)",
    "Platform": "folders, generated passwords and Portainer, which deploys the apps",
    "Services": "downloads and starts the apps (the longest part)",
    "Logins and keys": "creates the admin accounts and API keys inside the apps",
    "Homepage": "connects the dashboard widgets to the apps",
    "Scripts and schedule": "helper commands, scheduled jobs and the login screen",
    "Your devices and drives": "steps that need your input",
}


def welcome():
    say("This turns this machine into a home lab: Docker, Tailscale and up to nine apps (Homepage, Portainer, AdGuard Home "
        "(optional, you are asked), Beszel, Netdata, Speedtest Tracker, FileBrowser, Immich and Nextcloud), with their logins "
        "and dashboard widgets.")
    out("")
    say("It takes roughly 30 to 60 minutes and downloads about 10 GB. It can be left running and asks only when input is needed. "
        "If it stops, run the same command again: finished steps are skipped.")
    out("")
    say("Have ready:")
    for item in ("a password manager, to save the passwords the installer generates",
                 "a free Tailscale account (tailscale.com), to sign in once in a browser",
                 "about 20 GB of free space on this machine"):
        lines = styled(item, 6)
        out("    %s %s" % (S_DOT, lines[0][6:]))
        for l in lines[1:]:
            out(l)


def plan_install(res):
    open_auto = [s for s in STEPS if res[s.id].state in ("todo", "failed", "blocked") and s.kind == "auto"]

    def runs_now(s, seen=()):
        for n in s.needs:
            if res[n].state in ("done", "na", "skip"):
                continue
            d = BY_ID[n]
            if n in seen or not (d.kind == "auto" or n in DURING_INSTALL) or not runs_now(d, seen + (s.id,)):
                return False
        return True
    todo = [s for s in open_auto if runs_now(s)]
    later = [s for s in open_auto if s not in todo]
    by_hand = [s for s in STEPS if res[s.id].state in ("todo", "failed", "blocked") and s.kind != "auto"
               and not (s.id == "weather" and (Opt.dry or State.data["answers"].get("weather")))]
    return todo, later, by_hand


def by_hand_tag(s):
    if s.id in DURING_INSTALL:
        return "during the install"
    if getattr(s, "auto", None):
        return "detected automatically once done"
    return "afterwards"


def show_plan(todo, later, by_hand):
    rule("Planned steps")
    say("%d steps run automatically, in this order:" % len(todo))
    out("")
    for g in GROUPS:
        n = len([s for s in todo if s.group == g])
        if n:
            out("   %s%-22s%s %2d  %s%s%s" % (B, g, N, n, D, GROUP_BLURB.get(g, ""), N))
    if background_mode():
        slow = [s for s in todo + later if s.id in deferred_ids()]
        if slow:
            out("")
            say("%d of these (Nextcloud and Immich first logins, Beszel and the widget keys) finish in the background after the install is done, "
                "so you do not have to wait for them. `sudo homelab-setup status` shows how far they are." % len(slow))
    if later:
        out("")
        say("%d more %s automatically once the steps that need input are done: %s" % (
            len(later), "step runs" if len(later) == 1 else "steps run", "; ".join(s.title for s in later)))
    if by_hand:
        out("")
        say("%d steps need you:" % len(by_hand))
        out("")
        for s in by_hand:
            out("   %s%s%s %s  %s(%s)%s" % (Y, S_TODO, N, s.title, D, by_hand_tag(s), N))


def cmd_install():
    """`install`: show the plan, ask the questions, then build the lab."""
    load_all()
    if Mode.existing and not Opt.force_existing:
        out("")
        say("This machine already runs the lab, so nothing is installed. Its checklist is shown read-only. "
            "To run the installer on it anyway, add `--force-existing`.")
        res = evaluate()
        show_checklist(res)
        return
    refuse_while_finishing()
    rule("Home lab installer %s %s" % (S_DOT, "dry run - nothing will be changed" if Opt.dry else "v" + VERSION))
    if not State.ran("install-started"):
        welcome()
    else:
        say("An earlier install was started on this machine. It continues where it stopped; finished steps are skipped.")
    preflight()
    adopt_detect()
    if not Opt.dry:
        if not (State.data["answers"].get("admin") and State.data["answers"].get("email")):
            ask_answers()
        else:
            Ctx.detect()
        remember_repo()
        State.save()
        ask_grow_boot_volume(State.data["answers"])
        ask_restore_plan()
    else:
        if not Ctx.admin:
            Ctx.admin = Ctx.user.capitalize()
        if not Ctx.email:
            Ctx.email = "you@example.com"
        info = root_lvm_info()
        if info and info["free"] >= LVM_MIN_FREE:
            say("Would offer: give the %s the drive has left over to the system volume (now %s). It only grows the volume; nothing is erased." %
                (pretty_size(info["free"]), pretty_size(info["size"])))
    if State.ran("install-started"):
        wait_for_apps()
    res = evaluate()
    todo, later, by_hand = plan_install(res)
    if not todo and not by_hand and not later:
        out("")
        say("Nothing to do: all steps are complete.")
        show_checklist(res, "Setup")
        next_step_section(res)
        return
    show_plan(todo, later, by_hand)
    during = [s for s in by_hand if s.id in DURING_INSTALL]
    out("")
    if not Opt.dry:
        State.mark("install-started")
        if State.data["answers"].get("lvm_grow") == "yes":
            grow_boot_volume()
    later_ids = deferred_ids() if background_mode() else set()
    Live.begin_run(len([s for s in todo if s.id not in later_ids]) + len(during))
    run_install(res, later_ids)
    res = evaluate()
    write_progress(res)
    if not Opt.dry:
        final_report(res, start_finish_job(res))
    else:
        out("")
        say("This was a dry run. Nothing was changed.")


def run_install(res, later=None):
    """Run the install. Docker comes first, then image downloads start in the background, then the other early steps and the steps that need a person, then up to four more passes. Steps listed in `later` finish in the background."""
    rule("Installing")
    run_pass(res, {"os", "apt-update", "packages", "docker", "docker-group"})
    Prefetch.start()
    run_pass(res, {"tailscale-install"})
    for sid in ("tailscale-login", "tailscale-https"):
        s = BY_ID[sid]
        if res[s.id].state == "todo":
            out("")
            out("  %s %s" % (S_DOT, s.title))
            try:
                if s.fill():
                    res[s.id] = Result("done", s.detail())
                    Live.advance()
                    unblock(res, dry=Opt.dry)
            except Abort as e:
                bad(str(e))
    Ctx.refresh_tailscale()
    if Ctx.fqdn:
        with Live.pause():
            ask_tailscale_token(State.data["answers"])
    held = set(later or ()) | {"apt-upgrade"}
    for _ in range(4):
        gained = run_pass(res, skip=held)
        if not Opt.dry:
            res.update(evaluate())
        if not gained:
            break
    if "apt-upgrade" not in (later or ()):
        run_pass(res, {"apt-upgrade"})


def wait_for_apps():
    if not have("docker") or Opt.dry:
        return
    if not docker_answers():
        try:
            wait_for(docker_answers, "Docker to answer (up to 2 minutes)", 3 if FAKE else 120, every=5)
        except Abort:
            raise Abort(DOCKER_DOWN) from None
    if containers_starting():
        try:
            wait_for(lambda: not containers_starting(), "the apps to finish starting (up to 5 minutes)", 300, every=5)
        except Abort as e:
            warn(str(e) + " Going on anyway.")


def update_panel_when_blocked(res):
    s = BY_ID.get("panel-files")
    if s is None or Opt.dry or not s.applies() or res["panel-files"].state != "blocked" or not main_storage_missing():
        return False
    if not os.path.exists(P(PANEL_UNIT)) or safe_probe(s) == "done":
        return False
    try:
        s.run()
    except Abort as e:
        warn("The control panel could not be updated: %s" % e)
        return False
    good("The control panel was updated (it does not need the Main pool).")
    return True


def storage_notice(res):
    """Explain what is paused while the Main pool has no drive, and what to do about it."""
    if Opt.dry or not main_storage_missing():
        return
    waits = [s for s in STEPS if res[s.id].state in ("blocked", "todo", "failed") and s.id != "folders" and waits_for_folders(s)]
    rule("The Main pool has no drive")
    say("Nothing is wrong with the update itself: the new scripts and the control panel are installed. But /mnt/storage has no drive mounted, so the services "
        "that keep their files there stay stopped (nothing is written onto the boot drive by mistake).")
    out("")
    if waits:
        groups = []
        for g in GROUPS:
            n = sum(1 for s in waits if s.group == g)
            if n:
                groups.append("%s (%d)" % (g, n))
        say("%d steps wait for it: %s." % (len(waits), ", ".join(groups)))
        late = [s for s in waits if s.id in ("terminal", "stack-navidrome", "navidrome-stack", "stack-immich", "stack-nextcloud", "stack-filebrowser")]
        if late:
            say("That includes: %s." % ", ".join(s.title.split(" (")[0] for s in late))
        out("")
    say("What to do:\n1. Open the control panel, then Customize, then Drives, and drag a drive into Main pool (Keep the files if it already holds them).\n"
        "   Or run:  sudo drives\n"
        "2. The services that were stopped start again automatically.\n"
        "3. Run:  sudo homelab-setup refresh")
    out("")


def cmd_refresh():
    """`refresh`: check every step again and do whatever is now possible."""
    load_all()
    if Mode.existing and not Opt.force_existing:
        say("This machine already runs the lab. Its checklist is shown read-only.")
        if damaged_state_seen():
            say("The setup state file was damaged. To build a new one from what is installed: sudo homelab-setup refresh --force-existing")
        res = evaluate()
        show_checklist(res)
        write_progress(res)
        return
    if Mode.existing:
        # The owner asked for it: build a new state file from what is installed, then check everything again.
        if not looks_like_repo(Ctx.repo):
            raise Abort("The downloaded copy of the lab was not found (looked in %s and in the home folder of %s). Run the command again and name its folder:\n"
                        "  sudo homelab-setup refresh --force-existing --repo ~/My-Home-Lab-" % (Ctx.repo, Ctx.user))
        say("Building a new setup state file from what is installed.")
        if Opt.dry:
            preview_rebuild()
            return
        rebuild_state_from_machine()
        Mode.existing = False
    elif not State.exists():
        raise Abort("The installer has not run on this machine yet. Run `sudo homelab-setup install`.")
    refuse_while_finishing()
    wait_for_apps()
    res = evaluate()
    Live.begin_run(len([s for s in STEPS if s.kind == "auto" and res[s.id].state in ("todo", "failed", "blocked")]))
    rule("Checking and continuing")
    for _ in range(4):
        gained = run_pass(res)
        res = evaluate()
        if not gained:
            break
    if update_panel_when_blocked(res):
        res = evaluate()
    write_progress(res)
    show_checklist(res)
    storage_notice(res)
    next_step_section(res)
