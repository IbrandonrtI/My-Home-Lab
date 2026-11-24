"""Order is changed by dragging (or the arrow keys on a handle), never with up and down buttons: Layout, Cards, Links and the quick launch row."""
import os
import unittest

import helpers


def read(*parts):
    with open(os.path.join(helpers.ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class ReorderTests(unittest.TestCase):
    def test_the_panel_has_no_move_buttons(self):
        js = read("panel", "ui", "app.js")
        for text in ('" up"', '" down"', "Move the tab left", "Move the tab right"):
            self.assertNotIn(text, js)

    def test_the_quick_launch_row_has_no_move_buttons(self):
        js = read("homepage-config", "custom.js")
        self.assertNotIn('" earlier"', js)
        self.assertNotIn('" later"', js)

    def test_every_list_has_a_handle_that_takes_arrow_keys(self):
        js = read("panel", "ui", "app.js")
        self.assertEqual(js.count('onkeydown: ev => { if (ev.key === "Arrow'), 3)
        self.assertIn('grip.addEventListener("keydown"', read("homepage-config", "custom.js"))

    def test_cards_can_be_dragged(self):
        js = read("panel", "ui", "app.js")
        self.assertIn("async function dropCard", js)
        self.assertNotIn("if (!isCards) {\n      const after", js)


if __name__ == "__main__":
    unittest.main()
