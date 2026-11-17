# give_to_owner PATH: hands the folder or file to the lab's owner. A link is never followed (chown -h), so a link a user planted cannot make root change another file.
give_to_owner() {
  id -u "$OWNER" >/dev/null 2>&1 && chown -h "$OWNER:$OWNER" "$1"
  return 0
}

# app_marker FOLDER NAME UID GID TEXT [MODE]: makes FOLDER (under the main pool) and the marker file NAME in it for Immich or Nextcloud.
# Every part of the path below the main pool is opened without following links. A link at the marker's name is replaced by a plain file. Returns 1 when a part is a link or not a real folder, and then changes nothing there.
app_marker() {
  local rel=${1#"$MAIN_POOL"}
  rel=${rel#/}
  command -v python3 >/dev/null 2>&1 || return 1
  python3 - "$MAIN_POOL" "$rel" "$2" "$3" "$4" "$5" "${6:-}" <<'PY' 2>/dev/null
import os, stat, sys
base, rel, name, uid, gid, text, mode = sys.argv[1:8]
uid, gid = int(uid), int(gid)
flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
try:
    fd = os.open(os.path.realpath(base), os.O_RDONLY | os.O_DIRECTORY)
    for part in [p for p in rel.split("/") if p]:
        try:
            os.mkdir(part, 0o755, dir_fd=fd)
        except FileExistsError:
            pass
        nfd = os.open(part, flags, dir_fd=fd)
        os.close(fd)
        fd = nfd
    os.fchown(fd, uid, gid)
    if mode:
        os.fchmod(fd, int(mode, 8))
    try:
        st = os.stat(name, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        st = None
    if st is not None and stat.S_ISLNK(st.st_mode):
        os.unlink(name, dir_fd=fd)
        st = None
    if st is None:
        f = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=fd)
        os.write(f, text.encode())
        os.fchown(f, uid, gid)
        os.close(f)
    elif stat.S_ISREG(st.st_mode):
        os.chown(name, uid, gid, dir_fd=fd, follow_symlinks=False)
    else:
        sys.exit(1)
except OSError:
    sys.exit(1)
PY
}

# immich_marker FOLDER: the folder and its .immich marker belong to the owner.
immich_marker() {
  local u g
  u=$(id -u "$OWNER" 2>/dev/null) && g=$(id -g "$OWNER" 2>/dev/null) || return 0
  app_marker "$1" .immich "$u" "$g" "" || { log "left alone: $1 is not a real folder (a link or another kind of file is in the way)"; return 0; }
}

# nextcloud_marker: the Nextcloud data folder and its .ncdata marker belong to uid 33.
nextcloud_marker() {
  app_marker "$MAIN_POOL/nextcloud" .ncdata 33 33 $'# Nextcloud data directory\n' 750 || { log "left alone: $MAIN_POOL/nextcloud is not a real folder (a link or another kind of file is in the way)"; return 0; }
}

ensure_mp() {
  mkdir -p "$1"
  if ! mountpoint -q "$1"; then chattr +i "$1" 2>/dev/null || true; fi
}

mount_fstab() {
  local -a extra=()
  [ "$(awk -v m="$1" '!/^[[:space:]]*#/ && $2 == m {print $3; exit}' "$FSTAB" 2>/dev/null)" = fuse.mergerfs ] && extra=(-o nonempty)
  if [ "$PANEL_MODE" = 1 ] && [ -d "${SYSTEMD_DIR:-/run/systemd/system}" ] && command -v systemd-run >/dev/null 2>&1; then
    systemd-run --scope --quiet --collect --slice=system.slice mount -T "$FSTAB" "${extra[@]}" "$1" 6>&- 8>&- 9>&- || return 1
  else
    mount -T "$FSTAB" "${extra[@]}" "$1" 6>&- 8>&- 9>&- || return 1
  fi
  mountpoint -q "$1"
}

# xattr_get FILE NAME / xattr_set FILE NAME VALUE: read or set an extended attribute with python3, so the `attr` package is not needed.
xattr_get() { python3 -c 'import os, sys; sys.stdout.write(os.getxattr(sys.argv[1], sys.argv[2]).decode())' "$1" "$2" 2>/dev/null; }
xattr_set() { python3 -c 'import os, sys; os.setxattr(sys.argv[1], sys.argv[2], sys.argv[3].encode())' "$1" "$2" "$3" 2>/dev/null; }

pool_is_live() {
  local pool
  pool=$(role_pool "$1") || return 1
  command -v python3 >/dev/null 2>&1 || return 1
  mountpoint -q "$pool" 2>/dev/null || return 1
  [ "$(findmnt -no FSTYPE "$pool" 2>/dev/null)" = fuse.mergerfs ] && [ -e "$pool/.mergerfs" ]
}

pool_umount() {
  local mp=$1
  mountpoint -q "$mp" || return 0
  umount "$mp" 2>/dev/null && return 0
  fusermount -u "$mp" 2>/dev/null && return 0
  warn "$mp is busy, using a lazy unmount"
  umount -l "$mp"
}

apply_pool() {
  local role=$1 mp
  mp=$(role_pool "$role")
  ensure_mp "$mp"
  fstab_set_pool "$role"
  sd_reload
  pool_umount "$mp"
  if [ -n "$(branches_of "$role")" ]; then mount_fstab "$mp" || return 1
  elif [ "$role" = main ]; then boot_folder_ready
  fi
  [ "$role" = main ] && snapraid_active && snapraid_conf_write
  return 0
}

disk_of_part() {
  local src=${1%%\[*}
  lsblk -nsrpo NAME,TYPE "$src" 2>/dev/null | awk '$2 == "disk" || $2 == "loop" {print $1; exit}'
}

protected_disks() {
  {
    local t s
    for t in / /boot /boot/efi /var/lib/docker; do
      s=$(findmnt -nT "$t" -o SOURCE 2>/dev/null)
      [ -n "$s" ] && disk_of_part "$s"
    done
    swapon --noheadings --show=NAME 2>/dev/null | while read -r s; do disk_of_part "$s"; done
  } | sort -u
}

busy_disks() {
  findmnt -rn -o SOURCE,TARGET 2>/dev/null | while read -r src tgt; do
    case "$src" in /dev/*) ;; *) continue ;; esac
    case "$tgt" in /media/*|/run/media/*) continue ;; esac
    disk_of_part "$src"
  done | sort -u
}

managed_disks() {
  local mp p
  for mp in $(all_branches) $(parity_mounts); do
    p=$(branch_part "$mp")
    [ -n "$p" ] && disk_of_part "$p"
  done | sort -u
  array_disks
}

all_disks() {
  # A device with no size has no disk in it (an empty card reader, an unused network block device), so it is not a drive.
  lsblk -dnbpo NAME,TYPE,SIZE 2>/dev/null | awk '$2 == "disk" && $3 > 0 && $1 !~ /zram|\/ram[0-9]/ {print $1}'
  if [ "$TEST_MODE" = 1 ]; then
    losetup -ln -O NAME,BACK-FILE 2>/dev/null | awk -v s="$STATE_DIR/disk" 'index($2, s) == 1 {print $1}'
  fi
}

legacy_disks() {
  local mp s
  array_active && return 0
  for mp in "$MAIN_POOL" "$BACKUP_POOL"; do
    mountpoint -q "$mp" || continue
    [ "$(findmnt -no FSTYPE "$mp")" = ext4 ] || continue
    s=$(findmnt -no SOURCE "$mp")
    disk_of_part "$s"
  done | sort -u
}

refuse_unsafe_disk() {
  grep -qx "$1" <<<"$(protected_disks)" && die "$1 holds the operating system. Refusing."
  grep -qx "$1" <<<"$(busy_disks)" && die "$1 is in use (something on it is mounted). Refusing."
  return 0
}

candidate_disks() {
  local excl d
  excl=$( { protected_disks; managed_disks; legacy_disks; busy_disks; } | sort -u )
  for d in $(all_disks | sort -u); do
    grep -qx "$d" <<<"$excl" && continue
    echo "$d"
  done
}

