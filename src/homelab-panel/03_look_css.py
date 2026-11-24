def look_full(custom):
    v = dict(LOOK_DEFAULT)
    v.update({k: x for k, x in custom.items() if k not in ("tabs", "cards", "links", "labels", "names", "logo")})
    tabs = dict(SHIPPED_TAB_COLORS)
    tabs.update(custom.get("tabs") or {})
    v["tabs"] = tabs
    for k in ("cards", "links", "labels", "names", "logo"):
        v[k] = dict(custom.get(k) or {})
    return v


def num(x, places=3):
    return ("%.*f" % (places, x)).rstrip("0").rstrip(".") or "0"


NO_RIM = "0 0 0 0 transparent"


def rim_shadow(level, bevel=0, tone="dark"):
    """The shine on the glass edge (level) and the raised, rounded edge (bevel). On light glass the shade under the edge is a soft blue-gray, not black."""
    r = max(0.0, min(100.0, float(level))) / 100.0
    b = max(0.0, min(100.0, float(bevel))) / 100.0
    parts = []
    if r > 0:
        parts += ["inset 1px 1px 0 rgba(255, 255, 255, %s)" % num(0.7 * r), "inset -1px -1px 0 rgba(255, 255, 255, %s)" % num(0.32 * r),
                  "inset 0 0 %dpx rgba(255, 255, 255, %s)" % (round(10 + 14 * r), num(0.12 * r)), "inset 0 12px 18px -14px rgba(255, 255, 255, %s)" % num(0.30 * r)]
    if b > 0:
        shade = "70, 92, 126" if tone == "light" else "0, 0, 0"
        hi = 0.95 if tone == "light" else 0.4
        lo = 0.2 if tone == "light" else 0.45
        parts += ["inset 2px 2px 2px rgba(255, 255, 255, %s)" % num(hi * b), "inset -2px -3px 4px rgba(%s, %s)" % (shade, num(lo * b)),
                  "inset 0 0 14px rgba(255, 255, 255, %s)" % num((0.18 if tone == "light" else 0.08) * b),
                  "0 8px 18px -8px rgba(%s, %s)" % (shade, num(0.38 * b))]
    return ", ".join(parts) if parts else NO_RIM


TONE_TOKENS = {"dark": {"--lk-ink": "255, 255, 255", "--lk-hi": "#fff", "--lk-shadow": "0, 0, 0", "--lk-deepbase": "#070a12", "--lk-popbase": "#0b101c",
                        "--lk-popmuted": "#bcc6d6", "--lk-spotk": "1", "--lk-platek": "1", "color-scheme": "dark"},
               "light": {"--lk-ink": "22, 38, 64", "--lk-hi": "#0f1a2e", "--lk-shadow": "52, 74, 112", "--lk-deepbase": "#eaf1fb", "--lk-popbase": "#f4f8ff",
                         "--lk-popmuted": "#52627c", "--lk-spotk": "2.6", "--lk-platek": "3.4", "color-scheme": "light"}}


def glass_alpha(v):
    if not v["glassTint"]:
        return 0.0
    if v["glassClear"]:
        return 0.4 * (1 - v["glassLevel"] / 100.0)
    return v["glassOpacity"] / 100.0


def shipped_accent(css, key):
    before, _block, after = css_look_split(css)
    for text in (before, after):
        for m in re.finditer(r"(?m)^([^{}\n/]*)\{\s*--accent:\s*(\d+,\s*\d+,\s*\d+)\s*;?\s*\}", text):
            if "#" + key in [x.strip() for x in m.group(1).split(",")]:
                return m.group(2)
    return None


def shipped_group_accent(css, slug):
    before, _block, after = css_look_split(css)
    for text in (before, after):
        for m in re.finditer(r'\[data-group="%s"\]\s*\{\s*--accent:\s*(\d+,\s*\d+,\s*\d+)\s*;?\s*\}' % re.escape(slug), text):
            return m.group(1)
    return None


