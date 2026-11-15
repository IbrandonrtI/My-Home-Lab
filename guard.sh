#!/bin/bash
# Safety check for the real-drive test round. It decides whether ONE disk may be erased, and nothing else.
#
#   sudo bash guard.sh /dev/sdX            first time: shows the disk and asks you to type its serial number
#   sudo bash guard.sh --recheck           before every destructive step: confirms the same disk is still safe
#   sudo bash guard.sh --clear             forget the disk when the round is over
#
# The chosen disk is written to /root/.real-drive-ok. Every test step must read the device from that file, never from memory.

set -u
OK_FILE=/root/.real-drive-ok

die() { echo "REFUSED: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || die "run this with sudo"

parent_of() { lsblk -no PKNAME "$1" 2>/dev/null | head -1; }

# Every disk that the running system depends on: the one holding / and /boot, swap, and any disk named in fstab or crypttab.
busy_disks() {
  local src d
  for m in / /boot /boot/efi /home /var; do
    src=$(findmnt -no SOURCE "$m" 2>/dev/null) || continue
    src=${src%%\[*}
    d=$(parent_of "$src"); echo "${d:-$(basename "$src")}"
  done
  awk 'NR>1 {print $1}' /proc/swaps | while read -r s; do d=$(parent_of "$s"); echo "${d:-$(basename "$s")}"; done
}

check_disk() {
  local dev=$1 name
  [ -b "$dev" ] || die "$dev is not a block device"
  [ "$(lsblk -dno TYPE "$dev")" = disk ] || die "$dev is not a whole disk (give /dev/sdX, not a partition)"
  name=$(basename "$dev")
  case "$name" in loop*|ram*|zram*|dm-*|md*|nbd*) die "$dev is a virtual device; this guard is for real disks" ;; esac

  # 1. nothing on it may be mounted or used as swap
  if lsblk -rno MOUNTPOINTS "$dev" | grep -q .; then die "$dev has something mounted: $(lsblk -rno MOUNTPOINTS "$dev" | grep . | tr '\n' ' ')"; fi

  # 2. not a disk the system runs from
  if busy_disks | sort -u | grep -qx "$name"; then die "$dev is a disk the system runs from"; fi

  # 3. not named in fstab (by device, UUID, LABEL or PARTUUID) and not in a pool
  local ids
  ids="$dev $(lsblk -rno PATH,UUID,LABEL,PARTUUID "$dev" | tr ' ' '\n' | grep -v '^$' | sort -u | tr '\n' ' ')"
  for i in $ids; do
    if grep -v '^[[:space:]]*#' /etc/fstab /etc/crypttab 2>/dev/null | grep -qF -- "$i"; then die "$dev is in /etc/fstab or /etc/crypttab ($i)"; fi
  done
  if command -v drives >/dev/null 2>&1 && drives list 2>/dev/null | grep -E "(main|backup|parity|array)" | grep -q "/dev/$name"; then die "$dev is already in a pool (drives list)"; fi

  # 4. not part of a RAID or ZFS array that is active
  if grep -q "$name" /proc/mdstat 2>/dev/null; then die "$dev is part of an active RAID array"; fi
  if command -v zpool >/dev/null 2>&1 && zpool status 2>/dev/null | grep -q "$name"; then die "$dev is part of a ZFS pool"; fi
}

case "${1:-}" in
  --clear) rm -f "$OK_FILE"; echo "Cleared."; exit 0 ;;
  --recheck)
    [ -f "$OK_FILE" ] || die "no disk was chosen yet (run: sudo bash guard.sh /dev/sdX)"
    read -r dev serial _ < "$OK_FILE"
    now=$(lsblk -dno SERIAL "$dev" 2>/dev/null | tr -d ' ')
    [ "$now" = "$serial" ] || die "the disk at $dev now has serial '$now', not '$serial': it was unplugged or the names moved. Choose it again."
    check_disk "$dev"
    echo "GUARD OK: $dev (serial $serial)"
    exit 0 ;;
  /dev/*) ;;
  *) echo "usage: sudo bash guard.sh /dev/sdX | --recheck | --clear"; exit 2 ;;
esac

DEV=$1
check_disk "$DEV"
SERIAL=$(lsblk -dno SERIAL "$DEV" | tr -d ' ')
[ -n "$SERIAL" ] || die "$DEV reports no serial number, so it cannot be told apart safely. (Some USB cases hide it: try another port or case.)"

echo
echo "This disk will be ERASED by the tests:"
lsblk -o NAME,SIZE,MODEL,SERIAL,TRAN,FSTYPE,LABEL,MOUNTPOINTS "$DEV"
echo
echo "The disks the system runs from (never touched):"
busy_disks | sort -u | sed 's/^/  \/dev\//'
echo
printf 'Type the serial number of the disk above (%s) to allow erasing it: ' "$SERIAL"
read -r typed
[ "$typed" = "$SERIAL" ] || die "that is not the serial number"
echo "$DEV $SERIAL $(date +%F-%T)" > "$OK_FILE"
chmod 600 "$OK_FILE"
echo "GUARD OK: $DEV (serial $SERIAL) is the only disk the tests may erase."
