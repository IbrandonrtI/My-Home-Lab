"""The Drives tab's folder move: what the panel server lets through to the drives tool."""
import unittest

import helpers


class FolderMovePanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = helpers.panel()

    def words(self, **body):
        return self.p.job_words("movefolders", body)

    def test_builds_the_exact_words(self):
        w = self.words(role="main", id="MAIN2", folders=["6d6f76696573", "73686f7773"], keep=True)
        self.assertEqual(w, ["movefolders", "main", "MAIN2", "6d6f76696573,73686f7773", "yes"])
        self.assertEqual(self.words(role="backup", id="BACKUP2", folders=["6d6f76696573"], keep=False)[-1], "no")

    def test_keep_must_be_a_real_true(self):
        self.assertEqual(self.words(role="main", id="MAIN2", folders=["61"], keep="yes")[-1], "no")

    def test_refuses_odd_folder_names_and_drives(self):
        for bad in (["movies"], ["6D"], ["6"], ["../x"], [""], [5], "61", [], ["61"] * 61):
            with self.assertRaises(self.p.Fail, msg=repr(bad)):
                self.words(role="main", id="MAIN2", folders=bad, keep=True)
        for bad_id in ("", "../MAIN2", "MAIN2;rm", 5, None):
            with self.assertRaises(self.p.Fail, msg=repr(bad_id)):
                self.words(role="main", id=bad_id, folders=["61"], keep=True)
        with self.assertRaises(self.p.Fail):
            self.words(role="spare", id="MAIN2", folders=["61"], keep=True)

    def test_only_known_confirmation_words(self):
        with self.assertRaises(self.p.Fail):
            self.words(role="main", id="MAIN2", folders=["61"], keep=True, typed=["rm -rf"])
        self.assertEqual(self.words(role="main", id="MAIN2", folders=["61"], keep=True, typed=["NOW"])[-1], "NOW")


if __name__ == "__main__":
    unittest.main()
