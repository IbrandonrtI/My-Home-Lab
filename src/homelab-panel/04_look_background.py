def look_tab_names():
    return [t["name"] for t in layout_tabs(layout_groups(read(SETTINGS)))]


def look_version(custom):
    """A short fingerprint of the saved look. A page sends the one it was loaded with, so a save made from an older copy can be refused."""
    return hashlib.sha1(json.dumps(custom, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def look_state():
    custom = look_get()
    return {"version": look_version(custom), "custom": custom, "values": look_full(custom), "defaults": look_full({}), "themes": LOOK_THEMES,
            "tabNames": look_tab_names(), "helloDefault": hello_default()}


def look_regen():
    """A new version can change what a saved look writes into custom.css. This writes it again from the saved settings, when they differ."""
    with LOCK:
        css = read(CSS)
        custom = look_get(css)
        if not custom:
            return False
        new = css_with_look(css, custom)
        if new == css:
            return False
        tx = Tx("Look written again by a new version")
        tx.put(CSS, new)
        return tx.commit()


def look_regen_safe():
    try:
        look_regen()
    except Exception as e:
        sys.stderr.write("look: %r\n" % (e,))


def api_look_save(body):
    custom = look_clean(body.get("look"))
    seen = body.get("version")
    if seen is not None and seen != look_version(look_get()):
        raise Fail("The look was changed in another window or tab after this page was opened. Reload the panel to see that change, then make yours again. Nothing was saved.", 409)
    tx = Tx("Look changed")
    tx.put(CSS, css_with_look(tx.get(CSS), custom))
    tx.commit()
    return {}


def api_look_css(body):
    custom = look_clean(body.get("look"))
    css = read(CSS)
    return {"css": look_css(custom, full=True, saved=look_get(css), css=css)}


def api_look_reset(body):
    tx = Tx("Look reset")
    tx.put(CSS, css_with_look(tx.get(CSS), {}))
    tx.commit()
    return {}


BG_DEFAULT = {"blur": "md", "saturate": 60, "brightness": 42, "opacity": 80}
BLURS = ("sm", "md", "lg", "xl", "2xl", "3xl")
IMG_TYPES = {b"\xff\xd8\xff": ".jpg", b"\x89PNG\r\n\x1a\n": ".png", b"GIF8": ".gif"}


def bg_block(lines):
    for i, l in enumerate(lines):
        if re.match(r"^background:\s*(#.*)?$", l):
            j = i + 1
            while j < len(lines) and (lines[j].startswith((" ", "\t")) or (lines[j].strip() == "" and j + 1 < len(lines) and lines[j + 1].startswith(" "))):
                j += 1
            return i, j
    return None, None


def bg_get(text):
    lines = text.split("\n")
    i, j = bg_block(lines)
    d = {}
    if i is None:
        return d
    for l in lines[i + 1:j]:
        m = re.match(r"^\s+([A-Za-z0-9_]+):\s*(.*?)\s*$", l)
        if m:
            d[m.group(1)] = unq(m.group(2))
    return d


def bg_set(text, key, value):
    """Set one key of the background block, or remove it when value is None."""
    lines = text.split("\n")
    i, j = bg_block(lines)
    new = "  %s: %s" % (key, "'" + str(value).replace("'", "''") + "'" if key == "image" else value)
    if i is None:
        if value is None:
            return text
        return text.rstrip("\n") + "\n\nbackground:\n%s\n" % new
    for k in range(i + 1, j):
        if re.match(r"^\s+%s:" % re.escape(key), lines[k]):
            if value is None:
                del lines[k]
            else:
                lines[k] = new
            return "\n".join(lines)
    if value is not None:
        lines.insert(j, new)
    return "\n".join(lines)


def images_mounted():
    if NO_DOCKER:
        return None
    try:
        r = subprocess.run(["docker", "inspect", "homepage", "--format", "{{range .Mounts}}{{.Destination}} {{end}}"],
                           capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.SubprocessError):
        return None
    return ("/app/public/images" in r.stdout.split()) if r.returncode == 0 else None


def bg_state():
    d = bg_get(read(SETTINGS))
    return {"image": d.get("image", ""), "blur": d.get("blur", ""), "saturate": int(d.get("saturate") or 100), "brightness": int(d.get("brightness") or 100),
            "opacity": int(d.get("opacity") or 100), "defaults": BG_DEFAULT, "mounted": images_mounted(), "homepageUrl": HOMEPAGE_URL,
            "blurs": list(BLURS)}


def bg_numbers(body, tx_text):
    text = tx_text
    if "blur" in body:
        b = body["blur"]
        if b in (None, "", "none"):
            text = bg_set(text, "blur", None)
        elif b in BLURS:
            text = bg_set(text, "blur", b)
        else:
            raise Fail("The blur must be none or one of: %s." % ", ".join(BLURS))
    for k in ("saturate", "brightness", "opacity"):
        if k in body:
            text = bg_set(text, k, number(body[k], k.capitalize(), 0, 100))
    return text


def api_bg_save(body):
    tx = Tx("Background changed")
    text = tx.get(SETTINGS)
    u = body.get("url")
    if u and isinstance(u, str) and u.startswith("/images/"):
        name = u[len("/images/"):]
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", name) or not os.path.isfile(os.path.join(IMAGES, name)):
            raise Fail("That picture is no longer in the images folder.")
        text = bg_set(text, "image", u)
    elif u:
        text = bg_set(text, "image", clean_url(u, "The picture address", False))
    text = bg_numbers(body, text)
    tx.put(SETTINGS, text)
    tx.commit()
    return {}


def sniff_image(data):
    for magic, ext in IMG_TYPES.items():
        if data.startswith(magic):
            return ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[4:12] in (b"ftypavif", b"ftypavis"):
        return ".avif"
    return None


MAX_SIDE = 8000
MAX_PIXELS = 40000000


def image_size(data, ext):
    """Width and height of a picture, read from its header without decoding it; None when it cannot be read."""
    try:
        if ext == ".png" and data[12:16] == b"IHDR":
            return struct.unpack(">II", data[16:24])
        if ext == ".gif":
            return struct.unpack("<HH", data[6:10])
        if ext == ".webp":
            kind = data[12:16]
            if kind == b"VP8X":
                return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
            if kind == b"VP8 ":
                return struct.unpack("<HH", data[26:30])[0] & 0x3FFF, struct.unpack("<HH", data[26:30])[1] & 0x3FFF
            if kind == b"VP8L":
                bits = int.from_bytes(data[21:25], "little")
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if ext == ".jpg":
            i = 2
            while i + 9 < len(data):
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
                    i += 1 if marker == 0xFF else 2
                    continue
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return w, h
                i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
        if ext == ".avif":
            at = data.find(b"ispe")
            if at > 0:
                return struct.unpack(">II", data[at + 8:at + 16])
    except (struct.error, IndexError):
        return None
    return None


def check_picture_size(data, ext):
    """A small file can still hold a huge picture that every device must unpack. Refuse a picture larger than 8000 pixels on a side or 40 megapixels."""
    size = image_size(data, ext)
    if size and (max(size) > MAX_SIDE or size[0] * size[1] > MAX_PIXELS):
        raise Fail("That picture is too large (%d x %d pixels). Use one that is at most %d pixels wide or high and %d megapixels in all." % (size[0], size[1], MAX_SIDE, MAX_PIXELS // 1000000))


def restart_homepage():
    if NO_DOCKER:
        return False

    def go():
        try:
            subprocess.run(["docker", "restart", "homepage"], capture_output=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            pass
    threading.Thread(target=go, daemon=True).start()
    return True


def bg_store(data, body=None, fixed=None):
    """Keep a picture in the images folder and make it the background, with the sliders in `body` if any. Returns what the panel needs to know."""
    ext = sniff_image(data)
    if not ext:
        raise Fail("That file cannot be used as a picture. Choose a .jpg, .png, .webp, .gif or .avif file.")
    check_picture_size(data, ext)
    os.makedirs(IMAGES, exist_ok=True)
    stamp = time.time()
    while not fixed and os.path.exists(os.path.join(IMAGES, "background-%s%s" % (time.strftime("%Y%m%d%H%M%S", time.localtime(stamp)), ext))):
        stamp += 1
    name = (fixed + ext) if fixed else "background-%s%s" % (time.strftime("%Y%m%d%H%M%S", time.localtime(stamp)), ext)
    with open(os.path.join(IMAGES, name), "wb") as f:
        f.write(data)
    os.chmod(os.path.join(IMAGES, name), 0o644)
    try:
        tx = Tx("Background picture changed")
        text = bg_set(tx.get(SETTINGS), "image", "/images/" + name)
        tx.put(SETTINGS, bg_numbers(body or {}, text))
        tx.commit()
    except Exception:
        if not fixed:
            try:
                os.remove(os.path.join(IMAGES, name))
            except OSError:
                pass
        raise
    for old in ([] if fixed else os.listdir(IMAGES)):
        if re.fullmatch(r"background-\d{14}\.\w+", old) and old != name:
            try:
                if len([x for x in os.listdir(IMAGES) if x.startswith("background-")]) > 3:
                    os.remove(os.path.join(IMAGES, old))
            except OSError:
                pass
    return {"restarting": restart_homepage(), "image": "/images/" + name}


def api_bg_upload(data):
    return bg_store(data)


def theme_file(theme_id):
    """The stored picture of a theme (name in the images folder), or None."""
    for f in (sorted(os.listdir(IMAGES)) if os.path.isdir(IMAGES) else []):
        if re.fullmatch(r"theme-%s%s\.\w+" % (re.escape(theme_id), THEME_PIC_REV), f):
            return f
    return None


def theme_download(t, timeout=30):
    """Fetch the picture of a theme from the address in the list above (or from HLP_THEME_PICTURE_BASE in tests). Returns the bytes, or None."""
    base = os.environ.get("HLP_THEME_PICTURE_BASE")
    try:
        req = urllib.request.Request(base.rstrip("/") + "/" + t["id"] + ".png" if base else t["background"]["url"], headers={"User-Agent": "homelab-panel"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(MAX_UPLOAD + 1)
        return data if len(data) <= MAX_UPLOAD and sniff_image(data) else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def theme_picture(body):
    """Return the picture of a theme. The panel only names the theme and the address comes from the list above, so it cannot be made to use any other address."""
    t = next((x for x in LOOK_THEMES if x["id"] == body.get("theme")), None)
    if not t or not t.get("background"):
        raise Fail("That theme has no picture.")
    url = t["background"]["url"]
    with LOCK:
        have = theme_file(t["id"])
        if have:
            tx = Tx("Background picture changed")
            tx.put(SETTINGS, bg_numbers(body, bg_set(tx.get(SETTINGS), "image", "/images/" + have)))
            tx.commit()
            return {"restarting": False, "image": "/images/" + have, "stored": True, "cached": True}
    # A picture that is not stored yet is used from its web address. Storing it here would restart Homepage and reload the page, so only `homelab-setup refresh` stores them.
    with LOCK:
        tx = Tx("Background picture changed")
        tx.put(SETTINGS, bg_numbers(body, bg_set(tx.get(SETTINGS), "image", url)))
        tx.commit()
        return {"restarting": False, "image": url, "stored": False}


AUTOMATIC = {"Preview", "Music Library", "Library Totals", "Storage", "Folder Sizes", "Calendar"}
HL_ID = re.compile(r"^(stat|cal)-")
HL_BLOCKS = (("# >>> homelab stats >>>", "# <<< homelab stats <<<"), ("# >>> homelab calendar >>>", "# <<< homelab calendar <<<"))
HL_GROUP_LOOK = {"Preview": ("mdi-view-dashboard", 3, "Stats"), "Music Library": ("mdi-music", 2, "Stats"), "Library Totals": ("mdi-image-multiple", 2, "Stats"),
                 "Storage": ("mdi-harddisk", 2, "Stats"), "Folder Sizes": ("mdi-folder-multiple", 1, "Stats"),
                 "Calendar": ("mdi-calendar-month", 2, "Home")}
PROTECTED = {"Customize", "Edit Links", "Terminal"}


def layout_span(lines):
    i = next((k for k, l in enumerate(lines) if re.match(r"^layout:\s*(#.*)?$", l)), None)
    if i is None:
        return None, None
    j = i + 1
    while j < len(lines) and (lines[j].startswith((" ", "\t")) or not lines[j].strip()):
        j += 1
    while j > i + 1 and not lines[j - 1].strip():
        j -= 1
    return i, j


