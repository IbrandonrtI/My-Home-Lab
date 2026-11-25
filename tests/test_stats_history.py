"""What homelab-stats keeps in history.json (a week of temperatures and network speed, what was added each day) and how it asks Jellyfin for its totals."""
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
        h = self.m.history_update({}, t0, 51.5, {"Storage": 38}, {})
        self.assertEqual((h["t"], h["cpu"], h["drives"]), ([int(t0)], [51.5], {"Storage": [38]}))
        h = self.m.history_update(h, t0 + 900, 52.0, {"Storage": None}, {})
        self.assertEqual((h["cpu"], h["drives"]["Storage"]), ([51.5, 52.0], [38, None]))

    def test_a_drive_that_appears_later_is_padded_with_gaps(self):
        t0 = self.noon((2026, 11, 20))
        h = self.m.history_update({}, t0, 50, {"A": 30}, {})
        h = self.m.history_update(h, t0 + 900, 50, {"A": 30, "B": 40}, {})
        self.assertEqual(h["drives"]["B"], [None, 40])

    def test_a_second_run_within_ten_minutes_adds_no_reading_but_keeps_the_day_totals(self):
        t0 = self.noon((2026, 11, 20))
        h = self.m.history_update({}, t0, 50, {}, {"movies": 10})
        h = self.m.history_update(h, t0 + 60, 50, {}, {"movies": 12})
        self.assertEqual(len(h["t"]), 1)
        self.assertEqual(h["days"]["2026-11-20"]["movies"], 12)

    def test_only_a_week_of_readings_is_kept(self):
        h, t = {}, self.noon((2026, 11, 1))
        for i in range(self.m.HISTORY_POINTS + 20):
            h = self.m.history_update(h, t + i * 900, 40, {"Storage": 30}, {})
        self.assertEqual(len(h["t"]), self.m.HISTORY_POINTS)
        self.assertEqual({len(h["cpu"]), len(h["drives"]["Storage"])}, {self.m.HISTORY_POINTS})

    def test_a_damaged_file_starts_again_instead_of_failing(self):
        t0 = self.noon((2026, 11, 20))
        h = self.m.history_update({"t": [1, 2, 3], "cpu": [1], "drives": {"a": 5}}, t0, 50, {}, {})
        self.assertEqual(h["t"], [int(t0)])
        h = self.m.history_update([1, 2], t0, None, {}, {})
        self.assertEqual(h["cpu"], [None])

    def test_a_drive_that_never_gave_a_reading_is_left_out(self):
        h = self.m.history_update({}, self.noon((2026, 11, 20)), 50, {"Asleep": None, "Warm": 33}, {})
        self.assertEqual(list(h["drives"]), ["Warm"])

    def test_added_per_day_is_the_difference_between_the_last_totals_of_two_days(self):
        h = {}
        for day, movies, shows in (((2026, 11, 18), 100, 10), ((2026, 11, 19), 130, 10), ((2026, 11, 20), 125, 12)):
            h = self.m.history_update(h, self.noon(day), 50, {}, {"movies": movies, "shows": shows})
        rows = {r["day"]: r for r in h["activity"]}
        self.assertEqual(len(h["activity"]), self.m.ACTIVITY_DAYS)
        self.assertEqual(rows["2026-11-19"]["movies"], 30)
        self.assertEqual(rows["2026-11-20"]["movies"], 0)  # a smaller total (something deleted) is not a negative addition
        self.assertEqual(rows["2026-11-20"]["shows"], 2)
        self.assertIsNone(rows["2026-11-18"]["movies"])  # no total for the day before
        self.assertIsNone(rows["2026-11-20"]["episodes"])  # never counted

    def test_old_day_totals_are_dropped(self):
        h = self.m.history_update({}, self.noon((2026, 9, 1)), 50, {}, {"movies": 1})
        h = self.m.history_update(h, self.noon((2026, 11, 20)), 50, {}, {"movies": 2})
        self.assertEqual(list(h["days"]), ["2026-11-20"])

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

    def test_totals_and_the_recently_added_list(self):
        now = self.m.utc_epoch("2025-11-20T20:00:00Z")
        asked = []

        def fake(url, headers=None):
            asked.append((url, headers))
            if "/Items/Counts" in url:
                return {"MovieCount": 1234, "SeriesCount": 56, "EpisodeCount": 7890}
            return {"Items": [{"Name": "Dune", "Type": "Movie", "ProductionYear": 2021, "DateCreated": "2025-11-20T18:22:11.1234567Z"},
                              {"Name": "Severance", "Type": "Series", "ProductionYear": 2022, "DateCreated": "2025-11-18T09:00:00.0000000Z"},
                              {"Name": "", "Type": "Movie"}]}

        old, self.m.http_json = self.m.http_json, fake
        try:
            got = self.m.get_jellyfin({"url": "http://jf.test:8096", "key": "K"}, now)
        finally:
            self.m.http_json = old
        self.assertEqual((got["movies_raw"], got["shows_raw"], got["episodes_raw"]), (1234, 56, 7890))
        self.assertEqual(got["movies"], self.m.num(1234))
        self.assertEqual([r["name"] for r in got["recent"]], ["Dune (2021)", "Severance"])
        self.assertTrue(got["recent"][0]["label"].startswith("Movie - "))
        self.assertTrue(got["recent"][1]["label"].startswith("Show - "))
        self.assertTrue(all(h == {"X-Emby-Token": "K"} for _, h in asked))

    def test_an_empty_library_says_so(self):
        old, self.m.http_json = self.m.http_json, lambda url, headers=None: {"MovieCount": 0, "SeriesCount": 0, "EpisodeCount": 0}
        try:
            got = self.m.get_jellyfin({"url": "http://jf.test", "key": "K"}, 0)
        finally:
            self.m.http_json = old
        self.assertEqual(got["recent"][0]["name"], "Nothing added yet")


if __name__ == "__main__":
    unittest.main()
