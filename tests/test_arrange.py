"""Arranging the dashboard on the page itself: cards inside a group, cards between groups and the order of the groups, saved as one change that Undo takes back in one step."""
import os
import unittest

import helpers

SERVICES = """- Network & DNS:

    - Tailscale:
        id: tailscale-card
        href: http://192.168.1.5:1
    - AdGuard Home:
        id: adguard-card
        href: http://192.168.1.5:2
    - Speedtest:
        id: speedtest-card
        href: http://192.168.1.5:3

- Files & Photos:

    - Immich:
        id: immich-card
        href: http://192.168.1.5:4
    - Nextcloud:
        id: nextcloud-card
        href: http://192.168.1.5:5

- Media & Entertainment:

    - Navidrome:
        id: navidrome-card
        href: http://192.168.1.5:6
    - Jellyfin:
        id: jellyfin-card
        href: http://192.168.1.5:7

- Customize:

    - Control panel:
        id: customize-card
        href: http://192.168.1.5:8
"""

SETTINGS = """title: Home Lab
layout:
  Network & DNS:
    tab: Home
    icon: mdi-lan
  Files & Photos:
    tab: Home
    icon: mdi-folder-multiple-image
  Media & Entertainment:
    tab: Home
    icon: mdi-movie-open
    style: row
    columns: 2
  Customize:
    tab: Customize
    icon: mdi-tune
"""


def g(name, *cards):
    return {"name": name, "cards": list(cards)}