def rgb_to_hex(txt):
    r, g, b = [int(x) for x in txt.split(",")]
    return rgb_hex((r, g, b))


WRAP = "html body #inner_wrapper"


def paint_vars(rgbs, t, style):
    k = t ** 0.8
    if style == "solid":
        a1 = a2 = num(0.72 * k)
    else:
        a1, a2 = num(0.9 * k), num(0.22 * k)
    return "--accent:%s;--hl-a1:%s;--hl-a2:%s;" % (rgbs, a1, a2)


RESET_VARS = "--hl-a1:initial;--hl-a2:initial;"


def paint_decl(rgbs, t):
    return ("border-color:rgba(%s,%s)!important;"
            "box-shadow:0 0 0 1px rgba(%s,%s),0 0 18px -8px rgba(%s,%s),0 14px 30px -20px rgba(var(--lk-shadow,0,0,0),.75),var(--lk-rim,0 0 0 0 transparent),0 0 var(--lk-glowr,0px) rgba(var(--accent,var(--lk-accent)),var(--lk-glowa,0))!important;" % (
                rgbs, num(0.16 + 0.34 * t), rgbs, num(0.05 + 0.14 * t), rgbs, num(0.05 + 0.3 * t)))


PLAIN_DECL = "border-color:var(--lk-line)!important;box-shadow:0 14px 30px -20px rgba(var(--lk-shadow,0,0,0),.75),var(--lk-rim,0 0 0 0 transparent),0 0 var(--lk-glowr,0px) rgba(var(--accent,var(--lk-accent)),var(--lk-glowa,0))!important;"


def paint_rules(v, saved, css):
    """Build the rules for the colors of cards, tiles and bookmarks. With `saved` (the look on the page now), things that were painted and no longer are get rules that put them back."""
    t = v["paintStrength"] / 100.0
    st = v["paintStyle"]
    rules = []
    allc = "%d, %d, %d" % hex_rgb(v["paintAll"]) if v.get("paintAll") else None
    cards_all = WRAP + " .service" + "".join(':not([id="%s"])' % x for x in NO_PAINT)
    glob_was = saved is not None and (look_full(saved)["paintStrength"] != LOOK_DEFAULT["paintStrength"] or look_full(saved)["paintStyle"] != "gradient")
    if v["paintStrength"] != LOOK_DEFAULT["paintStrength"] or st != "gradient":
        al = paint_vars("0", t, st).split(";", 1)[1]
        rules.append("%s{%s}%s .bookmark>a{%s}" % (cards_all, al, WRAP, al))
    elif glob_was:
        rules.append("%s{%s}%s .bookmark>a{%s}" % (cards_all, RESET_VARS, WRAP, RESET_VARS))

    def card(cid, c):
        return "%s #%s{%s}%s #%s .service-card{%s}" % (WRAP, cid, paint_vars(c, t, st), WRAP, cid, paint_decl(c, t))

    def mark(sl, c):
        return '%s .bookmark>a[data-bm="%s"]{%s%s}' % (WRAP, sl, paint_vars(c, t, st), paint_decl(c, t))
    if allc:
        rules.append("%s{%s}%s .service-card{%s}" % (cards_all, paint_vars(allc, t, st), cards_all, paint_decl(allc, t)))
        rules.append("%s .bookmark>a{%s%s}" % (WRAP, paint_vars(allc, t, st), paint_decl(allc, t)))
    for cid in sorted(v["cards"]):
        rules.append(card(cid, "%d, %d, %d" % hex_rgb(v["cards"][cid])))
    for name in sorted(v["links"]):
        rules.append(mark(slugify(name), "%d, %d, %d" % hex_rgb(v["links"][name])))
    if saved is not None:
        was = look_full(saved)
        for cid in sorted(set(was["cards"]) - set(v["cards"])):
            if allc:
                rules.append(card(cid, allc))
            else:
                acc = shipped_accent(css, cid) or ("148, 163, 184" if cid.startswith(("stat-", "cal-")) else "var(--lk-accent)")
                rules.append("%s #%s{--accent:%s;%s}%s #%s .service-card{%s}" % (WRAP, cid, acc, RESET_VARS, WRAP, cid, PLAIN_DECL))
        have = {slugify(n) for n in v["links"]}
        for name in sorted(was["links"]):
            if slugify(name) not in have:
                if allc:
                    rules.append(mark(slugify(name), allc))
                else:
                    rules.append('%s .bookmark>a[data-bm="%s"]{--accent:inherit;%s%s}' % (WRAP, slugify(name), RESET_VARS, PLAIN_DECL))
        if was.get("paintAll") and not allc:
            rules.append("%s{%s}%s .service-card{%s}" % (cards_all, RESET_VARS, cards_all, PLAIN_DECL))
            rules.append("%s .bookmark>a{--accent:inherit;%s%s}" % (WRAP, RESET_VARS, PLAIN_DECL))
    return rules


