HP_FILES = ["services.yaml", "settings.yaml", "widgets.yaml", "bookmarks.yaml", "custom.css"]
# The person changes these two the most. When one is missing the checklist shows one item (the key-files step), not the whole Homepage group.
LOOK_FILES = ["custom.css", "bookmarks.yaml"]


def write_default_homepage_file(f):
    """Write the shipped version of one Homepage file, with this machine's addresses filled in."""
    body = subst(read_file(repo_file("homepage-config", f)))
    if not body:
        raise Abort("The repository file homepage-config/%s is missing." % f)
    if f == "services.yaml":
        body = hp_strip_widgets(body)
        if not adguard_wanted():
            body = hp_remove_card(body, "adguard-card")
    if f == "widgets.yaml":
        body = widgets_for_machine(body)
    write_file(hp_path(f), body, hp_mode(f), (Ctx.uid, Ctx.gid))


def widgets_for_machine(body):
    body = re.sub(r"(- resources:\n\s+label:) Server\b", lambda m: "%s %s" % (m.group(1), Ctx.hostname), body, count=1)
    w = State.data["answers"].get("weather")
    if w:
        new = weather_apply(body, w)
        if new is not None:
            body = new
            State.data["weather_set"] = w["name"]
            State.save()
    tz = State.data["answers"].get("tz_found")
    if tz:
        body = clock_apply(body, tz) or body
    return body


# Homepage serves a file under /images only if the file already existed when Homepage started. The progress ring and the header graphs read these files,
# so they are created empty before Homepage first starts (or, on a machine where Homepage already runs, once, with a restart of Homepage).
# trends.json is the short history of CPU, memory, network and temperature that the control panel keeps, for the small graphs in the header.
DASH_PLACEHOLDERS = {"install-status.json": "{}\n", "job-status.json": '{"version": 1, "updated": 0, "jobs": []}\n',
                     "trends.json": '{"version": 1, "updated": 0, "step": 30, "cpu": [], "mem": [], "rx": [], "tx": [], "temp": []}\n'}


def dashboard_placeholders():
    """Create the empty status files the progress ring reads. Returns True when Homepage had to be restarted to serve them."""
    made = False
    for name, body in DASH_PLACEHOLDERS.items():
        if not os.path.exists(hp_path("images/" + name)):
            write_file(hp_path("images/" + name), body, 0o644, (Ctx.uid, Ctx.gid))
            made = True
    if made and not Opt.dry and "homepage" in containers_running():
        docker("restart", "homepage", timeout=120)
        return True
    return False


@step
class HomepageFiles(Step):
    """Copy the shipped Homepage configuration files into the user's folder with this machine's addresses filled in. Existing files are only updated for addresses."""
    id, group, title = "homepage-files", "Homepage", "Homepage config files in place for this machine"
    needs = ("folders", "tailscale-login", "restore-configs")

    def probe(self):
        if not all(os.path.exists(hp_path(f)) for f in HP_FILES if f not in LOOK_FILES):
            return "todo"
        txt = read_file(hp_path())
        if PH_LAN in txt or PH_FQDN in txt:
            return "todo"
        if OLD_LAN and OLD_LAN in txt and OLD_LAN != Ctx.lan:
            return "todo"
        if OLD_FQDN and OLD_FQDN in txt and OLD_FQDN != Ctx.fqdn:
            return "todo"
        if not Mode.existing and any(not os.path.exists(hp_path("images/" + n)) for n in DASH_PLACEHOLDERS):
            return "todo"
        return "done"

    def run(self):
        for f in HP_FILES:
            dst = hp_path(f)
            if f in LOOK_FILES and not os.path.exists(dst):
                continue
            if not os.path.exists(dst):
                write_default_homepage_file(f)
            elif f in ("services.yaml", "bookmarks.yaml"):
                old = read_file(dst)
                new = subst(old)
                if new != old:
                    write_file(dst, new, hp_mode(f), (Ctx.uid, Ctx.gid))
        if dashboard_placeholders():
            out("      Homepage was restarted once so that it serves the progress ring's status files")
        if "navidrome" in adopted():
            # Navidrome's card is normally added together with its login; for the person's own copy it is a plain link.
            svc = read_file(hp_path("services.yaml"))
            if svc and card_widget_type(svc, "navidrome-card") is None:
                write_file(hp_path("services.yaml"), navidrome_card_added(svc, Ctx.lan or svc_host()), 0o600, (Ctx.uid, Ctx.gid))
        protect_key_files()


