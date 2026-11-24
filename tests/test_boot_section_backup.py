"""A pool made only of a boot-drive section (MAINBOOT, BACKUPBOOT) is connected: the stats and the bell must not call it missing."""
import os
import tempfile
import unittest

import helpers


class BootSectionPoolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.st = helpers.load_script("homelab_stats", "scripts/homelab-stats")
        cls.al = helpers.alerts()

    def setUp(self):
        self.disks = tempfile.mkdtemp(prefix="disks-")
        os.environ["HOMELAB_DISKS_DIR"] = self.disks
        os.environ["HOMELAB_STATS_NOMOUNT"] = "1"  # a folder stands in for a mount
        self.addCleanup(os.environ.pop, "HOMELAB_DISKS_DIR", None)
        self.addCleanup(os.environ.pop, "HOMELAB_STATS_NOMOUNT", None)
        self.st.temps = lambda: {}
        self.st.pool_space = lambda path: (100 * 2 ** 30, 25 * 2 ** 30, 75 * 2 ** 30)  # the pool itself is mounted

    def block(self, role):
        return self.st.pool_block("/mnt/x", role, {"main": [], "backup": []}, [], [])[0]

    def test_a_backup_pool_with_only_a_boot_section_is_connected(self):
        os.mkdir(os.path.join(self.disks, "BACKUPBOOT"))
        blk = self.block("backup")
        self.assertEqual(blk["percent"], "25%")
        self.assertEqual(blk["health"], "On the boot drive")
        self.assertEqual(blk["drives"], "1")

    def test_a_backup_pool_with_no_drive_at_all_is_still_not_connected(self):
        self.assertEqual(self.block("backup")["percent"], "Not connected")

    def test_the_main_pool_with_only_a_boot_section_is_not_called_empty(self):
        os.mkdir(os.path.join(self.disks, "MAINBOOT"))
        self.assertEqual(self.block("main")["health"], "On the boot drive")

    def test_a_section_does_not_count_for_the_other_pool(self):
        os.mkdir(os.path.join(self.disks, "MAINBOOT"))
        self.assertEqual(self.block("backup")["percent"], "Not connected")

    def test_the_bell_knows_a_backup_boot_section_in_fstab(self):
        fd, path = tempfile.mkstemp(prefix="fstab-")
        os.close(fd)
        self.addCleanup(os.remove, path)
        with open(path, "w", encoding="utf-8") as f:
            f.write("/var/lib/homelab-sections/backup.img  /mnt/disks/BACKUPBOOT  ext4  loop,nofail  0  0\n")
        self.al.FSTAB = path
        self.assertEqual(self.al.backup_drives_configured(), ["/mnt/disks/BACKUPBOOT"])
        self.assertTrue(self.al.backup_drive_configured())


if __name__ == "__main__":
    unittest.main()
