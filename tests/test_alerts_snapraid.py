"""The bell item for the nightly SnapRAID update: a stopped or failed update shows until a later one succeeds."""
import os
import tempfile
import time
import unittest

import helpers


class SnapraidAlertTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = helpers.alerts()

    def setUp(self):
        fd, self.path = tempfile.mkstemp(prefix="snapraid-last-")
        os.close(fd)
        self.addCleanup(os.remove, self.path)
        self.a.SNAPRAID_STATUS = self.path

    def write(self, line):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(line + "\n")

    def test_nothing_to_show_without_a_status_file(self):
        os.remove(self.path)
        self.addCleanup(open(self.path, "w").close)
        self.assertEqual(self.a.check_snapraid(), [])

    def test_a_good_night_shows_nothing(self):
        self.write("%d|ok|3 files deleted since the last update" % time.time())
        self.assertEqual(self.a.check_snapraid(), [])

    def test_a_stopped_update_shows_what_to_do(self):
        self.write("%d|aborted|120 files were deleted since the last update, and the limit is 40" % time.time())
        items = self.a.check_snapraid()
        self.assertEqual([i["id"] for i in items], ["snapraid:aborted"])
        self.assertEqual(items[0]["level"], "warn")
        self.assertIn("sudo drives snapraid sync", items[0]["detail"])
        self.assertIn("120 files", items[0]["detail"])

    def test_a_failed_update_shows(self):
        self.write("%d|failed|The update stopped with an error (exit 2)" % time.time())
        self.assertEqual([i["id"] for i in self.a.check_snapraid()], ["snapraid:failed"])

    def test_a_damaged_status_file_is_ignored(self):
        self.write("not a status line")
        self.assertEqual(self.a.check_snapraid(), [])

    def test_the_check_is_part_of_the_run(self):
        self.assertIn(self.a.check_snapraid, self.a.CHECKS)


if __name__ == "__main__":
    unittest.main()
