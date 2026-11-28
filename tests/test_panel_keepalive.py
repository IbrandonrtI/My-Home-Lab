"""A refused POST must not leave its body on the connection: the browser reuses the connection, and the next call (the login after "Please log in again") would fail."""
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

import helpers

PASSWORD = "test-password-123"


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class RefusedPostsKeepTheConnectionUsable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="hlp-keepalive-")
        hp = os.path.join(cls.dir, "homepage-config")
        shutil.copytree(os.path.join(helpers.ROOT, "homepage-config"), hp, ignore=shutil.ignore_patterns("images", "__pycache__"))
        cls.port = free_port()
        env = dict(os.environ, HLP_HOME=cls.dir, HOMELAB_HOMEPAGE_DIR=hp, HLP_STATE=os.path.join(cls.dir, "state"), HLP_UI=os.path.join(helpers.ROOT, "panel", "ui"),
                   HLP_PORT=str(cls.port), HLP_NO_DOCKER="1", HLP_COOKIE_PLAIN="1", HLP_SHIPPED=os.devnull, HLP_DRIVES=os.path.join(helpers.ROOT, "scripts", "drives"))
        os.makedirs(env["HLP_STATE"], exist_ok=True)
        script = os.path.join(helpers.ROOT, "scripts", "homelab-panel")
        subprocess.run([sys.executable, script, "set-password", "--stdin"], input=PASSWORD + "\n", text=True, env=env, check=True, capture_output=True)
        cls.server = subprocess.Popen([sys.executable, script, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/api/session" % cls.port, timeout=1).read()
                break
            except OSError:
                time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        cls.server.wait(10)
        shutil.rmtree(cls.dir, True)

    def connection(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        self.addCleanup(conn.close)
        return conn

    def post(self, conn, path, body):
        raw = json.dumps(body)
        conn.request("POST", path, body=raw, headers={"X-Panel": "1", "Content-Type": "application/json", "Content-Length": str(len(raw))})
        res = conn.getresponse()
        return res.status, json.loads(res.read() or b"{}")

    def test_login_works_on_the_same_connection_right_after_a_save_was_refused(self):
        conn = self.connection()
        status, _ = self.post(conn, "/api/arrange", {"tab": "Home", "groups": [{"name": "Media & Entertainment", "cards": ["Jellyfin", "Navidrome"]}]})
        self.assertEqual(status, 401)
        status, body = self.post(conn, "/api/login", {"password": PASSWORD})
        self.assertEqual((status, body.get("ok")), (200, True))

    def test_a_refusal_of_a_big_body_closes_the_connection_instead(self):
        conn = self.connection()
        raw = json.dumps({"pad": "x" * (2 << 20)})
        conn.request("POST", "/api/arrange", body=raw, headers={"X-Panel": "1", "Content-Type": "application/json"})
        res = conn.getresponse()
        res.read()
        self.assertEqual(res.status, 401)
        self.assertEqual(res.getheader("Connection"), "close")

    def test_a_request_without_a_body_still_keeps_the_connection_open(self):
        conn = self.connection()
        conn.request("GET", "/api/session")
        res = conn.getresponse()
        res.read()
        self.assertNotEqual(res.getheader("Connection"), "close")
        conn.request("GET", "/api/session")
        self.assertEqual(conn.getresponse().status, 200)


if __name__ == "__main__":
    unittest.main()
