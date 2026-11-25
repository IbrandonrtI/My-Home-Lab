"""What homelab-stats keeps for the Continue watching row: the half-watched titles of one Jellyfin user, their small posters, and the two files they are saved in."""
import json
import os
import tempfile
import unittest
from unittest import mock

import helpers

TICKS_MIN = 600000000


def episode(i="e1", series="Severance", season=2, number=5, name="Trojan's Horse", pos=10, total=50, tag="stag"):
    return {"Id": i, "Type": "Episode", "Name": name, "SeriesName": series, "SeriesId": "s-" + i, "SeriesPrimaryImageTag": tag, "ParentIndexNumber": season, "IndexNumber": number,
            "RunTimeTicks": total * TICKS_MIN, "UserData": {"PlaybackPositionTicks": pos * TICKS_MIN, "PlayedPercentage": pos * 100.0 / total}, "ImageTags": {"Primary": "epic"}, "ServerId": "srv1"}


def movie(i="m1", name="Dune", year=2021, pos=30, total=155, tag="mtag"):
    return {"Id": i, "Type": "Movie", "Name": name, "ProductionYear": year, "RunTimeTicks": total * TICKS_MIN,
            "UserData": {"PlaybackPositionTicks": pos * TICKS_MIN, "PlayedPercentage": pos * 100.0 / total}, "ImageTags": {"Primary": tag}, "ServerId": "srv1"}