class Arrange(unittest.TestCase):
    def setUp(self):
        self.p = helpers.panel()
        os.makedirs(os.path.dirname(self.p.SERVICES), exist_ok=True)
        for path, text in ((self.p.SERVICES, SERVICES), (self.p.SETTINGS, SETTINGS), (self.p.CSS, "")):
            with open(path, "w") as f:
                f.write(text)

    def cards(self):
        return {x["name"]: [c["name"] for c in x["cards"]] for x in self.p.services_parse(self.p.read(self.p.SERVICES).split("\n"))}

    def groups(self):
        return [x["name"] for x in self.p.layout_groups(self.p.read(self.p.SETTINGS))]

    def arrange(self, *groups, tab="Home"):
        return self.p.api_arrange({"tab": tab, "groups": list(groups)})

    def test_a_card_moves_to_the_front_of_its_group(self):
        self.arrange(g("Network & DNS", "Speedtest", "Tailscale", "AdGuard Home"), g("Files & Photos", "Immich", "Nextcloud"), g("Media & Entertainment", "Navidrome", "Jellyfin"))
        self.assertEqual(self.cards()["Network & DNS"], ["Speedtest", "Tailscale", "AdGuard Home"])
        self.assertEqual(self.cards()["Files & Photos"], ["Immich", "Nextcloud"])

    def test_a_card_moves_into_another_group_at_the_place_it_was_dropped(self):
        self.arrange(g("Network & DNS", "Tailscale", "Speedtest"), g("Files & Photos", "Immich", "AdGuard Home", "Nextcloud"), g("Media & Entertainment", "Navidrome", "Jellyfin"))
        self.assertEqual(self.cards()["Network & DNS"], ["Tailscale", "Speedtest"])
        self.assertEqual(self.cards()["Files & Photos"], ["Immich", "AdGuard Home", "Nextcloud"])

    def test_an_arrangement_that_changes_nothing_writes_nothing(self):
        before = (self.p.read(self.p.SERVICES), self.p.read(self.p.SETTINGS))
        self.arrange(g("Network & DNS", "Tailscale", "AdGuard Home", "Speedtest"), g("Files & Photos", "Immich", "Nextcloud"), g("Media & Entertainment", "Navidrome", "Jellyfin"))
        self.assertEqual((self.p.read(self.p.SERVICES), self.p.read(self.p.SETTINGS)), before)

    def test_groups_change_order_on_their_own_tab_and_keep_their_settings(self):
        self.arrange(g("Media & Entertainment", "Navidrome", "Jellyfin"), g("Network & DNS", "Tailscale", "AdGuard Home", "Speedtest"), g("Files & Photos", "Immich", "Nextcloud"))
        self.assertEqual(self.groups(), ["Media & Entertainment", "Network & DNS", "Files & Photos", "Customize"])
        by = {x["name"]: x["props"] for x in self.p.layout_groups(self.p.read(self.p.SETTINGS))}
        self.assertEqual(by["Media & Entertainment"], {"tab": "Home", "icon": "mdi-movie-open", "style": "row", "columns": "2"})
        self.assertEqual(by["Customize"]["tab"], "Customize")

    def test_two_groups_can_swap_all_their_cards_without_losing_either_group(self):
        self.arrange(g("Network & DNS", "Immich", "Nextcloud"), g("Files & Photos", "Tailscale", "AdGuard Home", "Speedtest"), g("Media & Entertainment", "Navidrome", "Jellyfin"))
        self.assertEqual(self.cards()["Network & DNS"], ["Immich", "Nextcloud"])
        self.assertEqual(self.cards()["Files & Photos"], ["Tailscale", "AdGuard Home", "Speedtest"])
        by = {x["name"]: x["props"] for x in self.p.layout_groups(self.p.read(self.p.SETTINGS))}
        self.assertEqual(by["Files & Photos"]["icon"], "mdi-folder-multiple-image")

    def test_a_group_left_without_cards_is_removed(self):
        self.arrange(g("Network & DNS", "Tailscale", "AdGuard Home", "Speedtest", "Immich", "Nextcloud"), g("Files & Photos"), g("Media & Entertainment", "Navidrome", "Jellyfin"))
        self.assertNotIn("Files & Photos", self.cards())
        self.assertNotIn("Files & Photos", self.groups())

    def test_one_undo_takes_the_whole_arrangement_back(self):
        before = (self.p.read(self.p.SERVICES), self.p.read(self.p.SETTINGS))
        self.arrange(g("Media & Entertainment", "Navidrome"), g("Network & DNS", "Speedtest", "Tailscale", "AdGuard Home", "Jellyfin"), g("Files & Photos", "Nextcloud", "Immich"))
        self.assertNotEqual((self.p.read(self.p.SERVICES), self.p.read(self.p.SETTINGS)), before)
        self.assertEqual(self.p.undo(), "Dashboard arranged")
        self.assertEqual((self.p.read(self.p.SERVICES), self.p.read(self.p.SETTINGS)), before)

    def refused(self, *groups, tab="Home"):
        before = (self.p.read(self.p.SERVICES), self.p.read(self.p.SETTINGS))
        with self.assertRaises(self.p.Fail):
            self.arrange(*groups, tab=tab)
        self.assertEqual((self.p.read(self.p.SERVICES), self.p.read(self.p.SETTINGS)), before)

    def test_a_list_that_does_not_match_the_file_is_refused_and_nothing_is_written(self):
        self.refused(g("Network & DNS", "Tailscale", "AdGuard Home"), g("Files & Photos", "Immich", "Nextcloud"))
        self.refused(g("Network & DNS", "Tailscale", "AdGuard Home", "Speedtest", "Ghost"), g("Files & Photos", "Immich", "Nextcloud"))
        self.refused(g("Network & DNS", "Tailscale", "Tailscale", "AdGuard Home", "Speedtest"), g("Files & Photos", "Immich", "Nextcloud"))

    def test_unknown_and_repeated_groups_are_refused(self):
        self.refused(g("Nowhere", "Tailscale"))
        self.refused(g("Files & Photos", "Immich", "Nextcloud"), g("Files & Photos", "Immich", "Nextcloud"))

    def test_the_panels_own_groups_cannot_be_arranged_here(self):
        self.refused(g("Customize", "Control panel"), tab="Customize")

    def test_the_card_that_belongs_to_the_panel_cannot_be_moved(self):
        self.refused(g("Network & DNS", "Tailscale", "AdGuard Home", "Speedtest", "Control panel"), g("Files & Photos", "Immich", "Nextcloud"), g("Customize"))

    def test_the_route_is_registered(self):
        with open(os.path.join(helpers.ROOT, "src", "homelab-panel", "12_http_handler.py"), encoding="utf-8") as f:
            self.assertIn('"/api/arrange": api_arrange', f.read())


TWO_TABS_SERVICES = """- Library Totals:

    - Jellyfin:
        id: stat-jellyfin
        href: http://192.168.1.5:7

- Music Library:

    - Downtify:
        id: stat-music
        href: http://192.168.1.5:9

- Files & Photos:

    - Immich:
        id: immich-card
        href: http://192.168.1.5:4
    - Nextcloud:
        id: nextcloud-card
        href: http://192.168.1.5:5

- Media & Entertainment:

    - Navidrome:
        id: navidrome-card
        href: http://192.168.1.5:6
    - Jellyfin:
        id: jellyfin-card
        href: http://192.168.1.5:7
    - Downtify:
        id: downtify-card
        href: http://192.168.1.5:9

- Photo Library:

    - Immich:
        id: stat-immich
        href: http://192.168.1.5:4
    - Nextcloud:
        id: stat-nextcloud
        href: http://192.168.1.5:5
"""

