# Maintenance

This page covers keeping the lab healthy: what to check, how updates work, how backups and restores work, what to do after a power loss or a dead boot drive, and where the secrets are kept. You can do most of it from the Customize panel. The terminal commands are here for when you want the details.

## Contents

- [Checking on it](#checking-on-it)
- [Updating](#updating)
- [Backups](#backups)
- [After a power loss or a disconnected drive](#after-a-power-loss-or-a-disconnected-drive)
- [When the Main drive is missing](#when-the-main-drive-is-missing)
- [If a data drive fails or goes missing](#if-a-data-drive-fails-or-goes-missing)
- [If the boot drive fails](#if-the-boot-drive-fails)
- [If the setup state file is damaged](#if-the-setup-state-file-is-damaged)
- [Secrets](#secrets)
- [Taking it off a machine](#taking-it-off-a-machine)

> **A note on testing.** I tested the restore and rebuild steps on a simulated machine, and the drive tools on the real server with spare USB sticks. I haven't yet used them after a real drive failure, and a full rebuild after a failed boot drive has only been tried on the simulated machine. Go slowly the first time, and read what a command does before you run it.

## Checking on it

The quickest check is the notification bell on the dashboard. No badge means nothing needs attention. If there is one, open the list: it says what's wrong and often has a button to fix it ([how the bell works](homepage.md#the-notification-bell)).

Opening a terminal on the server shows a short summary of the pools, the last backup, the containers and the free space. Type `homelab` for the full screen with suggested commands.

| Command | What it shows |
| :--- | :--- |
| `homelab` | The full status, with suggested next steps |
| `docker ps` | Which containers are running and how healthy they are |
| `sudo drives status` | The pools, the health of every drive and the last backup |
| `sudo drives health` | SMART health, temperature and wear for each drive |
| `sudo homelab-setup verify` | Whether every container and service answers |
| `sudo homelab-selftest` | A bigger check of the whole lab. It saves a report in your home folder (the newest 10 are kept) and Ctrl-C stops it and still saves what it found |

A healthy drive says `PASSED`. If its reallocated or pending sector counts start to climb, replace it. `sudo homelab-selftest` runs the repository's test files as root, so it only does so when root owns them and every folder above them, and it says when it skips them.

![The homelab screen in a terminal](images/homelab-status.png)

## Updating

Nothing updates by itself. Most stack files pin an image to an exact version, and a few follow a moving name on purpose (Downtify, MeTube, Netdata's `stable` and Redis in the Nextcloud stack). The weekly check still notices a newer image behind a moving name, and nothing is replaced until you ask for an update.

From the panel: the server looks for newer container versions about once a week, and the bell shows what it found. The Update button on the bell opens the [Updates screen](homepage.md#updates). Before any container update it dumps the Immich and Nextcloud databases. It won't start while a backup is running or files are being uploaded, and it tells you why.

From the terminal:

| Command | What it does |
| :--- | :--- |
| `sudo homelab-update check` | Only looks. Shows which images have something newer |
| `sudo homelab-update` | Updates each stack that has something new, asking before each one |
| `sudo homelab-update clean` | Deletes the saved old versions and leftover images, after asking |
| `sudo apt update && sudo apt upgrade` | The system packages |
| `sudo homelab-setup upgrade` | Brings the lab up to date with this repository |

- Pick a quiet time, not while a backup is running.
- Read the release notes for Immich and Nextcloud first. Nextcloud major versions are never updated automatically.
- To go back, use the saved copy. Before an update, each image's old version is kept as `homelab-rollback:<name>-<date>`, and for a small problem you can put it back in the stack's file in Portainer. Immich and Nextcloud can't be downgraded once their database has changed, so for those the way back is the database dump in the backup.
- FileBrowser gets no more updates, because its project was archived.

## Backups

The nightly backup is the first task in the Backups card of the Drives screen. It copies the Main pool and the lab's settings, keeps changed or deleted files as older versions for 30 days (1 to 3650 when you edit the task) and dumps the Nextcloud database. Immich's own database backups are copied too.

- To leave something out, open the nightly task's **Edit** window and untick it under **What to back up**. The list shows the folders of the Main pool (for example Photos and videos, Files and documents, Music), all ticked at first. A folder you untick is no longer copied or checked, so if a drive fails its files cannot be restored from this backup. The copy already in the backup stays where it is and stops being updated; delete it yourself if you want the space back. At least one folder has to stay ticked. The lab's settings and the Nextcloud database dump are always included. For something more specific, such as one folder to the cloud, add your own task.
- The backup goes to the Backup pool and runs only while a backup drive is connected. Until then it waits, and the Backups section of the Drives tab says "Waiting for a backup drive". Nothing is copied to the boot drive. An earlier install saved its copy in `~/boot-drive-files/backup-interim`. That folder is not removed for you and can be deleted when you no longer need it (it is owned by root, so use `sudo`).
- Backup times in the panel, in `homelab` and on the dashboard use the dashboard's time zone (for example 02:56 EST). A task's own schedule is set in the server's time, and the panel says so.
- To see whether it ran, check the bell, which warns if a backup failed or is more than a day old (it does not warn about age while the backup waits for a drive). `sudo drives status` shows the last result, and `sudo tail -20 /var/log/homelab-backup.log` shows why one failed.
- Every night the backup compares a sample of what it copied (up to 2 GB) byte for byte with the originals. A wrong copy makes the run fail and the bell warn. `sudo homelab-backup verify` compares everything, and `verify --repair` copies wrong files again. A file that changed on Main after the backup isn't wrong, and the next backup picks it up.
- A backup needs room for a copy of Main plus a tenth of the drive (at most 20 GB), so `sudo drives connect` warns you when a drive is too small.
- To get files back, open a task in the Backups card, browse its versions and restore. For a backup on a drive of this computer, Download saves a single file, or a folder as a `.zip`, to your device. FileBrowser shows the Backup pool too.
- The same card can back up to another computer over SSH or to the cloud (Backblaze B2, S3, Google Drive and others).

![The Backups card with a nightly task](images/panel-backups.png)

## After a power loss or a disconnected drive

If the server lost power or a drive was disconnected, press **Fix Drives** on the Drives screen, or run:

```bash
sudo drives remount
```

It mounts the pools again, checks that Immich and Nextcloud can find their files, makes sure the music folder belongs to the server user (so the Upload card can save songs), and then restarts the containers that depend on the pools. If files are missing, it keeps those two stopped and asks what to do ([next sections](#if-a-data-drive-fails-or-goes-missing)).

To remove a drive on purpose, don't just pull the cable. Use **Take Out** on the Drives screen (or `sudo drives disconnect`). It copies the drive's files to the other drives first and tells you when it's safe to unplug.

## When the Main drive is missing

The services never wait for a drive. The boot drive is the storage until a drive is in the Main pool, and it takes over again if the drive goes away.

| Situation | What happens |
| :--- | :--- |
| No drive in Main (a new install, or every drive was taken out) | `/mnt/storage` is a plain folder on the boot drive. Immich and Nextcloud use it and keep running |
| A drive is connected to Main | Everything the services saved on the boot drive is **copied** to the drive and checked. In the terminal it asks whether to remove the old copies. The panel keeps them and shows a **Files Are Waiting On The Boot Drive** box with a **Move the Files to the Drive** button |
| The Main drive is missing at start-up or at Fix Drives | The pool is not mounted, because it would be incomplete. The boot drive is the storage and the services start. The Drives screen and `sudo drives status` say so. Files on the missing drive can't be seen until it is back |
| The drive comes back | Fix Drives (or `sudo drives remount`) mounts it again and offers to copy what was saved on the boot drive in the meantime |

The copy never replaces a file that's already on the drive. If both places have a different version, the drive's version is kept, the boot-drive copy stays and a message tells you. **Move the Files to the Drive** (or `sudo drives moveboot`) does the copy and check at any time, and removes the old copies only after every file checks out. Only the small files that kept the services running are involved, not your photos or documents.

Two caveats. The boot drive has to have the room, since a big photo library saved there while the drive is away can fill it. And backups need a drive of their own, because a backup on the boot drive doesn't help if the boot drive fails.

## If a data drive fails or goes missing

Immich and Nextcloud keep their photos and files in the Main pool, but they don't depend on one particular drive. They depend on their folders being there. You can replace a drive and bring the services back with the same accounts, because the accounts, albums and settings live in databases on the boot drive.

Why they stop: both apps refuse to start when the marker file in their folder is missing (`.ncdata` for Nextcloud, `.immich` in each Immich folder). That's on purpose: if they started on an empty folder, the library would look empty, and a phone syncing with it could delete its own copies of your photos. So when the drive that held those folders is gone, Immich shows a 502 error and Nextcloud says "Your data directory is invalid". Nothing else is broken.

What to do:

1. Don't start the two apps by hand while the pool is incomplete. Docker would create an empty folder owned by root on whatever drive is left.
1. If the old drive still works, put it back: drag it into the Main pool on the Drives screen, choose **Keep the files** and press **Fix Drives**.
1. If the drive is dead, connect a replacement, add it to the Main pool and press **Fix Drives** (or run `sudo drives remount`). It offers two choices:
   - **Restore From Backup** copies back only the files that are missing, from the last backup. Nothing already there is overwritten, and anything added after that backup can't come back. A progress bar shows the amount copied, such as `5.00 GB / 11.00 GB`, and **Cancel** removes what this restore copied. Afterwards, check a few photos and files.
   - **Start on Empty Folders** starts the apps with nothing in them, using the same accounts. You have to type `START` (or tick the box in the panel). Immich will list photos it can't open any more, and apps that sync with Nextcloud may delete their own copies. Use it only when the old files are gone for good, or after restoring what you could.
1. If you choose neither, the two apps stay stopped, everything else starts, and the warning stays on the Drives screen.

Other tools for the same situation:

| Command | What it does |
| :--- | :--- |
| `sudo drives replace` | For a drive that is **missing**. Pick the new drive, it is erased and takes the old one's place, and a Main drive's files are copied back from the backup |
| `sudo drives restore` | Copies back only the files that are in the backup but missing from the Main pool. It shows the list first and asks you to type `RESTORE` |
| `sudo drives remount` | Mounts the pools, runs the Immich and Nextcloud check above and starts the containers. With a Main drive missing, the services run from the boot drive |
| `sudo drives moveboot` | Copies the files saved on the boot drive onto the Main pool, checks them and asks before removing the old copies |

A drive in the Backup pool is what makes all of this possible. Without one there is no backup of the Main pool, so the data on a failed drive is gone, and **Start on Empty Folders** is the only way to get the apps running again.

Restored folders and the `<time>-replaced` folder of replaced files belong to your user, so you can delete them without `sudo`. The empty `_restored` folder itself needs `sudo rmdir`, because it sits in a folder that belongs to root.

## If the boot drive fails

This is the plan for the day the drive with Linux on it dies. GitHub has the tools, the backup has the data and a password manager has the secrets.

1. Free the old name in Tailscale. Delete the old machine in the [admin console](https://login.tailscale.com/admin/machines). Otherwise the new server joins with `-1` on the end and the addresses stop matching.
1. Install Linux on the new drive with the same user name as before, and reserve the same fixed address in the router.
1. Plug in the data drives first. The installer never formats a drive. When it asks about them, keep the data.
1. Run the installer and point it at the backup, so the settings are restored:

   ```bash
   sudo bash setup.sh install --backup /path/to/backup
   ```

   Photos and files are copied back only if nothing is there yet, and nothing is overwritten. The Nextcloud database restore asks you to type `RESTORE` first.

1. Preview the saved settings with `sudo homelab-restore-configs check`, then check everything with `sudo homelab-setup verify`.

If there is no backup, the settings and the Nextcloud database are gone, but the photos and files on the data drive are still there. This is why I want a backup drive.

## If the setup state file is damaged

The installer keeps a small record of your answers and the one-time steps it has done in `/var/lib/homelab-setup/state.json`. If that file can't be read, `sudo homelab-setup refresh` says so, keeps a copy named `state.json.damaged-<date>` and changes nothing. To build a new record from what is installed, run:

```bash
sudo homelab-setup refresh --force-existing
```

It finds the downloaded copy of the lab in your home folder (or use `--repo ~/My-Home-Lab`), takes the admin name and e-mail from the damaged copy or the dashboard widgets, reads the address, time zone and weather place back from the machine and asks only for what it can't find. Nothing is upgraded or put back, and no container restarts. `--dry-run` lists what it would keep and ask for, and changes nothing. You can delete the `.damaged-<date>` copy afterwards.

## Secrets

Every password and key the lab needs, and what to do if one is lost. Real values never go in this repository. I keep them in a password manager. `homelab secrets` prints a short version of this list and checks what it can, without showing any value.

| Secret | Where it is used | If it is lost |
| :--- | :--- | :--- |
| Linux user login | `sudo`, SSH, the console | Boot into recovery mode (hold Shift at start-up) and run `passwd your-username` |
| Customize panel password | The panel and its web terminal | Run `sudo homelab-panel set-password` on the server |
| Admin passwords for Immich, Nextcloud, Portainer, AdGuard Home, Beszel, FileBrowser and Speedtest Tracker | Each service's own web page | The installer made one shared admin password. Each service has its own reset command, and `sudo homelab-setup secrets` shows the generated values again |
| Nextcloud database password | The Nextcloud stack and its `config.php` | Read it back from `config.php`. A rebuild must reuse the same one |
| Immich API key | The Upload card and the dashboard widget | Make a new one in your Immich account. Paste it in the Immich card's *Change* window (Customize, Cards) and again in the Upload card |
| Tailscale API token | The Tailscale card on the dashboard | It expires after 90 days by default. Make a new one in the admin console, then paste it in the Tailscale card's *Change* window (Customize, Cards) or run `sudo homelab-setup fill` |
| Tailscale, GitHub and router logins | Everything outside the server | Recover them through each provider. Keep GitHub's recovery codes somewhere safe |

If a secret ever leaks, change it in the service first. Deleting it from Git isn't enough, because the old version is still in the history.

## Taking it off a machine

One command takes the lab off a machine:

```bash
sudo homelab-setup uninstall
```

It shows what goes and what stays, then asks two questions. Nothing changes until you answer a final numbered question (1 for yes, 2 for no), and wiping asks "Are you sure?".

1. The data of the apps (photos, files, playlists, settings and the saved passwords): *keep* it or *wipe* it. Keeping is the safe answer, and installing again later finds the data. Wiping also deletes the downloaded copy of this repository.
1. The drives of the pools: *keep the files* or *wipe the drives*. Keeping takes the pools apart, but every file stays on its drive and each drive can be read like any normal drive. A drive that wasn't in a pool is never offered, and neither is the boot drive.

It removes the lab's containers, images and networks, the Tailscale addresses on ports 1000-1008 and 1100, the control panel and web terminal, the lab's lines in root's crontab (a copy is saved first), the scripts it installed, its settings and the login screen in `~/.bashrc`. It also turns the system's own DNS resolver back on.

It keeps services you already ran before the install (only their dashboard cards go), Tailscale (still logged in), Docker, the helper programs (mergerfs, SnapRAID, mdadm, ZFS, smartmontools) and all music files.

Two things to know before you run it:

- If your router or other devices use this machine for DNS (AdGuard Home), point them back to the router first. Otherwise no website can be found once AdGuard Home is gone.
- A real RAID or ZFS array can't be taken apart without erasing it, so the uninstall leaves it as it's and keeps the `drives` tool. To erase an array on purpose, use `sudo drives release`.

You can't run it from the dashboard's web terminal, because it removes the terminal and would close the window halfway. Use an SSH session. For scripts, `--yes` keeps the data and the drives' files, `--wipe-data` wipes the data (and deletes the repository folder) and `--wipe-drives` erases the drives of the pools. With `--yes` nothing is asked. If something can't be removed, it says what, keeps the installer and its record, and you can run it again.
