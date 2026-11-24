#!/usr/bin/env python3
"""homelab-panel - the control panel of the lab: change the look of the dashboard by pointing and clicking.

  homelab-panel serve                  run the panel (the installer starts this as the service homelab-panel)
  homelab-panel set-password           choose the panel's password (asks twice; or: --stdin reads it from a pipe)
  homelab-panel status                 is a password set, and where are the files
  homelab-panel theme-pictures         store the picture of every theme in the Homepage folder (--check only looks; the installer runs this)
  homelab-panel version | help

What the panel is:
  - a small web page that only listens on THIS machine (127.0.0.1); Tailscale Serve gives it an HTTPS address that only your own
    devices (your tailnet) can reach. It is never opened to your home network, and has its own password (not the other logins).
  - it runs as the same user as the dashboard files, so it needs no sudo for them: it edits ~/homepage-config (settings.yaml, services.yaml,
    bookmarks.yaml and the look block of custom.css) and nothing else. The work is done by plain text edits, the same files you could edit by hand.
  - the Drives tab asks the drives tool (sudo drives panel ...) through a narrow sudo rule: look at the drives, rename one, sleep or wake one,
    remount after a disconnection, add a spare drive to a pool, take one out, move one between pools, erase a spare drive. The drives tool itself asks
    for the typed confirmations (the drive name and ERASE, CONTINUE, REMOVE, KEEP) and refuses when a backup or an upload is running.
  - the Terminal card of the Links tab is a web terminal (ttyd, its own service as the same user) that listens on a private socket only this
    panel can reach. The panel checks the login before it passes anything through, so the terminal is as private as the panel: only your tailnet.
  - every change first saves a copy of the files it changes (.panel-history in the Homepage folder), so "Undo" brings the last state back.

Written with the Python standard library only (PyYAML is used when it is installed, to check a file before it is saved).
"""
import base64
import binascii
import datetime
import getpass
import glob
import hashlib
import hmac
import http.client
import json
import math
import mimetypes
import os
import re
import secrets
import select
import shlex
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zoneinfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import yaml
except ImportError:
    yaml = None

VERSION = "0.1"

HOME = os.environ.get("HLP_HOME") or os.path.expanduser("~")
HP = os.environ.get("HOMELAB_HOMEPAGE_DIR") or os.path.join(HOME, "homepage-config")
STATE_DIR = os.environ.get("HLP_STATE") or os.path.join(HOME, ".config", "homelab-panel")
UI_DIR = os.environ.get("HLP_UI") or "/usr/local/share/homelab-panel/ui"
PORT = int(os.environ.get("HLP_PORT") or 8300)
BIND = os.environ.get("HLP_BIND") or "127.0.0.1"
HOSTS = [h.strip().lower() for h in (os.environ.get("HLP_HOSTS") or "").split(",") if h.strip()]
FRAME = [h.strip() for h in (os.environ.get("HLP_FRAME") or "").split(",") if h.strip()]
HOMEPAGE_URL = (os.environ.get("HLP_HOMEPAGE_URL") or "").rstrip("/")
TERM_SOCK = os.environ.get("HLP_TERM_SOCK") or "/run/homelab-terminal/ttyd.sock"
COOKIE = "hlpanel" if os.environ.get("HLP_COOKIE_PLAIN") else "__Host-hlpanel"
NO_DOCKER = bool(os.environ.get("HLP_NO_DOCKER"))
DRIVES_CMD = shlex.split(os.environ.get("HLP_DRIVES") or "sudo -n /usr/local/sbin/drives")
BACKUP_CMD = shlex.split(os.environ.get("HLP_BACKUP") or "sudo -n /usr/local/sbin/homelab-backup-tasks panel")

SHIPPED = os.environ.get("HLP_SHIPPED") or "/usr/local/share/homelab-panel/shipped-services.yaml"
SHIPPED_EXTRAS = os.environ.get("HLP_SHIPPED_EXTRAS") or "/usr/local/share/homelab-panel/shipped-stat-extras.yaml"
SETTINGS = os.path.join(HP, "settings.yaml")
SERVICES = os.path.join(HP, "services.yaml")
BOOKMARKS = os.path.join(HP, "bookmarks.yaml")
CSS = os.path.join(HP, "custom.css")
WIDGETS = os.path.join(HP, "widgets.yaml")
IMAGES = os.path.join(HP, "images")
HISTORY = os.path.join(HP, ".panel-history")
PASSFILE = os.path.join(STATE_DIR, "password")
KEEP_HISTORY = 40
MAX_UPLOAD = 14 * 1024 * 1024
SESSION_IDLE = 24 * 3600
SESSION_MAX = 7 * 24 * 3600

