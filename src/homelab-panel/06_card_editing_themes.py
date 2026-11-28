def new_card_lines(name, href, icon, description, monitor):
    block = ["    - %s:" % yq(name)]
    if href:
        block.append("        href: %s" % yq(href))
    if monitor:
        block.append("        siteMonitor: %s" % yq(monitor))
    if icon:
        block.append("        icon: %s" % yq(icon))
    if description:
        block.append("        description: %s" % yq(description))
    return block


def tidy_blank(lines, at):
    while 0 < at < len(lines) and not lines[at].strip() and not lines[at - 1].strip():
        del lines[at]


def card_insert(lines, group, block, before=None):
    """Put a card block into a group, before the card named `before` or else at the end. A group that does not exist is created."""
    for g in services_parse(lines):
        if g["name"] == group:
            if before is not None:
                tgt = next((c for c in g["cards"] if c["name"] == before), None)
                at = tgt["start"] if tgt else None
            else:
                at = None
            if at is None:
                at = g["cards"][-1]["end"] if g["cards"] else g["start"] + 1
                ins = ([""] if lines[at - 1].strip() else []) + block + ([""] if at < len(lines) and lines[at].strip() else [])
            else:
                ins = block + [""]
            if before is None and not g["cards"]:
                ins = [""] + block + [""]
            lines[at:at] = ins
            return
    while lines and not lines[-1].strip():
        lines.pop()
    lines.extend(([""] if lines else []) + ["- %s:" % yq(group), ""] + block + [""])


def check_group_name(name):
    name = clean_text(name, "The group name", 40)
    if not re.fullmatch(r"[^\"'\\{};<>/*:#\[\]|`]+", name):
        raise Fail("The group name '%s' has characters that are not allowed." % name)
    return name


def card_values(body, managed_card=False):
    v = {"name": clean_text(body.get("name"), "The name", 60)}
    if not re.fullmatch(r"[^\"'\\{};<>/*:#\[\]|`]+", v["name"]):
        raise Fail("The name '%s' has characters that are not allowed (use letters, digits, spaces and - _ . , ( ) + )." % v["name"])
    v["description"] = clean_text(body.get("description", ""), "The description", 160, True)
    v["icon"] = clean_icon(body.get("icon", ""))
    if not managed_card:
        v["href"] = clean_url(body.get("href", ""), "The address")
        v["siteMonitor"] = v["href"] if body.get("dot") and v["href"] else ""
    return v


def ensure_layout_group(tx, group, tab=None, props=None):
    text = tx.get(SETTINGS)
    gs = layout_groups(text)
    if any(g["name"] == group for g in gs) or not gs:
        return
    t = tab or layout_tabs(gs)[0]["name"]
    gs.append({"name": group, "props": dict(props or {}, tab=t), "extra": []})
    tx.put(SETTINGS, layout_write(text, gs))


def hl_adopt(lines):
    done = False
    for b, _e in HL_BLOCKS:
        for i, l in enumerate(lines):
            if l.startswith(b) and not l[len(b):].strip():
                lines[i] = b + " customized"
                done = True
    return done


def hl_lan(live_text):
    m = re.search(r"http://([A-Za-z0-9._-]+):3001/images/", live_text or "")
    return m.group(1) if m else ""


def hl_catalog():
    """Return the cards HomeLab can fill in, from the files the installer keeps next to the panel: [{id, name, group, icon, description, extra, lines}]."""
    out, seen = [], set()
    lan = hl_lan(read(SERVICES))
    for path, extra in ((SHIPPED, False), (SHIPPED_EXTRAS, True)):
        text = read(path)
        if not text:
            continue
        if lan:
            text = text.replace("192.168.X.X", lan)
        lines = text.split("\n")
        for g in services_parse(lines):
            if g["name"] not in HL_GROUP_LOOK:
                continue
            for c in g["cards"]:
                f = card_fields(lines, c)
                if not HL_ID.match(f.get("id", "")) or f["id"] in seen:
                    continue
                seen.add(f["id"])
                out.append({"id": f["id"], "name": c["name"], "group": g["name"], "icon": f.get("icon", ""), "description": f.get("description", ""),
                            "extra": extra, "lines": lines[c["start"]:c["end"]]})
    return out


def hl_state():
    lines = read(SERVICES).split("\n")
    where = {}
    for g in services_parse(lines):
        for c in g["cards"]:
            i = card_fields(lines, c).get("id", "")
            if i:
                where[i] = g["name"]
    return [{"id": c["id"], "name": c["name"], "group": c["group"], "icon": c["icon"], "description": c["description"], "extra": c["extra"],
             "in": where.get(c["id"], "")} for c in hl_catalog()]


