"""What homelab-stats keeps in history.json (a week of temperatures, Jellyfin plays per day) and how it asks Jellyfin for its totals and plays."""
import datetime
import os
import tempfile
import unittest

import helpers


class StatsHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = tempfile.mkdtemp(prefix="stats-state-")
        cls.m = helpers.load_script("homelab_stats", "scripts/homelab-stats", {"HOMELAB_STATE_DIR": cls.state})

    def noon(self, day):
        return datetime.datetime(*day, 12, 0, 0).timestamp()

    def test_each_run_adds_one_reading_of_the_cpu_and_the_drives(self):
        t0 = self.noon((2026, 11, 20))
        h = self.m.history_update({}, t0, 51.5, {"Storage": 38}, None)
        self.assertEqual((h["t"], h["cpu"], h["drives"]), ([int(t0)], [51.5], {"Storage": [38]}))
        h = self.m.history_update(h, t0 + 900, 52.0, {"Storage": None}, None)
        self.assertEqual((h["cpu"], h["drives"]["Storage"]), ([51.5, 52.0], [38, None]))

    def test_a_drive_that_appears_later_is_padded_with_gaps(self):
        t0 = self.noon((2026, 11, 20))
        h = self.m.history_update({}, t0, 50, {"A": 30}, None)
        h = self.m.history_update(h, t0 + 900, 50, {"A": 30, "B": 40}, None)
        self.assertEqual(h["drives"]["B"], [None, 40])

    def test_a_second_run_within_ten_minutes_adds_no_reading_but_refreshes_the_plays(self):
        t0 = self.noon((2026, 11, 20))
        h = self.m.history_update({}, t0, 50, {}, [{"day": "2026-11-20", "movies": 1, "shows": 0, "music": 0}])
        h = self.m.history_update(h, t0 + 60, 50, {}, [{"day": "2026-11-20", "movies": 2, "shows": 0, "music": 0}])
        self.assertEqual(len(h["t"]), 1)
        self.assertEqual(h["plays"][0]["movies"], 2)

    def test_when_jellyfin_could_not_be_asked_the_last_plays_stay(self):
        t0 = self.noon((2026, 11, 20))
        row = [{"day": "2026-11-20", "movies": 1, "shows": 0, "music": 0}]
        h = self.m.history_update({}, t0, 50, {}, row)
        h = self.m.history_update(h, t0 + 900, 50, {}, None)
        self.assertEqual(h["plays"], row)

    def test_only_a_week_of_readings_is_kept(self):
        h, t = {}, self.noon((2026, 11, 1))
        for i in range(self.m.HISTORY_POINTS + 20):
            h = self.m.history_update(h, t + i * 900, 40, {"Storage": 30}, None)
        self.assertEqual(len(h["t"]), self.m.HISTORY_POINTS)
        self.assertEqual({len(h["cpu"]), len(h["drives"]["Storage"])}, {self.m.HISTORY_POINTS})

    def test_a_damaged_file_starts_again_instead_of_failing(self):
        t0 = self.noon((2026, 11, 20))
        h = self.m.history_update({"t": [1, 2, 3], "cpu": [1], "drives": {"a": 5}}, t0, 50, {}, None)
        self.assertEqual(h["t"], [int(t0)])
        h = self.m.history_update([1, 2], t0, None, {}, None)
        self.assertEqual(h["cpu"], [None])

    def test_a_drive_that_never_gave_a_reading_is_left_out(self):
        h = self.m.history_update({}, self.noon((2026, 11, 20)), 50, {"Asleep": None, "Warm": 33}, None)
        self.assertEqual(list(h["drives"]), ["Warm"])

    def test_the_cpu_temperature_is_the_hottest_sensor_in_degrees(self):
        sysd = tempfile.mkdtemp(prefix="sys-")
        os.makedirs(sysd + "/class/hwmon/hwmon0")
        for name, milli in (("temp1_input", "41000"), ("temp2_input", "57500"), ("temp3_input", "0")):
            with open(sysd + "/class/hwmon/hwmon0/" + name, "w") as f:
                f.write(milli + "\n")
        old, self.m.SYS = self.m.SYS, sysd
        try:
            self.assertEqual(self.m.cpu_temp(), 57.5)
            self.m.SYS = sysd + "/none"
            self.assertIsNone(self.m.cpu_temp())
        finally:
            self.m.SYS = old

    def test_the_drive_readings_come_from_the_sample_file_under_the_drive_name(self):
        with open(os.path.join(self.state, "temps"), "w") as f:
            f.write("Storage|/dev/sda|36|1700000000\nBackup|/dev/sdb|standby|1700000000\n")
        old, self.m.STATE_DIR = self.m.STATE_DIR, self.state
        try:
            got = self.m.drive_temps()
        finally:
            self.m.STATE_DIR = old
        self.assertEqual(sorted(got.values(), key=lambda v: (v is None, v)), [36, None])


