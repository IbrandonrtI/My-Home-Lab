def api_link(body):
    """Add, edit, remove or move bookmarks and bookmark groups. The Links screen sends the whole list with op "save", so one Save is one change and one Undo."""
    op = body.get("op")
    tx = Tx({"add": "Link added", "edit": "Link changed", "remove": "Link removed", "move": "Link moved", "group-add": "Link group added",
             "group-rename": "Link group renamed", "group-remove": "Link group removed", "save": "Links changed"}.get(op, "Links changed"))
    head, groups = marks_parse(tx.get(BOOKMARKS))

    def grp(name):
        g = next((x for x in groups if x["name"] == name), None)
        if not g:
            raise Fail("The group '%s' was not found. Reload the panel and try again." % name)
        return g

    def link(g, name):
        e = next((x for x in g["links"] if x["name"] == name), None)
        if not e:
            raise Fail("The link '%s' was not found. Reload the panel and try again." % name)
        return e

    def values(b):
        name = clean_text(b.get("name"), "The name", 60)
        if not re.fullmatch(r"[^\"'\\{};<>/*:#\[\]|`]+", name):
            raise Fail("The name '%s' has characters that are not allowed." % name)
        href = clean_url(b.get("href"), "The address", False)
        abbr = clean_text(b.get("abbr", ""), "The short label", 6, True) or abbr_of(name)
        if not re.fullmatch(r"[A-Za-z0-9 ]{1,6}", abbr):
            raise Fail("The short label can have up to 6 letters or digits.")
        return {"name": name, "abbr": abbr, "href": href, "icon": clean_icon(b.get("icon", "")),
                "description": clean_text(b.get("description", ""), "The description", 120, True), "extra": []}

    if op == "save":
        if body.get("version") != marks_version():
            raise Fail("The links were changed in another window or tab after this page was opened. Reload the panel to see that change, then make yours again. Nothing was saved.", 409)
        links_apply(tx, head, groups, body.get("groups"), values)
    elif op == "add":
        gname = check_group_name(body.get("group"))
        g = next((x for x in groups if x["name"] == gname), None)
        if g is None:
            g = {"name": gname, "links": []}
            groups.append(g)
        e = values(body)
        if any(x["name"] == e["name"] for gg in groups for x in gg["links"]):
            raise Fail("There is already a link called '%s'. Choose another name." % e["name"])
        g["links"].append(e)
        tx.put(BOOKMARKS, marks_write(head, groups))
        ensure_layout_group(tx, gname, body.get("tab") or "Links")
    elif op == "edit":
        g = grp(body.get("group"))
        e = link(g, body.get("old"))
        v = values(body)
        if v["name"] != e["name"] and any(x["name"] == v["name"] for gg in groups for x in gg["links"]):
            raise Fail("There is already a link called '%s'." % v["name"])
        v["extra"] = e["extra"]
        e.update(v)
        tx.put(BOOKMARKS, marks_write(head, groups))
    elif op == "remove":
        g = grp(body.get("group"))
        g["links"].remove(link(g, body.get("name")))
        if not g["links"]:
            groups.remove(g)
            drop_layout_group(tx, g["name"])
        tx.put(BOOKMARKS, marks_write(head, groups))
    elif op == "move":
        g = grp(body.get("group"))
        e = link(g, body.get("name"))
        to = check_group_name(body.get("to") or g["name"])
        tg = next((x for x in groups if x["name"] == to), None)
        if tg is None:
            tg = {"name": to, "links": []}
            groups.append(tg)
        g["links"].remove(e)
        before = body.get("before")
        at = next((i for i, x in enumerate(tg["links"]) if x["name"] == before), len(tg["links"]))
        tg["links"].insert(at, e)
        if not g["links"]:
            groups.remove(g)
            drop_layout_group(tx, g["name"])
        tx.put(BOOKMARKS, marks_write(head, groups))
        ensure_layout_group(tx, to, body.get("tab") or "Links")
    elif op == "group-rename":
        g = grp(body.get("group"))
        new = check_group_name(body.get("to"))
        if any(x["name"] == new for x in groups):
            raise Fail("There is already a group called '%s'." % new)
        text = tx.get(SETTINGS)
        gs = layout_groups(text)
        for x in gs:
            if x["name"] == g["name"]:
                x["name"] = new
        tx.put(SETTINGS, layout_write(text, gs))
        g["name"] = new
        tx.put(BOOKMARKS, marks_write(head, groups))
    elif op == "group-remove":
        g = grp(body.get("group"))
        groups.remove(g)
        drop_layout_group(tx, g["name"])
        tx.put(BOOKMARKS, marks_write(head, groups))
    else:
        raise Fail("Unknown action.")
    tx.commit()
    return {}