def homepage_skeleton_bookmarks(text):
    """True for the sample bookmarks.yaml that Homepage writes itself (groups Developer, Social and Entertainment with GitHub, Reddit and YouTube)."""
    return bool(text) and len(text) < 700 and "abbr: GH" in text and "abbr: YT" in text and "reddit" in text.lower()


def missing_look_files():
    """The look files that are gone, or that hold only what Homepage puts there itself: it writes an empty custom.css and a sample bookmarks.yaml as soon as its
    page is asked for while the file is missing, so the file being there does not mean it is the user's own."""
    gone = []
    for f in LOOK_FILES:
        text = read_file(hp_path(f)) if os.path.exists(hp_path(f)) else None
        if text is None or (f == "custom.css" and not text.strip()) or (f == "bookmarks.yaml" and homepage_skeleton_bookmarks(text)):
            gone.append(f)
    return gone


@step
class HomepageKeyFiles(Step):
    """Keep the files that hold the dashboard's widget keys readable by their owner only, and the dashboard folder and its files owned by the user. Nothing waits for this step, so a permission problem shows as one item."""
    id, group, title = "homepage-key-files", "Homepage", "The dashboard's key files (services.yaml and its copies) are readable by their owner only, and its look and bookmarks files are present"
    needs = ("homepage-files",)

    def applies(self):
        return not Mode.existing

    def probe(self):
        return "todo" if key_files_open() or wrong_owner_files() or missing_look_files() else "done"

    def detail(self):
        gone = missing_look_files()
        if gone and not key_files_open() and not wrong_owner_files():
            return "%s missing or empty; `sudo homelab-setup refresh` writes the shipped version (your own look can come back with: sudo homelab-restore-configs)" % " and ".join(gone)
        return "%d file(s) are readable by other users or belong to the wrong user; `sudo homelab-setup refresh` fixes it" % (len(key_files_open()) + len(wrong_owner_files()))

    def open_note(self):
        gone = missing_look_files()
        parts = []
        if gone:
            parts.append("%s missing or empty (Homepage puts an empty or sample file there when it is gone). `sudo homelab-setup refresh` writes the shipped version of only that file. Your own copy can come back with: sudo homelab-restore-configs" % " and ".join(gone))
        if key_files_open() or wrong_owner_files():
            parts.append("%d file(s) are readable by other users or belong to the wrong user. `sudo homelab-setup refresh` fixes it" % (len(key_files_open()) + len(wrong_owner_files())))
        return ". ".join(parts)

    def run(self):
        for f in missing_look_files():
            if Opt.dry:
                out("      would write the shipped %s" % f)
                continue
            write_default_homepage_file(f)
            if f == "bookmarks.yaml":
                # The shipped bookmark groups are not new layout entries: settings.yaml stays as it is.
                seen = list(State.data.get("layout_seen", []))
                for g in group_names(read_file(hp_path(f))):
                    if g not in seen:
                        seen.append(g)
                State.data["layout_seen"] = seen
                State.save()
            log("homepage-key-files: %s was missing or empty, the shipped version was written" % f)
            warn("%s was missing or empty, so the shipped version was written. Only that file was changed. Your own copy is in the backups and the control panel's Undo history; to bring it back run: sudo homelab-restore-configs" % f)
        protect_key_files()


