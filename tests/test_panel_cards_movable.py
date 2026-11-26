"""Navidrome and Continue Watching can be moved between groups on the Cards screen. Navidrome cannot be removed, because a refresh would put it back."""
import os
import unittest

import helpers

SERVICES = """- Network & DNS:

    - AdGuard Home:
        id: adguard-card
        href: http://192.168.1.5:3000

- Media & Entertainment:

    - Navidrome:
        id: navidrome-card
        href: http://192.168.1.5:1009
        icon: navidrome.svg

    - Jellyfin:
        id: jellyfin-card
        href: http://192.168.1.5:1012

    - Continue Watching:
        id: watching-card
        href: http://192.168.1.5:1012
        icon: mdi-play-circle-outline
        description: Pick up where you left off

    - Downloaders:
        id: downloaders-card
        icon: mdi-download-multiple
        description: Apps that find and download movies, music and videos

- Customize:

    - Customize:
        id: customize-card
        href: http://192.168.1.5:9000
"""


class CardsMovable(unittest.TestCase):
    def setUp(self):
        self.p = helpers.panel()
        os.makedirs(os.path.dirname(self.p.SERVICES), exist_ok=True)
        with open(self.p.SERVICES, "w") as f:
            f.write(SERVICES)

    def card(self, name):
        lines = self.p.read(self.p.SERVICES).split("\n")
        for g in self.p.services_parse(lines):
            for c in g["cards"]:
                if c["name"] == name:
                    return g, self.p.card_public(lines, c, g["name"])
        return None, None

    def test_what_the_screen_is_told_about_each_card(self):
        _, nav = self.card("Navidrome")
        _, watch = self.card("Continue Watching")
        _, custom = self.card("Customize")
        self.assertFalse(nav["locked"])
        self.assertTrue(nav["fixed"])
        self.assertFalse(watch["locked"] or watch["fixed"])
        self.assertTrue(custom["locked"])

    def test_the_continue_watching_address_can_be_changed(self):
        _, watch = self.card("Continue Watching")
        self.assertFalse(watch["managed"])

    def test_navidrome_moves_to_another_group(self):
        self.p.api_card({"op": "move", "group": "Media & Entertainment", "name": "Navidrome", "to": "Network & DNS"})
        self.assertEqual(self.card("Navidrome")[0]["name"], "Network & DNS")

    def test_continue_watching_moves_to_another_group(self):
        self.p.api_card({"op": "move", "group": "Media & Entertainment", "name": "Continue Watching", "to": "Network & DNS"})
        self.assertEqual(self.card("Continue Watching")[0]["name"], "Network & DNS")

    def test_continue_watching_moves_up_inside_its_group(self):
        self.p.api_card({"op": "move", "group": "Media & Entertainment", "name": "Continue Watching", "to": "Media & Entertainment", "before": "Navidrome"})
        g, _ = self.card("Continue Watching")
        self.assertEqual([c["name"] for c in g["cards"]], ["Continue Watching", "Navidrome", "Jellyfin", "Downloaders"])

    def test_navidrome_cannot_be_removed_but_continue_watching_can(self):
        with self.assertRaises(self.p.Fail):
            self.p.api_card({"op": "remove", "group": "Media & Entertainment", "name": "Navidrome"})
        self.assertIsNotNone(self.card("Navidrome")[0])
        self.p.api_card({"op": "remove", "group": "Media & Entertainment", "name": "Continue Watching"})
        self.assertIsNone(self.card("Continue Watching")[0])

    def test_the_downloaders_row_is_a_plain_card_that_can_be_moved_and_removed(self):
        _, row = self.card("Downloaders")
        self.assertFalse(row["managed"] or row["locked"] or row["fixed"])
        self.p.api_card({"op": "move", "group": "Media & Entertainment", "name": "Downloaders", "to": "Network & DNS"})
        self.assertEqual(self.card("Downloaders")[0]["name"], "Network & DNS")
        self.p.api_card({"op": "remove", "group": "Network & DNS", "name": "Downloaders"})
        self.assertIsNone(self.card("Downloaders")[0])

    def test_the_customize_card_still_cannot_be_moved(self):
        with self.assertRaises(self.p.Fail):
            self.p.api_card({"op": "move", "group": "Customize", "name": "Customize", "to": "Network & DNS"})


if __name__ == "__main__":
    unittest.main()
