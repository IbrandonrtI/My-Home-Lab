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
out=$(ASSUME_YES=0 moveboot_flow 2>&1 </dev/null); rc=$?
echo "$out" | sed 's/^/    | /'
check "the move reports the different file and stops" test "$rc" -ne 0
check "the new file arrived in the pool" test -f "$MAIN_POOL/docs/new.txt"
check "the pool's version was kept" grep -q 'pool version' "$MAIN_POOL/docs/same.txt"
boot_view_open
check "the boot copies were not removed" test -f "$BOOT_UNDER/docs/same.txt" -a -f "$BOOT_UNDER/docs/new.txt"
boot_view_close
check "the report names the file and both versions" grep -q 'docs/same.txt' <<<"$out"

# a file that only differs in its time stamp is not a conflict
mkdir -p "$MAIN_POOL/docs"
boot_view_open
printf 'identical\n' >"$BOOT_UNDER/docs/time.txt"; touch -d 2020-01-01 "$BOOT_UNDER/docs/time.txt"
printf 'identical\n' >"$MAIN_POOL/docs/time.txt"
check "a file with the same content is not listed" test "$(boot_conflicts)" = "docs/same.txt"
boot_view_close

# with --yes the boot version is saved next to the pool's, checked, and the old copies can go
out=$(ASSUME_YES=1 moveboot_flow 2>&1 </dev/null); rc=$?
echo "$out" | sed 's/^/    | /'
check "the move finishes when the other version is saved" test "$rc" -eq 0
check "the pool's version is still the one in use" grep -q 'pool version' "$MAIN_POOL/docs/same.txt"
check "the boot version is saved in the leftovers folder" grep -rq 'boot version' "$MAIN_POOL/boot-drive-leftovers"
boot_view_open
check "the boot drive no longer holds the files" test ! -e "$BOOT_UNDER/docs/same.txt" -a ! -e "$BOOT_UNDER/docs/new.txt"
boot_view_close
lab_result
