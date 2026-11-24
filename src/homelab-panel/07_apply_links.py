def api_mytheme(body):
    """Create, apply, rename and delete the user's saved themes."""
    op = body.get("op")
    lst = mythemes_load()
    if op == "create":
        if len(lst) >= MAX_MYTHEMES:
            raise Fail("The limit of %d themes has been reached. Delete one first." % MAX_MYTHEMES)
        name = clean_text(body.get("name"), "The theme name", 30)
        if not re.fullmatch(r"[^\"'\\{};<>/*:#\[\]|`]+", name):
            raise Fail("The name '%s' has characters that are not allowed (use letters, digits, spaces and - _ . , ( ) + )." % name)
        if any(t.get("name", "").lower() == name.lower() for t in lst) or any(t["name"].lower() == name.lower() for t in LOOK_THEMES):
            raise Fail("There is already a theme called '%s'. Choose another name." % name)
        parts = body.get("parts")
        if not isinstance(parts, list) or not parts or any(p not in MYTHEME_PARTS for p in parts):
            raise Fail("Select at least one item for the theme to contain.")
        tid = "my-" + secrets.token_hex(4)
        t = {"id": tid, "name": name, "blurb": clean_text(body.get("blurb", ""), "The description", 90, True) or "Your own theme.", "created": int(time.time())}
        if "look" in parts:
            custom = look_clean(body.get("look"))
            custom["theme"] = tid
            t["look"] = custom
            ui = body.get("ui")
            if isinstance(ui, dict):
                t["ui"] = {k: str(v)[:140] for k, v in ui.items() if k in ("bg", "panel", "panel2", "line", "field", "dialog", "blur", "rim") and re.fullmatch(r"[#A-Za-z0-9 .,()%-]+", str(v))}
        if "background" in parts:
            t["background"] = mytheme_background(body.get("background"), tid)
        if "layout" in parts:
            t["layout"] = layout_snapshot()
        if "cards" in parts:
            t["cards"] = cards_snapshot()
        lst.append(t)
        mythemes_save(lst)
        return {"id": tid}
    t = next((x for x in lst if x["id"] == body.get("id")), None)
    if t is None:
        raise Fail("The theme was not found. Reload the panel and try again.")
    if op == "rename":
        name = clean_text(body.get("name"), "The theme name", 30)
        if not re.fullmatch(r"[^\"'\\{};<>/*:#\[\]|`]+", name):
            raise Fail("The name '%s' has characters that are not allowed." % name)
        if any(x is not t and x.get("name", "").lower() == name.lower() for x in lst) or any(x["name"].lower() == name.lower() for x in LOOK_THEMES):
            raise Fail("There is already a theme called '%s'." % name)
        t["name"] = name
        t["blurb"] = clean_text(body.get("blurb", t.get("blurb", "")), "The description", 90, True)
        mythemes_save(lst)
    elif op == "delete":
        lst.remove(t)
        mythemes_save(lst)
        if os.path.isdir(IMAGES):
            for f in os.listdir(IMAGES):
                if re.fullmatch(r"theme-%s\.\w+" % re.escape(t["id"]), f):
                    try:
                        os.remove(os.path.join(IMAGES, f))
                    except OSError:
                        pass
    elif op == "apply":
        if "cards" not in t and "layout" not in t:
            return {"changed": False}
        tx = Tx("Theme “%s”: layout and cards" % t.get("name", ""))
        if "cards" in t:
            cards_apply(tx, t["cards"])
        if "layout" in t:
            layout_apply(tx, t["layout"])
        tx.commit()
        return {"changed": True}
    else:
        raise Fail("Unknown action.")
    return {}


