"""Immich and the graphics chip: the stack file the installer writes, when the stack is deployed again, and the setting made in Immich."""
import os
import unittest

import helpers


class ImmichGraphics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = helpers.installer()

    def chip(self, present):
        d = self.m.P("/dev/dri")
        for f in ("renderD128", "card0"):
            try:
                os.remove(d + "/" + f)
            except OSError:
                pass
        if present:
            os.makedirs(d, exist_ok=True)
            for f in ("renderD128", "card0"):
                open(d + "/" + f, "w").close()

    def test_a_machine_without_a_chip_gets_the_file_as_it_is(self):
        self.chip(False)
        plain = self.m.read_file(self.m.repo_file("stacks", "immich.yaml"))
        text = self.m.stack_text("immich")
        self.assertNotIn("/dev/dri", text)
        self.assertNotIn("openvino", text)
        self.assertIn("immich-machine-learning:${IMMICH_VERSION:-release}\n", plain)

    def test_a_machine_with_a_chip_passes_it_to_the_server_and_the_machine_learning(self):
        self.chip(True)
        text = self.m.stack_text("immich")
        self.assertEqual(text.count("/dev/dri:/dev/dri"), 2)
        server = text.split("\n  immich-machine-learning:\n")[0]
        ml = text.split("\n  immich-machine-learning:\n")[1].split("\n  redis:\n")[0]
        self.assertIn("/dev/dri", server)
        self.assertIn("/dev/dri", ml)
        self.assertIn("immich-machine-learning:${IMMICH_VERSION:-release}-openvino", text)
        self.assertIn("immich-server:${IMMICH_VERSION:-release}\n", text, "the server image keeps its plain tag")
        self.assertNotIn("/dev/dri", text.split("\n  redis:\n")[1], "the cache and the database get no device")
        self.chip(False)

    def test_the_changed_file_is_still_valid_yaml_shaped(self):
        self.chip(True)
        text = self.m.stack_text("immich")
        for svc in ("immich-server", "immich-machine-learning"):
            block = text.split("  %s:\n" % svc)[1].split("\n  ")[0:1]
            self.assertTrue(block)
        # every device line sits directly under its service at the same indent as the other keys
        for line in text.splitlines():
            if line.strip() == "devices:":
                self.assertEqual(len(line) - len(line.lstrip()), 4)
        self.chip(False)

    def test_the_stack_is_deployed_again_when_the_file_changed(self):
        step = self.m.BY_ID["stack-immich"]
        self.chip(False)
        self.m.State.data.pop("immich_stack", None)
        self.m.stack_up = lambda name: True
        self.assertEqual(step.probe(), "done", "no chip and nothing saved: leave the running stack alone")
        self.chip(True)
        self.assertEqual(step.probe(), "todo", "a chip appeared: the new file must be deployed")
        self.m.State.data["immich_stack"] = step.stamp()
        self.assertEqual(step.probe(), "done")
        self.chip(False)
        self.assertEqual(step.probe(), "todo", "the file changed back")
        self.m.State.data.pop("immich_stack", None)


class ImmichSetting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = helpers.installer()

    def run_with(self, ffmpeg, put_status=200):
        sent = {}

        def fake_http(method, url, body=None, headers=None, timeout=20, form=None, raw=False):
            if url.endswith("/api/auth/login"):
                return 201, {"accessToken": "tok"}, {}
            if url.endswith("/api/system-config") and method == "GET":
                return 200, {"ffmpeg": dict(ffmpeg), "job": {"x": 1}}, {}
            if url.endswith("/api/system-config") and method == "PUT":
                sent["cfg"] = body
                return put_status, {}, {}
            return 404, None, {}

        old, self.m.http = self.m.http, fake_http
        try:
            ok = self.m.immich_graphics_on("pw")
        finally:
            self.m.http = old
        return ok, sent

    def test_it_switches_conversion_to_quicksync_when_it_is_off(self):
        ok, sent = self.run_with({"accel": "disabled", "accelDecode": False, "crf": 23})
        self.assertTrue(ok)
        self.assertEqual(sent["cfg"]["ffmpeg"], {"accel": "qsv", "accelDecode": True, "crf": 23})
        self.assertEqual(sent["cfg"]["job"], {"x": 1}, "the other settings are sent back unchanged")

    def test_a_choice_made_in_immich_is_kept(self):
        ok, sent = self.run_with({"accel": "vaapi", "accelDecode": True})
        self.assertTrue(ok)
        self.assertEqual(sent, {}, "nothing is written when a method is already chosen")

    def test_a_refused_change_is_reported_and_not_marked_done(self):
        ok, _ = self.run_with({"accel": "disabled"}, put_status=400)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
