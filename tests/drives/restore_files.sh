#!/usr/bin/env bash
# Restore from a backup folder: only missing files are copied, files already in the pool are never overwritten, and the result is checked.
. "$(dirname "$0")/lab.sh"
lab_init
lab_drive TMAIN1 40 && lab_drive TMAIN2 40
lab_pool main
SRC="$LAB_DIR/backup-copy"
mkdir -p "$SRC/main/photos" "$SRC/main/docs" "$MAIN_POOL/docs"
printf 'photo one\n' >"$SRC/main/photos/1.jpg"
printf 'deleted since the backup\n' >"$SRC/main/docs/gone.txt"
printf 'old version from the backup\n' >"$SRC/main/docs/kept.txt"
printf 'current version in the pool\n' >"$MAIN_POOL/docs/kept.txt"
ln -s 1.jpg "$SRC/main/photos/link.jpg"
out=$(restore_files "$SRC" 2>&1 </dev/null); rc=$?
echo "$out" | sed 's/^/    | /'
check "the restore finishes" test "$rc" -eq 0
check "a missing photo is back" test -f "$MAIN_POOL/photos/1.jpg"
check "a file deleted since the backup is back" test -f "$MAIN_POOL/docs/gone.txt"
check "a symbolic link is back" test -L "$MAIN_POOL/photos/link.jpg"
check "a file already in the pool is not overwritten" grep -q 'current version' "$MAIN_POOL/docs/kept.txt"
out=$(restore_files "$SRC" 2>&1 </dev/null); rc=$?
check "a second restore finds nothing to do" grep -q 'Nothing is missing' <<<"$out"
lab_result
