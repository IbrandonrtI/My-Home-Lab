"""The hover box of the Docker charts must stay readable on every theme: solid, in the pop-up colors, never in the card glass color (a light glass with light text was unreadable)."""
import os
import re
import unittest

import helpers


class DockTooltipTests(unittest.TestCase):
    def rule(self):
        with open(os.path.join(helpers.ROOT, "homepage-config", "custom.css"), encoding="utf-8") as f:
            css = f.read()
        m = re.search(r"#hl-docker \.hl-dk-tip \{([^}]*)\}", css)
        self.assertTrue(m, "the tooltip rule is missing")
        return m.group(1)

    def test_background_is_solid_and_not_the_card_glass(self):
        body = self.rule()
        self.assertNotIn("--lk-glass", body)
        self.assertIn("--lk-popbase", body)

    def test_text_uses_the_pop_up_text_color(self):
        self.assertIn("color: var(--lk-hi", self.rule())

    def test_names_use_the_pop_up_muted_color(self):
        with open(os.path.join(helpers.ROOT, "homepage-config", "custom.css"), encoding="utf-8") as f:
            self.assertRegex(f.read(), r"\.hl-dk-tip \.hl-dk-row span[^{]*\{ color: var\(--lk-popmuted")


if __name__ == "__main__":
    unittest.main()
