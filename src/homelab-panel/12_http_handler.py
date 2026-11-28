def upload_photo(handler, name, n, mtime, key):
    """Send an uploaded photo to Immich with its original time stamp."""
    try:
        ms = int(mtime)
    except ValueError:
        ms = int(time.time() * 1000)
    stamp = datetime_iso(ms / 1000.0)
    safe = name.replace('"', "'")
    boundary = "hlpanel" + secrets.token_hex(12)
    fields = {"deviceAssetId": "%s-%d-%d" % (re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120], n, ms), "deviceId": "homelab-panel", "fileCreatedAt": stamp, "fileModifiedAt": stamp}
    pre = "".join('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (boundary, k, v) for k, v in fields.items())
    pre += '--%s\r\nContent-Disposition: form-data; name="assetData"; filename="%s"\r\nContent-Type: application/octet-stream\r\n\r\n' % (boundary, safe)
    pre, post = pre.encode("utf-8"), ("\r\n--%s--\r\n" % boundary).encode("ascii")
    u = urllib.parse.urlparse(IMMICH_URL)
    try:
        c = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=3600)
        c.putrequest("POST", "/api/assets")
        c.putheader("x-api-key", key)
        c.putheader("Accept", "application/json")
        c.putheader("Content-Type", "multipart/form-data; boundary=" + boundary)
        c.putheader("Content-Length", str(len(pre) + n + len(post)))
        c.endheaders()
        c.send(pre)
    except (OSError, http.client.HTTPException):
        raise Fail("Immich is not responding. Check that it is running.", 502) from None
    left = n
    try:
        while left > 0:
            b = handler.rfile.read(min(left, UPLOAD_CHUNK))
            if not b:
                c.close()
                raise Fail("The upload was cut off.", 400)
            c.send(b)
            left -= len(b)
        c.send(post)
    except (OSError, http.client.HTTPException):
        pass
    try:
        r = c.getresponse()
        raw = r.read(1 << 20)
        c.close()
    except (OSError, http.client.HTTPException):
        raise Fail("Immich stopped responding while the file was being sent.", 502) from None
    try:
        js = json.loads(raw)
    except ValueError:
        js = {}
    if r.status in (200, 201):
        return {"ok": True, "status": "duplicate" if js.get("status") == "duplicate" else "created", "id": js.get("id", "")}
    if r.status == 401:
        raise Fail("Immich rejected the key. Paste the key again.", 409)
    raise Fail("Immich rejected the file (code %d): %s" % (r.status, str(js.get("message") or raw[:200])[:200]), 502)


def datetime_iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(ts))


def upload_song(handler, name, n):
    """Save an uploaded song in the music folder after checking the folder, free space and file name."""
    d = music_dir()
    if not os.path.isdir(d):
        raise Fail("The music folder (%s) was not found. Check that the drive is connected." % d, 409)
    if not os.access(d, os.W_OK | os.X_OK):
        raise Fail("The panel does not have permission to write to the music folder (%s)." % d, 409)
    try:
        free = shutil.disk_usage(d).free
    except OSError:
        free = n + 10 ** 9
    if free < n + 200 * 1024 * 1024:
        raise Fail("There is not enough free space in the music folder for this song.", 507)
    tmp = os.path.join(d, ".upload-%s.part" % secrets.token_hex(6))
    try:
        with open(tmp, "wb") as f:
            left = n
            while left > 0:
                b = handler.rfile.read(min(left, UPLOAD_CHUNK))
                if not b:
                    raise Fail("The upload was cut off.", 400)
                f.write(b)
                left -= len(b)
        os.chmod(tmp, 0o664)
        base, dot, ext = name.rpartition(".")
        final, i = os.path.join(d, name), 1
        while True:
            try:
                os.close(os.open(final, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o664))
                break
            except FileExistsError:
                i += 1
                final = os.path.join(d, "%s (%d).%s" % (base, i, ext))
        os.replace(tmp, final)
    except OSError as e:
        raise Fail("The song could not be saved: %s" % (e.strerror or e), 500) from None
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    return {"ok": True, "saved": os.path.basename(final)}


TERM_MAX = 6_000_000
TERM_IDLE = 600


class UnixConn(http.client.HTTPConnection):
    def __init__(self, path, timeout=20):
        super().__init__("localhost", timeout=timeout)
        self.sock_path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.sock_path)


