# Which top-level folders sit on which drive of a pool, and moving whole folders from one drive to another.
# A pool shows the folders of all its drives as one. A file always lives whole on one drive, so a folder can be moved between the drives
# and the pool looks the same. When "keep new files on their drive" is on, the pool puts a new file on a drive that already has its folder.

pool_pinned() { [ "$(setting_get pin "$1")" = 1 ]; }

folders_real_branches() {
  local mp
  for mp in $(branches_of "$1"); do is_boot_section "$mp" || printf '%s\n' "$mp"; done
}

# folders_why_not ROLE: print the reason and return 1 when the folders of this pool cannot be moved between drives.
folders_why_not() {
  local role=$1 mp n=0
  if [ "$role" = main ] && array_active; then echo "The Main storage is a drive array, which is one volume, so there are no separate drives to move folders between."; return 1; fi
  if [ "$role" = main ] && snapraid_active; then echo "The Main storage uses SnapRAID. Moving folders would count as deleted files and block the nightly protection update, so it is not offered there."; return 1; fi
  for mp in $(folders_real_branches "$role"); do
    mountpoint -q "$mp" || { echo "$(branch_name "$mp") is not connected. Reconnect it first (Fix Drives)."; return 1; }
    n=$((n + 1))
  done
  if [ "$n" -lt 2 ]; then echo "This needs a pool with at least two drives. Add the second drive first."; return 1; fi
  mountpoint -q "$(role_pool "$role")" || { echo "The pool is not mounted."; return 1; }
  return 0
}

# folders_names ROLE: the top-level folders on any drive of the pool, one per line (hidden folders, lost+found and names with a line break are left out).
folders_names() {
  local mp
  for mp in $(folders_real_branches "$1"); do
    find "$mp" -mindepth 1 -maxdepth 1 -type d ! -name 'lost+found' ! -name '.*' -printf '%f\0' 2>/dev/null
  done | sort -zu | tr '\0' '\n' | grep -v '^$' || true
}

folder_bytes() {
  local n
  n=$(du -sxb -- "$1/$2" 2>/dev/null | cut -f1)
  [[ "$n" =~ ^[0-9]+$ ]] && echo "$n" || echo 0
}

folder_hex() { printf '%s' "$1" | od -An -v -tx1 | tr -d ' \n'; }

