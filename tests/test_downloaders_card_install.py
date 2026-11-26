"""The Downloaders dropdown: refresh adds its card once under the players and moves Seerr, Radarr, Prowlarr, qBittorrent, MeTube and Downtify right under it, in that order.
A card the person removes later is not added again, and nothing is moved a second time."""
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

    - Jellyfin:
        id: jellyfin-card
        href: https://homelab.example.ts.net:1012
        widget:
          type: jellyfin
          key: abc

    - Continue Watching:
        id: watching-card
        href: https://homelab.example.ts.net:1012

    - Metube:
        id: metube-card
        href: http://192.168.1.5:1010

    - Immich Frame:
        id: frame-card
        href: http://192.168.1.5:2284

    - Downtify:
        id: downtify-card
        href: http://192.168.1.5:1011

    - qBittorrent:
        id: qbittorrent-card
        href: http://192.168.1.5:8080

    - Seerr:
        id: seerr-card
        href: http://192.168.1.5:5055

    - Radarr:
        id: radarr-card
        href: http://192.168.1.5:7878

    - Sonarr:
        id: sonarr-card
        href: http://192.168.1.5:8989

    - Prowlarr:
        id: prowlarr-card
        href: http://192.168.1.5:9696

- Files & Photos:

    - Immich:
        id: immich-card
        href: http://192.168.1.5:2283