class Handler(BaseHTTPRequestHandler):
    """The panel's HTTP server: serves the page files and the API, checks the session and the request origin, and relays the terminal."""
    server_version = "homelab-panel"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    timeout = 120
    body_left = 0

    def handle(self):
        """A browser that vanishes or stalls mid-request is not an error worth a traceback."""
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            self.close_connection = True

    def log_message(self, fmt, *args):
        if os.environ.get("HLP_LOG"):
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def host_ok(self):
        host = (self.headers.get("Host") or "").lower()
        ok = {"localhost:%d" % PORT, "127.0.0.1:%d" % PORT, "[::1]:%d" % PORT}
        for h in HOSTS:
            ok.add(h)
        return host in ok

    def origin_ok(self, origin):
        net = urllib.parse.urlparse(origin).netloc.lower()
        return net == (self.headers.get("Host") or "").lower() or net in set(HOSTS) | {"localhost:%d" % PORT, "127.0.0.1:%d" % PORT}

    def cookie_token(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == COOKIE:
                return v
        return ""

    def settle_body(self, code):
        """A POST can be refused before its body was read (not logged in, wrong origin). Left on the connection, that body would be taken for the next request
        and the browser's next call would fail, so a small one is read and dropped, and any other closes the connection."""
        left, self.body_left = self.body_left, 0
        if left == 0 or (left == -1 and code < 400):
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if left is None and 0 <= n <= (1 << 20):
            if n:
                self.rfile.read(n)
        else:
            self.close_connection = True

    def send(self, code, body, ctype="application/json", extra=None, csp=None):
        self.settle_body(code)
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        anc = " ".join(["'self'"] + FRAME)
        self.send_header("Content-Security-Policy", csp or ("default-src 'self'; img-src 'self' data: https: http:; style-src 'self' 'unsafe-inline'; "
                                                           "script-src 'self'; connect-src 'self'; frame-ancestors " + anc))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True

    def fail(self, e):
        self.send(e.code, {"error": str(e)})

    def content_length(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise Fail("The request is not valid.", 400) from None
        if n < 0:
            raise Fail("The request is not valid.", 400)
        return n

    def read_body(self, limit):
        n = self.content_length()
        if n > limit:
            raise Fail("That is too big.", 413)
        self.body_left = 0
        return self.rfile.read(n) if n else b""

    def api_guard(self):
        if self.headers.get("X-Panel") != "1":
            raise Fail("This request did not come from the panel page.", 403)
        origin = self.headers.get("Origin")
        if origin and not self.origin_ok(origin):
            raise Fail("This request came from another website.", 403)
        if not session_ok(self.cookie_token()):
            raise Fail("Please log in again.", 401)

    def alerts_refresh(self):
        """The bell on the dashboard asks for a new look at what needs attention. It needs no login because it only re-runs the read-only check and returns nothing private.
        It is accepted only from a page on this same machine (any port), so another website cannot use it."""
        origin = self.headers.get("Origin") or ""
        host = (self.headers.get("Host") or "").lower().rsplit(":", 1)[0].strip("[]")
        net = urllib.parse.urlparse(origin).hostname or ""
        if not origin or net.lower() != host:
            raise Fail("This request did not come from the dashboard.", 403)
        return self.send(200, {"ok": True, "ran": alerts_refresh_now()}, extra={"Access-Control-Allow-Origin": origin, "Vary": "Origin"})

    def do_HEAD(self):
        self.do_GET()

    def other_method(self):
        self.close_connection = True
        self.send(405, {"error": "That kind of request is not accepted here."}, extra={"Allow": "GET, HEAD, POST"})

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_TRACE = do_CONNECT = other_method

    def send_error(self, code, message=None, explain=None):
        """Python's own error page (an HTML 501 for a verb it does not know) is replaced by the same short JSON answer everything else gives."""
        if code == 501:
            code = 405
        body = json.dumps({"error": "That kind of request is not accepted here." if code == 405 else "The request is not valid."}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if code == 405:
            self.send_header("Allow", "GET, HEAD, POST")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        """Handle GET requests: the page files, the session and the read-only API calls."""
        try:
            if not self.host_ok():
                return self.send(421, {"error": "Unknown address."})
            path = urllib.parse.urlparse(self.path).path
            if path.startswith("/api/") and path != "/api/session" and self.headers.get("Origin") and not self.origin_ok(self.headers.get("Origin")):
                raise Fail("This request came from another website.", 403)
            if path == "/api/session":
                return self.send(200, {"loggedIn": session_ok(self.cookie_token()), "passwordSet": os.path.exists(PASSFILE), "version": VERSION})
            if path == "/api/state":
                if self.headers.get("X-Panel") != "1" or not session_ok(self.cookie_token()):
                    raise Fail("Please log in again.", 401)
                with LOCK:
                    return self.send(200, full_state())
            if path == "/api/icons":
                if self.headers.get("X-Panel") != "1" or not session_ok(self.cookie_token()):
                    raise Fail("Please log in again.", 401)
                return self.send(200, icon_index())
            if path == "/api/drives/job":
                if self.headers.get("X-Panel") != "1" or not session_ok(self.cookie_token()):
                    raise Fail("Please log in again.", 401)
                return self.send(200, api_drives_job())
            if path == "/api/upload":
                if self.headers.get("X-Panel") != "1" or not session_ok(self.cookie_token()):
                    raise Fail("Please log in again.", 401)
                return self.send(200, api_upload_state())
            if path in ("/api/updates", "/api/updates/job"):
                if self.headers.get("X-Panel") != "1" or not session_ok(self.cookie_token()):
                    raise Fail("Please log in again.", 401)
                return self.send(200, api_updates_state("fresh=1" in self.path) if path == "/api/updates" else api_updates_job())
            if path == "/api/backup/download":
                if not session_ok(self.cookie_token()):
                    raise Fail("Please log in again.", 401)
                return backup_download(self, urllib.parse.urlparse(self.path).query)
            if path in ("/api/backup", "/api/backup/job", "/api/backup/versions", "/api/backup/browse"):
                if self.headers.get("X-Panel") != "1" or not session_ok(self.cookie_token()):
                    raise Fail("Please log in again.", 401)
                if path == "/api/backup/job":
                    return self.send(200, api_backup_job())
                if path == "/api/backup":
                    return self.send(200, api_backup_state())
                return self.send(200, api_backup_look(path.rsplit("/", 1)[1], urllib.parse.urlparse(self.path).query))
            if path in ("/api/drives", "/api/drives/health", "/api/drives/check", "/api/drives/setups", "/api/drives/apps", "/api/drives/folders"):
                if self.headers.get("X-Panel") != "1" or not session_ok(self.cookie_token()):
                    raise Fail("Please log in again.", 401)
                if path == "/api/drives":
                    return self.send(200, api_drives_state())
                action, extra = path.rsplit("/", 1)[1], ()
                if action == "folders":
                    role = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("role", [""])[0]
                    if role not in ("main", "backup"):
                        raise Fail("Choose Main or Backup.", 400)
                    extra = (role,)
                if action == "setups":
                    skip = [x for x in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("skip", [""])[0].split(",") if x]
                    if len(skip) > 24 or not all(DRIVE_ID.match(x) for x in skip):
                        raise Fail("Those are not drive names.", 400)
                    extra = (",".join(skip),) if skip else ()
                return self.send(200, drives_json(action, extra))
            if path.startswith("/api/"):
                raise Fail("Unknown address.", 404)
            if path == "/terminal":
                return self.send(302, b"", "text/plain", {"Location": "/terminal/"})
            if path.startswith("/terminal/"):
                return self.terminal()
            self.static(path)
        except Fail as e:
            self.fail(e)
        except Exception as e:
            sys.stderr.write("error: %r\n" % (e,))
            self.send(500, {"error": "An internal error occurred in the panel. See:  journalctl -u homelab-panel -n 30"})

    def terminal_page(self, code, text):
        page = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Terminal</title>"
                "<body style='font:16px system-ui,sans-serif;background:#0a0f19;color:#dbe4f5;padding:24px'><p>%s</p>"
                "<p><a style='color:#8ab4ff' target=_blank rel=noopener href='/'>Open the control panel</a></p>" % text)
        return self.send(code, page, "text/html; charset=utf-8")

    def terminal_target(self):
        u = urllib.parse.urlparse(self.path)
        return u.path + ("?" + u.query if u.query else "")

    def terminal(self):
        if not session_ok(self.cookie_token()):
            return self.terminal_page(401, "Log in to the control panel first (the Customize tab uses the same login), then reload this card.")
        if (self.headers.get("Upgrade") or "").lower() == "websocket":
            origin = self.headers.get("Origin")
            if not origin or not self.origin_ok(origin):
                raise Fail("This request came from another website.", 403)
            return self.terminal_socket()
        try:
            conn = UnixConn(TERM_SOCK)
            page = urllib.parse.urlparse(self.path).path.rstrip("/") in ("/terminal", "")
            conn.request("GET", self.terminal_target(), headers={"Host": "localhost", "Accept": self.headers.get("Accept") or "*/*",
                                                    "Accept-Encoding": "identity" if page else (self.headers.get("Accept-Encoding") or "identity")})
            r = conn.getresponse()
            body = r.read(TERM_MAX + 1)
            ctype, enc, status = r.getheader("Content-Type") or "application/octet-stream", r.getheader("Content-Encoding"), r.status
            conn.close()
        except (OSError, http.client.HTTPException):
            return self.terminal_page(502, "The terminal is not running. On the server, look at:  sudo systemctl status homelab-terminal")
        if len(body) > TERM_MAX or status not in (200, 304, 401, 404):
            return self.terminal_page(502, "The terminal returned a response that the panel cannot read.")
        if status == 200 and ctype.startswith("text/html") and not enc and b"</head>" in body:
            body = body.replace(b"</head>", b"<style>html,body{overscroll-behavior:contain}</style></head>", 1)
        anc = " ".join(["'self'"] + FRAME)
        csp = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; "
               "connect-src 'self' ws: wss:; worker-src 'self' blob:; frame-ancestors " + anc)
        return self.send(status, body, ctype, {"Content-Encoding": enc} if enc else None, csp=csp)

    def terminal_socket(self):
        """Relay the terminal's WebSocket: pass the handshake on, then pass bytes both ways until one side closes."""
        up = socket.socket(socket.AF_UNIX)
        try:
            up.settimeout(5)
            up.connect(TERM_SOCK)
        except OSError:
            up.close()
            return self.terminal_page(502, "The terminal is not running. On the server, look at:  sudo systemctl status homelab-terminal")
        keep = ("Upgrade", "Connection", "Sec-WebSocket-Key", "Sec-WebSocket-Version", "Sec-WebSocket-Protocol", "Sec-WebSocket-Extensions")
        head = ["GET %s HTTP/1.1" % self.terminal_target(), "Host: localhost"] + ["%s: %s" % (k, self.headers[k]) for k in keep if self.headers.get(k)]
        try:
            up.sendall(("\r\n".join(head) + "\r\n\r\n").encode("latin-1"))
        except (OSError, UnicodeEncodeError):
            up.close()
            return self.terminal_page(502, "The terminal could not be reached.")
        self.close_connection = True
        client = self.connection
        up.settimeout(None)
        client.settimeout(None)
        socks = [client, up]
        try:
            while True:
                ready = select.select(socks, [], [], TERM_IDLE)[0]
                if not ready:
                    break
                for x in ready:
                    data = x.recv(65536)
                    if not data:
                        return
                    (up if x is client else client).sendall(data)
        except OSError:
            pass
        finally:
            up.close()

    def static(self, path):
        names = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/app.css": "app.css", "/icon.svg": "icon.svg"}
        fn = names.get(path)
        if not fn:
            return self.send(404, {"error": "Not found."})
        data = read_bytes(os.path.join(UI_DIR, fn))
        if data is None:
            return self.send(404, {"error": "The panel's page files are not installed (%s). Run: sudo homelab-setup upgrade" % UI_DIR})
        ctype = mimetypes.guess_type(fn)[0] or "application/octet-stream"
        self.send(200, data, ctype + ("; charset=utf-8" if ctype.startswith("text/") or ctype.endswith("javascript") else ""))

    def do_POST(self):
        """Handle POST requests: login and every change the panel can make."""
        self.body_left = None
        try:
            if not self.host_ok():
                return self.send(421, {"error": "Unknown address."})
            path = urllib.parse.urlparse(self.path).path
            label = self.headers.get("X-Undo-Merge") or ""
            LOCAL.merge = label if re.fullmatch(r"[A-Za-z ]{1,40}", label) else ""
            if path == "/api/login":
                if self.headers.get("X-Panel") != "1" or (self.headers.get("Origin") and not self.origin_ok(self.headers.get("Origin"))):
                    raise Fail("This request did not come from the panel page.", 403)
                body = json.loads(self.read_body(4096) or b"{}")
                tok = login(body.get("password"), self.client_address[0])
                flags = "; HttpOnly; SameSite=Lax; Path=/; Max-Age=%d" % SESSION_MAX + ("" if os.environ.get("HLP_COOKIE_PLAIN") else "; Secure")
                return self.send(200, {"ok": True}, extra={"Set-Cookie": "%s=%s%s" % (COOKIE, tok, flags)})
            if path == "/api/alerts/refresh":
                return self.alerts_refresh()
            self.api_guard()
            if path == "/api/logout":
                SESSIONS.pop(self.cookie_token(), None)
                return self.send(200, {"ok": True}, extra={"Set-Cookie": "%s=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0%s" % (COOKIE, "" if os.environ.get("HLP_COOKIE_PLAIN") else "; Secure")})
            if path == "/api/background/theme":
                tb = json.loads(self.read_body(1 << 20) or b"{}")
                if not isinstance(tb, dict):
                    raise Fail("The request is not valid.")
                return self.send(200, theme_picture(tb))
            if path == "/api/background/upload":
                data = self.read_body(MAX_UPLOAD)
                with LOCK:
                    res = api_bg_upload(data)
                return self.send(200, res)
            if path in ("/api/upload/photo", "/api/upload/song"):
                self.body_left = -1
                return self.send(200, api_upload_stream(self, path.rsplit("/", 1)[1], urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)))
            body = json.loads(self.read_body(1 << 20) or b"{}")
            if not isinstance(body, dict):
                raise Fail("The request is not valid.")
            if path == "/api/upload/immich-key":
                return self.send(200, dict(api_upload_key(body), ok=True))
            if path == "/api/updates/start":
                return self.send(200, api_updates_start(body))
            if path == "/api/backup/save":
                return self.send(200, api_backup_save(body))
            if path == "/api/backup/dltoken":
                return self.send(200, api_backup_dltoken(body, self.cookie_token()))
            if path in ("/api/backup/run", "/api/backup/dry", "/api/backup/restore"):
                return self.send(200, api_backup_job_start(path.rsplit("/", 1)[1], body))
            if path in ("/api/backup/delete", "/api/backup/toggle", "/api/backup/sshkey", "/api/backup/sshtest", "/api/backup/cloud-add"):
                return self.send(200, dict(api_backup_task(path.rsplit("/", 1)[1], body), ok=True))
            if path == "/api/drives/abort":
                return self.send(200, dict(api_drives_abort(), ok=True))
            if path in ("/api/drives/add", "/api/drives/wipe", "/api/drives/disconnect", "/api/drives/move", "/api/drives/setup", "/api/drives/bootadd", "/api/drives/appsfix", "/api/drives/moveboot", "/api/drives/movefolders"):
                return self.send(200, api_drives_job_start(path.rsplit("/", 1)[1], body))
            if path in ("/api/drives/rename", "/api/drives/sleep", "/api/drives/wake", "/api/drives/remount", "/api/drives/folderpin"):
                return self.send(200, dict(api_drives_do(path.rsplit("/", 1)[1], body), ok=True))
            if path == "/api/location/search":
                return self.send(200, dict(api_location_search(body), ok=True))
            routes = {"/api/location": api_location_save, "/api/look": api_look_save, "/api/look/css": api_look_css, "/api/look/reset": api_look_reset, "/api/background": api_bg_save,
                      "/api/layout": api_layout_save, "/api/card": api_card, "/api/arrange": api_arrange, "/api/hlcards/restore": api_hl_restore, "/api/mytheme": api_mytheme, "/api/schedule": api_schedule, "/api/link": api_link, "/api/group": api_group,
                      "/api/undo": lambda b: {"undone": undo()}}
            fn = routes.get(path)
            if not fn:
                raise Fail("Unknown address.", 404)
            LOCAL.changed = None
            with LOCK:
                res = fn(body)
            res = dict(res, ok=True)
            if LOCAL.changed is not None and path != "/api/undo":
                res["changed"] = LOCAL.changed
            self.send(200, res)
        except Fail as e:
            self.fail(e)
        except ValueError:
            self.send(400, {"error": "The request is not valid."})
        except (TimeoutError, ConnectionError):
            self.close_connection = True  # a client that stalled or vanished mid-request: close quietly, no answer
        except Exception as e:
            sys.stderr.write("error: %r\n" % (e,))
            self.send(500, {"error": "An internal error occurred in the panel. See:  journalctl -u homelab-panel -n 30"})