def layout_apply(tx, snap):
    """Apply a theme's tabs, group order, icons, styles and columns to the groups that exist now. Groups the theme does not know stay on their tab."""
    text = tx.get(SETTINGS)
    cur = layout_groups(text)
    if not cur:
        return
    state = {g["name"]: g for g in cur}
    out, seen = [], set()
    for t in snap if isinstance(snap, list) else []:
        tname = str(t.get("name", ""))
        if not tname or not re.fullmatch(r"[^\"'\\{};<>/*:#]+", tname) or len(tname) > 24:
            continue
        for g in t.get("groups") or []:
            n = g.get("name")
            if n not in state or n in seen:
                continue
            seen.add(n)
            props = dict(state[n]["props"])
            props["tab"] = tname
            icon = g.get("icon", "")
            try:
                icon = clean_icon(icon)
            except Fail:
                icon = ""
            props["icon"] = icon
            if not icon:
                props.pop("icon")
            for k, ok in (("style", ("row", "column")), ("columns", tuple(str(i) for i in range(1, 9)))):
                v = str(g.get(k, "") or "")
                if v in ok:
                    props[k] = v
                else:
                    props.pop(k, None)
            out.append({"name": n, "props": props, "extra": state[n]["extra"]})
    out.extend(g for g in cur if g["name"] not in seen)
    tx.put(SETTINGS, layout_write(text, out))


def cards_apply(tx, snap):
    """Put the cards the way a theme had them: names, icons, texts, groups and order. A card that is gone is created again when HomeLab fills it in or the user made it."""
    lines = tx.get(SERVICES).split("\n")
    want = [(g["group"], c) for g in (snap.get("groups") if isinstance(snap, dict) else []) or [] for c in g.get("cards", [])]
    catalog = {c["id"]: c for c in hl_catalog()}
    if any(c.get("kind") == "hl" for _g, c in want) or any(HL_ID.match(i) for i in card_ids(lines)):
        hl_adopt(lines)

    def find(item):
        for g in services_parse(lines):
            for c in g["cards"]:
                f = card_fields(lines, c)
                if item.get("id"):
                    if f.get("id") == item["id"]:
                        return g, c
                elif not f.get("id") and c["name"] == item.get("key"):
                    return g, c
        if item.get("kind") == "own" and item.get("href"):
            for g in services_parse(lines):
                for c in g["cards"]:
                    f = card_fields(lines, c)
                    if not f.get("id") and not f.get("widget") and f.get("href") == item["href"]:
                        return g, c
        return None

    for group, item in want:
        try:
            group = check_group_name(group)
        except Fail:
            continue
        got = find(item)
        if got is None:
            if item.get("kind") == "hl" and item.get("id") in catalog:
                card = dict(catalog[item["id"]])
                try:
                    hl_place(tx, lines, card, group)
                except Fail:
                    continue
                got = find(item)
            elif item.get("kind") == "own" and item.get("name"):
                try:
                    v = card_values({"name": item["name"], "description": item.get("description", ""), "icon": item.get("icon", ""), "href": item.get("href", ""),
                                     "dot": bool(item.get("siteMonitor"))})
                except Fail:
                    continue
                if any(x["name"] == v["name"] for g in services_parse(lines) if g["name"] == group for x in g["cards"]):
                    continue
                card_insert(lines, group, new_card_lines(v["name"], v["href"], v["icon"], v["description"], v["siteMonitor"]))
                ensure_layout_group(tx, group)
                got = find(item)
        if got is None:
            continue
        g, c = got
        pub = card_public(lines, c, g["name"])
        if pub["locked"]:
            continue
        nm = item.get("name") or c["name"]
        if nm != c["name"] and not any(x["name"] == nm for gg in services_parse(lines) if gg["name"] == group for x in gg["cards"]) and re.fullmatch(r"[^\"'\\{};<>/*:#\[\]|`]+", nm) and len(nm) <= 60:
            lines[c["start"]] = "    - %s:" % yq(nm)
        try:
            set_line(lines, c, "icon", clean_icon(item.get("icon", "")))
        except Fail:
            pass
        try:
            set_line(lines, c, "description", clean_text(item.get("description", ""), "The description", 160, True))
        except Fail:
            pass
        block = lines[c["start"]:c["end"]]
        del lines[c["start"]:c["end"]]
        tidy_blank(lines, c["start"])
        card_insert(lines, group, block)
        ensure_layout_group(tx, group)
        left = next((x for x in services_parse(lines) if x["name"] == g["name"]), None)
        if left is not None and not left["cards"]:
            del lines[left["start"]:left["end"]]
            drop_layout_group(tx, g["name"])
    sids = {c["id"] for _g, c in want if c.get("id")}
    skeys = {c.get("key") for _g, c in want if not c.get("id")}
    for _ in range(200):
        hit = None
        for g in services_parse(lines):
            for c in g["cards"]:
                i = card_fields(lines, c).get("id", "")
                if HL_ID.match(i) and i not in sids:
                    hit = (g, c)
                    break
            if hit:
                break
        if not hit:
            break
        g, c = hit
        del lines[c["start"]:c["end"]]
        tidy_blank(lines, c["start"])
        left = next((x for x in services_parse(lines) if x["name"] == g["name"]), None)
        if left is not None and not left["cards"]:
            del lines[left["start"]:left["end"]]
            tidy_blank(lines, left["start"])
            drop_layout_group(tx, g["name"])
    gnames = {g for g, _c in want}
    later = []
    for g in services_parse(lines):
        if g["name"] in gnames:
            for c in g["cards"]:
                i = card_fields(lines, c).get("id", "")
                if not ((i in sids) if i else (c["name"] in skeys)):
                    later.append((g["name"], c["name"], i))
    for gname, cname, i in later:
        g = next((x for x in services_parse(lines) if x["name"] == gname), None)
        c = next((x for x in (g["cards"] if g else []) if x["name"] == cname and card_fields(lines, x).get("id", "") == i), None)
        if c is None:
            continue
        block = lines[c["start"]:c["end"]]
        del lines[c["start"]:c["end"]]
        tidy_blank(lines, c["start"])
        card_insert(lines, gname, block)
    tx.put(SERVICES, "\n".join(lines))