def hl_place(tx, lines, card, group, tab=None):
    if any(c["name"] == card["name"] for g in services_parse(lines) if g["name"] == group for c in g["cards"]):
        raise Fail("The group '%s' already has a card called '%s'. Change that card's name first." % (group, card["name"]))
    card_insert(lines, group, list(card["lines"]))
    look = HL_GROUP_LOOK.get(group)
    text = tx.get(SETTINGS)
    names = [t["name"] for t in layout_tabs(layout_groups(text))] if layout_groups(text) else []
    want = tab if tab in names else (look[2] if look and look[2] in names else None)
    ensure_layout_group(tx, group, want, {"icon": look[0], "columns": str(look[1])} if look else None)


def api_hl_restore(body):
    """Put back every card HomeLab ships that was changed, moved or hidden, each in its own group. Cards the user added stay."""
    cat = [c for c in hl_catalog() if not c["extra"]]
    if not cat:
        raise Fail("The list of HomeLab's cards is not on this machine yet. Run:  sudo homelab-setup upgrade")
    tx = Tx("HomeLab cards restored")
    lines = tx.get(SERVICES).split("\n")
    hl_adopt(lines)
    ids = {c["id"] for c in cat}
    while True:
        hit = None
        for g in services_parse(lines):
            for c in g["cards"]:
                if card_fields(lines, c).get("id") in ids:
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
    for card in cat:
        hl_place(tx, lines, card, card["group"])
    tx.put(SERVICES, "\n".join(lines))
    tx.commit()
    return {}


def drop_layout_group(tx, group):
    text = tx.get(SETTINGS)
    gs = layout_groups(text)
    left = [g for g in gs if g["name"] != group]
    if len(left) != len(gs):
        tx.put(SETTINGS, layout_write(text, left))


def card_move(tx, lines, group, name, to, tab=None, before=None, keep_empty=False):
    """Move a card to another group, or to another place in its own group, as part of the change that `tx` is collecting. A group left without cards is removed unless keep_empty is set."""
    g, c = find_card(lines, group, name)
    mv = card_public(lines, c, g["name"])
    if mv["locked"]:
        raise Fail("This card is part of the panel itself and cannot be moved here.")
    to = check_group_name(to or g["name"])
    if to in PROTECTED:
        raise Fail("The group '%s' is part of the panel itself. Choose another group." % to)
    if mv["hl"] or g["name"] in AUTOMATIC or to in AUTOMATIC:
        hl_adopt(lines)
    block = lines[c["start"]:c["end"]]
    del lines[c["start"]:c["end"]]
    tidy_blank(lines, c["start"])
    card_insert(lines, to, block, before=before)
    left = next((x for x in services_parse(lines) if x["name"] == g["name"]), None)
    if left is not None and not left["cards"] and not keep_empty:
        del lines[left["start"]:left["end"]]
        drop_layout_group(tx, g["name"])
    tx.put(SERVICES, "\n".join(lines))
    ensure_layout_group(tx, to, tab)


def api_arrange(body):
    """Apply an arrangement made on the dashboard itself: the order of the groups on one tab and the cards in each group. It is one change, so Undo takes it back in one step."""
    tab = clean_text(body.get("tab"), "The tab name", 24)
    want = body.get("groups")
    if not isinstance(want, list) or not want or len(want) > 60:
        raise Fail("The arrangement is missing.")
    tx = Tx("Dashboard arranged")
    lines = tx.get(SERVICES).split("\n")
    have = {g["name"]: [c["name"] for c in g["cards"]] for g in services_parse(lines)}
    names, asked = [], []
    for g in want:
        cards = g.get("cards") if isinstance(g, dict) else None
        n = g.get("name") if isinstance(g, dict) else None
        if n not in have or n in names or not isinstance(cards, list):
            raise Fail("The group '%s' is not known (or is listed twice). Reload the dashboard and try again." % n)
        if n in PROTECTED:
            raise Fail("The group '%s' is part of the panel itself and cannot be arranged here." % n)
        names.append(n)
        asked.extend(c if isinstance(c, str) else None for c in cards)
    if len(set(asked)) != len(asked) or sorted(map(str, asked)) != sorted(c for n in names for c in have[n]):
        raise Fail("The cards changed while you were arranging. Reload the dashboard and try again.")
    for g in want:
        cards = g["cards"]
        for i in range(len(cards) - 1, -1, -1):
            nxt = cards[i + 1] if i + 1 < len(cards) else None
            now = {x["name"]: [c["name"] for c in x["cards"]] for x in services_parse(lines)}
            where = next(x for x in now if cards[i] in now[x])
            cur = now[g["name"]] if g["name"] in now else []
            at = cur.index(cards[i]) if where == g["name"] else -1
            if at >= 0 and (cur[at + 1] == nxt if at + 1 < len(cur) else nxt is None):
                continue
            card_move(tx, lines, where, cards[i], g["name"], tab, nxt, keep_empty=True)
    for x in reversed(services_parse(lines)):
        if x["name"] in names and not x["cards"]:
            del lines[x["start"]:x["end"]]
            drop_layout_group(tx, x["name"])
    tx.put(SERVICES, "\n".join(lines))
    text = tx.get(SETTINGS)
    cur = layout_groups(text)
    slots = [i for i, g in enumerate(cur) if (g["props"].get("tab") or "Home") == tab]
    here = [cur[i]["name"] for i in slots]
    order = [n for n in names if n in here] + [n for n in here if n not in names]
    if order != here:
        by = {g["name"]: g for g in cur}
        out = list(cur)
        for i, n in zip(slots, order):
            out[i] = by[n]
        tx.put(SETTINGS, layout_write(text, out))
    tx.commit()
    return {}


