"""Checks that two files stay in agreement, or that something stays true across the whole repository.

These catch the kind of mistake no single-file check can: a number copied into two places, a step that needs a step that does not exist,
a stack file that nothing installs.
"""
import glob
import os
import re
import shutil
import subprocess
import unittest

import helpers

ROOT = helpers.ROOT

# Images allowed to follow a moving tag. Add to this list only on purpose: a pinned version is what makes an update something you choose.
FLOATING_IMAGES = {"henriquesebastiao/downtify:latest", "ghcr.io/alexta69/metube:latest", "netdata/netdata:stable", "redis:alpine",
                   "ghcr.io/immich-app/immich-server:release", "ghcr.io/immich-app/immich-machine-learning:release",
                   "ghcr.io/seerr-team/seerr:latest", "lscr.io/linuxserver/radarr:latest", "lscr.io/linuxserver/prowlarr:latest", "lscr.io/linuxserver/qbittorrent:latest"}

try:
    import yaml
except ImportError:
    yaml = None


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


class NoDuplicateKeysLoader(yaml.SafeLoader if yaml else object):
    """A YAML loader that refuses a repeated key, which plain YAML would silently accept (the last one wins)."""


if yaml:
    def _construct(loader, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.YAMLError("repeated key %r on line %d" % (key, key_node.start_mark.line + 1))
            seen.add(key)
        return yaml.SafeLoader.construct_mapping(loader, node, deep)
    NoDuplicateKeysLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct)


class DashboardFrameWidth(unittest.TestCase):
    def test_the_jellyfin_box_width_is_the_same_in_the_page_script_and_in_the_installer_css(self):
        js = int(re.search(r"var JF_WIDE = (\d+);", read("homepage-config/custom.js")).group(1))
        m = helpers.installer()
        css = int(re.search(r"width: (\d+)px", m.JELLYFIN_BOX_CSS).group(1))
        self.assertEqual(js, css, "custom.js draws the Jellyfin box at JF_WIDE pixels and the installer's CSS rule hides the slideshow at that exact width")


class InstallerSteps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = helpers.installer()

    def test_step_ids_are_unique(self):
        ids = [s.id for s in self.m.STEPS]
        self.assertEqual(len(ids), len(set(ids)), sorted({i for i in ids if ids.count(i) > 1}))

    def test_every_needed_step_exists_and_there_is_no_loop(self):
        by_id = self.m.BY_ID
        for s in self.m.STEPS:
            for n in s.needs:
                self.assertIn(n, by_id, "%s needs %s, which does not exist" % (s.id, n))
        state = {}

        def visit(s, path):
            if state.get(s.id) == 2:
                return
            self.assertNotEqual(state.get(s.id), 1, "a loop of needs: " + " -> ".join(path + [s.id]))
            state[s.id] = 1
            for n in s.needs:
                visit(by_id[n], path + [s.id])
            state[s.id] = 2
        for s in self.m.STEPS:
            visit(s, [])

    def test_every_step_has_a_title_and_a_known_group(self):
        for s in self.m.STEPS:
            self.assertTrue(s.title.strip(), s.id)
            self.assertIn(s.group, self.m.GROUPS, s.id)