def card_ids(lines):
    return [card_fields(lines, c).get("id", "") for g in services_parse(lines) for c in g["cards"]]


def marks_parse(text):
    """Return (the comment lines at the top, [{name, links: [{name, abbr, href, icon, description, extra}]}]) from bookmarks.yaml."""
    lines = text.split("\n")
    head, groups, cur, ent = [], [], None, None
    for l in lines:
        m = re.match(r"^- (.+?):\s*$", l)
        if m:
            cur = {"name": unq(m.group(1)), "links": []}
            groups.append(cur)
            ent = None
            continue
        if cur is None:
            if l.strip():
                head.append(l)
            continue
        m = re.match(r"^    - (.+?):\s*$", l)
        if m:
            ent = {"name": unq(m.group(1)), "abbr": "", "href": "", "icon": "", "description": "", "extra": []}
            cur["links"].append(ent)
            continue
        if ent is None or not l.strip():
            continue
        m = re.match(r"^\s+(?:- )?([A-Za-z][A-Za-z0-9_]*):\s*(.*?)\s*$", l)
        if m and m.group(1) in ("abbr", "href", "icon", "description"):
            ent[m.group(1)] = unq(m.group(2))
        elif m and l.strip() != "-":
            ent["extra"].append((m.group(1), m.group(2)))
    return head, groups


def marks_write(head, groups):
    out = list(head)
    for g in groups:
        out.append("- %s:" % yq(g["name"]))
        for e in g["links"]:
            out.append("    - %s:" % yq(e["name"]))
            fields = [(k, yq(e[k])) for k in ("abbr", "href", "icon", "description") if e.get(k)] + list(e["extra"])
            if not fields:
                fields = [("href", '""')]
            for n, (k, v) in enumerate(fields):
                out.append("        %s%s: %s" % ("- " if n == 0 else "  ", k, v))
            out.append("")
        if not g["links"]:
            out.append("")
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out) + "\n"


def marks_state():
    return [{"group": g["name"], "links": [{k: e[k] for k in ("name", "abbr", "href", "icon", "description")} for e in g["links"]]}
            for g in marks_parse(read(BOOKMARKS))[1]]


def marks_version():
    """A short fingerprint of the saved bookmarks. The Links screen sends the one it was loaded with, so a save made from an older copy is refused."""
    return hashlib.sha1(json.dumps(marks_state(), sort_keys=True).encode("utf-8")).hexdigest()[:12]


def abbr_of(name):
    w = re.sub(r"[^A-Za-z0-9 ]", "", name).split()
    return (w[0][:4] if len(w) == 1 else "".join(x[0] for x in w[:4])).upper()


def common_color(names, colors):
    """The color most of these links share, or "" when none of them has one."""
    seen = [colors[n] for n in names if colors.get(n)]
    return max(seen, key=seen.count) if seen else ""


