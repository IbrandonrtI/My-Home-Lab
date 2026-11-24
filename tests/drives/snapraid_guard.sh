#!/usr/bin/env bash
# The nightly SnapRAID update (real snapraid on loop drives): many deleted files stop it and are recorded; a normal night runs.
command -v snapraid >/dev/null 2>&1 || { echo "skipped: snapraid is not installed"; exit 0; }
. "$(dirname "$0")/lab.sh"
lab_init
lab_blank_loops 3 60
preset_flow snapraid1 >/dev/null 2>&1 </dev/null
check "the SnapRAID setup exists" test "$(preset_current)" = snapraid1
for i in $(seq 1 10); do printf 'file %s\n' "$i" >"$MAIN_POOL/f$i.txt"; done
sync
SNAPRAID_DELETE_LIMIT=3
out=$(snapraid_nightly 2>&1); rc=$?
check "a night with only new files runs" test "$rc" -eq 0
check "it is recorded as ok" grep -q '|ok|' "$SNAPRAID_STATUS"
rm -f "$MAIN_POOL"/f{1,2,3,4,5}.txt
out=$(snapraid_nightly 2>&1); rc=$?
echo "$out" | sed 's/^/    | /'
check "five deleted files stop the update" test "$rc" -eq 3
check "it is recorded as aborted" grep -q '|aborted|' "$SNAPRAID_STATUS"
check "the message tells what to do" grep -q 'drives snapraid sync' <<<"$out"
out=$(snapraid -c "$SNAPRAID_CONF" diff 2>&1)
check "nothing was updated: the deletions are still waiting" grep -qE '[[:space:]]5 removed' <<<"$out"
SNAPRAID_DELETE_LIMIT=40   # the default again
export SNAPRAID_DELETE_LIMIT
out=$(snapraid_flow sync 2>&1); rc=$?
check "the manual update works" test "$rc" -eq 0
check "it is recorded as ok again" grep -q '|ok|' "$SNAPRAID_STATUS"
printf '# old schedule\n0 4 * * * root snapraid sync -q\n' >"$SNAPRAID_CRON"
snapraid_flow schedule >/dev/null 2>&1
check "the schedule action rewrites an old schedule" grep -q "$SNAPRAID_NIGHTLY" "$SNAPRAID_CRON"
lab_result
