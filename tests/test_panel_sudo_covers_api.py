"""Every drives command the control panel can send has to be on the sudo list the installer writes, or the panel gets "interactive authentication is required"."""
import os
import re
import unittest

import helpers


class PanelSudoCoversApiTests(unittest.TestCase):
    def test_every_drives_route_is_allowed(self):
        hls = helpers.installer()
        allowed = set(hls.PANEL_SUDO_EXACT) | set(hls.PANEL_SUDO_WITH_WORDS)
        src = open(os.path.join(helpers.ROOT, "scripts", "homelab-panel")).read()
        routes = set(re.findall(r'/api/drives/([a-z]+)"', src)) - {"job", "state"}
        self.assertGreater(len(routes), 10, "the route scan found too little: " + ", ".join(sorted(routes)))
        missing = sorted(routes - allowed)
        self.assertEqual(missing, [], "the panel sends these to the drives tool, but the sudo rule does not allow them: " + ", ".join(missing))

    def test_the_rule_lists_each_new_folder_command(self):
        hls = helpers.installer()
        hls.Ctx.user = "brandon"
        text = hls.panel_sudoers_text()
        for w in ("folders", "folderpin", "movefolders"):
            self.assertIn("/usr/local/sbin/drives panel %s *" % w, text)


if __name__ == "__main__":
    unittest.main()