def links_apply(tx, head, old_groups, want, values):
    """Replace the bookmarks with the list the Links screen sends: the groups in order, each with its links. Everything is checked first and written as one
    change. Links keep their extra lines and their color when they are renamed or moved, and a new link takes the color of the others in its group."""
    if not isinstance(want, list) or len(want) > 60:
        raise Fail("The list of links is not valid.")
    old_links = {e["name"]: (e, g["name"]) for g in old_groups for e in g["links"]}
    old_names = [g["name"] for g in old_groups]
    custom = look_get(tx.get(CSS))
    colors = dict(custom.get("links") or {})
    old_dominant = {g["name"]: common_color([e["name"] for e in g["links"]], colors) for g in old_groups}
    new_groups, seen_groups, seen_links, kept, used = [], set(), set(), set(), set()
    renames, new_tabs, plan = {}, {}, []
    for gb in want:
        if not isinstance(gb, dict) or not isinstance(gb.get("links"), list):
            raise Fail("The list of links is not valid.")
        if not gb["links"]:
            continue
        was = gb.get("was") or ""
        gname = was if was and gb.get("name") == was and was in old_names else check_group_name(gb.get("name"))
        if gname in seen_groups:
            raise Fail("There is already a group called '%s'." % gname)
        seen_groups.add(gname)
        if was:
            if was not in old_names or was in kept:
                raise Fail("The group '%s' was not found. Reload the panel and try again." % was)
            kept.add(was)
            if was != gname:
                renames[was] = gname
        else:
            new_tabs[gname] = gb.get("tab") or "Links"
        g = {"name": gname, "links": []}
        for lb in gb["links"]:
            if not isinstance(lb, dict):
                raise Fail("The list of links is not valid.")
            before = lb.get("was") or ""
            if before and (before not in old_links or before in used):
                raise Fail("The link '%s' was not found. Reload the panel and try again." % before)
            if before:
                used.add(before)
                e = dict(old_links[before][0])
                same = all(str(lb.get(k) or "") == str(e.get(k) or "") for k in ("name", "href", "icon", "description", "abbr"))
            else:
                same = False
            if not same:
                # A link that was not touched is kept as it is, even if an older version let an unusual value in. Only what was changed or added is checked.
                try:
                    keep = e["extra"] if before else []
                    e = values(lb)
                    e["extra"] = keep
                except Fail as err:
                    raise Fail("The link “%s”: %s" % (str(lb.get("name") or "").strip() or "(no name)", err), err.code) from None
            if e["name"] in seen_links:
                raise Fail("There is already a link called '%s'. Choose another name." % e["name"])
            seen_links.add(e["name"])
            g["links"].append(e)
            plan.append((e["name"], before, old_links[before][1] if before else "", was, g))
        new_groups.append(g)
    if sum(len(g["links"]) for g in new_groups) > 400:
        raise Fail("There are too many links (400 at most).")
    # Colors. A link that stays in its group keeps its color. A new link, or a link moved to another group (unless it has a color of its own), takes the color that
    # the links already in that group share, so it matches the theme. A new group with no such links uses the one color all links share, if there is one.
    stays = {}
    for _name, before, old_group, was, g in plan:
        if before and old_group == was:
            stays.setdefault(id(g), []).append(before)
    everyone = {colors[n] for n in old_links if colors.get(n)}
    fallback = next(iter(everyone)) if len(everyone) == 1 else ""
    fresh = {}
    for name, before, old_group, was, g in plan:
        col = colors.get(before, "") if before else ""
        if before and old_group == was:
            fresh[name] = col
            continue
        if before and col and col != old_dominant.get(old_group, ""):
            fresh[name] = col
            continue
        fresh[name] = common_color(stays.get(id(g), []), colors) or fallback
    for n in old_links:
        colors.pop(n, None)
    for n, c in fresh.items():
        if c:
            colors[n] = c
    if colors != (custom.get("links") or {}):
        if colors:
            custom["links"] = colors
        else:
            custom.pop("links", None)
        tx.put(CSS, css_with_look(tx.get(CSS), custom))
    for n in old_names:
        if n not in kept:
            drop_layout_group(tx, n)
    if renames:
        text = tx.get(SETTINGS)
        gs = layout_groups(text)
        for x in gs:
            x["name"] = renames.get(x["name"], x["name"])
        tx.put(SETTINGS, layout_write(text, gs))
    for n, tab in new_tabs.items():
        ensure_layout_group(tx, n, tab)
    tx.put(BOOKMARKS, marks_write(head, new_groups))