def api_group(body):
    """Rename or remove a whole group of cards on the dashboard. Groups HomeLab keeps up to date cannot be removed."""
    op = body.get("op")
    name = body.get("group")
    if name in AUTOMATIC or name in PROTECTED:
        raise Fail("The group '%s' is kept up to date by HomeLab and cannot be changed here." % name)
    tx = Tx("Group changed")
    lines = tx.get(SERVICES).split("\n")
    g = next((x for x in services_parse(lines) if x["name"] == name), None)
    if g is None:
        raise Fail("The group '%s' was not found. Reload the panel and try again." % name)
    if op == "rename":
        new = check_group_name(body.get("to"))
        if any(x["name"] == new for x in services_parse(lines)):
            raise Fail("There is already a group called '%s'." % new)
        lines[g["start"]] = "- %s:" % yq(new)
        tx.put(SERVICES, "\n".join(lines))
        text = tx.get(SETTINGS)
        gs = layout_groups(text)
        for x in gs:
            if x["name"] == name:
                x["name"] = new
        tx.put(SETTINGS, layout_write(text, gs))
    elif op == "remove":
        if any(card_public(lines, c, name)["locked"] for c in g["cards"]):
            raise Fail("This group has a card HomeLab keeps up to date. Remove the other cards one by one.")
        del lines[g["start"]:g["end"]]
        tx.put(SERVICES, "\n".join(lines))
        drop_layout_group(tx, name)
    else:
        raise Fail("Unknown action.")
    tx.commit()
    return {}


def hash_password(pw, salt=None):
    salt = salt or secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode("utf-8"), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return "scrypt$%s$%s" % (base64.b64encode(salt).decode(), base64.b64encode(h).decode())


def check_password(pw):
    txt = read(PASSFILE).strip()
    m = re.fullmatch(r"scrypt\$([A-Za-z0-9+/=]+)\$([A-Za-z0-9+/=]+)", txt)
    if not m:
        return False
    salt = base64.b64decode(m.group(1))
    return hmac.compare_digest(hash_password(pw, salt), txt)


def password_problem(pw):
    if len(pw) < 10:
        return "The password must be at least 10 characters."
    if pw.strip() != pw:
        return "The password cannot start or end with a space."
    return ""


def set_password(pw):
    p = password_problem(pw)
    if p:
        raise Fail(p)
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)
    write_atomic(PASSFILE, hash_password(pw) + "\n", 0o600)
    SESSIONS.clear()


SESSIONS = {}
FAIL_FORGET = 15 * 60  # wrong guesses are forgotten after this many quiet seconds
FAILS = {}  # client address -> {"count", "until", "last"}


LOGIN_LOCK = threading.Lock()


