def indent(line):
    return len(line) - len(line.lstrip(" "))


def clean_text(s, what, maxlen=200, allow_empty=False):
    s = (s or "").strip() if isinstance(s, str) else ""
    if not s and not allow_empty:
        raise Fail("%s cannot be empty." % what)
    if len(s) > maxlen or re.search(r"[\x00-\x1f\x7f]", s):
        raise Fail("%s is too long or has characters that are not allowed." % what)
    return s


def clean_url(s, what, allow_empty=True):
    s = (s or "").strip() if isinstance(s, str) else ""
    if not s:
        if allow_empty:
            return ""
        raise Fail("%s cannot be empty." % what)
    if not re.match(r"^https?://[^\s\"'<>]+$", s) or len(s) > 600:
        raise Fail("%s must be a web address that starts with http:// or https:// and has no spaces." % what)
    return s


def clean_icon(s):
    s = (s or "").strip() if isinstance(s, str) else ""
    if not s:
        return ""
    if re.match(r"^https?://", s):
        return clean_url(s, "The icon address")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/+-]{0,80}(#[0-9a-fA-F]{3,8})?", s):
        raise Fail("The icon name can only contain letters, digits and the characters - _ . (for example mdi-home, plex.svg or an https:// picture address).")
    return s


def hex_rgb(s, what="color"):
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", (s or "").strip()) if isinstance(s, str) else None
    if not m:
        raise Fail("The %s must be a color like #8ab4ff." % what)
    h = m.group(1)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_hex(rgb):
    return "#%02x%02x%02x" % tuple(rgb)


def number(v, what, lo, hi):
    if isinstance(v, bool):
        raise Fail("%s must be a number from %s to %s." % (what, lo, hi))
    try:
        n = float(v)
    except (TypeError, ValueError):
        raise Fail("%s must be a number from %s to %s." % (what, lo, hi)) from None
    if not lo <= n <= hi:
        raise Fail("%s must be from %s to %s." % (what, lo, hi))
    return int(n) if n == int(n) else n


SHIPPED_TAB_COLORS = {"Stats": "#5ed6a4", "Links": "#bea0ff"}
LOOK_DEFAULT = {"accent": "#8ab4ff", "glass": "#0d121e", "glassOpacity": 56, "glassClear": False, "glassLevel": 70, "radius": 16, "edge": 7.5,
                "side": 70, "glassBlur": 14, "glassSat": 125, "glassRim": 0, "glassBevel": 0, "glow": 0, "veil": 100, "tone": "dark", "font": "default", "motion": "subtle", "iconStyle": "plate", "hello": True, "helloName": "", "dockMode": "auto", "dock": [], "glassTint": True, "cardDepth": 0, "text": "#eef2f9", "muted": "#a9b4c7", "theme": "calm", "playerHeight": 600, "paintStrength": 10, "paintStyle": "gradient", "labelIcon": "plain", "tabs": {}, "paintAll": "", "cards": {}, "links": {}, "labels": {}, "names": {}, "logo": {}}
LABEL_ICONS = ("plain", "circle", "square", "ring")
TONES = ("dark", "light")
MOTIONS = {"off": "--lk-mo: 0; --lk-lift: 0px; --lk-spot: 0; --lk-aur-op: 0; --lk-aur-dur: 0s;",
           "subtle": "--lk-mo: 1; --lk-lift: 2px; --lk-spot: 0.55; --lk-aur-op: 0.4; --lk-aur-dur: 70s;",
           "lively": "--lk-mo: 1.3; --lk-lift: 5px; --lk-spot: 1; --lk-aur-op: 0.7; --lk-aur-dur: 38s;"}
ICON_STYLES = ("plate", "none")
DOCK_MODES = ("auto", "custom", "off")
# What a day or night theme must not overwrite, because it belongs to the person and not to a theme.
PERSONAL_KEYS = ("names", "logo", "labels", "labelIcon", "motion", "iconStyle", "hello", "helloName", "dockMode", "dock")
FONTS = {"default": "inherit",
         "apple": '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif',
         "windows": '"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif',
         "mono": 'ui-monospace, "JetBrains Mono", "Fira Code", "Cascadia Code", Menlo, Consolas, monospace',
         "rounded": 'ui-rounded, "SF Pro Rounded", Nunito, system-ui, sans-serif'}
PAINT_STYLES = ("gradient", "solid")
NO_PAINT = ("customize-card", "linkedit-card", "terminal-card")
# Bump the number when the pictures change, so a picture stored by an older version is fetched again.
THEME_PIC_REV = "-v3"
THEME_PICTURES = "https://raw.githubusercontent.com/IbrandonrtI/My-Home-Lab/main/theme-pictures/"


def theme_bg(name, blur="none", saturate=100, brightness=100, opacity=100):
    """The picture of a theme: one of the files in the theme-pictures folder of the repository."""
    return {"url": THEME_PICTURES + name + ".jpg", "blur": blur, "saturate": saturate, "brightness": brightness, "opacity": opacity}


LOOK_THEMES = [
    {"id": "mocha", "name": "Pastel Night", "blurb": "Soft pastel colors on a warm dark blue. Based on the Catppuccin Mocha colors.",
     "look": {"veil": 70, "glass": "#313244", "glassOpacity": 62, "accent": "#cba6f7", "radius": 16, "edge": 9, "glassBlur": 18, "glassSat": 130, "paintStrength": 22,
              "text": "#cdd6f4", "muted": "#a6adc8", "tabs": {"Stats": "#a6e3a1", "Links": "#f5c2e7"}},
     "palette": ["#cba6f7", "#89b4fa", "#a6e3a1", "#fab387", "#f5c2e7", "#94e2d5", "#f9e2af", "#f38ba8"], "paintLinks": "#f5c2e7",
     "background": theme_bg("mocha"),
     "ui": {"bg": "#11111b", "panel": "#1e1e2e", "panel2": "#313244", "line": "rgba(205,214,244,0.12)", "field": "#181825", "dialog": "#1e1e2e"}},
    {"id": "dracula", "name": "Violet Glow", "blurb": "Purple and pink with a soft glow on dark violet. Based on the Dracula colors.",
     "look": {"veil": 70, "glass": "#282a36", "glassOpacity": 72, "accent": "#bd93f9", "radius": 10, "edge": 10, "glassBlur": 12, "glassSat": 125, "glow": 35, "paintStrength": 24,
              "text": "#f8f8f2", "muted": "#b9bdd6", "tabs": {"Stats": "#50fa7b", "Links": "#ff79c6"}},
     "palette": ["#bd93f9", "#ff79c6", "#8be9fd", "#50fa7b", "#ffb86c", "#f1fa8c"], "paintLinks": "#ff79c6",
     "background": theme_bg("dracula"),
     "ui": {"bg": "#191a21", "panel": "#21222c", "panel2": "#343746", "line": "rgba(189,147,249,0.18)", "field": "#191a21", "dialog": "#21222c"}},
    {"id": "nord", "name": "Arctic Slate", "blurb": "Calm blue-gray with flat, quiet cards. Based on the Nord colors.",
     "look": {"veil": 85, "glass": "#3b4252", "glassOpacity": 82, "accent": "#88c0d0", "radius": 6, "edge": 7, "glassBlur": 6, "glassSat": 100, "paintStrength": 12,
              "text": "#eceff4", "muted": "#a7b2c5", "tabs": {"Stats": "#a3be8c", "Links": "#b48ead"}},
     "palette": ["#88c0d0", "#81a1c1", "#a3be8c", "#ebcb8b", "#b48ead", "#d08770"], "paintLinks": "#81a1c1",
     "background": theme_bg("nord"),
     "ui": {"bg": "#242933", "panel": "#2e3440", "panel2": "#3b4252", "line": "rgba(216,222,233,0.12)", "field": "#272c36", "dialog": "#2e3440"}},
    {"id": "tokyo", "name": "City Lights", "blurb": "Deep navy with blue and violet lights. Based on the Tokyo Night colors.",
     "look": {"veil": 65, "glass": "#1a1b26", "glassOpacity": 68, "accent": "#7aa2f7", "radius": 12, "edge": 9, "glassBlur": 16, "glassSat": 135, "glow": 28, "paintStrength": 24,
              "text": "#c0caf5", "muted": "#9aa5ce", "tabs": {"Stats": "#9ece6a", "Links": "#bb9af7"}},
     "palette": ["#7aa2f7", "#bb9af7", "#7dcfff", "#9ece6a", "#e0af68", "#f7768e", "#ff9e64"], "paintLinks": "#bb9af7",
     "background": theme_bg("tokyo"),
     "ui": {"bg": "#16161e", "panel": "#1a1b26", "panel2": "#24283b", "line": "rgba(122,162,247,0.16)", "field": "#13131a", "dialog": "#1a1b26"}},
    {"id": "gruvbox", "name": "Retro Amber", "blurb": "Warm browns, yellow and orange with solid cards and a monospace font. Based on the Gruvbox colors.",
     "look": {"veil": 80, "glass": "#3c3836", "glassOpacity": 88, "accent": "#fabd2f", "radius": 4, "edge": 12, "glassBlur": 0, "glassSat": 100, "paintStrength": 14, "font": "mono",
              "text": "#ebdbb2", "muted": "#bdae93", "tabs": {"Stats": "#b8bb26", "Links": "#d3869b"}},
     "palette": ["#fabd2f", "#fe8019", "#b8bb26", "#83a598", "#d3869b", "#8ec07c", "#fb4934"], "paintLinks": "#83a598",
     "background": theme_bg("gruvbox"),
     "ui": {"bg": "#1d2021", "panel": "#282828", "panel2": "#3c3836", "line": "rgba(235,219,178,0.14)", "field": "#1d2021", "dialog": "#282828"}},
    {"id": "solarized", "name": "Deep Teal", "blurb": "Dark teal with soft yellow and blue accents and flat cards. Based on the Solarized Dark colors.",
     "look": {"veil": 80, "glass": "#073642", "glassOpacity": 88, "accent": "#268bd2", "radius": 6, "edge": 10, "glassBlur": 0, "glassSat": 100, "paintStrength": 14,
              "text": "#eee8d5", "muted": "#93a1a1", "tabs": {"Stats": "#859900", "Links": "#6c71c4"}},
     "palette": ["#268bd2", "#2aa198", "#859900", "#b58900", "#cb4b16", "#d33682", "#6c71c4"], "paintLinks": "#2aa198",
     "background": theme_bg("solarized"),
     "ui": {"bg": "#00212b", "panel": "#002b36", "panel2": "#073642", "line": "rgba(147,161,161,0.18)", "field": "#001f27", "dialog": "#002b36"}},
    {"id": "macos", "name": "Frosted Wave", "blurb": "Dark frosted glass over a colorful wave picture, with an Apple-style font.",
     "look": {"veil": 25, "glass": "#1e1e24", "glassOpacity": 46, "accent": "#0a84ff", "radius": 14, "edge": 16, "glassBlur": 40, "glassSat": 180, "glassRim": 22, "paintStrength": 16, "font": "apple",
              "text": "#ffffff", "muted": "#cfcfd8", "tabs": {"Stats": "#30d158", "Links": "#bf5af2"}},
     "palette": ["#0a84ff", "#bf5af2", "#30d158", "#ff9f0a", "#ff375f", "#64d2ff", "#ffd60a"], "paintLinks": "#64d2ff",
     "background": theme_bg("macos"),
     "ui": {"bg": "linear-gradient(135deg,#1b1747,#3a1c63 55%,#12254d)", "panel": "rgba(255,255,255,0.08)", "panel2": "rgba(255,255,255,0.14)",
            "line": "rgba(255,255,255,0.20)", "field": "rgba(255,255,255,0.09)", "dialog": "#2a2240", "blur": "24px", "rim": 25}},
    {"id": "windows", "name": "Mica Blue", "blurb": "Gray panels with small corners, a light-blue accent and a Windows-style font.",
     "look": {"veil": 35, "glass": "#202020", "glassOpacity": 74, "accent": "#4cc2ff", "radius": 8, "edge": 9, "glassBlur": 30, "glassSat": 125, "paintStrength": 12, "font": "windows",
              "text": "#ffffff", "muted": "#cbcbcb", "tabs": {"Stats": "#6ccb5f", "Links": "#c4a0ff"}},
     "palette": ["#4cc2ff", "#6ccb5f", "#ffb900", "#ff99a4", "#c4a0ff", "#00cc6a", "#ff8c00"], "paintLinks": "#4cc2ff",
     "background": theme_bg("windows"),
     "ui": {"bg": "#101010", "panel": "#202020", "panel2": "#2b2b2b", "line": "rgba(255,255,255,0.10)", "field": "#181818", "dialog": "#2b2b2b"}},
    {"id": "liquid", "name": "Crystal Glass", "blurb": "Light, clear glass with raised rounded edges and dark text, on a blue-gray background.",
     "look": {"tone": "light", "glass": "#dde8f5", "glassClear": True, "glassLevel": 30, "accent": "#2f5fd0", "radius": 26, "edge": 45, "glassBlur": 24, "glassSat": 150,
              "glassBevel": 55, "paintStrength": 22, "text": "#13203a", "muted": "#2c3d56", "tabs": {"Stats": "#12806f", "Links": "#6a47c2"}},
     "palette": ["#2f5fd0", "#4a7fb0", "#12806f", "#6a5cc8", "#3a76a8", "#2a8fc7"], "paintLinks": "#2f5fd0",
     "background": theme_bg("liquid"),
     "ui": {"bg": "linear-gradient(135deg,#2b3b4e,#3f5167 50%,#2a3c4d)", "panel": "rgba(255,255,255,0.08)", "panel2": "rgba(255,255,255,0.14)",
            "line": "rgba(255,255,255,0.18)", "field": "rgba(255,255,255,0.08)", "dialog": "#2f4156", "blur": "28px", "rim": 55}},
    {"id": "crystalnight", "name": "Crystal Night", "blurb": "Dark, clear glass with raised rounded edges and light text, on a deep blue-gray background.",
     "look": {"veil": 40, "glass": "#9fb8d8", "glassClear": True, "glassLevel": 72, "accent": "#7aa8ff", "radius": 26, "edge": 24, "glassBlur": 26, "glassSat": 160, "glassRim": 18,
              "glassBevel": 60, "glow": 12, "paintStrength": 24, "text": "#eef4ff", "muted": "#b4c3da", "tabs": {"Stats": "#5fd6c0", "Links": "#b69cff"}},
     "palette": ["#7aa8ff", "#6cc4e8", "#5fd6c0", "#b69cff", "#8fb0e8", "#7ad0f0"], "paintLinks": "#7aa8ff",
     "background": theme_bg("crystalnight"),
     "ui": {"bg": "linear-gradient(135deg,#131c29,#223249 50%,#17222f)", "panel": "rgba(255,255,255,0.07)", "panel2": "rgba(255,255,255,0.13)",
            "line": "rgba(255,255,255,0.16)", "field": "rgba(255,255,255,0.07)", "dialog": "#1f2e43", "blur": "28px", "rim": 45}},
]
THEME_IDS = [t["id"] for t in LOOK_THEMES]


def slugify(text):
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()))


