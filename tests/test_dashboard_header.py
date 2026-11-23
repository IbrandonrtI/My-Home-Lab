"""The name in the dashboard header and the Docker numbers behind the charts on the Stats tab."""
import os
import shutil
import subprocess
import unittest

import helpers


class HelloName(unittest.TestCase):
    def setUp(self):
        self.panel = helpers.panel()
        self.saved = os.environ.get("HLP_ADMIN")

    def tearDown(self):
        os.environ.pop("HLP_ADMIN", None)
        if self.saved is not None:
            os.environ["HLP_ADMIN"] = self.saved

    def test_installer_name_comes_first(self):
        os.environ["HLP_ADMIN"] = "brandon"
        self.assertEqual(self.panel.hello_default(), "Brandon")

    def test_installer_name_keeps_its_capitals_and_is_cleaned(self):
        os.environ["HLP_ADMIN"] = 'Mc"Dee<x>'
        self.assertEqual(self.panel.hello_default(), "McDeex")

    def test_without_it_the_account_name_is_used(self):
        os.environ.pop("HLP_ADMIN", None)
        self.assertEqual(self.panel.hello_default(), os.path.basename(self.panel.HOME.rstrip("/")).capitalize()[:24])

    def test_unit_file_carries_the_installer_name(self):
        inst = helpers.installer()
        old = inst.Ctx.admin
        try:
            inst.Ctx.admin = "Brandon"
            self.assertIn('Environment="HLP_ADMIN=Brandon"', inst.panel_unit_text())
            inst.Ctx.admin = ""
            self.assertNotIn("HLP_ADMIN", inst.panel_unit_text())
            inst.Ctx.admin = 'a"b\nExecStart=/bin/sh'
            self.assertEqual(inst.panel_unit_text().count("ExecStart="), 1)
        finally:
            inst.Ctx.admin = old


class DockerNumbers(unittest.TestCase):
    def setUp(self):
        self.panel = helpers.panel()

    def test_sizes(self):
        b = self.panel.docker_bytes
        self.assertEqual(b("1.5GiB"), 1610612736)
        self.assertEqual(b("312kB"), 312000)
        self.assertEqual(b("120MiB"), 125829120)
        self.assertEqual(b("--"), 0)
        self.assertEqual(b(None), 0)

    def test_parse_divides_cpu_by_the_cores(self):
        raw = "\n".join([
            '{"Name":"jellyfin","CPUPerc":"80.00%","MemUsage":"1.5GiB / 15GiB"}',
            '{"Name":"navidrome","CPUPerc":"--","MemUsage":"120MiB / 15GiB"}',
            "not json at all",
            '{"Name":"","CPUPerc":"1%","MemUsage":"1MiB / 2MiB"}'])
        got = self.panel.docker_parse(raw, 4)
        self.assertEqual(sorted(got), ["jellyfin"])
        self.assertEqual(got["jellyfin"], (20.0, 1610612736))

    def test_a_container_that_starts_later_counts_as_zero_before(self):
        full = {"t": [], "names": [], "cpu": {}, "mem": {}}
        self.panel.docker_push(full, {"a": (1.0, 100)}, 1000)
        self.panel.docker_push(full, {"a": (1.0, 100), "b": (2.0, 200)}, 1060)
        self.assertEqual(full["cpu"]["b"], [0, 2.0])
        self.assertEqual(full["mem"]["a"], [100, 100])

    def test_history_is_capped_and_gone_containers_are_dropped(self):
        full = {"t": [], "names": [], "cpu": {}, "mem": {}}
        self.panel.docker_push(full, {"old": (1.0, 5)}, 0)
        for i in range(self.panel.DOCKER_POINTS + 5):
            self.panel.docker_push(full, {"a": (1.0, 100)}, 60 * (i + 1))
        self.assertEqual(len(full["t"]), self.panel.DOCKER_POINTS)
        self.assertNotIn("old", full["names"])
        self.assertEqual(len(full["cpu"]["a"]), self.panel.DOCKER_POINTS)

    def test_summary_keeps_the_busiest_and_sums_the_rest(self):
        full = {"t": [], "names": [], "cpu": {}, "mem": {}}
        sample = {"c%d" % i: (float(i), 1000 * i) for i in range(1, 10)}
        for k in range(3):
            self.panel.docker_push(full, sample, 60 * k)
        out = self.panel.docker_summary(full, 5, 4)
        self.assertEqual(len(out["names"]), self.panel.DOCKER_TOP + 1)
        self.assertEqual(out["names"][0], "c9")
        self.assertEqual(out["names"][-1], "other")
        self.assertEqual(out["cpu"]["other"][0], 1.0 + 2.0 + 3.0)
        self.assertEqual(out["mem"]["other"][0], 6000)
        self.assertEqual(out["cores"], 4)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class ScriptsParse(unittest.TestCase):
    def test_dashboard_scripts_are_valid_javascript(self):
        for rel in ("homepage-config/custom.js", "panel/ui/app.js"):
            r = subprocess.run(["node", "--check", os.path.join(helpers.ROOT, rel)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, rel + ": " + r.stderr)


if __name__ == "__main__":
    unittest.main()