"""

UNDER_PLAYERS = ["adguard-card", "navidrome-card", "jellyfin-card", "watching-card", "downloaders-card", "seerr-card", "radarr-card", "sonarr-card", "prowlarr-card",
                 "qbittorrent-card", "metube-card", "downtify-card", "frame-card", "immich-card"]


def ids(text):
    return [l.split("id:")[1].strip() for l in text.split("\n") if l.strip().startswith("id:")]


class DownloadersCardText(unittest.TestCase):
    def setUp(self):
        self.m = helpers.installer()

    def test_the_card_and_the_apps_go_right_under_the_players_in_order(self):
        new = self.m.services_with_downloaders(SERVICES)
        self.assertEqual(ids(new), UNDER_PLAYERS)
        self.assertIn("    - Downloaders:\n        id: downloaders-card\n        icon: mdi-download-multiple\n", new)
        self.assertNotIn("\n\n\n", new)
        self.assertEqual(new.count("- Media & Entertainment:"), 1)
        self.assertIn("type: jellyfin\n          key: abc", new)

    def test_it_goes_under_jellyfin_when_there_is_no_continue_watching_card(self):
        text = self.m.services_without_card(SERVICES, "watching-card")
        self.assertEqual(ids(self.m.services_with_downloaders(text))[:5], ["adguard-card", "navidrome-card", "jellyfin-card", "downloaders-card", "seerr-card"])

    def test_it_goes_under_navidrome_when_there_is_only_navidrome(self):
        text = self.m.services_without_card(self.m.services_without_card(SERVICES, "watching-card"), "jellyfin-card")
        self.assertEqual(ids(self.m.services_with_downloaders(text))[:4], ["adguard-card", "navidrome-card", "downloaders-card", "seerr-card"])

    def test_apps_that_are_not_installed_are_skipped(self):
        text = SERVICES
        for gone in ("seerr-card", "radarr-card", "sonarr-card", "prowlarr-card", "qbittorrent-card"):
            text = self.m.services_without_card(text, gone)
        self.assertEqual(ids(self.m.services_with_downloaders(text)), ["adguard-card", "navidrome-card", "jellyfin-card", "watching-card", "downloaders-card",
                                                                        "metube-card", "downtify-card", "frame-card", "immich-card"])

    def test_an_app_in_another_group_stays_where_it_is(self):
        block = "    - Radarr:\n        id: radarr-card\n        href: http://192.168.1.5:7878\n\n"
        self.assertIn(block, SERVICES)
        text = SERVICES.replace(block, "").rstrip("\n") + "\n\n" + block.rstrip("\n") + "\n"
        new = self.m.services_with_downloaders(text)
        self.assertEqual(ids(new), [i for i in UNDER_PLAYERS if i != "radarr-card"] + ["radarr-card"])

    def test_a_second_run_changes_nothing(self):
        once = self.m.services_with_downloaders(SERVICES)
        self.assertEqual(self.m.cards_grouped_under(once, "downloaders-card", self.m.DOWNLOADERS_MEMBERS), once)

    def test_the_member_list_is_the_seven_download_apps(self):
        self.assertEqual(self.m.DOWNLOADERS_MEMBERS, ("seerr-card", "radarr-card", "sonarr-card", "prowlarr-card", "qbittorrent-card", "metube-card", "downtify-card"))
        self.assertEqual(self.m.DOWNLOADERS_FIRST, tuple(m for m in self.m.DOWNLOADERS_MEMBERS if m != "sonarr-card"))

    def test_a_new_app_goes_after_the_app_that_comes_before_it_and_nothing_else_moves(self):
        """The dropdown was added without Sonarr; the person has moved Downtify to the top of it. Sonarr's card, made later, lands after Radarr."""
        without = self.m.services_without_card(SERVICES, "sonarr-card")
        arranged = self.m.card_moved_after(self.m.services_with_downloaders(without), "downtify-card", "downloaders-card")
        later = self.m.card_added_after(arranged, "frame-card", ["    - Sonarr:", "        id: sonarr-card", "        href: http://192.168.1.5:8989"])
        new = self.m.services_with_new_downloaders(later, set(self.m.DOWNLOADERS_FIRST))
        self.assertEqual(ids(new), ["adguard-card", "navidrome-card", "jellyfin-card", "watching-card", "downloaders-card", "downtify-card", "seerr-card", "radarr-card",
                                    "sonarr-card", "prowlarr-card", "qbittorrent-card", "metube-card", "frame-card", "immich-card"])

    def test_a_new_app_goes_under_the_dropdown_when_it_is_the_first_one_there(self):
        only = self.m.services_without_card(self.m.services_with_downloaders(self.m.services_without_card(SERVICES, "sonarr-card")), "seerr-card")
        for gone in ("radarr-card", "prowlarr-card", "qbittorrent-card", "metube-card", "downtify-card"):
            only = self.m.services_without_card(only, gone)
        later = self.m.card_added_after(only, "frame-card", ["    - Sonarr:", "        id: sonarr-card", "        href: http://192.168.1.5:8989"])
        self.assertEqual(ids(self.m.services_with_new_downloaders(later, set(self.m.DOWNLOADERS_FIRST)))[3:6], ["watching-card", "downloaders-card", "sonarr-card"])