class Stacks(unittest.TestCase):
    def files(self):
        return sorted(glob.glob(os.path.join(ROOT, "stacks", "*.yaml")))

    @unittest.skipUnless(yaml, "PyYAML is not installed")
    def test_stack_and_homepage_files_are_valid_yaml_without_repeated_keys(self):
        for path in self.files() + sorted(glob.glob(os.path.join(ROOT, "homepage-config", "*.yaml"))):
            with open(path, encoding="utf-8") as f:
                try:
                    yaml.load(f, NoDuplicateKeysLoader)
                except yaml.YAMLError as e:
                    self.fail("%s: %s" % (os.path.relpath(path, ROOT), e))

    def test_every_stack_file_is_used_by_the_installer(self):
        installer_source = read("installer/homelab-setup")
        for path in self.files():
            self.assertIn(os.path.basename(path), installer_source, "%s is not mentioned by the installer" % os.path.basename(path))

    def test_every_stack_the_installer_names_exists(self):
        for name in set(re.findall(r"stacks/([A-Za-z0-9_.-]+\.yaml)", read("installer/homelab-setup"))):
            self.assertTrue(os.path.exists(os.path.join(ROOT, "stacks", name)), name)

    def test_images_are_pinned_unless_listed(self):
        for path in self.files():
            for image in re.findall(r"^\s*image:\s*(\S+)", read(os.path.relpath(path, ROOT)), flags=re.M):
                image = re.sub(r"\$\{\w+:-([^}]*)\}", r"\1", image)   # a version kept in a variable: its default counts
                if image in FLOATING_IMAGES:
                    continue
                name = image.split("@")[0]
                tag = name.rsplit(":", 1)[1] if ":" in name.rsplit("/", 1)[-1] else ""
                self.assertTrue(re.search(r"\d", tag) and tag != "latest", "%s uses %s without a fixed version (add it to FLOATING_IMAGES only if that is on purpose)" % (os.path.basename(path), image))


class PageScripts(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node is not installed")
    def test_continue_watching_files_and_schedule_agree(self):
        """The dashboard reads two files that homelab-stats writes; Homepage only serves a file that existed when it started, so the installer must create both, and cron must run the command every minute."""
        js, setup, stats = read("homepage-config/custom.js"), read("installer/homelab-setup"), read("scripts/homelab-stats")
        for name in ("watching.json", "watching-posters.json"):
            self.assertIn("/images/" + name, js)
            self.assertIn('"%s"' % name, setup, name + " is not among the files created before Homepage starts")
            self.assertIn(name, stats)
        self.assertIn('"watching"', stats)
        self.assertIn('("homelab-stats watching", "* * * * * /usr/local/sbin/homelab-stats watching >/dev/null 2>&1")', setup)

    def test_the_continue_watching_card_id_matches_everywhere(self):
        """The installer writes the card, the dashboard script fills it, and the stylesheet sizes it, all by the same id."""
        js, css, setup = read("homepage-config/custom.js"), read("homepage-config/custom.css"), read("installer/homelab-setup")
        self.assertIn('WATCHING_ID = "watching-card"', setup)
        self.assertIn('getElementById("watching-card")', js)
        self.assertRegex(js, r"\(customize\|linkedit\|terminal\|navidrome\|watching\|downloaders\)-card")
        self.assertIn("li#watching-card", css)

    def test_the_downloaders_dropdown_names_the_same_cards_everywhere(self):
        """The installer groups six cards under the Downloaders card; the dashboard script hides and shows the same six by id, and the stylesheet sizes the row by its id."""
        js, css, setup, panel = read("homepage-config/custom.js"), read("homepage-config/custom.css"), read("installer/homelab-setup"), read("scripts/homelab-panel")
        installer = re.search(r"DOWNLOADERS_MEMBERS = \(([^)]*)\)", setup).group(1)
        script = re.search(r"var DL_APPS = \[([^\]]*)\]", js).group(1)
        self.assertEqual(re.findall(r'"([^"]+)"', installer), re.findall(r'"([^"]+)"', script))
        self.assertEqual(len(re.findall(r'"([^"]+)"', script)), 6)
        self.assertIn('DOWNLOADERS_ID = "downloaders-card"', setup)
        self.assertIn('getElementById("downloaders-card")', js)
        self.assertIn("li#downloaders-card", css)
        self.assertIn('("watching-card", "downloaders-card")', panel)
        stacks = read("stacks/requests.yaml") + read("stacks/music-downloader.yaml")
        for card in re.findall(r'"([^"]+)"', script):
            self.assertRegex(stacks, r"container_name:\s*%s\s" % card[:-len("-card")], "the card %s should belong to a container of the same name" % card)

    def test_the_browser_scripts_parse(self):
        for rel in ("homepage-config/custom.js", "panel/ui/app.js"):
            r = subprocess.run(["node", "--check", os.path.join(ROOT, rel)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, "%s: %s" % (rel, r.stderr))


if __name__ == "__main__":
    unittest.main()
