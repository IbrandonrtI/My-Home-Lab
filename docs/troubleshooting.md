# Troubleshooting

These are problems I ran into while building and running this lab, and how I fixed them. Each one has a Symptom, a Cause and a Fix. Names and addresses are stand-ins: `your-username` is the Linux user, `192.168.X.X` is the server's address and `your-tailnet.ts.net` is your Tailscale network.

> **Built with Claude's help, so expect rough edges.** If your problem isn't here, the [bell](homepage.md#the-notification-bell) and `sudo homelab-selftest` are good places to start, and `sudo homelab-setup verify` tells you which service isn't answering.

**Quick checks that solve a lot of things**

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"   # is everything running and healthy?
sudo drives status                                    # are the pools mounted, and are the drives healthy?
sudo homelab-setup verify                             # does every service answer?
docker logs --tail 50 NAME                            # what a container last said
```

## Contents

- [Installing](#installing)
- [Drives and storage](#drives-and-storage)
- [Dashboard and panel](#dashboard-and-panel)
- [Services](#services)
- [Network and DNS](#network-and-dns)

## Installing

### The installer ends the SSH session

**Symptom:** the session freezes or ends in the middle of the install.

**Cause:** the installer frees port 53 for AdGuard Home and restarts Tailscale. An SSH session that runs through Tailscale goes down with it.

**Fix:** run the installer on the machine's own screen, or over SSH on your home network (`ssh your-username@192.168.X.X`). Then run `sudo bash setup.sh install` again. Finished steps are skipped and the failed one is retried.

### The installer says a service was already running

**Symptom:** the start of the install lists services under "Services you already run", and no stack, login or widget is made for them.

**Cause:** a container with the name or image of a lab service (for example `immich_server`) existed before the first install step. The installer looks only once, at the start of a fresh install, and leaves what it finds alone.

**Fix:** nothing needs fixing. The card on the dashboard links to your copy. To let the lab manage the service instead, remove your container and its stack, remove its `adopted` entry from `/var/lib/homelab-setup/state.json` (or reinstall) and run `sudo homelab-setup refresh`. Removing the container doesn't touch the data as long as you keep its folders and volumes.

### An image download says `toomanyrequests`

**Symptom:** a stack fails to deploy with `toomanyrequests`.

**Cause:** GitHub's container registry (`ghcr.io`) limits how many images one machine can download at once. Immich, Homepage and Speedtest Tracker all come from there. The limit belongs to the registry, not to your machine.

**Fix:** wait a minute and run the installer again, or pull the images one at a time with `docker pull IMAGE` and deploy after.

### The install says it's finished, but Nextcloud or Immich don't respond yet

**Symptom:** the installer ended and listed "Finishing in the background", and the Nextcloud or Immich login doesn't work yet. The login screen of the terminal says "The last steps of the install are finishing in the background".

**Cause:** the slow last steps (Nextcloud's first start, the Immich admin account, the Beszel and widget keys) run in a background job called `homelab-finish`, so the install doesn't wait for them. The job carries on if you close the terminal.

**Fix:** run `sudo homelab-setup status` to see how far it's, and `journalctl -u homelab-finish` for details. A step that failed is listed there, and `sudo homelab-setup finish` tries it again. If the machine restarted before the job was done, the same command picks it up. `refresh` and `install` wait until the job has ended.

### `permission denied` on the Docker socket

**Symptom:** `docker ps` says permission denied when you don't use `sudo`.

**Cause:** your user isn't in the `docker` group yet in this session.

**Fix:** log out and back in, or run `newgrp docker`. `groups` should list `docker`.

## Drives and storage

### The services show an empty or old drive after a disconnection

**Symptom:** after a drive was disconnected and reconnected, Immich, Nextcloud or Navidrome show nothing, or old data.

**Cause:** a container keeps the view of the drive that it had when it started.

**Fix:** press **Fix Drives** on the Drives screen, or run `sudo drives remount`. It mounts the pools again and restarts the containers that use them.

### Immich shows a 502 and Nextcloud says the data directory is invalid

**Symptom:** after a drive was taken out of the Main pool or died, Immich shows a 502 error (its log says `ENOENT … /.immich`) and Nextcloud says "Your data directory is invalid" or "not writable".

**Cause:** the marker files in their folders were on that drive. Both apps refuse to start without them, so they can't show an empty library by mistake. Their accounts and settings are on the boot drive and are fine.

**Fix:** press **Fix Drives**, or run `sudo drives remount`, and choose **Restore From Backup** or **Start on Empty Folders**. The steps and the risks are in [If a data drive fails or goes missing](maintenance.md#if-a-data-drive-fails-or-goes-missing).

### The containers start before the drive is mounted after a reboot

**Symptom:** after a restart, a service starts with no data, or a folder on the boot drive gets filled instead of the pool.

**Cause:** Docker started the containers before the pool was ready.

**Fix:** the installer adds a rule that makes Docker wait for the pool. If it's missing, run `sudo homelab-setup refresh`. After a reboot, `findmnt /mnt/storage` prints nothing if the pool isn't mounted.

### Immich and Nextcloud make the machine crawl when they start together

**Symptom:** the machine is very slow for a while after a fresh install or a reboot, and a service shows `unhealthy` for a few minutes.

**Cause:** both start heavy background work at once on a spinning boot drive. Immich also prepares its machine learning models after the first upload, which can keep the CPU at 100% for a long time. This isn't an error.

**Fix:** wait, and don't start anything else. Watch `docker ps` until everything says `healthy`. New installs have Immich's text recognition (OCR) switched off to keep the load down, and a faster boot drive shortens all of this a lot.

### The Upload card says "Cannot write there" for songs

**Symptom:** photos upload fine, but songs fail with a message that the music folder can't be written to.

**Cause:** the music folder is owned by root, so the panel's user can't save into it. This can happen when Docker creates the folder by itself, for example after a data drive was replaced.

**Fix:** press **Fix Drives** on the Drives screen. It gives the server user ownership of the music folder again. You can also run the command shown in the message, such as `sudo setfacl -m u:your-username:rwx /mnt/storage/downloads/downtify`. On an older install, run `sudo homelab-setup refresh`. If it says `setfacl` isn't found, install it with `sudo apt install acl`.

## Dashboard and panel

### A Homepage card shows an error or a red dot

**Symptom:** a card says `API token invalid` or `No items returned`, or shows a red dot.

**Cause:** its key is missing or wrong, or the service is down. The Tailscale API token expires after 90 days by default.

**Fix:** check the bell and `docker ps` first. If the service is fine, make a new key in that service. Then either paste it in the card's *Change* window (Customize, Cards, *Change*, the box under *Web address*), or run `sudo homelab-setup fill`. The panel saves what you paste without testing it. `fill` tests the key before saving it, and a wrong key never replaces a working one.

### The page says `Host validation failed`

**Symptom:** the dashboard shows `Host validation failed`.

**Cause:** Homepage only answers for addresses it has been told about.

**Fix:** list every address you use in `HOMEPAGE_ALLOWED_HOSTS` in the Homepage stack, for example `192.168.X.X:3001,pc.your-tailnet.ts.net:1000`, and redeploy.

> **Photo to add:** A screenshot of the `Host validation failed` message. Save it in `docs/images/` as `host-validation-error.png`.

### The bell is empty, or its list is old

**Symptom:** the bell shows no badge even though something is down, or it says it was updated a long time ago.

**Cause:** the server rewrites the bell's file every five minutes with `homelab-alerts`. If the cron job is missing, the file stops changing.

**Fix:** run `sudo homelab-alerts show` to see what it finds. Run `sudo homelab-setup upgrade` to put the job back, then `sudo homelab-alerts` once to write the file right away.

### The Customize panel doesn't accept the login, or Updates can't update

**Symptom:** the panel refuses the password, or an update button is refused.

**Cause:** the panel's password is the admin password from the install, saved separately, so it doesn't change when you change the admin password somewhere else. The update buttons also need a sudo rule that an older install doesn't have.

**Fix:** set a new password with `sudo homelab-panel set-password`. For the update rule, run `sudo homelab-setup upgrade`, which adds it.

### Colors or cards look old after a change

**Symptom:** after picking a theme, a card or frame still has the old colors, the Files & Photos cards look clear instead of frosted, or the colors fall back to an older theme after Save while the background stays.

**Cause:** the browser is showing an older copy of the page, a custom color was set earlier for that card (custom colors win over the theme), or the dashboard files on the server are from an older version.

**Fix:** reload with `Ctrl+F5`. If it's still wrong, run `sudo homelab-setup upgrade` to get the current dashboard files and reload again. Then open the Look screen, go to Colors and Glass and clear that card's own color. After a Save, check that the Look screen says "Saved".

### A card on the Stats tab is gone, or a new one doesn't show up after an upgrade

**Symptom:** a number card was hidden, renamed or moved (Preview, Storage, Calendar and so on) and now a card is missing, or a card from a newer version isn't shown.

**Cause:** the cards HomeLab fills in can be customized on the Cards screen. The first change marks their block in `services.yaml` as `customized`, so `sudo homelab-setup upgrade` leaves it alone instead of overwriting your changes. Hidden cards are simply not in the file.

**Fix:** open Customize, then Cards. *Add From HomeLab's List* brings back a hidden card and offers new ones, and *Put HomeLab's Cards Back* resets all of them to the shipped names, icons and groups (your own cards are kept). If the list says the cards aren't on this machine yet, run `sudo homelab-setup upgrade` once and reload the panel.

## Services

### Nextcloud says "Access through untrusted domain"

**Symptom:** Nextcloud refuses an address.

> **Photo to add:** A screenshot of the "Access through untrusted domain" page. Save it in `docs/images/` as `nextcloud-untrusted-domain.png`.

**Cause:** the address isn't in its list of trusted domains. That setting is only read on the first install.

**Fix:**

```bash
docker exec -u www-data nextcloud php occ config:system:get trusted_domains
docker exec -u www-data nextcloud php occ config:system:set trusted_domains 3 --value=pc.your-tailnet.ts.net
```

Use an index number that isn't taken yet.

### Nextcloud shows a 502 right after the first start

**Symptom:** a 502 error on its Tailscale address.

**Cause:** the first start installs Nextcloud, and that takes 2 to 15 minutes on this machine.

**Fix:** follow `docker logs -f nextcloud` until the install is done, then refresh.

### Navidrome still lists a deleted song

**Symptom:** after deleting a song from the music folder, it shows grayed out in Navidrome.

**Cause:** Navidrome never deletes anything. It sees the music folder as read-only, so all it can do is mark missing files.

**Fix:** in Navidrome, open the settings and the Missing Files page, and remove the grayed entries.

### Jellyfin shows no movies or shows

**Symptom:** a library is empty, or a title shows under the wrong name.

**Cause:** the library points at a folder Jellyfin cannot see, or the files are named in a way Jellyfin does not recognise.

**Fix:** in Jellyfin open Dashboard, Libraries and check that the folders are `/media/movies` and `/media/shows`. Then name the files like `Movie Name (2019)/Movie Name (2019).mkv` and `Show Name/Season 01/Show Name - S01E01.mkv`, and run Scan All Libraries.

### A TV or streaming stick cannot find Jellyfin

**Symptom:** the Jellyfin app on a TV finds no server.

**Cause:** the app searches the network on its own, and some TVs do not manage that.

**Fix:** in the app choose to add a server by hand and type `http://` followed by the machine's address and `:8096`. The address is in the card on the dashboard. The TV has to be on the same network as the server, so Tailscale is not needed.

### Jellyfin stutters or the processor is at 100 percent

**Symptom:** a video stops and starts, and Netdata shows the processor busy while Jellyfin plays.

**Cause:** the video has to be converted for the device, and without the graphics chip the processor does that work alone.

**Fix:** in Jellyfin open Dashboard, Playback, Transcoding and choose Intel QuickSync (or VAAPI). If the choice does nothing, run `ls /dev/dri` on the server. With no `renderD128` in the list, the machine has no usable graphics chip and Jellyfin keeps converting on the processor. Choosing a lower quality in the player, or a file the device plays as it is, also helps.

### Portainer says "created outside of Portainer" for Downtify and MeTube

**Symptom:** in Portainer, the stack `music-downloader` has a label saying it was created outside of Portainer, and it can't be edited there.

**Cause:** Downtify and MeTube were started by hand with `docker compose`, so Portainer only sees the containers and doesn't own them.

**Fix:** run `sudo homelab-setup refresh`. It reads the settings of the two containers, removes them and starts them again from a Portainer stack with the same settings. Songs and videos aren't touched. If Portainer refuses, the old containers are started again the way they were, and the old settings are kept in `/root/.homelab-setup/music-downloader-before.yaml`.

### FileBrowser rejects the login

**Symptom:** the login is rejected.

**Cause:** FileBrowser keeps its own user list. The installer sets its login to `admin` with the shared admin password, using the first password FileBrowser prints in its log. If that password is gone from the log, the installer can't set it.

**Fix:** open FileBrowser, log in as `admin` and change the password there. Then run `sudo homelab-setup fill` so the dashboard card learns the new one.

### Downtify rejects the login

**Symptom:** Downtify shows "Wrong username or password" for the name and password you typed during the install.

**Cause:** Downtify keeps its own accounts. The installer sets the first account to your install name and password, but not when Downtify's password was already changed, or when Downtify was running before the install. A new Downtify has one account, `admin`, with the password `downtify`.

**Fix:** run `sudo homelab-setup refresh`. If Downtify still has the first account and the default password, it's changed to your install name and password. If not, sign in with the account you have, or run `docker exec downtify python main.py auth-reset`, which puts `admin` back to `downtify`. Other accounts aren't changed. Then run `sudo homelab-setup refresh` again.

## Network and DNS

### AdGuard Home says port 53 is already in use

**Symptom:** AdGuard Home doesn't start, and `sudo ss -tulpn | grep :53` shows `systemd-resolve`.

**Cause:** Ubuntu's built-in resolver listens on port 53.

**Fix:** the installer stops it and tells Tailscale not to take over DNS. If you set up AdGuard Home later, run `sudo homelab-setup adguard` over a connection that doesn't go through Tailscale. Moving AdGuard to another port doesn't help, because devices only send DNS to port 53.

### Devices don't use AdGuard Home

**Symptom:** AdGuard Home shows no queries from a phone or PC, but `nslookup google.com 192.168.X.X` works.

**Cause:** the device is still using the DNS server the router gives it. My router wouldn't let me change its DNS, so each device has to be pointed at the server by hand.

**Fix:** on each device, set the DNS server to the server's address (`192.168.X.X`). Adding `8.8.8.8` as a second server keeps the internet working when the server is off, but then a device can skip the filtering. The AdGuard query log shows when a device starts using it.

### The server can't look up names after a Tailscale update

**Symptom:** `ping google.com` fails on the server, but an IP address works.

**Cause:** the server's own DNS points at AdGuard Home, and Tailscale rewrote `/etc/resolv.conf`.

**Fix:** run `sudo systemctl restart tailscaled`. If it keeps happening, check with `docker ps` that AdGuard Home is running, because the server asks it for names too.

### The lab can't be reached from outside

**Symptom:** the addresses ending in `.ts.net` don't open from a phone.

**Cause:** Tailscale on the server isn't connected, or HTTPS certificates aren't switched on in the Tailscale account.

**Fix:** the bell shows a Tailscale item when the server is disconnected. Run `sudo tailscale up` and check `tailscale status`. You turn on HTTPS certificates at <https://login.tailscale.com/admin/dns>.
