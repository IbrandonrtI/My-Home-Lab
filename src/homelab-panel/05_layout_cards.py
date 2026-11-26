def layout_groups(text):
    """Return [{name, props: {tab, icon, style, columns, ...}, extra: [lines]}] in the order of the file."""
    lines = text.split("\n")
    i, j = layout_span(lines)
    out = []
    if i is None:
        return out
    cur = None
    for l in lines[i + 1:j]:
        m = re.match(r"^  (?! )(.+?):\s*$", l)
        if m and not l.lstrip().startswith("#"):
            cur = {"name": unq(m.group(1)), "props": {}, "extra": []}
            out.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"^    ([A-Za-z0-9_]+):\s*(.*?)\s*$", l)
        if m:
            cur["props"][m.group(1)] = unq(m.group(2))
        elif l.strip():
            cur["extra"].append(l)
    return out


def layout_tabs(groups):
    tabs = []
    for g in groups:
        t = g["props"].get("tab") or "Home"
        tab = next((x for x in tabs if x["name"] == t), None)
        if not tab:
            tab = {"name": t, "groups": []}
            tabs.append(tab)
        tab["groups"].append(g)
    return tabs


def layout_write(text, groups):
    lines = text.split("\n")
    i, j = layout_span(lines)
    block = ["layout:"]
    for g in groups:
        block.append("  %s:" % yq(g["name"]))
        p = dict(g["props"])
        for k in ("tab", "icon", "style", "columns"):
            if p.get(k) not in (None, ""):
                block.append("    %s: %s" % (k, p[k] if k in ("style", "columns") else yq(p[k])))
        for k, v in p.items():
            if k not in ("tab", "icon", "style", "columns") and v != "":
                block.append("    %s: %s" % (k, v))
        block.extend(g["extra"])
    if i is None:
        return text.rstrip("\n") + "\n\n" + "\n".join(block) + "\n"
    return "\n".join(lines[:i] + block + lines[j:])


def group_kinds():
    kinds = {}
    for g in services_parse(read(SERVICES).split("\n")):
        kinds.setdefault(g["name"], set()).add("services")
    for g in marks_parse(read(BOOKMARKS))[1]:
        kinds.setdefault(g["name"], set()).add("bookmarks")
    return kinds


ROWS_B1 = "/* >>> homelab groups per row >>> written by the control panel; change it on the Layout screen */"
ROWS_B2 = "/* <<< homelab groups per row <<< */"
ROWS_RULE = 'html[data-tab="%s"] body #inner_wrapper { --hl-cols: %d; }'


DEFAULT_PER_ROW = 2  # groups side by side on a Links tab when nothing is set


def rows_get(css):
    """Read the groups-per-row setting of every tab from the block in custom.css: {tab name: 1 to 4}."""
    a = css.find(ROWS_B1)
    z = css.find(ROWS_B2, a) if a >= 0 else -1
    if a < 0 or z < 0:
        return {}
    return {m.group(1): int(m.group(2)) for m in re.finditer(r'html\[data-tab="([^"]+)"\] body #inner_wrapper \{ --hl-cols: ([1-4]); \}', css[a:z])}


def rows_put(css, rows):
    """Write the groups-per-row block of custom.css (removed when no tab has a setting). Everything else in the file is left as it was."""
    a = css.find(ROWS_B1)
    z = css.find(ROWS_B2, a) if a >= 0 else -1
    if a >= 0 and z >= 0:
        end = z + len(ROWS_B2)
        if css[end:end + 1] == "\n":
            end += 1
        css = css[:a].rstrip("\n") + ("\n" if css[:a].strip() else "") + css[end:]
    if not rows:
        return css
    block = "\n".join([ROWS_B1] + [ROWS_RULE % (n, rows[n]) for n in sorted(rows)] + [ROWS_B2]) + "\n"
    return css.rstrip("\n") + "\n\n" + block


