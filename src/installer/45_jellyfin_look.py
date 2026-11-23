JELLYFIN_THEME_URL = "https://cdn.jsdelivr.net/gh/n00bcodr/Jellyfish/"
JELLYFIN_CSS_FILES = ("theme.css", "colors/jellyflix.css", "slideshow.css", "progress_bar.css", "indicators.css", "card_buttons.css",
                      "icontext.css", "scrollbar.css", "streamberry_logo.css")
JELLYFIN_PLUGIN_REPO = ("IAmParadox27 plugins", "https://www.iamparadox.dev/jellyfin/plugins/manifest.json")
JELLYFIN_PLUGINS = ("File Transformation", "Media Bar")
JELLYFIN_LIBRARIES = (("Movies", "movies", "/media/movies"), ("Shows", "tvshows", "/media/shows"))
JELLYFIN_DISPLAY = {"enableBackdrops": "true", "detailsBanner": "true"}


def jellyfin_css(slideshow=True):
    """The Custom CSS for Jellyfin: the Jellyfish theme with the Jellyflix colors and its add-ons. The slideshow file is left out without the Media Bar plugin."""
    return "\n".join('@import url("%s%s");' % (JELLYFIN_THEME_URL, f) for f in JELLYFIN_CSS_FILES if slideshow or f != "slideshow.css") + "\n"


def jf_auth():
    key = Secrets.get("JELLYFIN_HOMEPAGE_KEY") or hp_get("jellyfin-card", "key")
    return jellyfin_headers(key) if key else None


def jf_get(path, auth):
    st, js, _ = http("GET", url("jellyfin", path), headers=auth, timeout=30)
    return js if st == 200 else None


def jf_plugins(auth):
    """The plugins Jellyfin has, as {name: status}, or None when it did not answer."""
    js = jf_get("/Plugins", auth)
    if not isinstance(js, list):
        return None
    return {str(p.get("Name", "")).lower(): str(p.get("Status", "")) for p in js if isinstance(p, dict)}


def jf_wait_up(secs=120):
    """Wait for Jellyfin to go down and come back after a restart."""
    time.sleep(0 if FAKE else 6)
    try:
        wait_for(lambda: http("GET", url("jellyfin", "/System/Info/Public"), timeout=8)[0] == 200, "Jellyfin to start again", 3 if FAKE else secs, every=3)
        return True
    except Abort:
        return False


def jf_find_package(auth, plugin):
    """Look a plugin up in Jellyfin's catalog; a newly added repository can take a moment to appear."""
    def look():
        js = jf_get("/Packages", auth)
        return next((p for p in js if isinstance(p, dict) and str(p.get("name", "")).lower() == plugin.lower()), None) if isinstance(js, list) else None
    try:
        return wait_for(look, "the plugin catalog to list %s" % plugin, 3 if FAKE else 45, every=3, quiet=True)
    except Abort:
        return None


def jf_install_plugins(auth):
    """Add the plugin repository and install the Media Bar plugins. Returns (slideshow works, restart needed, note)."""
    have = jf_plugins(auth)
    if have is None:
        return False, False, "Jellyfin did not list its plugins"
    if all(p.lower() in have for p in JELLYFIN_PLUGINS):
        return True, False, ""
    name, repo_url = JELLYFIN_PLUGIN_REPO
    repos = jf_get("/Repositories", auth)
    if not isinstance(repos, list):
        return False, False, "Jellyfin did not list its plugin repositories"
    if not any(isinstance(r, dict) and str(r.get("Url", "")).rstrip("/") == repo_url for r in repos):
        st, _, _ = http("POST", url("jellyfin", "/Repositories"), headers=auth, body=repos + [{"Name": name, "Url": repo_url, "Enabled": True}], timeout=30)
        if st not in (200, 204):
            return False, False, "Jellyfin did not accept the plugin repository (HTTP %s)" % st
    changed = False
    for plugin in JELLYFIN_PLUGINS:
        if plugin.lower() in have:
            continue
        pkg = jf_find_package(auth, plugin)
        if not pkg:
            return False, changed, "%s is not in the plugin catalog" % plugin
        q = urllib.parse.urlencode({"assemblyGuid": pkg.get("guid", ""), "repositoryUrl": repo_url})
        st, _, _ = http("POST", url("jellyfin", "/Packages/Installed/%s?%s" % (urllib.parse.quote(pkg.get("name", plugin)), q)), headers=auth, body={}, timeout=120)
        if st not in (200, 204):
            return False, changed, "%s has no build for this Jellyfin version (HTTP %s)" % (plugin, st)
        changed = True
    return True, changed, ""


def jf_set_css(auth, slideshow):
    """Put the theme into the Custom CSS box, but only when the box is empty. Returns a note when it was left alone."""
    cur = jf_get("/System/Configuration/branding", auth)
    if not isinstance(cur, dict):
        return "Jellyfin did not give its branding settings"
    css = str(cur.get("CustomCss") or "")
    if css.strip():
        return "" if "n00bcodr/Jellyfish" in css else "the Custom CSS box already has your own CSS, so the theme was not added (Dashboard, Branding)"
    cur["CustomCss"] = jellyfin_css(slideshow)
    st, _, _ = http("POST", url("jellyfin", "/System/Configuration/branding"), headers=auth, body=cur, timeout=30)
    return "" if st in (200, 204) else "Jellyfin did not accept the theme (HTTP %s)" % st