class DownloadersCardStep(unittest.TestCase):
    def setUp(self):
        self.m = helpers.installer()
        self.m.Ctx.home = "/home/test"
        self.m.Ctx.uid = self.m.Ctx.gid = os.getuid()
        self.path = self.m.hp_path("services.yaml")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        mark = self.m.P(self.m.DOWNLOADERS_MARK)
        if os.path.exists(mark):
            os.remove(mark)
        for leftover in (mark, self.path, self.path + ".before-downloaders"):
            self.addCleanup(lambda f=leftover: os.path.exists(f) and os.remove(f))
        self.step = self.m.BY_ID["downloaders-card"]

    def put(self, text):
        with open(self.path, "w") as f:
            f.write(text)

    def get(self):
        with open(self.path) as f:
            return f.read()

    def test_an_older_install_gets_the_dropdown_once(self):
        self.put(SERVICES)
        self.assertEqual(self.step.probe(), "todo")
        self.step.run()
        self.assertEqual(ids(self.get()), UNDER_PLAYERS)
        self.assertEqual(self.step.probe(), "done")
        self.assertTrue(os.path.exists(self.m.P(self.m.DOWNLOADERS_MARK)))
        self.assertTrue(os.path.exists(self.path + ".before-downloaders"))

    def test_a_card_the_person_removed_stays_removed(self):
        self.put(SERVICES)
        self.step.run()
        self.put(self.m.services_without_card(self.get(), "downloaders-card"))
        self.assertNotIn("downloaders-card", self.get())
        self.assertEqual(self.step.probe(), "done")

    def test_an_order_the_person_chose_afterwards_is_kept(self):
        self.put(SERVICES)
        self.step.run()
        moved = self.m.card_moved_after(self.get(), "downtify-card", "downloaders-card")
        self.put(moved)
        self.step.run()
        self.assertEqual(ids(self.get()), ids(moved))

    def test_running_the_step_twice_adds_one_card(self):
        self.put(SERVICES)
        self.step.run()
        self.step.run()
        self.assertEqual(self.get().count("id: downloaders-card"), 1)

    def test_nothing_happens_when_no_download_app_has_a_card(self):
        text = SERVICES
        for gone in self.m.DOWNLOADERS_MEMBERS:
            text = self.m.services_without_card(text, gone)
        self.put(text)
        self.assertEqual(self.step.probe(), "done")
        self.assertFalse(os.path.exists(self.m.P(self.m.DOWNLOADERS_MARK)))

    def test_a_dry_run_changes_nothing(self):
        self.put(SERVICES)
        self.m.Opt.dry = True
        self.addCleanup(setattr, self.m.Opt, "dry", False)
        self.step.run()
        self.assertEqual(self.get(), SERVICES)
        self.assertFalse(os.path.exists(self.m.P(self.m.DOWNLOADERS_MARK)))

    def sonarr_arrives_after_the_dropdown_was_added(self, marker):
        self.put(self.m.services_without_card(SERVICES, "sonarr-card"))
        self.step.run()
        if marker is not None:
            with open(self.m.P(self.m.DOWNLOADERS_MARK), "w") as f:
                f.write(marker)
        self.put(self.m.card_added_after(self.get(), "frame-card", ["    - Sonarr:", "        id: sonarr-card", "        href: http://192.168.1.5:8989"]))

    def test_sonarr_is_put_in_the_dropdown_when_its_card_appears_later(self):
        self.sonarr_arrives_after_the_dropdown_was_added(None)
        self.assertEqual(self.step.probe(), "todo")
        self.step.run()
        self.assertEqual(ids(self.get())[4:9], ["downloaders-card", "seerr-card", "radarr-card", "sonarr-card", "prowlarr-card"])
        self.assertEqual(self.step.probe(), "done")
        self.assertIn("sonarr-card", self.m.downloaders_handled())

    def test_the_first_version_of_the_marker_file_counts_as_the_six_original_apps(self):
        self.sonarr_arrives_after_the_dropdown_was_added("added\n")
        self.assertEqual(self.m.downloaders_handled(), set(self.m.DOWNLOADERS_FIRST))
        self.assertEqual(self.step.probe(), "todo")
        self.step.run()
        self.assertEqual(ids(self.get())[7], "sonarr-card")

    def test_a_card_the_person_moved_out_of_the_dropdown_is_not_pulled_back(self):
        self.sonarr_arrives_after_the_dropdown_was_added(None)
        self.step.run()
        moved = self.m.card_moved_after(self.get(), "sonarr-card", "frame-card")
        self.put(moved)
        self.assertEqual(self.step.probe(), "done")
        self.step.run()
        self.assertEqual(self.get(), moved)

    def test_a_new_app_is_left_alone_when_the_person_removed_the_dropdown(self):
        self.sonarr_arrives_after_the_dropdown_was_added(None)
        self.put(self.m.services_without_card(self.get(), "downloaders-card"))
        self.assertEqual(self.step.probe(), "done")

    def test_it_comes_after_the_steps_that_make_the_cards(self):
        self.assertTrue({"homepage-files", "stack-requests", "stack-music-downloader", "watching-card"} <= set(self.step.needs))


if __name__ == "__main__":
    unittest.main()