def clean_map(raw, what, limit, key_ok, value_fn):
    if raw is None or raw == {}:
        return {}
    if not isinstance(raw, dict) or len(raw) > limit:
        raise Fail("%s are not valid (too many?)." % what)
    out = {}
    for k, val in raw.items():
        k = clean_text(k, "A name", 60)
        if not key_ok(k):
            raise Fail("The name '%s' has characters that are not allowed here." % k)
        got = value_fn(val, k)
        if got:
            out[k] = got
    return out


NAME_KEYS = {"homelab": "HomeLab", "main": "Main Pool", "backup": "Backup Pool"}
LOGO_DATA_MAX = 150_000
LOGO_SIZE = (24, 96)


def names_clean(raw):
    if raw in (None, {}):
        return {}
    if not isinstance(raw, dict):
        raise Fail("The names are not understood.")
    out = {}
    for k, val in raw.items():
        if k not in NAME_KEYS:
            raise Fail("The name '%s' is not one that can be changed." % k)
        val = re.sub(r"\s+", " ", val.strip()) if isinstance(val, str) else ""
        if not val or val == NAME_KEYS[k]:
            continue
        if len(val) > 24:
            raise Fail("A name can have up to 24 characters.")
        if re.search(r"[\x00-\x1f\x7f\"\\<>{}`]", val):
            raise Fail("A name cannot have these characters:  \" \\ < > { } `  or line breaks.")
        out[k] = val
    return out


