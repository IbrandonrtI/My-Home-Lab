#!/usr/bin/env bash
# A drain that is started again after an interrupted copy must not call the files that are already there a conflict.
. "$(dirname "$0")/lab.sh"
lab_init
lab_drive TMAIN1 40 && lab_drive TMAIN2 40
lab_pool main
mkdir -p "$DISKS_DIR/TMAIN2/a/b"
printf 'one\n' >"$DISKS_DIR/TMAIN2/a/one.txt"; printf 'two\n' >"$DISKS_DIR/TMAIN2/a/b/two.txt"; ln -s one.txt "$DISKS_DIR/TMAIN2/a/soft.txt"
head -c 3000000 /dev/urandom >"$DISKS_DIR/TMAIN2/a/big.bin"
ln "$DISKS_DIR/TMAIN2/a/one.txt" "$DISKS_DIR/TMAIN2/a/hard.txt"
# first try copied some of the files and was stopped
rsync -aH "$DISKS_DIR/TMAIN2/a/one.txt" "$DISKS_DIR/TMAIN1/" 2>/dev/null; mkdir -p "$DISKS_DIR/TMAIN1/a"; rsync -aH "$DISKS_DIR/TMAIN2/a/one.txt" "$DISKS_DIR/TMAIN1/a/"; rm -f "$DISKS_DIR/TMAIN1/one.txt"
out=$(drain_branch "$DISKS_DIR/TMAIN2" 2>&1); rc=$?
echo "$out" | sed 's/^/    | /'
check "the second try finishes" test "$rc" -eq 0
check "every file is on the drive that stays" test -f "$DISKS_DIR/TMAIN1/a/b/two.txt" -a -L "$DISKS_DIR/TMAIN1/a/soft.txt" -a -f "$DISKS_DIR/TMAIN1/a/big.bin"
check "the large file is identical" cmp -s "$DISKS_DIR/TMAIN1/a/big.bin" "$DISKS_DIR/TMAIN2/a/big.bin"
check "hard links stay hard links" test "$(stat -c %h "$DISKS_DIR/TMAIN1/a/hard.txt")" = 2
check "the drive being emptied still has its files" test -f "$DISKS_DIR/TMAIN2/a/one.txt"
lab_result
