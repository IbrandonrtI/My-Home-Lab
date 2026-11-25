"""The Preview and Storage rows on the Stats tab got fewer tiles, so an existing dashboard has to go from 4 to 3 and from 3 to 2 columns, once."""
import unittest

import helpers

LAYOUT = "layout:\n  Preview:\n    tab: Stats\n    style: row\n    columns: %d\n  Storage:\n    tab: Stats\n    style: row\n    columns: %d\n  Music Library:\n    columns: 2\n"


class StatsColumns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = helpers.installer()

    def test_old_layout_goes_to_three_and_two(self):
        sett, seen = self.m.layout_storage_narrow(LAYOUT % (4, 3), [])
        sett, seen = self.m.layout_preview_narrow(sett, seen)
        self.assertEqual(sett, LAYOUT % (3, 2))
        self.assertEqual(sorted(seen), sorted([self.m.STORAGE_NARROW, self.m.PREVIEW_NARROW]))

    def test_it_runs_once_so_a_later_choice_is_kept(self):
        sett, seen = self.m.layout_storage_narrow(LAYOUT % (4, 3), [])
        sett, seen = self.m.layout_preview_narrow(sett, seen)
        mine = LAYOUT % (4, 3)
        again, _ = self.m.layout_storage_narrow(mine, seen)
        again, _ = self.m.layout_preview_narrow(again, seen)
        self.assertEqual(again, mine)

    def test_a_layout_already_at_the_new_size_is_left_alone(self):
        sett, _ = self.m.layout_storage_narrow(LAYOUT % (3, 2), [])
        self.assertEqual(sett, LAYOUT % (3, 2))

    def test_the_shipped_layout_matches(self):
        import re
        import os
        text = open(os.path.join(helpers.ROOT, "homepage-config", "settings.yaml"), encoding="utf-8").read()
        for group, n in (("Preview", 3), ("Storage", 2)):
            m = re.search(r"(?m)^  %s:\n(?:    .*\n)*?    columns: (\d+)" % group, text)
            self.assertEqual(int(m.group(1)), n, group)


if __name__ == "__main__":
    unittest.main()
