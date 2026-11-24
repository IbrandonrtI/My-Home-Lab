#!/usr/bin/env bash
# The ready-made setups (sudo drives preset) that build plain ext4 pools: pool, mirror and SnapRAID. Drives are loop devices.
. "$(dirname "$0")/lab.sh"
lab_init
SCEN=${1:-pool}
case "$SCEN" in
  pool)
    lab_blank_loops 2 60
    out=$(preset_flow pool 2>&1 </dev/null); rc=$?
    check "the plain pool is built" test "$rc" -eq 0
    check "the Main pool is mounted" mountpoint -q "$MAIN_POOL"
    check "the pool has two drives" test "$(branches_of main | wc -l)" -eq 2
    printf 'x\n' >"$MAIN_POOL/hello.txt"
    check "a file can be written" test -f "$MAIN_POOL/hello.txt"
    check "the setup is recorded" test "$(preset_current)" = pool ;;
  mirror)
    lab_blank_loops 2 60
    out=$(preset_flow mirror 2>&1 </dev/null); rc=$?
    check "the mirror is built" test "$rc" -eq 0
    check "one drive is Main" test "$(branches_of main | wc -l)" -eq 1
    check "one drive is Backup" test "$(branches_of backup | wc -l)" -eq 1
    check "the setup is recorded" test "$(preset_current)" = mirror ;;
  snapraid1)
    command -v snapraid >/dev/null 2>&1 || { echo "skipped: snapraid is not installed"; exit 0; }
    lab_blank_loops 3 60
    out=$(preset_flow snapraid1 2>&1 </dev/null); rc=$?
    check "the SnapRAID setup is built" test "$rc" -eq 0
    check "the data drives are in the Main pool" test "$(branches_of main | wc -l)" -eq 2
    check "one parity drive is mounted" test "$(parity_mounts | wc -l)" -eq 1
    check "the SnapRAID settings were written" test -s "$SNAPRAID_CONF"
    check "the nightly job points at the guarded run" grep -q "$SNAPRAID_NIGHTLY" "$SNAPRAID_CRON" ;;
esac
echo "$out" | tail -5 | sed 's/^/    | /'
# a second setup on top of existing drives is refused
preset_flow pool >/dev/null 2>&1 </dev/null; rc2=$?
check "a second setup is refused" test "$rc2" -ne 0
lab_result
