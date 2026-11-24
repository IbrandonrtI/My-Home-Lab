#!/usr/bin/env bash
# Moving a whole folder from one drive of a pool to another, and keeping new files of that folder on its drive.
# Two drives hold different folders. Movies is moved to the second drive. Afterwards the pool looks the same, the first drive no longer has the
# folder at all (not even empty), and a new file written into the folder through the pool lands on the second drive while new files in the
# other folders still land on the first.
. "$(dirname "$0")/lab.sh"
lab_init
lab_drive TMAIN1 80 && lab_drive TMAIN2 80
lab_pool main
D1=$DISKS_DIR/TMAIN1; D2=$DISKS_DIR/TMAIN2
mkdir -p "$D1/movies/Alpha (2020)" "$D1/shows/Show/Season 01" "$D1/photos" "$D1/movies/.hidden-stays"
head -c 3000000 /dev/urandom >"$D1/movies/Alpha (2020)/Alpha (2020).mkv"
head -c 1000000 /dev/urandom >"$D1/movies/Beta.mkv"
head -c 2000000 /dev/urandom >"$D1/shows/Show/Season 01/Show S01E01.mkv"
head -c 500000 /dev/urandom >"$D1/photos/one.jpg"
printf 'odd name' >"$D1/movies/it's a file with spaces & marks.txt"
chmod 750 "$D1/movies"; chown 1234:1234 "$D1/movies/Beta.mkv"
sync
before=$(cd "$MAIN_POOL" && find . -type f ! -path './lost+found/*' -exec md5sum {} + | sort -k2 | md5sum)

check "the pool can be used for folder moves" folders_why_not main
check "a folder name goes through hex and back" test "$(folder_from_hex "$(folder_hex "it's a name")")" = "it's a name"
folder_from_hex "$(folder_hex ".hidden")" >/dev/null && check "a hidden folder name is refused" false || check "a hidden folder name is refused" true
folder_from_hex "$(folder_hex "a/b")" >/dev/null && check "a name with a slash is refused" false || check "a name with a slash is refused" true

json=$(panel_folders_json main)
check "the folder list is valid JSON" python3 -c 'import json,sys; d=json.loads(sys.argv[1]); assert d["eligible"] and [x["name"] for x in d["folders"]]==["movies","photos","shows"], d' "$json"
check "the list gives the size of movies on the first drive" python3 -c 'import json,sys; d=json.loads(sys.argv[1]); m=[x for x in d["folders"] if x["name"]=="movies"][0]; assert m["bytes"]["TMAIN1"]>4000000 and m["bytes"]["TMAIN2"] is None, m' "$json"

# a dry run changes nothing
DRY_RUN=1 folders_move_core main "$D2" yes movies >/dev/null 2>&1
check "a dry run leaves the folder where it was" test -d "$D1/movies" -a ! -d "$D2/movies"

out=$(folders_move_core main "$D2" yes movies 2>&1 </dev/null); rc=$?
echo "$out" | sed 's/^/    | /'
check "the move finishes" test "$rc" -eq 0
check "the folder is on the second drive" test -f "$D2/movies/Beta.mkv" -a -f "$D2/movies/Alpha (2020)/Alpha (2020).mkv"
check "the first drive no longer has the folder, not even an empty one" test ! -e "$D1/movies"
check "the other folders did not move" test -d "$D1/shows" -a -d "$D1/photos" -a ! -e "$D2/shows"
check "the folder keeps its permissions" test "$(stat -c %a "$D2/movies")" = 750
check "a file keeps its owner" test "$(stat -c %u "$D2/movies/Beta.mkv")" = 1234
check "the pool shows the same files with the same content" test "$before" = "$(cd "$MAIN_POOL" && find . -type f ! -path './lost+found/*' -exec md5sum {} + | sort -k2 | md5sum)"
check "pinning is saved" pool_pinned main
check "the pool policy is now the path-keeping one" test "$(pool_policy main)" = epff
check "the running pool uses it" test "$(pool_policy_live "$MAIN_POOL")" = epff
check "fstab has it" test "$(pool_policy_now "$MAIN_POOL")" = epff

