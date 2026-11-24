#!/usr/bin/env bash
# F19 for `balance`: a file changed through the pool between pass 1 and pass 2 must keep its newer content.
# TMAIN1 comes first in the pool order, so a change to a file that exists on both drives is written to TMAIN1, the drive that receives the file.
. "$(dirname "$0")/lab.sh"
lab_init
lab_drive TMAIN1 60 && lab_drive TMAIN2 60
lab_pool main
mkdir -p "$DISKS_DIR/TMAIN2/media"
for i in 1 2 3 4 5 6; do head -c 4000000 /dev/urandom >"$DISKS_DIR/TMAIN2/media/f$i.bin"; done
touch -d '3 days ago' "$DISKS_DIR"/TMAIN2/media/*.bin
sync
before=$(cd "$DISKS_DIR/TMAIN2" && find . -type f ! -path './lost+found/*' | sort | tr '\n' ' ')
# every file that moves is changed once, after pass 1 (when the containers are told to stop)
stop_containers() { for f in "$MAIN_POOL"/media/*.bin; do printf 'changed during the move\n' >"$f"; done; }
out=$(balance_main 2>&1 </dev/null); rc=$?
echo "$out" | sed 's/^/    | /'
check "the balance finishes" test "$rc" -eq 0
check "something moved to TMAIN1" test -n "$(find "$DISKS_DIR/TMAIN1/media" -type f 2>/dev/null)"
bad=0
for f in "$MAIN_POOL"/media/*.bin; do grep -q 'changed during the move' "$f" || bad=$((bad + 1)); done
check "every file still has its newer content in the pool" test "$bad" -eq 0
after=$(cd "$MAIN_POOL" && find . -type f ! -path './lost+found/*' | sort | tr '\n' ' ')
check "no file was lost" test "$before" = "$after"
lab_result