def tab_takes_rows(groups, kinds):
    """True for a tab that holds bookmark groups and nothing but bookmark groups and the Edit Links box: the only kind of tab where groups sit side by side."""
    names = [g["name"] for g in groups]
    has = any("bookmarks" in kinds.get(n, ()) for n in names)
    other = any(n not in PROTECTED and "bookmarks" not in kinds.get(n, ()) for n in names)
    return has and not other


def layout_state():
    text = read(SETTINGS)
    groups = layout_groups(text)
    kinds = group_kinds()
    svc = {g["name"]: len(g["cards"]) for g in services_parse(read(SERVICES).split("\n"))}
    bm = {g["name"]: len(g["links"]) for g in marks_parse(read(BOOKMARKS))[1]}
    listed = {g["name"] for g in groups}
    extra = [n for n in list(svc) + list(bm) if n not in listed]
    for n in dict.fromkeys(extra):
        groups.append({"name": n, "props": {"tab": (layout_tabs(groups)[0]["name"] if groups else "Home")}, "extra": [], "unlisted": True})
    tabs = []
    rows = rows_get(read(CSS))
    for t in layout_tabs(groups):
        tabs.append({"name": t["name"], "rowsOk": tab_takes_rows(t["groups"], kinds), "perRow": rows.get(t["name"], ""), "groups": [{
            "name": g["name"], "icon": g["props"].get("icon", ""), "style": g["props"].get("style", ""), "columns": g["props"].get("columns", ""),
            "kind": "+".join(sorted(kinds.get(g["name"], ()))) or "empty", "locked": g["name"] in AUTOMATIC or g["name"] in PROTECTED,
            "automatic": g["name"] in AUTOMATIC, "count": svc.get(g["name"], 0) + bm.get(g["name"], 0)} for g in t["groups"]]})
    return {"tabs": tabs}


def api_layout_save(body):
    """Save the tabs, the order of the groups and their icons, styles and columns."""
    want = body.get("tabs")
    if not isinstance(want, list) or not want or len(want) > 12:
        raise Fail("The layout is missing.")
    tx = Tx("Layout changed")
    text = tx.get(SETTINGS)
    cur = layout_groups(text)
    state = {g["name"]: g for g in cur}
    for n in group_kinds():
        if n not in state:
            state[n] = {"name": n, "props": {}, "extra": []}
    out, seen = [], set()
    names = set()
    rows = {}
    for t in want:
        tname = clean_text(t.get("name"), "A tab name", 24)
        if not re.fullmatch(r"[^\"'\\{};<>/*:#]+", tname):
            raise Fail("The tab name '%s' has characters that are not allowed." % tname)
        if tname in names:
            raise Fail("Two tabs are called '%s'." % tname)
        names.add(tname)
        if t.get("perRow") not in ("", None):
            per = number(t["perRow"], "The number of groups in a row", 1, 4)
            if per != int(per):
                raise Fail("The number of groups in a row must be a whole number from 1 to 4.")
            if per != DEFAULT_PER_ROW and tab_takes_rows([{"name": g.get("name")} for g in t.get("groups") or []], group_kinds()):
                rows[tname] = per  # the default is not written: the line goes away instead
        for g in t.get("groups") or []:
            n = g.get("name")
            if n not in state or n in seen:
                raise Fail("The group '%s' is not known (or is listed twice). Reload the panel and try again." % n)
            seen.add(n)
            o = state[n]
            props = dict(o["props"])
            props["tab"] = tname
            icon = clean_icon(g.get("icon", props.get("icon", "")))
            if icon:
                props["icon"] = icon
            else:
                props.pop("icon", None)
            style = g.get("style", props.get("style", ""))
            if style not in ("", "row", "column"):
                raise Fail("The style must be 'row' or 'column'.")
            if style:
                props["style"] = style
            else:
                props.pop("style", None)
            cols = g.get("columns", props.get("columns", ""))
            if cols in ("", None):
                props.pop("columns", None)
            else:
                props["columns"] = str(number(cols, "The number of columns", 1, 8))
            out.append({"name": n, "props": props, "extra": o["extra"]})
    missing = [n for n in state if n not in seen and (n in {g["name"] for g in cur} or n in group_kinds())]
    if missing:
        raise Fail("These groups are missing from the layout: %s. Reload the panel and try again." % ", ".join(missing))
    def layout_sig(groups):
        return [(t["name"], [(g["name"], dict(g["props"])) for g in t["groups"]]) for t in layout_tabs(groups)]
    if layout_sig(out) != layout_sig(cur):  # only a real change rewrites the file (and takes over Undo)
        tx.put(SETTINGS, layout_write(text, out))
    css = tx.get(CSS)
    if rows_get(css) != rows:
        tx.put(CSS, rows_put(css, rows))
    tx.commit()
    return {}


