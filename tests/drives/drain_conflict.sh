#!/usr/bin/env bash
# F7: the drive that receives the files already has a different file at the same path.
# The drain must stop and say which file, and change nothing, instead of overwriting the file that is already there.
. "$(dirname "$0")/lab.sh"
lab_init
lab_drive TMAIN1 40 && lab_drive TMAIN2 40
lab_pool main
mkdir -p "$DISKS_DIR/TMAIN1/docs" "$DISKS_DIR/TMAIN2/docs"
printf 'old copy\n' >"$DISKS_DIR/TMAIN1/docs/report.txt"
printf 'the real, newer report with more in it\n' >"$DISKS_DIR/TMAIN2/docs/report.txt"
touch -d '2020-01-01' "$DISKS_DIR/TMAIN1/docs/report.txt"
printf 'only here\n' >"$DISKS_DIR/TMAIN1/docs/only.txt"
out=$(drain_branch "$DISKS_DIR/TMAIN1" 2>&1); rc=$?
echo "$out" | sed 's/^/    | /'
check "the drain stops with an error" test "$rc" -ne 0
check "the file that was already there is untouched" grep -q 'the real, newer report' "$DISKS_DIR/TMAIN2/docs/report.txt"
check "the drive that was being emptied is untouched" grep -q 'old copy' "$DISKS_DIR/TMAIN1/docs/report.txt"
check "the message names the file" grep -q 'docs/report.txt' <<<"$out"
check "no file was copied before the stop" test ! -e "$DISKS_DIR/TMAIN2/docs/only.txt"
lab_result