def panel_script_for_root(check):
    """The control panel script that root may run. Only the installed copy (root's own) is used for a look at the checklist; the copy in the repository, which the
    lab user can change, only when a person asked for a refresh and nobody else can change that file either."""
    installed = installed_copy("homelab-panel", "/usr/local/sbin")
    if installed:
        return installed
    if check:
        return None
    return trusted_real_path(repo_file("scripts", "homelab-panel"), Ctx.user) if not FAKE else repo_file("scripts", "homelab-panel")


def theme_pictures_run(check):
    """Ask the control panel's own script to store the picture of every theme. Returns True when all are stored."""
    script = panel_script_for_root(check)
    if not script:
        return False
    env = dict(os.environ, HLP_HOME=P(Ctx.home), HOMELAB_HOMEPAGE_DIR=hp_path(""))
    rc, _ = run([sys.executable, script, "theme-pictures"] + (["--check"] if check else []), env=env, timeout=60 if check else 600)
    return rc == 0


@step
class ThemePictures(Step):
    """Store the pictures of all the themes in the Homepage folder. Homepage serves a picture only if it was there when Homepage started, so with them in place
    choosing a theme later never has to restart Homepage (which shows "API Error" on the tiles for a few seconds and reloads the page)."""
    id, group, title = "theme-pictures", "Homepage", "The pictures of the themes stored, so changing a theme never restarts the dashboard"
    needs = ("homepage-files",)

    def applies(self):
        return not Mode.existing and (not FAKE or bool(os.environ.get("HLP_THEME_PICTURE_BASE")))

    def probe(self):
        if theme_pictures_run(True):
            return "done"
        return "done" if State.ran(self.id) else "todo"

    def detail(self):
        return "" if theme_pictures_run(True) else "some pictures could not be downloaded; the panel fetches one when its theme is chosen"

    def run(self):
        if Opt.dry:
            out("      would download the picture of each theme into the Homepage folder")
            return
        before = set(os.listdir(hp_path("images"))) if os.path.isdir(hp_path("images")) else set()
        theme_pictures_run(False)
        State.mark(self.id)
        images = hp_path("images")
        added = (set(os.listdir(images)) - before) if os.path.isdir(images) else set()
        for f in added:
            chown(os.path.join(images, f), Ctx.uid, Ctx.gid)
        if added and "homepage" in containers_running():
            docker("restart", "homepage", timeout=120)
            out("      Homepage was restarted once so that it serves the theme pictures")


