#!/usr/bin/env bash
# F19: files written through the pool while a drive is being drained.
# Pass 1 copies the files and the services keep running. A service then changes a file through the pool. mergerfs sends the change to the
# first drive that has the file, and when the drive being drained comes later in the order, that is the drive it is copied TO.
# Pass 2 must not put the older copy from the drained drive back over that newer file.
. "$(dirname "$0")/lab.sh"
lab_init
lab_drive TMAIN1 40 && lab_drive TMAIN2 40
lab_pool main
mkdir -p "$DISKS_DIR/TMAIN2/photos"
printf 'original text of the file\n' >"$DISKS_DIR/TMAIN2/photos/list.txt"
printf 'untouched\n' >"$DISKS_DIR/TMAIN2/photos/other.txt"
touch -d '3 days ago' "$DISKS_DIR/TMAIN2/photos/list.txt" "$DISKS_DIR/TMAIN2/photos/other.txt"
# the "service" changes list.txt once the containers have been told to stop (that is after pass 1, before pass 2)
stop_containers() { printf 'newer text written during the drain\n' >"$MAIN_POOL/photos/list.txt"; }
out=$(drain_branch "$DISKS_DIR/TMAIN2" 2>&1); rc=$?
echo "$out" | sed 's/^/    | /'
check "the drain finishes" test "$rc" -eq 0
check "the newer text survives on the pool" grep -q 'newer text written during the drain' "$MAIN_POOL/photos/list.txt"
check "the newer text is on the drive that stays" grep -q 'newer text' "$DISKS_DIR/TMAIN1/photos/list.txt"
check "the other file arrived" test -f "$DISKS_DIR/TMAIN1/photos/other.txt"
lab_result