def services_parse(lines):
    """Return [{name, start, end, cards: [{name, start, end}]}] with line numbers. end is exclusive."""
    heads = [(i, re.match(r"^- (.+?):\s*$", l)) for i, l in enumerate(lines)]
    heads = [(i, unq(m.group(1))) for i, m in heads if m]
    groups = []
    for n, (i, name) in enumerate(heads):
        e = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        g = {"name": name, "start": i, "end": e, "cards": []}
        cards = [(k, re.match(r"^    - (.+?):\s*$", lines[k])) for k in range(i + 1, e)]
        cards = [(k, unq(m.group(1))) for k, m in cards if m]
        for c, (k, cn) in enumerate(cards):
            ce = cards[c + 1][0] if c + 1 < len(cards) else e
            while ce > k + 1 and (not lines[ce - 1].strip() or lines[ce - 1].lstrip().startswith("#") and indent(lines[ce - 1]) < 8):
                ce -= 1
            g["cards"].append({"name": cn, "start": k, "end": ce})
        while g["end"] > g["start"] + 1 and (not lines[g["end"] - 1].strip() or (lines[g["end"] - 1].lstrip().startswith("#") and indent(lines[g["end"] - 1]) < 4)):
            g["end"] -= 1
        groups.append(g)
    return groups


def card_fields(lines, c):
    """Return the simple lines of a card (id, href, icon, description, siteMonitor) and the type of its widget ('' when it has none)."""
    f = {}
    for k in range(c["start"] + 1, c["end"]):
        m = re.match(r"^        (id|href|icon|description|siteMonitor|target):\s*(.*?)\s*$", lines[k])
        if m:
            f[m.group(1)] = unq(m.group(2))
    w = ""
    for k in range(c["start"] + 1, c["end"]):
        if re.match(r"^        widget:\s*$", lines[k]):
            w = "yes"
            for q in range(k + 1, c["end"]):
                m = re.match(r"^          type:\s*(\S+)\s*$", lines[q])
                if m:
                    w = unq(m.group(1))
                    break
            break
    f["widget"] = w
    return f


def card_public(lines, c, group):
    f = card_fields(lines, c)
    managed = bool(f.get("widget")) or (f.get("id", "").endswith("-card") and f.get("id", "") not in ("watching-card", "downloaders-card"))
    return {"name": c["name"], "id": f.get("id", ""), "href": f.get("href", ""), "icon": f.get("icon", ""), "description": f.get("description", ""),
            "siteMonitor": f.get("siteMonitor", ""), "widget": f.get("widget", ""), "managed": managed,
            "keys": widget_secrets_public(lines, c),
            "hl": bool(HL_ID.match(f.get("id", ""))),
            "locked": f.get("id", "") == "customize-card", "fixed": f.get("id", "") == "navidrome-card"}


def services_state():
    lines = read(SERVICES).split("\n")
    out = []
    for g in services_parse(lines):
        out.append({"group": g["name"], "locked": g["name"] in PROTECTED, "automatic": g["name"] in AUTOMATIC,
                    "cards": [card_public(lines, c, g["name"]) for c in g["cards"]]})
    return out