@step
class HomepageTabs(Step):
    """Bring settings.yaml, custom.css, custom.js and services.yaml up to the shipped tabs layout once; a layout the user removed is not added again."""
    id, group, title = "homepage-tabs", "Homepage", "Homepage tabs (Home, Stats, Links), group icons, bookmark cards, the STATS cards and their styles"
    needs = ("homepage-files", "scripts")

    def applies(self):
        return not Mode.existing and os.path.exists(hp_path("settings.yaml")) and os.path.exists(hp_path("custom.css")) and bool(read_file(repo_file("homepage-config", "settings.yaml")))

    def wanted(self):
        sett, css = read_file(hp_path("settings.yaml")), read_file(hp_path("custom.css"))
        if not State.ran("homepage-tabs"):
            sett = settings_with_layout(sett, read_file(repo_file("homepage-config", "settings.yaml")))
        svc = read_file(hp_path("services.yaml"))
        if re.search(r"(?m)^layout:", sett):
            shipped_svc = subst(read_file(repo_file("homepage-config", "services.yaml")))
            if not State.ran("homepage-stats") or STATS_BEGIN in svc:
                svc = services_stats_block(svc, shipped_svc)
            if not State.ran("homepage-calendar") or CAL_BEGIN in svc:
                svc = services_calendar_block(svc, shipped_svc)
            if not State.ran("homepage-customize") or CUSTOM_BEGIN in svc:
                svc = services_customize_block(svc, shipped_svc)
        svc = cards_worded(svc)
        sett = layout_renamed(sett)
        sett, seen = layout_complete(sett, group_names(svc), group_names(read_file(hp_path("bookmarks.yaml"))), State.data.get("layout_seen", []))
        if re.search(r"(?m)^layout:", sett):
            sett, seen = layout_storage_wide(sett, seen)
            sett, seen = layout_music_wide(sett, seen)
            sett, seen = layout_calendar_on_stats(sett, seen)
            sett, seen = layout_calendar_on_home(sett, seen)
            sett, seen = layout_stats_before_links(sett, seen)
            sett, seen = layout_linkedit_first(sett, seen)
            sett, seen = layout_terminal_to_customize(sett, seen)
            sett, seen = layout_home_order(sett, seen)
        sett, seen = settings_quicklaunch(sett, seen)
        new_css = css_tabs_block(css, read_file(repo_file("homepage-config", "custom.css")))
        new_js = js_groups_block(read_file(hp_path("custom.js")), read_file(repo_file("homepage-config", "custom.js")))
        return sett, new_css, seen, new_js, svc

    def open_note(self):
        if "custom.css" in missing_look_files():
            return "waits for custom.css, which is missing or empty (see the dashboard's key files item); the layout is added after it is restored"
        return ""

    def widgets_new(self):
        old = read_file(hp_path("widgets.yaml")) if os.path.exists(hp_path("widgets.yaml")) else ""
        if State.ran("homepage-clock") or not old:
            return old
        return re.sub(r"(?m)^(\s+dateStyle:\s*)short\s*$", r"\1medium", old)

    def remember(self, seen):
        if seen != State.data.get("layout_seen", []):
            State.data["layout_seen"] = seen
            State.save()

    def probe(self):
        sett, css, seen, js, svc = self.wanted()
        if (sett != read_file(hp_path("settings.yaml")) or css != read_file(hp_path("custom.css")) or js != read_file(hp_path("custom.js"))
                or svc != read_file(hp_path("services.yaml")) or self.widgets_new() != (read_file(hp_path("widgets.yaml")) if os.path.exists(hp_path("widgets.yaml")) else "")):
            return "todo"
        if not Opt.dry:
            self.remember(seen)
            for k in ("homepage-tabs", "homepage-stats", "homepage-calendar", "homepage-customize", "homepage-clock"):
                if not State.ran(k):
                    State.mark(k)
        return "done"

    def run(self):
        old_sett, old_css, old_js, old_svc = (read_file(hp_path(n)) for n in ("settings.yaml", "custom.css", "custom.js", "services.yaml"))
        sett, css, seen, js, svc = self.wanted()
        wid, old_wid = self.widgets_new(), (read_file(hp_path("widgets.yaml")) if os.path.exists(hp_path("widgets.yaml")) else "")
        own = (Ctx.uid, Ctx.gid)
        if Opt.dry:
            out("      would add the tabs (Home, Stats, Links), the group icons, the bookmark cards, the STATS cards and their styles to the Homepage files")
            return
        saved = []
        for name, old, new in (("settings.yaml", old_sett, sett), ("custom.css", old_css, css), ("custom.js", old_js, js), ("services.yaml", old_svc, svc), ("widgets.yaml", old_wid, wid)):
            if new == old:
                continue
            if old and not os.path.exists(hp_path(name) + ".before-tabs"):
                write_file(hp_path(name) + ".before-tabs", old, hp_mode(name), own)
                saved.append(name + ".before-tabs")
            write_file(hp_path(name), new, hp_mode(name), own)
        self.remember(seen)
        State.mark("homepage-tabs")
        State.mark("homepage-stats")
        State.mark("homepage-calendar")
        State.mark("homepage-customize")
        State.mark("homepage-clock")
        stats_file = hp_path("images/stats.json")
        if not FAKE and not os.path.exists(stats_file) and os.path.exists(P("/usr/local/sbin/homelab-stats")):
            make_folder(os.path.dirname(stats_file))
            run_as_root_stats(stats_file)
        if CAL_BEGIN in svc and os.path.exists(P("/usr/local/bin/homelab-calendar")):
            make_folder(hp_path("images"))
            run_calendar_build()
        if not FAKE and "homepage" in containers_all():
            act(["docker", "restart", "homepage"], timeout=120)
        out("      Reload the dashboard (Ctrl+Shift+R)." + ((" The old versions of the changed files are saved as %s." % ", ".join(saved)) if saved else ""))
        if STATS_BEGIN in svc:
            out("      The Stats tab is filled in within 15 minutes; folder sizes take a little longer. To fill it in now, run:  sudo homelab-stats")
        if CUSTOM_BEGIN in svc:
            out("      The Customize tab is the control panel: change the look, the layout, the cards and the links by clicking. Its password is the admin password; change it with:  homelab panel password")
        if CAL_BEGIN in svc:
            out("      The Calendar is at the bottom of the Home tab, under the service cards. Add your own events with:  homelab event add 2026-12-25 \"Family dinner\"")