def jf_make_libraries(auth):
    """Add the Movies and Shows libraries for the two media folders when no library uses them yet. Returns the notes for the ones that failed."""
    cur = jf_get("/Library/VirtualFolders", auth)
    if not isinstance(cur, list):
        return ["Jellyfin did not list its libraries"]
    notes = []
    for name, kind, path in JELLYFIN_LIBRARIES:
        if any(isinstance(f, dict) and (f.get("Name") == name or path in (f.get("Locations") or [])) for f in cur):
            continue
        q = urllib.parse.urlencode({"name": name, "collectionType": kind, "paths": path, "refreshLibrary": "true"})
        st, _, _ = http("POST", url("jellyfin", "/Library/VirtualFolders?" + q), headers=auth, body={"LibraryOptions": {"PathInfos": [{"Path": path}]}}, timeout=60)
        if st not in (200, 204):
            notes.append("the %s library was not created (HTTP %s)" % (name, st))
    return notes


def jf_display(auth):
    """Turn on backdrops and the details banner in the admin's saved display settings. The web page may also keep them per browser, so this can come to nothing."""
    users = jf_get("/Users", auth)
    me = next((u for u in users if isinstance(u, dict) and str(u.get("Name", "")).lower() == str(Ctx.admin).lower()), None) if isinstance(users, list) else None
    if not me:
        return False
    path = "/DisplayPreferences/usersettings?" + urllib.parse.urlencode({"userId": me.get("Id", ""), "client": "emby"})
    prefs = jf_get(path, auth)
    if not isinstance(prefs, dict):
        return False
    prefs.setdefault("CustomPrefs", {})
    prefs["CustomPrefs"].update(JELLYFIN_DISPLAY)
    return http("POST", url("jellyfin", path), headers=auth, body=prefs, timeout=30)[0] in (200, 204)


@step
class JellyfinLook(Step):
    id, group, title = "jellyfin-look", "Services", "Jellyfin look: theme, Media Bar slideshow and the Movies and Shows libraries"
    needs = ("w-jellyfin",)
    optional = True

    def applies(self):
        return BY_ID["stack-jellyfin"].applies()

    def stamp(self):
        return hashlib.md5((jellyfin_css() + "".join(JELLYFIN_PLUGINS) + JELLYFIN_PLUGIN_REPO[1] + str(JELLYFIN_LIBRARIES) + str(JELLYFIN_DISPLAY)).encode()).hexdigest()[:12]

    def probe(self):
        done = State.data.get("jellyfin_look") or ""
        if not done.startswith(self.stamp()):
            return "todo"
        if ":" in done:
            # the plugins had no build for that Jellyfin version: try again after Jellyfin has been updated
            st, js, _ = http("GET", url("jellyfin", "/System/Info/Public"), timeout=15)
            if st == 200 and isinstance(js, dict) and js.get("Version") and js.get("Version") != done.split(":", 1)[1]:
                return "todo"
        return "done"

    def detail(self):
        return "slideshow plugin not available for this Jellyfin version" if ":" in (State.data.get("jellyfin_look") or "") else ""

    def help(self):
        return "Open Jellyfin, Dashboard, Branding and paste the theme lines into Custom CSS (see docs/services.md). Then run:\n$ sudo homelab-setup done jellyfin-look"

    def run(self):
        if Opt.dry:
            out("      would add the Jellyfish theme, the Media Bar plugins and the Movies and Shows libraries to Jellyfin")
            return
        auth = jf_auth()
        if not auth:
            raise Abort("The Jellyfin key is not known yet. Run `sudo homelab-setup refresh` again after the Jellyfin widget step is done.")
        notes = []
        slideshow, restart, why = jf_install_plugins(auth)
        if why:
            notes.append("the slideshow plugin was skipped: " + why)
        if restart:
            out("      Restarting Jellyfin once so the new plugins load.")
            http("POST", url("jellyfin", "/System/Restart"), headers=auth, body={}, timeout=30)
            if not jf_wait_up():
                notes.append("Jellyfin did not answer again after its restart; check that the container is running")
            else:
                have = jf_plugins(auth) or {}
                slideshow = all(have.get(p.lower()) == "Active" for p in JELLYFIN_PLUGINS)
                if not slideshow:
                    notes.append("the slideshow plugins did not start with this Jellyfin version")
        note = jf_set_css(auth, slideshow)
        if note:
            notes.append(note)
        notes += jf_make_libraries(auth)
        shown = jf_display(auth)
        version = ""
        if not slideshow:
            st, js, _ = http("GET", url("jellyfin", "/System/Info/Public"), timeout=15)
            version = js.get("Version", "") if st == 200 and isinstance(js, dict) else ""
        State.data["jellyfin_look"] = self.stamp() + (":" + str(version) if version else "")
        State.save()
        for n in notes:
            warn("Jellyfin: " + n + ".")
        out("      The Jellyfin look is set up. Hard refresh the page (Ctrl+Shift+R) to see it.")
        if not shown:
            out("      If the picture backgrounds are missing, turn on Backdrops and Details Banner in Jellyfin: your profile, Settings, Display.")