def api_card(body):
    """Add, edit, remove or move cards in services.yaml."""
    op = body.get("op")
    tx = Tx({"add": "Card added", "add-list": "Cards added", "edit": "Card changed", "remove": "Card removed", "move": "Card moved"}.get(op, "Cards changed"))
    lines = tx.get(SERVICES).split("\n")
    if op == "add-list":
        want = body.get("ids")
        if not isinstance(want, list) or not want or len(want) > 40:
            raise Fail("Choose at least one card from the list.")
        cat = {c["id"]: c for c in hl_catalog()}
        here = {card_fields(lines, c).get("id") for g in services_parse(lines) for c in g["cards"]}
        hl_adopt(lines)
        for i in want:
            card = cat.get(i)
            if card is None:
                raise Fail("That card is not on the list. Reload the panel and try again.")
            if i in here:
                raise Fail("The card '%s' is already on the dashboard." % card["name"])
            group = check_group_name(body.get("group")) if body.get("group") else card["group"]
            if group in PROTECTED:
                raise Fail("Choose another group.")
            hl_place(tx, lines, card, group, body.get("tab"))
        tx.put(SERVICES, "\n".join(lines))
    elif op == "add":
        group = check_group_name(body.get("group"))
        if group in PROTECTED:
            raise Fail("The group '%s' is part of the panel itself. Put the card in another group." % group)
        if group in AUTOMATIC:
            hl_adopt(lines)
        v = card_values(body)
        if any(c["name"] == v["name"] for g in services_parse(lines) for c in g["cards"]):
            raise Fail("There is already a card called '%s'. Choose another name." % v["name"])
        card_insert(lines, group, new_card_lines(v["name"], v["href"], v["icon"], v["description"], v["siteMonitor"]))
        tx.put(SERVICES, "\n".join(lines))
        ensure_layout_group(tx, group, body.get("tab"))
    elif op == "edit":
        g, c = find_card(lines, body.get("group"), body.get("old"))
        pub = card_public(lines, c, g["name"])
        if pub["locked"]:
            raise Fail("This card is part of the panel itself and cannot be changed here.")
        if pub["hl"] or g["name"] in AUTOMATIC:
            hl_adopt(lines)
        v = card_values(body, pub["managed"])
        if v["name"] != c["name"] and any(x["name"] == v["name"] for gg in services_parse(lines) for x in gg["cards"]):
            raise Fail("There is already a card called '%s'." % v["name"])
        lines[c["start"]] = "    - %s:" % yq(v["name"])
        set_line(lines, c, "icon", v["icon"])
        set_line(lines, c, "description", v["description"])
        if not pub["managed"]:
            set_line(lines, c, "href", v["href"])
            set_line(lines, c, "siteMonitor", v["siteMonitor"])
        set_widget_secrets(lines, c, body.get("secrets"))
        tx.put(SERVICES, "\n".join(lines))
    elif op == "remove":
        g, c = find_card(lines, body.get("group"), body.get("name"))
        pub = card_public(lines, c, g["name"])
        if pub["locked"]:
            raise Fail("This card is part of the panel itself and cannot be removed here.")
        if pub["fixed"]:
            raise Fail("The Navidrome card is part of HomeLab and cannot be removed. You can move it to another group.")
        if pub["hl"] or g["name"] in AUTOMATIC:
            hl_adopt(lines)
        del lines[c["start"]:c["end"]]
        tidy_blank(lines, c["start"])
        left = next((x for x in services_parse(lines) if x["name"] == g["name"]), None)
        if left is not None and not left["cards"]:
            del lines[left["start"]:left["end"]]
            tx.put(SERVICES, "\n".join(lines))
            drop_layout_group(tx, g["name"])
        else:
            tx.put(SERVICES, "\n".join(lines))
    elif op == "move":
        card_move(tx, lines, body.get("group"), body.get("name"), body.get("to"), body.get("tab"), body.get("before"))
    else:
        raise Fail("Unknown action.")
    tx.commit()
    return {}


