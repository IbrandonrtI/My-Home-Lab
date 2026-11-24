"""The drives tool on loop devices: real ext4 drives (files that act as drives) in a real mergerfs pool.

Each scenario in tests/drives/ is a small shell script that prints one "ok" or "FAIL" line per check.
These tests need root, loop devices, FUSE, mergerfs, rsync and parted. When one of them is missing, the tests are skipped.
"""
import os
import shutil
import subprocess
import unittest

import helpers

DIR = os.path.join(helpers.ROOT, "tests", "drives")
NEEDED = ("losetup", "mkfs.ext4", "mergerfs", "rsync", "parted", "partprobe", "blkid", "fusermount3")

# scenario file, then its argument if it takes one
SCENARIOS = [
    ("smoke.sh",),
    ("drain_between_passes.sh",),
    ("drain_conflict.sh",),
    ("drain_retry.sh",),
    ("balance_between_passes.sh",),
    ("absorb_boot_files.sh",),
    ("moveboot.sh",),
    ("restore_files.sh",),
    ("migrate_copy.sh",),
    ("preset_flow.sh", "pool"),
    ("preset_flow.sh", "mirror"),
    ("preset_flow.sh", "snapraid1"),
    ("snapraid_guard.sh",),
]


def why_not():
    if os.geteuid() != 0:
        return "needs root"
    missing = [c for c in NEEDED if shutil.which(c) is None and shutil.which(c.replace("3", "")) is None]
    if missing:
        return "missing: " + ", ".join(missing)
    if not os.path.exists("/dev/fuse"):
        return "no /dev/fuse"
    probe = subprocess.run(["losetup", "-f"], capture_output=True, text=True, check=False)
    if probe.returncode != 0:
        return "no loop devices"
    return ""


@unittest.skipIf(why_not(), "the loop-device tests cannot run here: " + why_not())
class DrivesLoopTests(unittest.TestCase):
    def test_scenarios(self):
        for scenario in SCENARIOS:
            with self.subTest(" ".join(scenario)):
                run = subprocess.run(
                    ["bash", os.path.join(DIR, scenario[0]), *scenario[1:]],
                    capture_output=True, text=True, timeout=600, check=False,
                )
                lines = run.stdout.splitlines()
                failed = [line for line in lines if line.startswith("FAIL")]
                oks = [line for line in lines if line.startswith("ok")]
                skipped = [line for line in lines if line.startswith("skipped")]
                if skipped:
                    self.skipTest(skipped[0])
                self.assertEqual(failed, [], run.stdout + run.stderr)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertTrue(oks, "the scenario ran no checks:\n" + run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
