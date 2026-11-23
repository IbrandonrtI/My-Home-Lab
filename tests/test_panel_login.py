"""The Customize panel's password and login rules: hashing, wrong-password lockout, session lifetime."""
import os
import stat
import unittest
from unittest import mock

import helpers


class PanelLoginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = helpers.panel()

    def setUp(self):
        self.p.SESSIONS.clear()
        self.p.FAILS.update(count=0, until=0.0)
        if os.path.exists(self.p.PASSFILE):
            os.remove(self.p.PASSFILE)

    def test_password_rules(self):
        self.assertTrue(self.p.password_problem("short"))
        self.assertTrue(self.p.password_problem(" has-a-leading-space"))
        self.assertTrue(self.p.password_problem("has-a-trailing-space "))
        self.assertEqual(self.p.password_problem("a-long-enough-one"), "")

    def test_password_is_stored_hashed_and_private(self):
        self.p.set_password("correct horse battery")
        with open(self.p.PASSFILE, encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("scrypt$"))
        self.assertNotIn("correct horse", text)
        self.assertEqual(stat.S_IMODE(os.stat(self.p.PASSFILE).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.p.STATE_DIR).st_mode), 0o700)
        self.assertTrue(self.p.check_password("correct horse battery"))
        self.assertFalse(self.p.check_password("correct horse batterz"))

    def test_login_before_a_password_exists_is_refused(self):
        with self.assertRaises(self.p.Fail) as ctx:
            self.p.login("anything at all")
        self.assertEqual(ctx.exception.code, 403)

    def test_right_password_gives_a_working_session(self):
        self.p.set_password("correct horse battery")
        tok = self.p.login("correct horse battery")
        self.assertTrue(self.p.session_ok(tok))
        self.assertFalse(self.p.session_ok("not-a-token"))
        self.assertFalse(self.p.session_ok(""))

    def test_four_wrong_passwords_lock_out_even_the_right_one_for_a_while(self):
        self.p.set_password("correct horse battery")
        for _ in range(4):
            with self.assertRaises(self.p.Fail) as ctx:
                self.p.login("wrong wrong wrong")
        self.assertEqual(ctx.exception.code, 401)
        with self.assertRaises(self.p.Fail) as ctx:
            self.p.login("correct horse battery")
        self.assertEqual(ctx.exception.code, 429)
        self.assertGreater(self.p.FAILS["until"], 0)

    def test_lockout_clears_after_the_wait_and_a_good_login_resets_the_count(self):
        self.p.set_password("correct horse battery")
        for _ in range(4):
            with self.assertRaises(self.p.Fail):
                self.p.login("wrong wrong wrong")
        later = self.p.FAILS["until"] + 1
        with mock.patch.object(self.p.time, "time", return_value=later):
            self.p.login("correct horse battery")
        self.assertEqual(self.p.FAILS["count"], 0)

    def test_changing_the_password_ends_every_session(self):
        self.p.set_password("correct horse battery")
        tok = self.p.login("correct horse battery")
        self.p.set_password("another long password")
        self.assertFalse(self.p.session_ok(tok))

    def test_sessions_expire_when_idle_and_when_too_old(self):
        self.p.set_password("correct horse battery")
        tok = self.p.login("correct horse battery")
        start = self.p.SESSIONS[tok]["created"]
        with mock.patch.object(self.p.time, "time", return_value=start + self.p.SESSION_IDLE + 5):
            self.assertFalse(self.p.session_ok(tok))
        tok = self.p.login("correct horse battery")
        start = self.p.SESSIONS[tok]["created"]
        with mock.patch.object(self.p.time, "time", return_value=start + self.p.SESSION_MAX + 5):
            self.assertFalse(self.p.session_ok(tok))

    def test_a_non_text_password_is_a_wrong_password_not_a_crash(self):
        self.p.set_password("correct horse battery")
        with self.assertRaises(self.p.Fail) as ctx:
            self.p.login(["not", "text"])
        self.assertEqual(ctx.exception.code, 401)


if __name__ == "__main__":
    unittest.main()