LOOK_B1, LOOK_B2 = "/* >>> homelab look >>>", "/* <<< homelab look <<< */"
BG_B1, BG_B2 = "/* >>> homelab picture >>>", "/* <<< homelab picture <<< */"
BLUR_PX = {"sm": 4, "md": 12, "lg": 16, "xl": 24, "2xl": 40, "3xl": 64}
THEME_B1 = "/* >>> homelab theme >>>"


class Fail(Exception):
    def __init__(self, msg, code=400):
        Exception.__init__(self, msg)
        self.code = code


def read(p):
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""
    except PermissionError:
        raise Fail("The panel is not allowed to read %s. Run  sudo homelab-setup refresh  to put its permissions right." % os.path.basename(p), 500) from None


def private_open(path, flags):
    return os.open(path, flags, 0o600)


def nofollow_open(path, flags):
    """Open a file in the Undo history without following a link that someone put in its place."""
    return os.open(path, flags | os.O_NOFOLLOW, 0o600)


def write_atomic(p, text, mode=None):
    """Write a file in one step through a fresh temporary file in the same folder (a planted link cannot be followed). The new file keeps the permissions of the old one, and nobody else can read it before that is set."""
    if mode is None:
        try:
            mode = os.stat(p).st_mode & 0o777
        except OSError:
            mode = 0o644
    try:
        fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(p) + ".", suffix=".panel-tmp", dir=os.path.dirname(p) or ".")
    except PermissionError:
        raise Fail("The panel is not allowed to change %s. Run  sudo homelab-setup refresh  to put its permissions right (if that does not help: sudo chown $USER: the folder, see sudo homelab-selftest). Nothing was changed." % os.path.basename(p), 500) from None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fchmod(f.fileno(), mode)
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


LOCK = threading.RLock()


LOCAL = threading.local()
MERGE_AFTER = ("Background changed", "Background picture changed")


def snap_merge(group, olds):
    """Add the files of this change to the Undo entry made a moment ago for the background, so saving a look and a background together is one Undo step. Returns None when there is no such entry, otherwise a function that takes the added files out again (used when the save fails)."""
    last = history_last()
    if not last or time.time() - last[1].get("time", 0) > 30 or last[1].get("label") not in MERGE_AFTER:
        return None
    d, meta = last
    before = json.loads(json.dumps(meta))
    have = {i["path"] for i in meta["files"].values()}
    n = len(meta["files"])
    for path, text in sorted(olds.items()):
        if path in have:
            continue
        with open(os.path.join(d, "f%d" % n), "w", encoding="utf-8", opener=nofollow_open) as f:
            f.write(text)
        meta["files"]["f%d" % n] = {"path": path, "existed": os.path.exists(path)}
        n += 1
    meta["label"] = group
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8", opener=nofollow_open) as f:
        json.dump(meta, f)

    def undo_merge():
        for fn in set(meta["files"]) - set(before["files"]):
            try:
                os.unlink(os.path.join(d, fn))
            except OSError:
                pass
        try:
            with open(os.path.join(d, "meta.json"), "w", encoding="utf-8", opener=nofollow_open) as f:
                json.dump(before, f)
        except OSError:
            pass
    return undo_merge


class Tx:
    """One change to the dashboard files. The files are collected, checked and written together, and the old texts are saved first so Undo can restore them."""
    def __init__(self, label):
        self.label = label
        self.old = {}
        self.new = {}

    def get(self, path):
        if path not in self.new:
            self.old[path] = read(path)
            self.new[path] = self.old[path]
        return self.new[path]

    def put(self, path, text):
        self.get(path)
        self.new[path] = text

    def commit(self):
        if SETTINGS in self.new or CSS in self.new:
            css = self.get(CSS)
            fixed = css_with_picture(css, self.get(SETTINGS))
            if fixed != css:
                self.put(CSS, fixed)
        changed = [p for p in self.new if self.new[p] != self.old[p]]
        for p in changed:
            check_text(p, self.new[p])
        if not changed:
            if getattr(LOCAL, "changed", None) is None:
                LOCAL.changed = False
            return False
        LOCAL.changed = True
        olds = {p: self.old[p] for p in changed}
        group = getattr(LOCAL, "merge", "")
        saved = None
        merged = snap_merge(group, olds) if group else None
        if merged is None:
            saved = snap(self.label, olds)
        written = []
        try:
            for p in changed:
                write_atomic(p, self.new[p])
                written.append(p)
        except BaseException:
            for p in written:
                try:
                    write_atomic(p, self.old[p])
                except (OSError, Fail):
                    pass
            if saved:
                shutil.rmtree(saved, ignore_errors=True)
            if merged:
                merged()
            LOCAL.changed = False
            raise
        return True


