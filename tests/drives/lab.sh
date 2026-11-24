# shellcheck shell=bash
# Test bench for scripts/drives. Source this file from a scenario. It builds a small lab out of loop devices (files that act as drives) with the
# tool's own test mode (DRIVES_TEST=1), so nothing outside the temporary folder is touched. It needs root, losetup, mkfs.ext4, mergerfs and rsync.
#
#   lab_init                create the lab folder and load scripts/drives as functions
#   lab_drive NAME SIZE_MB  make a drive, format it and mount it as a branch of the Main (TMAIN<n>) or Backup (TBACKUP<n>) pool
#   lab_pool ROLE           (re)build the pool of a role from its branches and mount it
#   lab_done                unmount everything and remove the lab (also runs on exit)

LAB_REPO=${LAB_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}
LAB_LOOPS=()

lab_init() {
  LAB_DIR=$(mktemp -d /var/tmp/drives-lab.XXXXXX)
  export DRIVES_TEST=1 DRIVES_STATE_DIR="$LAB_DIR/state" DISKS_DIR="$LAB_DIR/disks" MAIN_POOL="$LAB_DIR/main" BACKUP_POOL="$LAB_DIR/backup"
  export DRIVES_OWNER=root POOL_MINFREE=1M DRIVES_BOOT_KEEP=1000000 BUSY_POLL_SECS=1 DRAIN_SPARE_BYTES=1048576
  export PANEL_MODE_FORCE=0
  mkdir -p "$DRIVES_STATE_DIR" "$DISKS_DIR" "$MAIN_POOL" "$BACKUP_POOL"
  # shellcheck disable=SC1091
  source "$LAB_REPO/scripts/drives"
  set +e
  trap lab_done EXIT   # after the tool is loaded: it sets an exit trap of its own
  # shellcheck disable=SC2034
  ASSUME_YES=1
  # shellcheck disable=SC2034
  CONFIRM_ERASE=1
  # The tests have no containers and nobody to ask.
  docker_ok() { return 1; }
  stop_containers() { :; }
  start_containers() { :; }
  sync_filebrowser() { :; }
  restore_services() { :; }
  busy_gate() { return 0; }
  die() { printf 'ERROR: %s\n' "$*" >&2; return 1; }
}

lab_drive() {
  local name=$1 mb=$2 img dev
  img="$LAB_DIR/$name.img"
  truncate -s "${mb}M" "$img"
  dev=$(losetup -f --show "$img") || return 1
  LAB_LOOPS+=("$dev")
  mkfs.ext4 -q -F -m 0 "$dev" || return 1
  mkdir -p "$DISKS_DIR/$name"
  fstab_add "UUID=$(blkid -s UUID -o value "$dev")  $DISKS_DIR/$name  ext4  $BRANCH_OPTS  0  2"
  mount_fstab "$DISKS_DIR/$name" || return 1
}

lab_pool() {
  apply_pool "$1"
}

lab_done() {
  local mp d
  trap - EXIT
  cd / || true
  for mp in $(awk -v d="$LAB_DIR" 'index($2, d) == 1 {print $2}' /proc/mounts | sort -r); do umount "$mp" 2>/dev/null || umount -l "$mp" 2>/dev/null; done
  for d in "${LAB_LOOPS[@]}"; do losetup -d "$d" 2>/dev/null; done
  find "$LAB_DIR" -type d -exec chattr -i {} + 2>/dev/null
  rm -rf "$LAB_DIR"
}

# check DESCRIPTION COMMAND...: one line per check, "ok" or "FAIL"; the scenario's exit status says whether any failed.
LAB_FAILS=0
check() {
  local what=$1; shift
  if "$@"; then printf 'ok    %s\n' "$what"; else printf 'FAIL  %s\n' "$what"; LAB_FAILS=$((LAB_FAILS + 1)); fi
}
lab_result() { [ "$LAB_FAILS" -eq 0 ]; }

# lab_blank_loops N MB: make N blank loop devices with a partition table-ready size and list them in WIZARD_DEVS, like drives picked in the wizard.
lab_blank_loops() {
  local n=$1 mb=$2 i d
  WIZARD_DEVS=""
  for i in $(seq 1 "$n"); do
    truncate -s "${mb}M" "$LAB_DIR/blank$i.img"
    d=$(losetup -f --show -P "$LAB_DIR/blank$i.img") || return 1
    LAB_LOOPS+=("$d")
    WIZARD_DEVS="${WIZARD_DEVS:+$WIZARD_DEVS
}$d"
  done
  export WIZARD_DEVS
}
