#!/usr/bin/env bash
# Files that were saved in the plain pool folder on the boot drive are copied onto a new drive.
# A different file at the same path on the new drive must stop the copy; nothing is removed from the boot drive.
. "$(dirname "$0")/lab.sh"
lab_init
lab_drive TMAIN1 40
# 1. a new drive that already holds a different file at the same path
mkdir -p "$MAIN_POOL/docs" "$DISKS_DIR/TMAIN1/docs"
printf 'boot copy\n' >"$MAIN_POOL/docs/a.txt"; touch -d '2021-01-01' "$MAIN_POOL/docs/a.txt"
printf 'the file that is already on the drive\n' >"$DISKS_DIR/TMAIN1/docs/a.txt"
out=$(absorb_plain_pool main "$DISKS_DIR/TMAIN1" 2>&1 </dev/null); rc=$?
echo "$out" | sed 's/^/    | /'
check "the copy stops with an error" test "$rc" -ne 0
check "the boot drive file is still there" grep -q 'boot copy' "$MAIN_POOL/docs/a.txt"
check "the file on the drive is untouched" grep -q 'already on the drive' "$DISKS_DIR/TMAIN1/docs/a.txt"
# 2. no conflict: everything is copied and verified
rm -f "$DISKS_DIR/TMAIN1/docs/a.txt"
printf 'second\n' >"$MAIN_POOL/docs/b.txt"
mkdir -p "$STATE_DIR"
out=$(absorb_plain_pool main "$DISKS_DIR/TMAIN1" 2>&1 </dev/null); rc=$?
echo "$out" | sed 's/^/    | /'
check "the copy succeeds" test "$rc" -eq 0
check "both files are on the drive" test -f "$DISKS_DIR/TMAIN1/docs/a.txt" -a -f "$DISKS_DIR/TMAIN1/docs/b.txt"
check "the content is right" grep -q 'boot copy' "$DISKS_DIR/TMAIN1/docs/a.txt"
lab_result