class WatchingItems(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = helpers.load_script("homelab_stats", "scripts/homelab-stats", {"HOMELAB_STATE_DIR": tempfile.mkdtemp(prefix="stats-state-")})

    def test_an_episode_shows_the_series_season_and_number(self):
        got = self.m.watch_item(episode())
        self.assertEqual((got["title"], got["sub"], got["pct"], got["left"]), ("Severance", "S2 E5 - Trojan's Horse", 20, 40))
        self.assertEqual(got["art"], ("s-e1", "stag"))

    def test_an_episode_without_a_series_picture_uses_its_own(self):
        self.assertEqual(self.m.watch_item(episode(tag=""))["art"], ("e1", "epic"))

    def test_a_movie_shows_the_year_and_its_own_poster(self):
        got = self.m.watch_item(movie())
        self.assertEqual((got["title"], got["sub"], got["pct"], got["left"], got["art"]), ("Dune", "2021", 19, 125, ("m1", "mtag")))

    def test_the_percent_is_worked_out_when_jellyfin_gives_none(self):
        it = movie()
        del it["UserData"]["PlayedPercentage"]
        self.assertEqual(self.m.watch_item(it)["pct"], 19)

    def test_missing_pieces_do_not_stop_the_row(self):
        got = self.m.watch_item({"Id": "x", "Type": "Movie", "Name": "Odd"})
        self.assertEqual((got["title"], got["sub"], got["pct"], got["left"], got["art"]), ("Odd", "", 0, None, ("x", "")))
        self.assertIsNone(self.m.watch_item({"Id": "x", "Type": "Movie"}))
        self.assertIsNone(self.m.watch_item({"Name": "No id"}))
        self.assertIsNone(self.m.watch_item("text"))

    def test_less_than_a_minute_left_still_says_one_minute(self):
        it = movie(pos=154, total=155)
        it["RunTimeTicks"] = 155 * TICKS_MIN
        it["UserData"]["PlaybackPositionTicks"] = 155 * TICKS_MIN - 1000
        self.assertEqual(self.m.watch_item(it)["left"], 1)


class WatchingCollect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = helpers.load_script("homelab_stats", "scripts/homelab-stats", {"HOMELAB_STATE_DIR": tempfile.mkdtemp(prefix="stats-state-")})

    def setUp(self):
        self.asked, self.posters = [], []
        self.users = [{"Id": "u-b", "Name": "Guest", "Policy": {"IsAdministrator": False}}, {"Id": "u-a", "Name": "Brandon", "Policy": {"IsAdministrator": True}},
                      {"Id": "u-c", "Name": "Old", "Policy": {"IsAdministrator": True, "IsDisabled": True}}]
        self.resume = [episode(), movie()]
        self._json, self._poster = self.m.http_json, self.m.jellyfin_poster
        self.m.http_json = self.fake_json
        self.m.jellyfin_poster = lambda w, i, t: (self.posters.append((i, t)) or "data:image/jpeg;base64,QUJD")
        self.addCleanup(self.restore)
        self.w = {"url": "http://jf:8096", "key": "K", "href": "https://pc.example.ts.net:1009"}
        os.environ.pop("HOMELAB_JELLYFIN_USER", None)

    def restore(self):
        self.m.http_json, self.m.jellyfin_poster = self._json, self._poster
        os.environ.pop("HOMELAB_JELLYFIN_USER", None)

    def fake_json(self, url, headers=None):
        self.asked.append(url)
        if url.endswith("/Users"):
            return self.users
        if "/Items/Resume" in url:
            return {"Items": self.resume}
        raise AssertionError("unexpected " + url)

    def test_the_first_administrator_is_shown_and_a_disabled_one_is_skipped(self):
        data, _ = self.m.collect_watching(self.w, 1700000000, {})
        self.assertEqual(data["user"], "Brandon")
        self.assertTrue(any("/Users/u-a/Items/Resume" in u for u in self.asked))

    def test_a_named_user_is_shown_instead(self):
        os.environ["HOMELAB_JELLYFIN_USER"] = "guest"
        data, _ = self.m.collect_watching(self.w, 1700000000, {})
        self.assertEqual(data["user"], "Guest")

    def test_the_user_can_also_be_named_in_a_file(self):
        state = tempfile.mkdtemp(prefix="stats-state-")
        patch = mock.patch.object(self.m, "STATE_DIR", state)
        patch.start()
        self.addCleanup(patch.stop)
        with open(os.path.join(state, "watching-user"), "w") as f:
            f.write("Guest\n")
        data, _ = self.m.collect_watching(self.w, 1700000000, {})
        self.assertEqual(data["user"], "Guest")

    def test_a_named_user_that_does_not_exist_is_an_error_not_someone_else(self):
        os.environ["HOMELAB_JELLYFIN_USER"] = "nobody"
        with self.assertRaises(ValueError):
            self.m.collect_watching(self.w, 1700000000, {})

    def test_the_details_and_the_poster_keys(self):
        data, posters = self.m.collect_watching(self.w, 1700000000, {})
        self.assertEqual((data["version"], data["updated"], data["link"], data["server"]), (1, 1700000000, "https://pc.example.ts.net:1009", "srv1"))
        self.assertEqual([i["title"] for i in data["items"]], ["Severance", "Dune"])
        self.assertEqual([i["poster"] for i in data["items"]], ["s-e1-stag", "m1-mtag"])
        self.assertEqual(sorted(posters), ["m1-mtag", "s-e1-stag"])
        self.assertNotIn("art", data["items"][0])

    def test_a_poster_that_is_already_saved_is_not_asked_for_again(self):
        _, posters = self.m.collect_watching(self.w, 1700000000, {"s-e1-stag": "data:image/jpeg;base64,SAVED"})
        self.assertEqual(self.posters, [("m1", "mtag")])
        self.assertEqual(posters["s-e1-stag"], "data:image/jpeg;base64,SAVED")

    def test_posters_of_titles_that_left_the_row_are_dropped(self):
        _, posters = self.m.collect_watching(self.w, 1700000000, {"gone-1": "data:image/jpeg;base64,OLD"})
        self.assertNotIn("gone-1", posters)

    def test_a_title_whose_poster_cannot_be_had_is_still_in_the_row(self):
        self.m.jellyfin_poster = lambda w, i, t: ""
        data, posters = self.m.collect_watching(self.w, 1700000000, {})
        self.assertEqual([i["poster"] for i in data["items"]], ["", ""])
        self.assertEqual(posters, {})

    def test_the_link_falls_back_to_the_address_the_dashboard_uses_for_jellyfin(self):
        data, _ = self.m.collect_watching({"url": "http://jf:8096", "key": "K"}, 1700000000, {})
        self.assertEqual(data["link"], "http://jf:8096")

    def test_nothing_in_progress_gives_an_empty_row(self):
        self.resume = []
        data, posters = self.m.collect_watching(self.w, 1700000000, {})
        self.assertEqual((data["items"], posters), ([], {}))


class WatchingFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = helpers.load_script("homelab_stats", "scripts/homelab-stats", {"HOMELAB_STATE_DIR": tempfile.mkdtemp(prefix="stats-state-")})

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="watching-")
        self.out = os.path.join(self.dir, "stats.json")
        self.fail = False
        self._json, self._poster = self.m.http_json, self.m.jellyfin_poster
        self.m.http_json = self.fake_json
        self.m.jellyfin_poster = lambda w, i, t: "data:image/jpeg;base64,QUJD"
        self.addCleanup(self.restore)
        self.m.PROBLEMS.clear()
        self.widgets = {"jellyfin": {"url": "http://jf:8096", "key": "K", "href": "https://j.example"}}

    def restore(self):
        self.m.http_json, self.m.jellyfin_poster = self._json, self._poster
        self.m.PROBLEMS.clear()

    def fake_json(self, url, headers=None):
        if self.fail:
            raise OSError("connection refused")
        if url.endswith("/Users"):
            return [{"Id": "u", "Name": "Brandon", "Policy": {"IsAdministrator": True}}]
        return {"Items": [movie()]}

    def load(self, name):
        with open(os.path.join(self.dir, name)) as f:
            return json.load(f)

    def test_the_two_files_are_written_next_to_the_stats_file(self):
        self.m.write_watching(self.widgets, self.out, 1700000000)
        self.assertEqual(self.load("watching.json")["items"][0]["title"], "Dune")
        self.assertEqual(self.load("watching-posters.json"), {"m1-mtag": "data:image/jpeg;base64,QUJD"})

    def test_jellyfin_not_answering_leaves_the_files_as_they_were(self):
        self.m.write_watching(self.widgets, self.out, 1700000000)
        before = self.load("watching.json")
        self.fail = True
        self.assertIsNone(self.m.write_watching(self.widgets, self.out, 1700000600))
        self.assertEqual(self.load("watching.json"), before)
        self.assertTrue(any("Continue watching" in p for p in self.m.PROBLEMS))

    def test_without_a_jellyfin_card_nothing_is_written(self):
        self.assertIsNone(self.m.write_watching({}, self.out, 1700000000))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "watching.json")))

    def test_the_forced_location_is_used_for_both_files(self):
        forced = os.path.join(self.dir, "x", "w.json")
        os.makedirs(os.path.dirname(forced))
        os.environ["HOMELAB_WATCHING_OUT"] = forced
        try:
            self.m.write_watching(self.widgets, self.out, 1700000000)
        finally:
            del os.environ["HOMELAB_WATCHING_OUT"]
        self.assertTrue(os.path.exists(forced))
        self.assertTrue(os.path.exists(os.path.join(self.dir, "x", "watching-posters.json")))

    def test_the_watching_command_reads_the_card_from_services_yaml(self):
        hp = os.path.join(self.dir, "hp")
        os.makedirs(os.path.join(hp, "images"))
        with open(os.path.join(hp, "services.yaml"), "w") as f:
            f.write("- Media:\n    - Jellyfin:\n        href: https://j.example/\n        widget:\n          type: jellyfin\n          url: http://jf:8096\n          key: abc\n")
        state = os.path.join(self.dir, "state")
        os.makedirs(state)
        patch = mock.patch.object(self.m, "STATE_DIR", state)
        patch.start()
        self.addCleanup(patch.stop)
        with open(os.path.join(state, "homepage-dir"), "w") as f:
            f.write(hp)
        os.environ["HOMELAB_STATS_OUT"] = os.path.join(hp, "images", "stats.json")
        os.environ["HOMELAB_WATCHING_LOCK"] = os.path.join(self.dir, "lock")
        self.m.WATCH_LOCK = os.environ["HOMELAB_WATCHING_LOCK"]
        try:
            self.assertEqual(self.m.watching_command(), 0)
        finally:
            del os.environ["HOMELAB_STATS_OUT"]
        with open(os.path.join(hp, "images", "watching.json")) as f:
            got = json.load(f)
        self.assertEqual((got["link"], got["items"][0]["title"]), ("https://j.example", "Dune"))


