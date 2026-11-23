"""The tick list of the nightly backup: the setting the panel writes and what the backup script does with it."""
import os
import shutil
import subprocess
import tempfile
import unittest

import helpers

HAVE_RSYNC = shutil.which("rsync") is not None and shutil.which("bash") is not None


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TickList(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="hlb-test-")
        self.src = os.path.join(self.dir, "main")
        self.conf = os.path.join(self.dir, "homelab-backup.conf")
        for name in ("immich", "nextcloud", "music"):
            os.makedirs(os.path.join(self.src, name))
        write(self.conf, 'SRC="%s"\nRETENTION_DAYS=30\n' % self.src)
        self.tasks = helpers.load_script("homelab_backup_tasks", "scripts/homelab-backup-tasks", {
            "HLB_CONF": os.path.join(self.dir, "tasks.json"), "HLB_STATE": os.path.join(self.dir, "state"),
            "HLB_LEGACY_CONF": self.conf, "HLB_CRONTAB": "true", "HLB_LOGFILE": os.path.join(self.dir, "log")})
        self.tasks.LEGACY_CONF = self.conf
        self.nightly = self.tasks.nightly_task()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def save(self, skip):
        return self.tasks.clean_task({"name": "Nightly", "enabled": True, "schedule": {"kind": "daily", "time": "02:00"}, "skip": skip}, self.nightly)

    def test_everything_is_ticked_until_you_untick_something(self):
        self.assertEqual(self.tasks.nightly_skip(), [])
        self.assertEqual(self.tasks.main_folders(), ["immich", "music", "nextcloud"])

    def test_unticked_folders_are_written_to_the_settings_file(self):
        self.save(["music"])
        self.assertIn('SKIP_FOLDERS="music"', read(self.conf))
        self.assertIn("RETENTION_DAYS=30", read(self.conf))
        self.assertEqual(self.tasks.nightly_skip(), ["music"])
        self.save([])
        self.assertEqual(self.tasks.nightly_skip(), [])

    def test_a_folder_that_is_left_out_can_be_ticked_again_even_when_it_is_gone(self):
        self.save(["music"])
        shutil.rmtree(os.path.join(self.src, "music"))
        self.assertIn("music", self.tasks.main_folders())

    def test_bad_names_and_an_empty_backup_are_refused(self):
        for bad in (["../x"], ["a/b"], ["*"], ["lost+found"], [".."], "music", [5]):
            with self.assertRaises(self.tasks.Bad, msg=repr(bad)):
                self.save(bad)
        with self.assertRaises(self.tasks.Bad):
            self.save(["immich", "nextcloud", "music"])
        self.assertEqual(self.tasks.nightly_skip(), [])

    def test_the_panel_view_carries_the_list(self):
        self.save(["music"])
        view = self.tasks.task_view(self.nightly)
        self.assertEqual(view["skip"], ["music"])
        self.assertEqual(view["folders"], ["immich", "music", "nextcloud"])


@unittest.skipUnless(HAVE_RSYNC, "rsync and bash are needed")
class BackupScript(unittest.TestCase):
    """Run the real script on small folders. A fake mountpoint makes the folders count as mounted pools."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="hlb-run-")
        d = self.dir
        for sub in ("src/photos", "src/docs", "src/music", "dest/main/music", "bin", "state"):
            os.makedirs(os.path.join(d, sub))
        write(os.path.join(d, "src/photos/a.jpg"), "p1")
        write(os.path.join(d, "src/docs/a.txt"), "d1")
        write(os.path.join(d, "src/music/s.mp3"), "new")
        write(os.path.join(d, "dest/main/music/s.mp3"), "stale")
        write(os.path.join(d, "bin/mountpoint"), "#!/bin/sh\nexit 0\n")
        os.chmod(os.path.join(d, "bin/mountpoint"), 0o755)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_script(self, skip, *args):
        d = self.dir
        write(os.path.join(d, "conf"), 'SRC="%s/src"\nDEST_POOL="%s/dest"\nLOGFILE="%s/log"\nSTATUS_FILE="%s/state/last-run"\nSKIP_FOLDERS="%s"\n' % (d, d, d, d, skip))
        env = dict(os.environ, HOMELAB_EXTRA_PATH=os.path.join(d, "bin"), BACKUP_CONF=os.path.join(d, "conf"))
        subprocess.run(["bash", os.path.join(helpers.ROOT, "scripts/homelab-backup")] + list(args), env=env, capture_output=True, text=True, timeout=120)
        return read(os.path.join(d, "log"))

    def copy(self, rel):
        path = os.path.join(self.dir, "dest/main", rel)
        return read(path) if os.path.exists(path) else None

    def test_a_folder_that_is_left_out_is_not_copied_and_its_old_copy_stays(self):
        log = self.run_script("music")
        self.assertEqual(self.copy("docs/a.txt"), "d1")
        self.assertEqual(self.copy("photos/a.jpg"), "p1")
        self.assertEqual(self.copy("music/s.mp3"), "stale")
        self.assertIn("left out of the backup (not ticked): music", log)

    def test_the_sample_and_the_full_check_do_not_call_an_old_copy_damaged(self):
        self.run_script("music")
        write(os.path.join(self.dir, "src/music/s.mp3"), "newer")
        log = self.run_script("music")
        self.assertNotIn("still differ", log)
        self.assertNotIn("differ from the originals", log)
        log = self.run_script("music", "verify")
        self.assertIn("verify: every file matches", log)

    def test_without_a_setting_everything_is_copied(self):
        self.run_script("")
        self.assertEqual(self.copy("music/s.mp3"), "new")

    def test_bad_names_in_the_setting_are_ignored(self):
        log = self.run_script("../x|*|lost+found|a/b|music")
        self.assertIn("(not ticked): music", log)
        self.assertEqual(self.copy("photos/a.jpg"), "p1")

    def test_nothing_is_copied_when_every_folder_is_left_out(self):
        log = self.run_script("music|docs|photos")
        self.assertIn("is left out of the backup, nothing was copied", log)
        self.assertIsNone(self.copy("docs/a.txt"))


if __name__ == "__main__":
    unittest.main()
