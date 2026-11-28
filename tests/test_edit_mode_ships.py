"""`homelab-setup refresh` only copies named blocks of custom.js and the one `tabs` block of custom.css into the files of a machine that already has them.
Everything the dashboard needs for edit mode has to be inside those blocks, or the Edit button never reaches the server."""
import os
import re
import unittest

import helpers

JS = os.path.join(helpers.ROOT, "homepage-config", "custom.js")
CSS = os.path.join(helpers.ROOT, "homepage-config", "custom.css")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class EditModeShips(unittest.TestCase):
    def test_every_block_of_the_shipped_script_is_copied_by_refresh(self):
        hls = helpers.installer()
        shipped = read(JS)
        names = re.findall(r"/\* >>> homelab (\w+) >>>", shipped)
        self.assertIn("edit", names)
        merged = hls.js_groups_block("var mine = 1;\n", shipped)
        self.assertIn("var mine = 1;", merged)
        for name in names:
            self.assertIn("/* >>> homelab %s >>>" % name, merged, "the block '%s' is not copied by refresh, so it would never reach the server" % name)
            self.assertEqual(merged.count("/* >>> homelab %s >>>" % name), 1)

    def test_a_script_that_already_has_the_edit_block_gets_its_new_version(self):
        hls = helpers.installer()
        shipped = read(JS)
        old = "/* >>> homelab edit >>> */\nold edit code\n/* <<< homelab edit <<< */\n"
        merged = hls.js_groups_block(old, shipped)
        self.assertNotIn("old edit code", merged)
        self.assertIn('"hl-edit-bridge"', merged)

    def test_the_edit_styles_are_inside_the_block_that_refresh_copies(self):
        css = read(CSS)
        a, z = css.index("/* >>> homelab tabs >>>"), css.index("/* <<< homelab tabs <<< */")
        for needle in ("#hl-editbar {", "html.hl-editing", ".hl-grip {", "#hl-edit-bridge"):
            self.assertTrue(a < css.index(needle) < z, needle + " is outside the block, so a refresh would not install it")
        self.assertEqual(re.findall(r"/\* >>> homelab (\w+) >>>", css), ["tabs"])

    def test_refresh_adds_the_edit_styles_to_an_older_file(self):
        hls = helpers.installer()
        live = "body { margin: 0; }\n/* >>> homelab tabs >>> */\nold rules\n/* <<< homelab tabs <<< */\n"
        merged = hls.css_tabs_block(live, read(CSS))
        self.assertIn("body { margin: 0; }", merged)
        self.assertIn("#hl-editbar {", merged)
        self.assertNotIn("old rules", merged)


if __name__ == "__main__":
    unittest.main()