class WatchingPoster(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = helpers.load_script("homelab_stats", "scripts/homelab-stats", {"HOMELAB_STATE_DIR": tempfile.mkdtemp(prefix="stats-state-")})

    def fake_open(self, body):
        seen = []

        class Resp:
            def __enter__(self_):
                return self_

            def __exit__(self_, *a):
                return False

            def read(self_, n=-1):
                return body[:n] if n >= 0 else body
        orig = self.m.urllib.request.urlopen
        self.m.urllib.request.urlopen = lambda req, timeout=None: (seen.append(req) or Resp())
        self.addCleanup(lambda: setattr(self.m.urllib.request, "urlopen", orig))
        return seen

    def test_the_poster_is_asked_for_small_and_as_a_jpeg_with_the_login(self):
        seen = self.fake_open(b"ABC")
        got = self.m.jellyfin_poster({"url": "http://jf:8096", "key": "K"}, "m1", "tag/1")
        self.assertEqual(got, "data:image/jpeg;base64,QUJD")
        url = seen[0].full_url
        self.assertIn("/Items/m1/Images/Primary?", url)
        self.assertIn("maxHeight=270", url)
        self.assertIn("format=Jpg", url)
        self.assertIn("tag=tag%2F1", url)
        self.assertIn("MediaBrowser", seen[0].get_header("Authorization"))

    def test_no_tag_means_no_poster_and_no_request(self):
        seen = self.fake_open(b"ABC")
        self.assertEqual(self.m.jellyfin_poster({"url": "http://jf:8096", "key": "K"}, "m1", ""), "")
        self.assertEqual(seen, [])

    def test_a_picture_that_is_too_big_is_left_out(self):
        self.fake_open(b"x" * (self.m.POSTER_MAX_BYTES + 5))
        self.assertEqual(self.m.jellyfin_poster({"url": "http://jf:8096", "key": "K"}, "m1", "t"), "")

    def test_the_card_address_is_read_from_services_yaml(self):
        hp = tempfile.mkdtemp(prefix="hp-")
        with open(os.path.join(hp, "services.yaml"), "w") as f:
            f.write("- Media:\n    - Jellyfin:\n        href: https://j.example/\n        widget:\n          type: jellyfin\n          url: http://jf:8096\n          key: abc\n")
        self.assertEqual(self.m.widgets_from_services(hp)["jellyfin"], {"url": "http://jf:8096", "key": "abc", "href": "https://j.example"})


if __name__ == "__main__":
    unittest.main()