def check_text(path, text):
    if yaml is None or not path.endswith(".yaml"):
        return
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise Fail("That change would make %s unreadable (%s). Nothing was changed." % (os.path.basename(path), str(e).splitlines()[0])) from None
    if os.path.basename(path) in ("services.yaml", "bookmarks.yaml") and data is not None and not isinstance(data, list):
        raise Fail("That change would break the shape of %s. Nothing was changed." % os.path.basename(path))


def snap(label, olds):
    os.makedirs(HISTORY, mode=0o700, exist_ok=True)
    os.chmod(HISTORY, 0o700)
    name = "%s-%04d" % (time.strftime("%Y%m%d-%H%M%S"), int(time.time() * 1000) % 10000)
    d = os.path.join(HISTORY, name)
    os.makedirs(d, mode=0o700)
    meta = {"label": label, "time": int(time.time()), "files": {}}
    for i, (p, text) in enumerate(sorted(olds.items())):
        fn = "f%d" % i
        with open(os.path.join(d, fn), "w", encoding="utf-8", opener=private_open) as f:
            f.write(text)
        meta["files"][fn] = {"path": p, "existed": os.path.exists(p)}
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8", opener=private_open) as f:
        json.dump(meta, f)
    old = sorted(x for x in os.listdir(HISTORY) if os.path.isdir(os.path.join(HISTORY, x)))
    for x in old[:-KEEP_HISTORY]:
        shutil.rmtree(os.path.join(HISTORY, x), ignore_errors=True)
    return d


def history_last():
    if not os.path.isdir(HISTORY):
        return None
    dirs = sorted(x for x in os.listdir(HISTORY) if os.path.isfile(os.path.join(HISTORY, x, "meta.json")))
    if not dirs:
        return None
    d = os.path.join(HISTORY, dirs[-1])
    try:
        with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
            return d, json.load(f)
    except (OSError, ValueError):
        return None


def undo():
    h = history_last()
    if not h:
        raise Fail("There is nothing to undo.")
    d, meta = h
    files = meta.get("files")
    allowed = (SETTINGS, SERVICES, BOOKMARKS, CSS, WIDGETS)
    if not isinstance(files, dict) or any(not re.fullmatch(r"f\d+", str(fn)) or not isinstance(i, dict) or i.get("path") not in allowed for fn, i in files.items()):
        raise Fail("The last Undo entry does not belong to the dashboard files, so nothing was changed. It can be removed from the .panel-history folder.", 500)
    texts = {}
    for fn in files:
        try:
            with open(os.path.join(d, fn), encoding="utf-8", opener=nofollow_open) as f:
                texts[fn] = f.read()
        except OSError:
            raise Fail("The last Undo entry cannot be read, so nothing was changed.", 500) from None
    gone = set()
    for info in files.values():
        if info["path"] == SETTINGS:
            gone |= set(re.findall(r"/images/(background-\d{14}\.\w+)", read(SETTINGS)))
    for fn, info in files.items():
        write_atomic(info["path"], texts[fn])
    shutil.rmtree(d, ignore_errors=True)
    if gone:
        now = read(SETTINGS) + read(CSS)
        for name in gone:
            if "/images/" + name not in now:
                try:
                    os.remove(os.path.join(IMAGES, name))
                except OSError:
                    pass
    return meta.get("label", "")


YAML_WORDS = {"yes", "no", "true", "false", "on", "off", "null", "~", "y", "n"}


def yq(s):
    s = str(s)
    if s == "":
        return '""'
    bad = (s[0] in "-?:,[]{}#&*!|>'\"%@`" or ": " in s or " #" in s or s.endswith(":") or s.lower() in YAML_WORDS
           or re.fullmatch(r"[-+]?[0-9][0-9_.,:e+-]*", s) is not None or s != s.strip() or "\t" in s)
    if not bad:
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def unq(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] == '"':
        return re.sub(r'\\(["\\])', r"\1", s[1:-1])
    if len(s) >= 2 and s[0] == s[-1] == "'":
        return s[1:-1].replace("''", "'")
    return s