def login(pw, addr="-"):
    """Check the password. Checks go one at a time, so a burst of wrong guesses is stopped by the wait after the fourth one and cannot all be tried first.
    Wrong guesses are counted for each address, so someone guessing from one device cannot lock the owner out on another, and the count is forgotten after 15 quiet minutes."""
    with LOGIN_LOCK:
        now = time.time()
        for a in [a for a, f in FAILS.items() if now >= f["until"] and now - f["last"] > FAIL_FORGET]:
            del FAILS[a]
        if len(FAILS) > 2000:
            for a in sorted(FAILS, key=lambda a: FAILS[a]["last"])[:len(FAILS) - 2000]:
                del FAILS[a]
        fail = FAILS.get(addr)
        if fail and now < fail["until"]:
            raise Fail("Too many wrong passwords. Wait %d seconds and try again." % int(fail["until"] - now + 1), 429)
        if not os.path.exists(PASSFILE):
            raise Fail("No password is set yet. In a terminal on the server, run:  homelab panel password", 403)
        if not isinstance(pw, str) or not check_password(pw):
            fail = FAILS.setdefault(addr, {"count": 0, "until": 0.0, "last": now})
            fail["count"] += 1
            fail["last"] = now
            fail["until"] = now + min(300, 2 ** min(fail["count"], 8)) if fail["count"] >= 4 else 0.0
            raise Fail("That is not the password.", 401)
        FAILS.pop(addr, None)
    tok = secrets.token_urlsafe(32)
    SESSIONS[tok] = {"created": now, "seen": now, "pw": pw_version()}
    for t in [t for t, s in SESSIONS.items() if now - s["seen"] > SESSION_IDLE or now - s["created"] > SESSION_MAX]:
        del SESSIONS[t]
    return tok


def pw_version():
    try:
        return os.stat(PASSFILE).st_mtime_ns
    except OSError:
        return 0


def session_ok(tok):
    s = SESSIONS.get(tok or "")
    now = time.time()
    if not s or now - s["seen"] > SESSION_IDLE or now - s["created"] > SESSION_MAX or s["pw"] != pw_version():
        SESSIONS.pop(tok or "", None)
        return False
    s["seen"] = now
    return True


def paint_state():
    """Return the cards, tiles, bookmarks and group labels that the Colors screen lists."""
    lines = read(SERVICES).split("\n")
    css = read(CSS)
    look_accent = look_full(look_get(css))["accent"]
    cards, stats, cal, labels = [], [], [], []
    for g in services_parse(lines):
        if g["name"] not in PROTECTED and g["name"] not in labels:
            labels.append(g["name"])
        for c in g["cards"]:
            cid = card_fields(lines, c).get("id", "")
            if not cid or cid in NO_PAINT or not re.fullmatch(r"[A-Za-z0-9_-]+", cid):
                continue
            tile = cid.startswith(("stat-", "cal-"))
            acc = shipped_accent(css, cid)
            col = rgb_to_hex(acc) if acc else ("#94a3b8" if tile else look_accent)
            (stats if cid.startswith("stat-") else cal if cid.startswith("cal-") else cards).append({"id": cid, "name": c["name"], "group": g["name"], "color": col})
    links = []
    for g in marks_parse(read(BOOKMARKS))[1]:
        if g["name"] not in labels:
            labels.append(g["name"])
        gcol = rgb_to_hex(shipped_group_accent(css, slugify(g["name"])) or "148, 163, 184")
        links += [{"name": e["name"], "group": g["name"], "color": gcol} for e in g["links"]]
    return {"cards": cards, "stats": stats, "calendar": cal, "links": links, "labels": labels}


ICON_CACHE_DAYS = 30
ICON_TREE_URLS = [os.environ["HLP_ICON_TREE"]] if os.environ.get("HLP_ICON_TREE") else [
    "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/tree.json", "https://raw.githubusercontent.com/homarr-labs/dashboard-icons/main/tree.json"]
ICON_MDI_URLS = [os.environ["HLP_ICON_MDI"]] if os.environ.get("HLP_ICON_MDI") else [
    "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/meta.json", "https://raw.githubusercontent.com/Templarian/MaterialDesign-SVG/master/meta.json"]


