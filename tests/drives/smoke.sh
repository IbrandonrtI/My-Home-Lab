#!/usr/bin/env bash
# Does the lab itself work: two Main drives, a pool, a file through the pool.
. "$(dirname "$0")/lab.sh"
lab_init
lab_drive TMAIN1 40 && lab_drive TMAIN2 40
lab_pool main
check "the pool is mounted" mountpoint -q "$MAIN_POOL"
echo hello >"$MAIN_POOL/a.txt"
check "a file written through the pool lands on a drive" test -f "$DISKS_DIR/TMAIN1/a.txt"
check "branches are listed in order" test "$(branches_of main | xargs -n1 basename | tr '\n' ' ')" = "TMAIN1 TMAIN2 "
lab_result