def label_rules(v, saved):
    rules = []
    for name in sorted(v["labels"]):
        sl = slugify(name)
        d = v["labels"][name]
        sel = '%s [data-group="%s"]' % (WRAP, sl)
        if d.get("text"):
            rules.append("%s .service-group-name,%s .bookmark-group-name{color:%s!important}" % (sel, sel, d["text"]))
        if d.get("icon"):
            rules.append("%s{--icon-color:%s;--hl-label:%d, %d, %d}" % ((sel, d["icon"]) + hex_rgb(d["icon"])))
    if saved is not None:
        for name in sorted(look_full(saved)["labels"]):
            now = v["labels"].get(name, {})
            sel = '%s [data-group="%s"]' % (WRAP, slugify(name))
            was = look_full(saved)["labels"][name]
            if was.get("text") and not now.get("text"):
                rules.append("%s .service-group-name,%s .bookmark-group-name{color:var(--lk-text)!important}" % (sel, sel))
            if was.get("icon") and not now.get("icon"):
                rules.append("%s{--icon-color:#c9d6f2;--hl-label:var(--lk-accent)}" % sel)
    style = v["labelIcon"]
    icons = ".service-group-icon,%s .bookmark-group-icon" % WRAP
    ring = "rgba(var(--hl-label,var(--lk-accent)),"
    if style == "circle":
        rules.append("%s %s{box-sizing:content-box;padding:6px;border-radius:50%%;background:%s.20)}" % (WRAP, icons, ring))
    elif style == "square":
        rules.append("%s %s{box-sizing:content-box;padding:6px;border-radius:10px;background:%s.20)}" % (WRAP, icons, ring))
    elif style == "ring":
        rules.append("%s %s{box-sizing:content-box;padding:5px;border-radius:50%%;border:1.5px solid %s.75);box-shadow:0 0 12px %s.45)}" % (WRAP, icons, ring, ring))
    elif saved is not None and look_full(saved)["labelIcon"] != "plain":
        rules.append("%s %s{padding:0;border-radius:0;background:none;border:0;box-shadow:none}" % (WRAP, icons))
    return rules


def light_rules():
    """Extra rules for a light look: dark text on the widgets, a lighter picture and no dark veil over it."""
    return [WRAP + " #information-widgets *:not(svg):not(svg *){color:var(--lk-text)!important}",
            "html body #inner_wrapper .service-block-value{color:var(--lk-text)}",
            "html body #background{filter:blur(3px) saturate(1.05)}",
            "html body #background::after{background:none!important}"]


