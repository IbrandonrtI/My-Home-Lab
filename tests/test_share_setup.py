"""Sharing the movies and shows folders with Windows (Samba): the settings file, the steps and the command, with the system commands replaced by a recorder.
What Samba and Windows do with it is not tested here."""
import os
import shutil
import unittest
from unittest import mock

import helpers


class ShareSetup(unittest.TestCase):
    def setUp(self):
        self.m = helpers.installer()
        m = self.m
        self.calls, self.active, self.installed, self.smbpasswd_rc, self.testparm_rc = [], False, False, 0, 0

        def fake_run(args, input_text=None, **kw):
            self.calls.append((list(args), input_text))
            if args[0] == "systemctl" and args[1] == "is-active":
                return 0, "active\n" if self.active else "inactive\n"
            if args[0] == "systemctl" and args[1] == "enable":
                self.active = True
            if args[0] == "dpkg-query":
                return (0, "install ok installed") if self.installed else (1, "")
            if args[0] == "testparm":
                return self.testparm_rc, "Unknown parameter" if self.testparm_rc else "Loaded services file OK."
            if args[0] == "smbpasswd":
                return self.smbpasswd_rc, "Failed" if self.smbpasswd_rc else "Added user"
            return 0, ""

        for patcher in (mock.patch.object(m, "run", fake_run), mock.patch.object(m, "apt_install", lambda pkgs: setattr(self, "installed", True)),
                        mock.patch.object(m.State, "data", {"share": True}), mock.patch.object(m.State, "save", lambda *a, **k: None),
                        mock.patch.object(m.Runtime, "password", "Secret-pass-1"), mock.patch.object(m.Ctx, "user", "brandon"),
                        mock.patch.object(m.Ctx, "uid", os.getuid()), mock.patch.object(m.Ctx, "gid", os.getgid()),
                        mock.patch.object(m.Ctx, "lan", "192.168.1.198"), mock.patch.object(m.Ctx, "fqdn", "homelab.example.ts.net"),
                        mock.patch.object(m.Ctx, "hostname", "homelab")):
            patcher.start()
            self.addCleanup(patcher.stop)
        os.makedirs(os.path.dirname(m.P(m.SHARE_MAIN_CONF)), exist_ok=True)
        with open(m.P(m.SHARE_MAIN_CONF), "w") as f:
            f.write("[global]\n   workgroup = WORKGROUP\n\n[printers]\n   path = /var/spool/samba\n")
        for _, path in m.SHARES:
            self.addCleanup(shutil.rmtree, m.P(path), True)
        self.addCleanup(lambda: [os.path.exists(m.P(p)) and os.remove(m.P(p)) for p in (m.SHARE_CONF, m.SHARE_MAIN_CONF)])

    def main_conf(self):
        with open(self.m.P(self.m.SHARE_MAIN_CONF)) as f:
            return f.read()

    def ran(self, *start):
        return [c for c, _ in self.calls if tuple(c[:len(start)]) == start]

    def test_the_settings_share_the_two_folders_for_the_lab_user_with_write_access(self):
        text = self.m.share_config_text()
        for name, path in (("movies", "/mnt/storage/movies"), ("shows", "/mnt/storage/shows")):
            self.assertIn("[%s]\n   path = %s\n" % (name, path), text)
        self.assertEqual(text.count("read only = no"), 2)
        self.assertNotIn("downloads", text)
        self.assertEqual(text.count("valid users = brandon"), 2)
        self.assertEqual(text.count("force user = brandon"), 2)
        self.assertEqual(text.count("guest ok"), 0)

    def test_only_the_home_network_and_tailscale_may_connect(self):
        text = self.m.share_config_text()
        self.assertEqual(text.count("hosts deny = ALL"), 2)
        for allowed in ("192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12", "100.64.0.0/10"):
            self.assertIn(allowed, text)
        self.assertNotIn("0.0.0.0/0", text)

    def test_every_step_waits_until_the_person_asks(self):
        self.m.State.data.pop("share")
        for sid in ("share-package", "share-folders", "share-config", "share-login"):
            self.assertFalse(self.m.BY_ID[sid].applies(), sid)

    def test_the_package_is_installed_once(self):
        step = self.m.BY_ID["share-package"]
        self.assertEqual(step.probe(), "todo")
        step.run()
        self.assertEqual(step.probe(), "done")

    def test_the_folders_are_made(self):
        step = self.m.BY_ID["share-folders"]
        self.assertEqual(step.probe(), "todo")
        step.run()
        self.assertEqual(step.probe(), "done")

    def test_the_settings_are_written_included_once_and_samba_is_started(self):
        step = self.m.BY_ID["share-config"]
        self.assertEqual(step.probe(), "todo")
        step.run()
        self.assertEqual(step.probe(), "done")
        with open(self.m.P(self.m.SHARE_CONF)) as f:
            self.assertEqual(f.read(), self.m.share_config_text())
        main = self.main_conf()
        self.assertEqual(main.count("include = /etc/samba/homelab.conf"), 1)
        self.assertTrue(main.startswith("[global]\n   workgroup = WORKGROUP\n"))
        self.assertEqual(self.ran("systemctl", "enable", "--now", "smbd", "nmbd"), [["systemctl", "enable", "--now", "smbd", "nmbd"]])
        self.assertEqual(len(self.ran("systemctl", "restart")), 1)

    def test_a_second_run_changes_nothing(self):
        step = self.m.BY_ID["share-config"]
        step.run()
        before = self.main_conf()
        self.calls.clear()
        step.run()
        self.assertEqual(self.main_conf(), before)
        self.assertEqual(self.ran("systemctl", "restart"), [])

    def test_settings_that_samba_does_not_accept_are_not_kept(self):
        self.testparm_rc = 1
        with self.assertRaises(self.m.Abort) as cm:
            self.m.BY_ID["share-config"].run()
        self.assertIn("does not accept", str(cm.exception))
        self.assertFalse(os.path.exists(self.m.P(self.m.SHARE_CONF)))
        self.assertNotIn("homelab.conf", self.main_conf())
        self.assertEqual(self.ran("systemctl"), [])

    def test_the_admin_password_becomes_the_samba_login_and_is_not_saved(self):
        step = self.m.BY_ID["share-login"]
        self.assertEqual(step.probe(), "todo")
        step.run()
        self.assertEqual(step.probe(), "done")
        (call,) = [(c, i) for c, i in self.calls if c[0] == "smbpasswd"]
        self.assertEqual(call, (["smbpasswd", "-a", "-s", "brandon"], "Secret-pass-1\nSecret-pass-1\n"))
        self.assertNotIn("Secret-pass-1", repr(self.m.State.data))

    def test_a_refused_login_is_reported(self):
        self.smbpasswd_rc = 1
        with self.assertRaises(self.m.Abort):
            self.m.BY_ID["share-login"].run()
        self.assertEqual(self.m.BY_ID["share-login"].probe(), "todo")

    def test_a_dry_run_changes_nothing(self):
        with mock.patch.object(self.m.Opt, "dry", True):
            for sid in ("share-folders", "share-config", "share-login"):
                self.m.BY_ID[sid].run()
        self.assertFalse(os.path.exists(self.m.P(self.m.SHARE_CONF)))
        self.assertEqual(self.ran("smbpasswd"), [])

    def test_sharing_can_be_removed_and_the_files_are_left_alone(self):
        self.m.BY_ID["share-folders"].run()
        self.m.BY_ID["share-config"].run()
        self.m.State.data["share_login"] = "brandon"
        keep = self.m.P("/mnt/storage/movies/film.mkv")
        open(keep, "w").close()
        with mock.patch.object(self.m, "yesno", lambda *a, **k: True):
            self.m.share_remove()
        self.assertFalse(os.path.exists(self.m.P(self.m.SHARE_CONF)))
        self.assertNotIn("homelab.conf", self.main_conf())
        self.assertIn("workgroup = WORKGROUP", self.main_conf())
        self.assertEqual(self.ran("smbpasswd", "-x", "brandon"), [["smbpasswd", "-x", "brandon"]])
        self.assertNotIn("share", self.m.State.data)
        self.assertTrue(os.path.exists(keep))

    def test_the_password_can_be_set_again(self):
        self.m.share_password()
        self.assertEqual([i for c, i in self.calls if c[0] == "smbpasswd"], ["Secret-pass-1\nSecret-pass-1\n"])

    def test_the_addresses_to_type_in_file_explorer_are_the_local_and_the_tailscale_name(self):
        self.assertEqual(self.m.share_addresses(), ["\\\\192.168.1.198", "\\\\homelab.example.ts.net"])

    def test_the_command_is_known_everywhere(self):
        with open(os.path.join(helpers.ROOT, "installer", "homelab-setup")) as f:
            text = f.read()
        self.assertIn("elif cmd == \"share\"", text)
        self.assertEqual(text.count('"navilist", "share"'), 3)
        self.assertIn("  share                    share the movies and shows folders with Windows", text)


if __name__ == "__main__":
    unittest.main()