# folder_from_hex HEX: the folder name for a hex string. The panel hands names over this way so no odd character can reach a command.
folder_from_hex() {
  [[ "$1" =~ ^([0-9a-f]{2}){1,200}$ ]] || return 1
  local name
  name=$(printf '%b' "$(printf '%s' "$1" | sed 's/../\\x&/g')"; printf x)
  name=${name%x}
  case "$name" in ""|.|..|.*|*/*|*$'\n'*|lost+found) return 1 ;; esac
  printf '%s' "$name"
}

pool_policy_name() {
  case "$1" in
    ff|epff)   echo "one drive at a time" ;;
    mfs|epmfs) echo "spread by free space" ;;
    *)         echo "$1" ;;
  esac
}

# panel_folders_json ROLE: what the Drives tab shows for the folder move: the drives with their free space, and each folder with its size on each drive.
panel_folders_json() {
  local role=$1 why mp f first=1 d first_d=1 id used avail lim
  why=$(folders_why_not "$role") || { printf '{"eligible":false,"why":%s}\n' "$(json_str "$why")"; return 0; }
  printf '{"eligible":true,"role":%s,"pinned":%s,"policy":%s,"drives":[' "$(json_str "$role")" "$(pool_pinned "$role" && echo true || echo false)" "$(json_str "$(pool_policy_name "$(pool_policy "$role")")")"
  for mp in $(folders_real_branches "$role"); do
    used=$(used_bytes "$mp"); avail=$(avail_bytes "$mp"); lim=$(branch_minfree "$mp" | tr -d K); lim=${lim:-0}
    [ "$first_d" = 1 ] || printf ','
    first_d=0
    printf '{"id":%s,"name":%s,"used_bytes":%s,"free_bytes":%s,"limit_bytes":%s}' "$(json_str "$(basename "$mp")")" "$(json_str "$(branch_name "$mp")")" "$(json_num "$used")" "$(json_num "$avail")" "$(json_num $(( lim * 1024 )))"
  done
  printf '],"folders":['
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    [ "$first" = 1 ] || printf ','
    first=0
    printf '{"name":%s,"hex":%s,"bytes":{' "$(json_str "$f")" "$(json_str "$(folder_hex "$f")")"
    d=1
    for mp in $(folders_real_branches "$role"); do
      id=$(basename "$mp")
      [ "$d" = 1 ] || printf ','
      d=0
      if [ -d "$mp/$f" ]; then printf '%s:%s' "$(json_str "$id")" "$(json_num "$(folder_bytes "$mp" "$f")")"; else printf '%s:null' "$(json_str "$id")"; fi
    done
    printf '}}'
  done < <(folders_names "$role")
  printf ']}\n'
}

# folders_undo_pairs TARGET LIST...: take the copies made on TARGET away again. Only files that are still on the old drive are removed there.
folders_undo_pairs() {
  local target=$1 pair src f rel; shift
  for pair in "$@"; do
    src=${pair%%|*}; f=${pair#*|}
    while IFS= read -r -d '' rel; do rm -f -- "${target:?}/$f/$rel"; done < <(find "$src/$f" -type f -printf '%P\0' 2>/dev/null)
    find "$target/$f" -depth -type d -empty -delete 2>/dev/null || true
  done
}

# folders_move_core ROLE TARGET_MOUNT PIN(yes|no) FOLDER...: move the folders onto one drive of the pool.
folders_move_core() {
  local role=$1 target=$2 pin=$3; shift 3
  local pool mp f pair sz need=0 free lim n rel bad=0 i total_files=0 conflicts
  local -a pairs=() sizes=() others=()
  pool=$(role_pool "$role")
  for mp in $(folders_real_branches "$role"); do [ "$mp" = "$target" ] || others+=("$mp"); done
  for f in "$@"; do
    for mp in "${others[@]}"; do
      [ -d "$mp/$f" ] || continue
      sz=$(folder_bytes "$mp" "$f")
      pairs+=("$mp|$f"); sizes+=("$sz"); need=$((need + sz))
    done
  done
  if [ ${#pairs[@]} -eq 0 ]; then
    say "Those folders are already only on $(branch_name "$target"). Nothing needs to be moved."
    folders_apply_pin "$role" "$pin" || return 1
    return 0
  fi
  lim=$(branch_minfree "$target" | tr -d K); lim=${lim:-0}
  free=$(( $(avail_bytes "$target") - lim * 1024 ))
  say ""
  say "The plan: move $(human "$need") to $(branch_name "$target"):"
  for i in "${!pairs[@]}"; do say "  - ${pairs[$i]#*|}   $(human "${sizes[$i]}") from $(branch_name "${pairs[$i]%%|*}")"; done
  say "$(branch_name "$target") has $(human "$(( free > 0 ? free : 0 ))") free above its limit."
  if [ "$need" -gt "$free" ]; then
    NOROOM=1
    note "There is not enough room on $(branch_name "$target") for this ($(human "$need") needed). Nothing was changed."
    return 1
  fi
  for pair in "${pairs[@]}"; do
    f=${pair#*|}; mp=${pair%%|*}
    [ -d "$target/$f" ] || continue
    if conflicts=$(copy_conflicts "$mp/$f/" "$target/$f/"); then :; else
      note "A file in '$f' exists on both drives with different content, and a move never replaces a file:"
      printf '%s\n' "$conflicts" | head -5 | sed 's/^/    /' >&2
      note "Nothing was changed."
      return 1
    fi
  done
  say "Each file is copied and checked first, then removed from the old drive. The folders keep their place in the pool."
  say "The services keep running while the files are copied. They stop for a short time at the end to copy the last changes."
  yn "Move the folders now?" || { say "Cancelled. Nothing was changed."; return 1; }
  local -a steps=("Copy the chosen folders ($(human "$need")) onto $(branch_name "$target") while the services run."
                  "Stop the containers that use the $role pool for a short time and copy the last changes."
                  "Check every copied file, remove the old copies and the emptied folders, and start the containers again.")
  [ "$pin" = yes ] && steps+=("Keep new files of these folders on $(branch_name "$target").")
  pre_change "${steps[@]}" && return 0
  local listdir; listdir=$(mktemp -d) || { note "Not enough space for working files. Nothing was changed."; return 1; }
  for i in "${!pairs[@]}"; do
    mp=${pairs[$i]%%|*}; f=${pairs[$i]#*|}
    find "$mp/$f" -type f -printf '%P\0' >"$listdir/$i" 2>/dev/null
    total_files=$((total_files + $(tr -cd '\0' <"$listdir/$i" | wc -c)))
  done
  local done_bytes=0
  for i in "${!pairs[@]}"; do
    mp=${pairs[$i]%%|*}; f=${pairs[$i]#*|}
    say "Copying '$f' from $(branch_name "$mp") to $(branch_name "$target") (pass 1, services keep running)..."
    progress $(( need > 0 ? done_bytes * 85 / need : 0 )) "Copying files"
    mkdir -p "$target/$f"
    rsync -aH --numeric-ids "$mp/$f/" "$target/$f/"
    n=$?
    if [ "$n" -ne 0 ] && [ "$n" -ne 24 ]; then
      warn "Copy failed (code $n). The old copies were not removed."
      folders_undo_pairs "$target" "${pairs[@]}"
      rm -rf "$listdir"
      return 1
    fi
    done_bytes=$((done_bytes + sizes[i]))
  done
  progress 88 "Checking the copies"
  stop_containers "$pool"
  say "Pass 2 (catching changes made during the first pass)..."
  for i in "${!pairs[@]}"; do
    mp=${pairs[$i]%%|*}; f=${pairs[$i]#*|}
    while IFS= read -r -d '' rel; do
      [ -e "$mp/$f/$rel" ] || rm -f -- "${target:?}/$f/$rel"
    done <"$listdir/$i"
    rsync -aH --numeric-ids --update "$mp/$f/" "$target/$f/"
    n=$?
    if [ "$n" -ne 0 ] && [ "$n" -ne 24 ]; then bad=1; break; fi
    if ! copy_check "$mp/$f/" "$target/$f/" >/dev/null; then bad=1; break; fi
  done
  if [ "$bad" = 1 ]; then
    warn "The check found files that are not copied correctly. Nothing was removed from the old drives."
    folders_undo_pairs "$target" "${pairs[@]}"
    start_containers
    rm -rf "$listdir"
    return 1
  fi
  say "Verified: every file is on $(branch_name "$target"). Removing the old copies..."
  progress 94 "Removing the old copies"
  for pair in "${pairs[@]}"; do
    mp=${pair%%|*}; f=${pair#*|}
    find "$mp/$f" ! -type d -delete 2>/dev/null
    find "$mp/$f" -depth -type d -empty -delete 2>/dev/null
    [ -d "$mp/$f" ] && warn "'$f' on $(branch_name "$mp") still holds something that could not be removed. It stays where it is."
  done
  sync_fs "$target" "${others[@]}"
  rm -rf "$listdir"
  folders_apply_pin "$role" "$pin" || { start_containers; return 1; }
  start_containers
  progress 100 "Done"
  log "moved folders to $(basename "$target") in $role: $* ($need bytes)"
  say ""
  say "Done. $(human "$need") moved to $(branch_name "$target")."
  return 0
}

# folders_apply_pin ROLE yes|no: switch "keep new files on their drive" on or off for the pool, now and in fstab.
folders_apply_pin() {
  local role=$1 want=$2 now=0
  pool_pinned "$role" && now=1
  if [ "$want" = yes ] && [ "$now" = 1 ]; then return 0; fi
  if [ "$want" != yes ] && [ "$now" = 0 ]; then return 0; fi
  settings_snapshot
  if [ "$want" = yes ]; then setting_put pin "$role" 1; else setting_del pin "$role"; fi
  pool_reconfigure "$role" || { settings_rollback; return 1; }
  settings_discard
  if [ "$want" = yes ]; then say "New files of these folders now stay on the drive that holds the folder."; else say "New files go by the pool's fill setting again ($(pool_policy_name "$(pool_policy "$role")"))."; fi
  log "pool $role pin $want"
  return 0
}

# `folders`: look at which drive holds which folder, and move folders to another drive of the same pool.
folders_flow() {
  array_guard || return 1
  local role why mp f idx i sel tgt target pin=yes
  local -a mps=() fl=() items=() titems=()
  role=$(pick_pool_role 2) || return 1
  why=$(folders_why_not "$role") || { note "$why Nothing was changed."; return 1; }
  for mp in $(folders_real_branches "$role"); do mps+=("$mp"); done
  say ""
  say "Measuring the folders of the $role pool (this can take a minute)..."
  while IFS= read -r f; do [ -n "$f" ] && fl+=("$f"); done < <(folders_names "$role")
  if [ ${#fl[@]} -eq 0 ]; then say "There are no folders on these drives yet. Nothing to move."; return 0; fi
  for f in "${fl[@]}"; do
    sel="$f   ("
    for mp in "${mps[@]}"; do
      if [ -d "$mp/$f" ]; then sel="$sel$(branch_name "$mp"): $(human "$(folder_bytes "$mp" "$f")")  "; fi
    done
    items+=("${sel% })")
  done
  say ""
  say "Free space: $(for mp in "${mps[@]}"; do printf '%s %s free   ' "$(branch_name "$mp")" "$(human "$(avail_bytes "$mp")")"; done)"
  idx=$(choose "Which folder do you want to move? " "${items[@]}") || return 1
  f=${fl[$idx]}
  for mp in "${mps[@]}"; do titems+=("$(branch_name "$mp")"); done
  tgt=$(choose "Move '$f' to which drive? " "${titems[@]}") || return 1
  target=${mps[$tgt]}
  yn_yes "Keep new files of the folders you move on that drive (instead of following the pool's fill setting)?" || pin=no
  folders_move_core "$role" "$target" "$pin" "$f"
}

# panel_folderpin ROLE yes|no
panel_folderpin() {
  folders_why_not "$1" >/dev/null || { panel_refuse "Folders cannot be moved in this pool, so the setting does not apply."; return 1; }
  folders_apply_pin "$1" "$2"
}

# panel_movefolders ROLE DRIVE_ID HEXLIST PIN: the Drives tab's folder move.
panel_movefolders() {
  local role=$1 tid=$2 hexlist=$3 pin=$4 why mp target="" h f
  local -a names=() hexes=()
  why=$(folders_why_not "$role") || { panel_refuse "$why"; return 1; }
  for mp in $(folders_real_branches "$role"); do [ "$(basename "$mp")" = "$tid" ] && target=$mp; done
  [ -n "$target" ] || { panel_refuse "That drive is not in the $role pool."; return 1; }
  IFS=, read -ra hexes <<<"$hexlist"
  [ "${#hexes[@]}" -ge 1 ] && [ "${#hexes[@]}" -le 60 ] || { panel_refuse "Choose between one and sixty folders."; return 1; }
  for h in "${hexes[@]}"; do
    f=$(folder_from_hex "$h") || { panel_refuse "A folder name is not allowed."; return 1; }
    local seen=0
    for mp in $(folders_real_branches "$role"); do [ -d "$mp/$f" ] && seen=1; done
    [ "$seen" = 1 ] || { panel_refuse "The folder '$f' is not on the drives any more."; return 1; }
    names+=("$f")
  done
  PROG_ITEM=folders
  progress 0 "Planning the move"
  folders_move_core "$role" "$target" "$pin" "${names[@]}"
}