def find_card(lines, group, name):
    for g in services_parse(lines):
        if g["name"] == group:
            for c in g["cards"]:
                if c["name"] == name:
                    return g, c
    raise Fail("The card '%s' was not found in '%s'. Reload the panel and try again." % (name, group))


def set_line(lines, c, key, value):
    """Set one simple line of a card. A value of None or '' removes it. The widget lines are never touched."""
    ind = " " * 8
    idx = None
    for k in range(c["start"] + 1, c["end"]):
        if re.match(r"^        %s:\s" % re.escape(key), lines[k] + " "):
            idx = k
            break
    if value in (None, ""):
        if idx is not None:
            del lines[idx]
            c["end"] -= 1
        return
    new = "%s%s: %s" % (ind, key, yq(value))
    if idx is not None:
        lines[idx] = new
        return
    at = c["end"]
    for k in range(c["start"] + 1, c["end"]):
        if re.match(r"^        (widget|server|container|stack):", lines[k]):
            at = k
            break
    lines.insert(at, new)
    c["end"] += 1


# The lines inside a card's widget that hold a key or a password, and what the Change window calls them.
SECRET_FIELDS = {"key": "API key", "apikey": "API key", "token": "API key", "password": "Password"}
SECRET_PLACEHOLDER = re.compile(r"your-own-key|your-password|^TOKEN$|^changeme$|^yours?$")


def widget_secret_lines(lines, c):
    """Return [(line number, field, value)] for the key and password lines of the card's widget. The value is for checks only and is never sent to the browser."""
    out = []
    in_widget = False
    for k in range(c["start"] + 1, c["end"]):
        if re.match(r"^        widget:\s*$", lines[k]):
            in_widget = True
            continue
        if not in_widget:
            continue
        if lines[k].strip() and indent(lines[k]) <= 8:
            break
        m = re.match(r"^          (%s):\s*(.*?)\s*$" % "|".join(SECRET_FIELDS), lines[k])
        if m:
            out.append((k, m.group(1), unq(m.group(2))))
    return out


def widget_secrets_public(lines, c):
    """What the Change window may know about a card's keys: which ones exist and whether each is filled in. Never the value."""
    return [{"field": f, "label": SECRET_FIELDS[f], "set": bool(v) and not SECRET_PLACEHOLDER.search(v)} for _k, f, v in widget_secret_lines(lines, c)]


def secret_word(field):
    return "password" if field == "password" else "API key"


def clean_secret(value, field):
    """Check a new key or password. The messages never repeat the value."""
    if not isinstance(value, str):
        raise Fail("The %s is not valid." % secret_word(field))
    value = value.strip()
    if len(value) > 400 or re.search(r"[\x00-\x1f\x7f]", value):
        raise Fail("The %s is too long or has characters that are not allowed." % secret_word(field))
    if field != "password" and re.search(r"\s", value):
        raise Fail("The %s cannot contain spaces. Copy it again, without anything around it." % secret_word(field))
    return value


def set_widget_secrets(lines, c, secrets):
    """Replace the key or password lines named in `secrets` ({field: new value}). An empty value keeps what is there. Only lines that already exist in the card's widget are changed."""
    if secrets in (None, {}):
        return False
    if not isinstance(secrets, dict):
        raise Fail("The key could not be read. Reload the panel and try again.")
    have = {f: k for k, f, _v in widget_secret_lines(lines, c)}
    new = {}
    for field, value in secrets.items():
        if field not in have:
            raise Fail("This card has no %s to change." % (secret_word(field) if field in SECRET_FIELDS else "key"))
        value = clean_secret(value, field)
        if value:
            new[field] = value
    for field, value in new.items():
        # Always in double quotes, so a value such as 0x1F or 1e3 stays text.
        lines[have[field]] = '          %s: "%s"' % (field, value.replace("\\", "\\\\").replace('"', '\\"'))
    return bool(new)


