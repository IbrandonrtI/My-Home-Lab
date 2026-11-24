"""The reload fix has to be inside the part of custom.css that `homelab-setup refresh` copies to a machine that already has the file."""
import os
import subprocess
import unittest

import helpers

CSS = os.path.join(helpers.ROOT, "homepage-config", "custom.css")


class ReloadCloakShipsTests(unittest.TestCase):
    def test_cloak_is_inside_the_copied_block(self):
        s = open(CSS).read()
        a, z = s.index("/* >>> homelab tabs >>>"), s.index("/* <<< homelab tabs <<< */")
        for needle in ("hl-reveal", "html:not(.hl-ready)"):
            self.assertTrue(a < s.index(needle) < z, needle + " is outside the block, so a refresh would not install it")

    def test_refresh_adds_it_to_an_older_file(self):
        hls = helpers.installer()
        shipped = open(CSS).read()
        try:
            old = subprocess.run(["git", "show", "HEAD:homepage-config/custom.css"], cwd=helpers.ROOT, capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("no git history to take an older file from")
        self.assertNotIn("html:not(.hl-ready)", old)
        self.assertIn("html:not(.hl-ready)", hls.css_tabs_block(old, shipped))


if __name__ == "__main__":
    unittest.main()
