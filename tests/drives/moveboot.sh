#!/usr/bin/env bash
# Files saved on the boot drive while the pool had no drive are moved into the pool.
# A file that is already in the pool is never replaced; a different file at the same path keeps the boot copy and is reported.
. "$(dirname "$0")/lab.sh"
lab_init
lab_drive TMAIN1 40 && lab_drive TMAIN2 40
mkdir -p "$MAIN_POOL/docs"
printf 'saved on boot\n' >"$MAIN_POOL/docs/new.txt"
printf 'boot version\n' >"$MAIN_POOL/docs/same.txt"; touch -d 2021-01-01 "$MAIN_POOL/docs/same.txt"
lab_pool main
mkdir -p "$MAIN_POOL/docs"; printf 'pool version, written later\n' >"$MAIN_POOL/docs/same.txt"
out=$(moveboot_flow 2>&1 </dev/null); rc=$?
echo "$out" | sed 's/^/    | /'
check "the move reports the different file and stops" test "$rc" -ne 0
check "the new file arrived in the pool" test -f "$MAIN_POOL/docs/new.txt"
check "the pool's version was kept" grep -q 'pool version' "$MAIN_POOL/docs/same.txt"
boot_view_open
check "the boot copies were not removed" test -f "$BOOT_UNDER/docs/same.txt" -a -f "$BOOT_UNDER/docs/new.txt"
boot_view_close
lab_result
