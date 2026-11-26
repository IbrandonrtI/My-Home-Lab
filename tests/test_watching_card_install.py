"""The Continue Watching card: refresh adds it once, under the Jellyfin card, and puts Jellyfin right under Navidrome so the order on the Cards screen matches what the dashboard shows.
A card the person removes later is not added again, and Navidrome is no longer forced to the top of its group."""
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

    - Metube:
        id: metube-card
        href: http://192.168.1.5:1010

    - Downtify:
        id: downtify-card
        href: http://192.168.1.5:1011

    - Jellyfin:
        id: jellyfin-card
        href: https://homelab.example.ts.net:1012
        widget:
          type: jellyfin
          key: abc

- Files & Photos:

    - Immich:
        id: immich-card
        href: http://192.168.1.5:2283
"""


def ids(text):
    return [l.split("id:")[1].strip() for l in text.split("\n") if l.strip().startswith("id:")]


class WatchingCardText(unittest.TestCase):
    def setUp(self):
        self.m = helpers.installer()

    def test_jellyfin_moves_up_under_navidrome(self):
        new = self.m.card_moved_after(SERVICES, "jellyfin-card", "navidrome-card")
        self.assertEqual(ids(new), ["adguard-card", "navidrome-card", "jellyfin-card", "metube-card", "downtify-card", "immich-card"])
        self.assertNotIn("\n\n\n", new)
        self.assertIn("type: jellyfin\n          key: abc", new)

    def test_a_card_already_in_place_is_left_alone(self):
        once = self.m.card_moved_after(SERVICES, "jellyfin-card", "navidrome-card")
        self.assertEqual(self.m.card_moved_after(once, "jellyfin-card", "navidrome-card"), once)

    def test_cards_in_different_groups_are_not_moved(self):
        self.assertEqual(self.m.card_moved_after(SERVICES, "immich-card", "navidrome-card"), SERVICES)
        self.assertEqual(self.m.card_moved_after(SERVICES, "nothing-card", "navidrome-card"), SERVICES)

    def test_the_new_card_goes_right_under_jellyfin_with_its_link(self):
        moved = self.m.card_moved_after(SERVICES, "jellyfin-card", "navidrome-card")
        new = self.m.card_added_after(moved, "jellyfin-card", self.m.watching_card_lines(self.m.card_href(moved, "jellyfin-card")))
        self.assertEqual(ids(new), ["adguard-card", "navidrome-card", "jellyfin-card", "watching-card", "metube-card", "downtify-card", "immich-card"])
        self.assertIn("    - Continue Watching:\n        id: watching-card\n        href: https://homelab.example.ts.net:1012\n", new)
        self.assertEqual(new.count("- Files & Photos:"), 1)

    def test_the_card_has_no_link_line_when_jellyfin_has_none(self):
        self.assertNotIn("href", "\n".join(self.m.watching_card_lines("")))


class WatchingCardStep(unittest.TestCase):
    def setUp(self):
        self.m = helpers.installer()
        self.m.Ctx.home = "/home/test"
        self.m.Ctx.uid = self.m.Ctx.gid = os.getuid()
        self.path = self.m.hp_path("services.yaml")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        mark = self.m.P(self.m.WATCHING_MARK)
        if os.path.exists(mark):
            os.remove(mark)
        self.step = self.m.BY_ID["watching-card"]

    def put(self, text):
        with open(self.path, "w") as f:
            f.write(text)

    def get(self):
        with open(self.path) as f:
            return f.read()

    def test_an_older_install_gets_the_card_once(self):
        self.put(SERVICES)
        self.assertEqual(self.step.probe(), "todo")
        self.step.run()
        self.assertEqual(ids(self.get()), ["adguard-card", "navidrome-card", "jellyfin-card", "watching-card", "metube-card", "downtify-card", "immich-card"])
        self.assertEqual(self.step.probe(), "done")
        self.assertTrue(os.path.exists(self.m.P(self.m.WATCHING_MARK)))

    def test_a_card_the_person_removed_stays_removed(self):
        self.put(SERVICES)
        self.step.run()
        lines = self.get().split("\n")
        start = lines.index("    - Continue Watching:")
        self.put("\n".join(lines[:start] + lines[start + 6:]))
        self.assertNotIn("watching-card", self.get())
        self.assertEqual(self.step.probe(), "done")

    def test_running_the_step_twice_adds_one_card(self):
        self.put(SERVICES)
        self.step.run()
        self.step.run()
        self.assertEqual(self.get().count("id: watching-card"), 1)

    def test_nothing_happens_before_jellyfin_has_a_card(self):
        self.put(SERVICES.replace("jellyfin-card", "other-card"))
        self.assertEqual(self.step.probe(), "done")
        self.assertFalse(os.path.exists(self.m.P(self.m.WATCHING_MARK)))

    def test_navidrome_is_not_forced_to_the_top_any_more(self):
        self.assertFalse(hasattr(self.m, "card_to_top"))
        self.assertFalse(hasattr(self.m, "navidrome_card_first"))


if __name__ == "__main__":
    unittest.main()