TWO_TABS_SETTINGS = """title: Home Lab
layout:
  Library Totals:
    tab: Stats
  Music Library:
    tab: Stats
  Files & Photos:
    tab: Home
  Media & Entertainment:
    tab: Home
  Photo Library:
    tab: Stats
"""


class ArrangeWithSameNamesOnTwoTabs(unittest.TestCase):
    """Jellyfin, Downtify, Immich and Nextcloud each have a card on Home and another one on Stats. Saving one tab must never touch the other."""

    def setUp(self):
        self.p = helpers.panel()
        os.makedirs(os.path.dirname(self.p.SERVICES), exist_ok=True)
        for path, text in ((self.p.SERVICES, TWO_TABS_SERVICES), (self.p.SETTINGS, TWO_TABS_SETTINGS), (self.p.CSS, "")):
            with open(path, "w") as f:
                f.write(text)

    def cards(self):
        out = {}
        for x in self.p.services_parse(self.p.read(self.p.SERVICES).split("\n")):
            lines = self.p.read(self.p.SERVICES).split("\n")
            out[x["name"]] = [(c["name"], self.p.card_fields(lines, c).get("id")) for c in x["cards"]]
        return out

    def test_saving_home_leaves_the_cards_of_the_stats_tab_alone(self):
        self.p.api_arrange({"tab": "Home", "groups": [g("Files & Photos", "Immich", "Nextcloud"), g("Media & Entertainment", "Jellyfin", "Navidrome", "Downtify")]})
        c = self.cards()
        self.assertEqual(c["Library Totals"], [("Jellyfin", "stat-jellyfin")])
        self.assertEqual(c["Photo Library"], [("Immich", "stat-immich"), ("Nextcloud", "stat-nextcloud")])
        self.assertEqual(c["Music Library"], [("Downtify", "stat-music")])
        self.assertEqual(c["Media & Entertainment"], [("Jellyfin", "jellyfin-card"), ("Navidrome", "navidrome-card"), ("Downtify", "downtify-card")])

    def test_saving_the_stats_tab_leaves_the_cards_of_home_alone(self):
        self.p.api_arrange({"tab": "Stats", "groups": [g("Library Totals", "Jellyfin"), g("Music Library", "Downtify"), g("Photo Library", "Nextcloud", "Immich")]})
        c = self.cards()
        self.assertEqual(c["Photo Library"], [("Nextcloud", "stat-nextcloud"), ("Immich", "stat-immich")])
        self.assertEqual(c["Files & Photos"], [("Immich", "immich-card"), ("Nextcloud", "nextcloud-card")])
        self.assertEqual(c["Media & Entertainment"], [("Navidrome", "navidrome-card"), ("Jellyfin", "jellyfin-card"), ("Downtify", "downtify-card")])

    def test_moving_a_group_on_home_changes_only_the_layout_file(self):
        before = self.p.read(self.p.SERVICES)
        self.p.api_arrange({"tab": "Home", "groups": [g("Media & Entertainment", "Navidrome", "Jellyfin", "Downtify"), g("Files & Photos", "Immich", "Nextcloud")]})
        self.assertEqual(self.p.read(self.p.SERVICES), before)
        self.assertEqual([x["name"] for x in self.p.layout_groups(self.p.read(self.p.SETTINGS))], ["Library Totals", "Music Library", "Media & Entertainment", "Files & Photos", "Photo Library"])

    def test_a_same_named_card_moves_between_groups_of_the_same_tab_only(self):
        self.p.api_arrange({"tab": "Home", "groups": [g("Files & Photos", "Immich", "Nextcloud", "Jellyfin"), g("Media & Entertainment", "Navidrome", "Downtify")]})
        c = self.cards()
        self.assertEqual(c["Files & Photos"], [("Immich", "immich-card"), ("Nextcloud", "nextcloud-card"), ("Jellyfin", "jellyfin-card")])
        self.assertEqual(c["Library Totals"][0], ("Jellyfin", "stat-jellyfin"))

    def test_only_the_lines_of_the_moved_cards_change(self):
        before = self.p.read(self.p.SERVICES).split("\n")
        self.p.api_arrange({"tab": "Home", "groups": [g("Files & Photos", "Immich", "Nextcloud"), g("Media & Entertainment", "Jellyfin", "Navidrome", "Downtify")]})
        after = self.p.read(self.p.SERVICES).split("\n")
        self.assertEqual(sorted(l for l in before if l.strip()), sorted(l for l in after if l.strip()))


if __name__ == "__main__":
    unittest.main()