def look_css(custom, full=False, saved=None, css=""):
    """Build the rules of the look block for a look (only what differs from the default). `full` writes every value, for a preview in front of a saved look."""
    if not custom and not full and saved is None:
        return ""
    v = look_full(custom)
    rules = []
    tok = []
    if full or "accent" in custom:
        tok.append("--lk-accent: %d, %d, %d;" % hex_rgb(v["accent"]))
    if full or "glass" in custom:
        tok.append("--lk-glass: %d, %d, %d;" % hex_rgb(v["glass"]))
    if full or "glassOpacity" in custom or "glassClear" in custom or "glassLevel" in custom or "glassTint" in custom:
        tok.append("--lk-glass-a: %s;" % num(glass_alpha(v)))
    if full or "glassTint" in custom:
        tok.append("--lk-tshadow: %s;" % ("none" if v["glassTint"] else "0 1px 2px rgba(0, 0, 0, 0.6), 0 0 8px rgba(0, 0, 0, 0.3)"))
    if full or "radius" in custom:
        tok.append("--lk-radius: %dpx;" % v["radius"])
    if full or "edge" in custom:
        tok.append("--lk-line: rgba(255, 255, 255, %s);" % num(v["edge"] / 100.0))
    if full or "side" in custom:
        tok.append("--lk-side: %dpx;" % v["side"])
    if full or "glassBlur" in custom:
        tok.append("--lk-blur: %spx;" % num(v["glassBlur"]))
    if full or "glassSat" in custom:
        tok.append("--lk-sat: %s%%;" % num(v["glassSat"]))
    if full or "cardDepth" in custom:
        tok.append("--lk-deep: %s%%;" % num(round(v["cardDepth"] * 0.85, 1)))
    if full or "glassRim" in custom or "glassBevel" in custom or "tone" in custom:
        tok.append("--lk-rim: %s;" % rim_shadow(v["glassRim"], v["glassBevel"], v["tone"]))
    if full or "tone" in custom:
        tok += ["%s: %s;" % kv for kv in TONE_TOKENS[v["tone"]].items()]
    if full or "glow" in custom:
        g = v["glow"] / 100.0
        tok.append("--lk-glowr: %dpx; --lk-glowa: %s;" % (round(6 + 22 * g) if g else 0, num(0.6 * g)))
    if full or "font" in custom:
        tok.append("--lk-font: %s;" % FONTS[v["font"]])
    if full or "text" in custom:
        tok.append("--lk-text: %s;" % v["text"])
    if full or "muted" in custom:
        tok.append("--lk-muted: %s;" % v["muted"])
    if full or "playerHeight" in custom:
        tok.append("--lk-player-h: %dpx;" % v["playerHeight"])
    if not full:
        for k, val in sorted((custom.get("names") or {}).items()):
            tok.append('--hl-name-%s: "%s";' % (k, val))
        if custom.get("hello") is False:
            tok.append('--hl-hello: "off";')
        elif custom.get("helloName") or hello_default():
            tok.append('--hl-hello: "%s";' % (custom.get("helloName") or hello_default()))
        if custom.get("dockMode") == "off":
            tok.append('--hl-dock: "off";')
        elif custom.get("dockMode") == "custom":
            tok.append('--hl-dock: "%s";' % ",".join(custom.get("dock") or []) if custom.get("dock") else '--hl-dock: "none";')
        lg = custom.get("logo") or {}
        if lg.get("src") and not lg.get("off"):
            tok.append('--hl-logo-src: "%s";' % lg["src"])
            if lg.get("link"):
                tok.append('--hl-logo-link: "%s";' % lg["link"])
            tok.append("--hl-logo-size: %spx;" % num(lg.get("size", 48)))
    if tok:
        rules.append("html body #inner_wrapper { %s }" % " ".join(tok))
    body_tok = []
    if full or "veil" in custom:
        body_tok.append("--lk-veilk: %s;" % num(v["veil"] / 100.0))
    if full or "motion" in custom:
        body_tok.append(MOTIONS[v["motion"]])
    if full or "iconStyle" in custom:
        body_tok.append("--lk-plate: %d;" % (1 if v["iconStyle"] == "plate" else 0))
    if full or "accent" in custom or "tabs" in custom:
        body_tok.append("--lk-aur-1: %d, %d, %d; --lk-aur-2: %d, %d, %d; --lk-aur-3: %d, %d, %d;" % (
            hex_rgb(v["accent"]) + hex_rgb(v["tabs"].get("Links", SHIPPED_TAB_COLORS["Links"])) + hex_rgb(v["tabs"].get("Stats", SHIPPED_TAB_COLORS["Stats"]))))
    if full or "tone" in custom:
        body_tok.append("--lk-aur-blend: %s;" % ("soft-light" if v["tone"] == "light" else "screen"))
    if body_tok:
        rules.append("html body { %s }" % " ".join(body_tok))
    tabs = v["tabs"] if full else (custom.get("tabs") or {})
    for name in sorted(tabs):
        rules.append('html[data-tab="%s"] body #inner_wrapper { --lk-accent: %d, %d, %d; }' % ((name,) + hex_rgb(tabs[name])))
    if full or "playerHeight" in custom:
        ph = max(240, v["playerHeight"] - 40)
        rules.append("@media (max-width: 700px) { html body #inner_wrapper { --lk-player-h: %dpx; } }" % ph)
    if v["tone"] == "light":
        rules += light_rules()
    rules += paint_rules(v, saved, css) + label_rules(v, saved)
    return "\n".join(rules)