def logo_clean(raw):
    """Check the logo settings: `src` (a web address of a picture, or the picture itself as a data: address), `link` (optional), `size` (height in pixels) and `off`."""
    if raw in (None, {}):
        return {}
    if not isinstance(raw, dict):
        raise Fail("The logo is not understood.")
    src = raw.get("src") or ""
    if not isinstance(src, str):
        raise Fail("The logo picture is not valid.")
    src = src.strip()
    if not src:
        return {}
    if src.startswith("data:"):
        m = re.fullmatch(r"data:image/(png|jpeg|webp|gif);base64,([A-Za-z0-9+/]+={0,2})", src)
        if not m or len(src) > LOGO_DATA_MAX:
            raise Fail("That logo picture is too big or not a picture the dashboard can show. Choose a smaller PNG, JPG, WebP or GIF.")
        try:
            data = base64.b64decode(m.group(2), validate=True)
        except (ValueError, binascii.Error):
            raise Fail("That logo picture is damaged. Choose it again.") from None
        if sniff_image(data) not in (".png", ".jpg", ".webp", ".gif"):
            raise Fail("That file cannot be used as a logo.")
    else:
        src = clean_url(src, "The logo address", False)
        if "\\" in src:
            raise Fail("The logo address has a character that is not allowed.")
    out = {"src": src}
    if raw.get("off"):
        out["off"] = True
    link = clean_url(raw.get("link"), "The logo link")
    if link:
        if "\\" in link:
            raise Fail("The logo link has a character that is not allowed.")
        out["link"] = link
    if raw.get("size") not in (None, ""):
        size = number(raw["size"], "The logo size", LOGO_SIZE[0], LOGO_SIZE[1])
        if size != 48:
            out["size"] = size
    return out


