#!/usr/bin/env bash
# Converting the Main pool: the copy into the new setup is checked strictly, and a copy that is not complete is refused.
. "$(dirname "$0")/lab.sh"
lab_init
lab_drive TMAIN1 40 && lab_drive TMAIN2 40
lab_pool main
MIGRATE_DIR="$LAB_DIR/new-setup"; mkdir -p "$MIGRATE_DIR"
mkdir -p "$MAIN_POOL/a/b"
printf 'one\n' >"$MAIN_POOL/a/one.txt"; printf 'two\n' >"$MAIN_POOL/a/b/two.txt"; ln -s one.txt "$MAIN_POOL/a/soft.txt"
out=$(migrate_copy 2>&1); rc=$?
echo "$out" | sed 's/^/    | /'
check "a complete copy is accepted" test "$rc" -eq 0
check "every file is in the new setup" test -f "$MIGRATE_DIR/a/b/two.txt" -a -L "$MIGRATE_DIR/a/soft.txt"
# a file changed in the new setup is no longer the same
printf 'changed behind our back\n' >"$MIGRATE_DIR/a/one.txt"
rsync_run() { return 0; }   # pretend the copy step ran; only the check is under test
out=$(migrate_copy 2>&1); rc=$?
check "a copy that differs is refused" test "$rc" -ne 0
rm -f "$MIGRATE_DIR/a/b/two.txt"
out=$(migrate_copy 2>&1); rc=$?
check "a copy with a missing file is refused" test "$rc" -ne 0
lab_result