printf 'new movie' >"$MAIN_POOL/movies/New Movie.mkv"
mkdir -p "$MAIN_POOL/movies/Gamma (2022)" && printf 'new' >"$MAIN_POOL/movies/Gamma (2022)/Gamma (2022).mkv"
printf 'new episode' >"$MAIN_POOL/shows/Show/Season 01/Show S01E02.mkv"
printf 'new photo' >"$MAIN_POOL/photos/two.jpg"
check "a new file in the moved folder lands on the second drive" test -f "$D2/movies/New Movie.mkv" -a ! -e "$D1/movies"
check "a new subfolder of the moved folder lands on the second drive" test -f "$D2/movies/Gamma (2022)/Gamma (2022).mkv"
check "new files in the other folders stay on the first drive" test -f "$D1/shows/Show/Season 01/Show S01E02.mkv" -a -f "$D1/photos/two.jpg"

# moving it again to the same drive does nothing, and moving it back works
out=$(folders_move_core main "$D2" yes movies 2>&1 </dev/null)
check "moving it to the drive it is on says so" grep -q "already only on" <<<"$out"
out=$(folders_move_core main "$D1" yes movies 2>&1 </dev/null); rc=$?
check "moving it back works" test "$rc" -eq 0 -a -f "$D1/movies/New Movie.mkv" -a ! -e "$D2/movies"

# turning the setting off puts the plain fill order back
folders_apply_pin main no >/dev/null 2>&1
check "unpinning is saved" bash -c '! pool_pinned main' 2>/dev/null || ! pool_pinned main
check "the policy is the plain one again" test "$(pool_policy main)" = ff

# not enough room: nothing is changed
mkdir -p "$D2/filler"; head -c 35000000 /dev/urandom >"$D2/filler/f.bin"; head -c 50000000 /dev/urandom >"$D1/shows/big.bin"; sync
out=$(folders_move_core main "$D2" yes shows 2>&1 </dev/null); rc=$?
check "a move that does not fit is refused" test "$rc" -ne 0
check "and nothing moved" test -f "$D1/shows/big.bin" -a ! -e "$D2/shows"

# a file on both drives with different content is never replaced
rm -f "$D1/shows/big.bin"; rm -rf "$D2/filler"
mkdir -p "$D2/photos"; printf 'different' >"$D2/photos/one.jpg"
out=$(folders_move_core main "$D2" yes photos 2>&1 </dev/null); rc=$?
check "a file that differs on both drives stops the move" test "$rc" -ne 0
check "and the files are untouched" test "$(cat "$D2/photos/one.jpg")" = different -a -f "$D1/photos/one.jpg"

# the panel command takes hex names and refuses odd input
out=$(panel_movefolders main TMAIN2 "$(folder_hex shows)" no 2>&1 </dev/null); rc=$?
check "the panel move works" test "$rc" -eq 0 -a -f "$D2/shows/Show/Season 01/Show S01E01.mkv" -a ! -e "$D1/shows"
out=$(panel_movefolders main TMAIN9 "$(folder_hex shows)" no 2>&1 </dev/null); rc=$?
check "an unknown drive is refused" test "$rc" -ne 0
out=$(panel_movefolders main TMAIN2 "$(folder_hex nothere)" no 2>&1 </dev/null); rc=$?
check "a folder that is not there is refused" test "$rc" -ne 0
# not offered where it would do harm
snapraid_active() { return 0; }
folders_why_not main >/dev/null 2>&1 && check "SnapRAID main is refused" false || check "SnapRAID main is refused" true
snapraid_active() { return 1; }
folders_why_not backup >/dev/null 2>&1 && check "a pool with no drives is refused" false || check "a pool with no drives is refused" true
lab_result