def fetch_picture(addr):
    if FAKE:
        f = os.environ.get("HLS_FAKE_BG_FILE", "")
        data = open(f, "rb").read() if f and os.path.isfile(f) else None
    else:
        try:
            req = urllib.request.Request(addr, headers={"User-Agent": "homelab-setup"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read(30 * 1024 * 1024)
        except (urllib.error.URLError, OSError, ValueError):
            return None
    return data if data and (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n" or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")) else None


@step
class HomepageBackground(Step):
    """Download the dashboard background picture and save it on the server so the dashboard does not depend on the original address."""
    id, group, title = "homepage-background", "Homepage", "The dashboard's background picture is saved on this server (loads fast, works offline)"
    needs = ("homepage-tabs",)

    def applies(self):
        return not Mode.existing and os.path.exists(hp_path("settings.yaml"))

    def probe(self):
        cur = background_image(read_file(hp_path("settings.yaml")))
        tried = time.time() - State.data.get("background_tried", 0) < 7 * 86400
        return "done" if State.ran(self.id) or tried or not re.match(r"https?://", cur) else "todo"

    def detail(self):
        return background_image(read_file(hp_path("settings.yaml")))[:60]

    def run(self):
        sett = read_file(hp_path("settings.yaml"))
        cur = background_image(sett)
        if Opt.dry:
            out("      would download the background picture into %s and use it from there" % hp_path("images"))
            return
        data = fetch_picture(cur)
        if data is None:
            warn("Could not download the background picture (%s). It stays as it is; an upgrade a week from now tries again." % cur[:70])
            State.data["background_tried"] = int(time.time())
            State.save()
            return
        ext = ".png" if data[:4] == b"\x89PNG" else ".webp" if data[:4] == b"RIFF" else ".jpg"
        name = "background" + ext
        make_folder(hp_path("images"))
        path = hp_path("images/" + name)
        write_bytes(path, data, 0o644, (Ctx.uid, Ctx.gid))
        if not os.path.exists(hp_path("settings.yaml") + ".before-background"):
            write_file(hp_path("settings.yaml") + ".before-background", sett, 0o644, (Ctx.uid, Ctx.gid))
        write_file(hp_path("settings.yaml"), settings_with_background(sett, "/images/" + name), 0o644, (Ctx.uid, Ctx.gid))
        State.mark(self.id)
        if not FAKE and "homepage" in containers_all():
            act(["docker", "restart", "homepage"], timeout=120)
        out("      The background is now %s in the images folder (the old settings.yaml is kept as settings.yaml.before-background). "
            "To use another picture later:  homelab theme background URL-or-FILE" % name)


def run_calendar_build():
    run([P("/usr/local/bin/homelab-calendar"), "build"], env=dict(os.environ, HP_DIR=P(hp_dir())), timeout=60)


def run_as_root_stats(stats_file):
    run([P("/usr/local/sbin/homelab-stats"), "quick"], env=dict(os.environ, HOMELAB_STATS_OUT=stats_file), timeout=180)