class JellyfinTotals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = helpers.load_script("homelab_stats", "scripts/homelab-stats", {"HOMELAB_STATE_DIR": tempfile.mkdtemp(prefix="stats-state-")})

    def test_the_date_has_seven_decimals_in_jellyfin(self):
        self.assertEqual(self.m.utc_epoch("2025-11-20T18:22:11.1234567Z"), 1763662931)
        self.assertIsNone(self.m.utc_epoch("yesterday"))
        self.assertIsNone(self.m.utc_epoch(None))

    def fake(self, entries, kinds, asked):
        def f(url, headers=None):
            asked.append((url, headers))
            if "/Items/Counts" in url:
                return {"MovieCount": 1234, "SeriesCount": 56, "EpisodeCount": 7890}
            if "/System/ActivityLog/Entries" in url:
                return {"Items": entries}
            if "Ids=" in url:
                ids = url.split("Ids=")[1].split(",")
                return {"Items": [{"Id": i, "Type": kinds[i]} for i in ids if i in kinds]}
            return {"Items": [{"Name": "Dune", "Type": "Movie", "ProductionYear": 2021, "DateCreated": "2025-11-20T18:22:11.1234567Z"},
                              {"Name": "Severance", "Type": "Series", "ProductionYear": 2022, "DateCreated": "2025-11-18T09:00:00.0000000Z"},
                              {"Name": "", "Type": "Movie"}]}
        return f

    def test_totals_and_the_recently_added_list(self):
        now = self.m.utc_epoch("2025-11-20T20:00:00Z")
        asked = []
        old, self.m.http_json = self.m.http_json, self.fake([], {}, asked)
        try:
            got = self.m.get_jellyfin({"url": "http://jf.test:8096", "key": "K"}, now)
        finally:
            self.m.http_json = old
        self.assertEqual(got["movies"], self.m.num(1234))
        self.assertEqual([r["name"] for r in got["recent"]], ["Dune (2021)", "Severance"])
        self.assertTrue(got["recent"][0]["label"].startswith("Movie - "))
        self.assertTrue(got["recent"][1]["label"].startswith("Show - "))
        self.assertTrue(all(h == {"X-Emby-Token": "K"} for _, h in asked))

    def test_plays_per_day_split_into_movies_shows_and_music(self):
        now = self.m.utc_epoch("2025-11-20T20:00:00Z")
        entries = [{"Type": "VideoPlayback", "Date": "2025-11-20T18:00:00.0000000Z", "ItemId": "aaa"},
                   {"Type": "VideoPlayback", "Date": "2025-11-20T19:00:00.0000000Z", "ItemId": "bbb"},
                   {"Type": "VideoPlayback", "Date": "2025-11-19T15:00:00.0000000Z", "ItemId": "bbb"},
                   {"Type": "VideoPlayback", "Date": "2025-11-19T16:00:00.0000000Z", "ItemId": "gone"},
                   {"Type": "AudioPlayback", "Date": "2025-11-19T17:00:00.0000000Z", "ItemId": "ccc"},
                   {"Type": "VideoPlaybackStopped", "Date": "2025-11-19T17:30:00.0000000Z", "ItemId": "aaa"},
                   {"Type": "UserLoggedIn", "Date": "2025-11-19T17:31:00.0000000Z"},
                   {"Type": "VideoPlayback", "Date": "2024-01-01T00:00:00.0000000Z", "ItemId": "aaa"}]
        asked = []
        old, self.m.http_json = self.m.http_json, self.fake(entries, {"aaa": "Movie", "bbb": "Episode"}, asked)
        try:
            got = self.m.jellyfin_plays({"url": "http://jf.test", "key": "K"}, now)
        finally:
            self.m.http_json = old
        self.assertEqual(len(got), self.m.PLAY_DAYS)
        rows = {r["day"]: r for r in got}
        zone = self.m.at(now).date()
        last, before = rows[zone.isoformat()], rows[(zone - datetime.timedelta(days=1)).isoformat()]
        self.assertEqual((last["movies"], last["shows"], last["music"]), (1, 1, 0))
        self.assertEqual((before["movies"], before["shows"], before["music"]), (1, 1, 1))  # the item Jellyfin no longer knows counts as a movie
        self.assertEqual(sum(r["movies"] + r["shows"] + r["music"] for r in got), 5, "stops, logins and old entries are not plays")
        self.assertTrue(any("minDate=" in u for u, _ in asked))

    def test_plays_are_none_when_the_log_can_not_be_read(self):
        def boom(url, headers=None):
            raise OSError("down")
        old, self.m.http_json = self.m.http_json, boom
        try:
            self.assertIsNone(self.m.jellyfin_plays({"url": "http://jf.test", "key": "K"}, 1700000000))
        finally:
            self.m.http_json = old

    def test_an_empty_library_says_so(self):
        old, self.m.http_json = self.m.http_json, lambda url, headers=None: {"MovieCount": 0, "SeriesCount": 0, "EpisodeCount": 0}
        try:
            got = self.m.get_jellyfin({"url": "http://jf.test", "key": "K"}, 0)
        finally:
            self.m.http_json = old
        self.assertEqual(got["recent"][0]["name"], "Nothing added yet")


if __name__ == "__main__":
    unittest.main()
