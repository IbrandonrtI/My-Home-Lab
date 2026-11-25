"""The every-minute Continue watching job reaches machines that were installed before it existed: refresh adds that one line to root's crontab and leaves the others as they are."""
import unittest

import helpers


class CronWatching(unittest.TestCase):
    def setUp(self):
        self.m = helpers.installer()
        self.saved = []
        self._text, self._run = self.m.crontab_text, self.m.run
        self.addCleanup(self.restore)
        self.old = "\n".join(line for key, line in self.m.CRON_LINES if key != "homelab-stats watching") + "\n"

    def restore(self):
        self.m.crontab_text, self.m.run = self._text, self._run

    def use(self, text):
        self.m.crontab_text = lambda: text

        def fake_run(cmd, input_text=None, **kw):
            if cmd[:2] == ["crontab", "-"]:
                self.saved.append(input_text)
            return 0, ""
        self.m.run = fake_run

    def test_an_older_install_is_missing_the_line(self):
        self.use(self.old)
        self.assertEqual(self.m.CronLines().probe(), "todo")

    def test_a_current_install_has_it(self):
        self.use("\n".join(line for _, line in self.m.CRON_LINES) + "\n")
        self.assertEqual(self.m.CronLines().probe(), "done")

    def test_only_the_missing_line_is_added(self):
        self.use(self.old)
        self.m.crontab_add(self.m.CRON_LINES)
        new = self.saved[-1]
        self.assertEqual(new.count("homelab-stats watching"), 1)
        self.assertEqual(new.count("/usr/local/sbin/homelab-stats >/dev/null"), 1)
        self.assertEqual(new.count("homelab-sample"), 1)
        self.assertIn("* * * * * /usr/local/sbin/homelab-stats watching", new)


if __name__ == "__main__":
    unittest.main()