def fetch_json(urls):
    for u in urls:
        try:
            if u.startswith("/"):
                with open(u, "rb") as f:
                    raw = f.read(8_000_000)
            else:
                req = urllib.request.Request(u, headers={"User-Agent": "homelab-panel"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    raw = r.read(8_000_000)
            return json.loads(raw.decode("utf-8"))
        except (OSError, ValueError, urllib.error.URLError):
            continue
    return None


def icon_index():
    """Return {"apps": [names like plex.svg], "mdi": [names like home-outline]} from the icon lists the dashboard uses. The lists are downloaded once and kept for a month."""
    cache = os.path.join(STATE_DIR, "icons.json")
    try:
        with open(cache, encoding="utf-8") as f:
            have = json.load(f)
    except (OSError, ValueError):
        have = None
    if have and time.time() - have.get("time", 0) < ICON_CACHE_DAYS * 86400:
        return have["data"]
    tree, meta = fetch_json(ICON_TREE_URLS), fetch_json(ICON_MDI_URLS)
    data = {"apps": (have or {}).get("data", {}).get("apps", []), "mdi": (have or {}).get("data", {}).get("mdi", [])}
    if isinstance(tree, dict):
        svg = [x for x in tree.get("svg", []) if isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,80}\.svg", x)]
        have_svg = {x[:-4] for x in svg}
        png = [x for x in tree.get("png", []) if isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,80}\.png", x) and x[:-4] not in have_svg]
        data["apps"] = sorted(svg + png)
    if isinstance(meta, list):
        data["mdi"] = sorted({m["name"] for m in meta if isinstance(m, dict) and isinstance(m.get("name"), str) and re.fullmatch(r"[a-z0-9-]{1,60}", m["name"])})
    if data["apps"] or data["mdi"]:
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            write_atomic(cache, json.dumps({"time": time.time(), "data": data}), 0o600)
        except OSError:
            pass
    return data


GEOCODE_API = os.environ.get("HLP_GEOCODE_API") or "https://geocoding-api.open-meteo.com"
ZONE_NAME = re.compile(r"[A-Za-z0-9_+/-]{1,60}\Z")


def widget_block(text, key):
    m = re.search(r"(- %s:)(.*?)(\n- |\Z)" % key, text, re.S)
    return (m.start(2), m.end(2)) if m else None


def location_state(zones=True):
    text = read(WIDGETS)
    out = {"timeZone": "", "city": "", "lat": None, "lon": None, "zones": sorted(zoneinfo.available_timezones()) if zones else []}
    b = widget_block(text, "datetime")
    if b:
        m = re.search(r"\n\s+timeZone:\s*(\S+)", text[b[0]:b[1]])
        out["timeZone"] = m.group(1).strip("\"'") if m else ""
    b = widget_block(text, "openmeteo")
    if b:
        blk = text[b[0]:b[1]]
        m = re.search(r"\n\s+label:\s*(.*)", blk)
        out["city"] = m.group(1).strip().strip("\"'") if m else ""
        for key, k in (("lat", "latitude"), ("lon", "longitude")):
            m = re.search(r"\n\s+%s:\s*(-?[0-9.]+)" % k, blk)
            out[key] = float(m.group(1)) if m else None
    return out


def api_location_search(body):
    """Search cities by name with Open-Meteo's free search. The page shows the results and the person picks one."""
    q = str(body.get("q") or "").strip()[:60]
    if not q:
        raise Fail("Type the name of a city first.")
    try:
        req = urllib.request.Request(GEOCODE_API + "/v1/search?count=6&language=en&format=json&name=" + urllib.parse.quote(q), headers={"User-Agent": "homelab-panel"})
        with urllib.request.urlopen(req, timeout=15) as r:
            js = json.loads(r.read().decode("utf-8", "replace"))
    except (OSError, ValueError):
        raise Fail("The city search did not respond. Check that the server is online and try again.") from None
    found = []
    for r in js.get("results") or []:
        try:
            found.append({"name": str(r["name"]), "region": str(r.get("admin1") or ""), "country": str(r.get("country") or ""),
                          "lat": float(r["latitude"]), "lon": float(r["longitude"])})
        except (KeyError, TypeError, ValueError):
            continue
    return {"places": found}