MYTHEMES = os.path.join(HP, ".panel-themes.json")
MYTHEME_ID = re.compile(r"^my-[a-z0-9]{4,24}$")
MAX_MYTHEMES = 24
MYTHEME_PARTS = ("look", "background", "layout", "cards")


def mythemes_load():
    try:
        data = json.loads(read(MYTHEMES) or "{}")
        lst = data.get("themes") if isinstance(data, dict) else None
        return [t for t in lst if isinstance(t, dict) and MYTHEME_ID.match(str(t.get("id", "")))] if isinstance(lst, list) else []
    except ValueError:
        return []


def mythemes_save(lst):
    body = read(MYTHEMES)
    if body.strip():
        try:
            json.loads(body)
        except ValueError:
            # The saved themes file is damaged: keep it before it is replaced.
            keep = "%s.damaged-%s" % (MYTHEMES, time.strftime("%Y%m%d-%H%M%S"))
            if not any(read(o) == body for o in glob.glob(MYTHEMES + ".damaged-*")):
                write_atomic(keep, body, 0o600)
    write_atomic(MYTHEMES, json.dumps({"version": 1, "themes": lst}, indent=1, sort_keys=True), 0o644)


def mythemes_state():
    out = []
    for t in mythemes_load():
        parts = [p for p in MYTHEME_PARTS if p in t]
        look = t.get("look") or {}
        out.append({"id": t["id"], "name": t.get("name", ""), "blurb": t.get("blurb", ""), "mine": True, "parts": parts, "look": look, "background": t.get("background"),
                    "ui": t.get("ui") or {}, "paintAll": look.get("paintAll", ""), "palette": [],
                    "counts": {"tabs": len(t.get("layout") or []), "cards": sum(len(g.get("cards", [])) for g in (t.get("cards") or {}).get("groups", []))}})
    return out


def layout_snapshot():
    out = []
    for t in layout_tabs(layout_groups(read(SETTINGS))):
        out.append({"name": t["name"], "groups": [{"name": g["name"], "icon": g["props"].get("icon", ""), "style": g["props"].get("style", ""),
                                                   "columns": str(g["props"].get("columns", ""))} for g in t["groups"]]})
    return out


def cards_snapshot():
    lines = read(SERVICES).split("\n")
    groups = []
    for g in services_parse(lines):
        if g["name"] in PROTECTED:
            continue
        cards = []
        for c in g["cards"]:
            pub = card_public(lines, c, g["name"])
            if pub["locked"]:
                continue
            kind = "hl" if pub["hl"] else ("managed" if pub["managed"] else "own")
            item = {"key": pub["id"] or c["name"], "id": pub["id"], "name": c["name"], "icon": pub["icon"], "description": pub["description"], "kind": kind}
            if kind == "own":
                item["href"], item["siteMonitor"] = pub["href"], pub["siteMonitor"]
            cards.append(item)
        if cards:
            groups.append({"group": g["name"], "cards": cards})
    return {"groups": groups}


def mytheme_background(raw, tid):
    """Check the picture settings of a theme. A picture on this machine is copied to a file of the theme's own, so replacing the background later does not change it."""
    if not isinstance(raw, dict):
        raise Fail("The picture settings are missing.")
    out = {}
    img = raw.get("image") or ""
    if img.startswith("/images/"):
        name = img[len("/images/"):]
        src = os.path.join(IMAGES, name)
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", name) or not os.path.isfile(src):
            raise Fail("The background picture cannot be found. Choose it again on the Look screen.")
        ext = os.path.splitext(name)[1].lower()
        mine = "theme-%s%s" % (tid, ext)
        if name != mine:
            shutil.copyfile(src, os.path.join(IMAGES, mine))
            os.chmod(os.path.join(IMAGES, mine), 0o644)
        img = "/images/" + mine
    elif img:
        img = clean_url(img, "The picture address")
    out["image"] = img
    b = raw.get("blur")
    if b in (None, "", "none"):
        out["blur"] = "none"
    elif b in BLURS:
        out["blur"] = b
    else:
        raise Fail("The blur must be none or one of: %s." % ", ".join(BLURS))
    for k in ("saturate", "brightness", "opacity"):
        out[k] = number(raw.get(k, BG_DEFAULT[k]), k.capitalize(), 0, 100)
    return out