def look_block(custom):
    if not custom:
        return ""
    data = json.dumps(custom, sort_keys=True, separators=(",", ":")).replace("*/", "*\\/")
    return "%s written by the control panel. Remove it with the Reset button there (or delete this block). */\n/* data: %s */\n%s\n%s\n" % (
        LOOK_B1, data, look_css(custom), LOOK_B2)


def css_look_split(text):
    a = text.find(LOOK_B1)
    if a < 0:
        return text, "", ""
    b = text.find(LOOK_B2, a)
    if b < 0:
        return text, "", ""
    end = b + len(LOOK_B2)
    if text[end:end + 1] == "\n":
        end += 1
    return text[:a], text[a:end], text[end:]


def look_get(css=None):
    css = read(CSS) if css is None else css
    block = css_look_split(css)[1]
    m = re.search(r"/\* data: (.*?) \*/", block)
    if not m:
        return {}
    try:
        data = json.loads(m.group(1).replace("*\\/", "*/"))
        return look_clean(data)
    except (ValueError, Fail):
        return {}


def css_with_look(css, custom):
    before, block, after = css_look_split(css)
    new = look_block(custom)
    if block:
        return before + new + after
    if not new:
        return css
    t = css.find(THEME_B1)
    if t >= 0:
        return css[:t].rstrip("\n") + "\n\n" + new + "\n" + css[t:]
    return css.rstrip("\n") + "\n\n" + new


def picture_block(settings_text):
    d = bg_get(settings_text)
    decl = []
    if d.get("blur") in BLUR_PX:
        decl.append("--tw-backdrop-blur: blur(%dpx);" % BLUR_PX[d["blur"]])
    for key, name in (("brightness", "brightness"), ("saturate", "saturate")):
        try:
            n = float(d.get(key))
        except (TypeError, ValueError):
            continue
        if 0 <= n <= 300:
            decl.append("--tw-backdrop-%s: %s(%s);" % (name, name, num(n / 100.0)))
    if not decl:
        return ""
    return "%s written by the control panel from the picture sliders. It is rewritten when they change. */\nhtml body #inner_wrapper { %s }\n%s\n" % (BG_B1, " ".join(decl), BG_B2)


def css_with_picture(css, settings_text):
    a = css.find(BG_B1)
    b = css.find(BG_B2, a) if a >= 0 else -1
    new = picture_block(settings_text)
    if a >= 0 and b >= 0:
        end = b + len(BG_B2)
        if css[end:end + 1] == "\n":
            end += 1
        return css[:a] + new + css[end:]
    if not new:
        return css
    return css.rstrip("\n") + "\n\n" + new