def hello_name(val):
    val = re.sub(r"\s+", " ", val.strip()) if isinstance(val, str) else ""
    if len(val) > 24:
        raise Fail("The name in the greeting can have up to 24 characters.")
    if re.search(r"[\x00-\x1f\x7f\"\\<>{}`]", val):
        raise Fail("The name in the greeting cannot have these characters:  \" \\ < > { } `  or line breaks.")
    return val


def hello_default():
    """The name in the greeting when none is set: the admin name typed in the installer, else the name of the account the panel runs as (not root)."""
    clean = lambda v: re.sub(r"[^A-Za-z0-9 ._-]", "", v or "").strip()[:24]
    name = clean(os.environ.get("HLP_ADMIN"))
    if name:
        return name[:1].upper() + name[1:]
    name = clean(os.path.basename(HOME.rstrip("/")))
    return "" if name in ("", "root") else name.capitalize()


def dock_ids(val):
    if val in (None, ""):
        return []
    if not isinstance(val, list) or len(val) > 12:
        raise Fail("The quick launch list can have up to 12 cards.")
    out = []
    for x in val:
        if not isinstance(x, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", x):
            raise Fail("A card in the quick launch list is not valid.")
        if x not in out:
            out.append(x)
    return out


def look_clean(raw):
    """Validate the requested look and keep only the values that differ from the default."""
    if not isinstance(raw, dict):
        raise Fail("The look is missing.")
    out = {}
    if "accent" in raw:
        out["accent"] = rgb_hex(hex_rgb(raw["accent"], "main color"))
    if "glass" in raw:
        out["glass"] = rgb_hex(hex_rgb(raw["glass"], "glass color"))
    if "glassOpacity" in raw:
        out["glassOpacity"] = number(raw["glassOpacity"], "How solid the glass is", 0, 100)
    if "glassClear" in raw:
        out["glassClear"] = bool(raw["glassClear"])
    if "glassLevel" in raw:
        out["glassLevel"] = number(raw["glassLevel"], "How transparent the glass is", 0, 100)
    if "radius" in raw:
        out["radius"] = number(raw["radius"], "How round the corners are", 0, 40)
    if "edge" in raw:
        out["edge"] = number(raw["edge"], "The edge brightness", 0, 60)
    if "side" in raw:
        out["side"] = number(raw["side"], "The space at the sides", 0, 120)
    if "glassBlur" in raw:
        out["glassBlur"] = number(raw["glassBlur"], "How much the glass blurs", 0, 60)
    if "glassSat" in raw:
        out["glassSat"] = number(raw["glassSat"], "How vivid the picture behind the glass is", 50, 300)
    if "text" in raw:
        out["text"] = rgb_hex(hex_rgb(raw["text"], "text color"))
    if "muted" in raw:
        out["muted"] = rgb_hex(hex_rgb(raw["muted"], "color of the smaller text"))
    if "glassTint" in raw:
        out["glassTint"] = bool(raw["glassTint"])
    if "cardDepth" in raw:
        out["cardDepth"] = number(raw["cardDepth"], "How deep the color behind the words is", 0, 100)
    if "glassRim" in raw:
        out["glassRim"] = number(raw["glassRim"], "How bright the shine on the glass edge is", 0, 100)
    if "glassBevel" in raw:
        out["glassBevel"] = number(raw["glassBevel"], "How raised the glass edge is", 0, 100)
    if "glow" in raw:
        out["glow"] = number(raw["glow"], "How much the cards glow", 0, 100)
    if "veil" in raw:
        out["veil"] = number(raw["veil"], "How dark the layer over the picture is", 0, 100)
    if "tone" in raw:
        if raw["tone"] not in TONES:
            raise Fail("The light or dark setting is not valid.")
        out["tone"] = raw["tone"]
    if "font" in raw:
        if raw["font"] not in FONTS:
            raise Fail("The text style is not valid.")
        out["font"] = raw["font"]
    if "motion" in raw:
        if raw["motion"] not in MOTIONS:
            raise Fail("The motion setting is not valid.")
        out["motion"] = raw["motion"]
    if "iconStyle" in raw:
        if raw["iconStyle"] not in ICON_STYLES:
            raise Fail("The icon style is not valid.")
        out["iconStyle"] = raw["iconStyle"]
    if "hello" in raw:
        out["hello"] = bool(raw["hello"])
    if "helloName" in raw:
        out["helloName"] = hello_name(raw["helloName"])
    if "dockMode" in raw:
        if raw["dockMode"] not in DOCK_MODES:
            raise Fail("The quick launch setting is not valid.")
        out["dockMode"] = raw["dockMode"]
    if "dock" in raw:
        out["dock"] = dock_ids(raw["dock"])
    if "theme" in raw:
        if raw["theme"] not in THEME_IDS and not MYTHEME_ID.match(str(raw["theme"])):
            raise Fail("The theme is not understood.")
        out["theme"] = raw["theme"]
    if "playerHeight" in raw:
        out["playerHeight"] = number(raw["playerHeight"], "The height of the music player", 240, 1000)
    if "paintStrength" in raw:
        out["paintStrength"] = number(raw["paintStrength"], "How strong the colors are", 0, 100)
    if "paintStyle" in raw:
        if raw["paintStyle"] not in PAINT_STYLES:
            raise Fail("The color style is not valid.")
        out["paintStyle"] = raw["paintStyle"]
    if "labelIcon" in raw:
        if raw["labelIcon"] not in LABEL_ICONS:
            raise Fail("The label icon style is not valid.")
        out["labelIcon"] = raw["labelIcon"]
    if raw.get("paintAll"):
        out["paintAll"] = rgb_hex(hex_rgb(raw["paintAll"], "color for everything"))
    for key, fn in (("names", names_clean), ("logo", logo_clean)):
        got = fn(raw.get(key))
        if got:
            out[key] = got
    tabs = raw.get("tabs") or {}
    if not isinstance(tabs, dict) or len(tabs) > 30:
        raise Fail("The tab colors are not valid.")
    tt = {}
    for name, col in tabs.items():
        name = clean_text(name, "A tab name", 40)
        if not re.fullmatch(r"[^\"'\\{};<>/*]+", name):
            raise Fail("The tab name '%s' has characters that are not allowed." % name)
        if col:
            tt[name] = rgb_hex(hex_rgb(col, "color of the tab " + name))
    if tt:
        out["tabs"] = tt
    color_of = lambda val, k: rgb_hex(hex_rgb(val, "color of " + k)) if val else ""
    cards = clean_map(raw.get("cards"), "The card colors", 200, lambda k: re.fullmatch(r"[A-Za-z0-9_-]{1,60}", k) is not None, color_of)
    links = clean_map(raw.get("links"), "The bookmark colors", 400, lambda k: slugify(k) != "", color_of)

    def label_of(val, k):
        if not isinstance(val, dict):
            raise Fail("The colors of the label '%s' are not valid." % k)
        d = {}
        for part in ("text", "icon"):
            if val.get(part):
                d[part] = rgb_hex(hex_rgb(val[part], "%s color of the label %s" % (part, k)))
        return d
    labels = clean_map(raw.get("labels"), "The label colors", 60, lambda k: slugify(k) != "", label_of)
    for key, val in (("cards", cards), ("links", links), ("labels", labels)):
        if val:
            out[key] = val
    keep = ("tabs", "cards", "links", "labels", "paintAll", "names", "logo")
    return {k: v for k, v in out.items() if k in keep or v != LOOK_DEFAULT[k]}


