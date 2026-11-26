# The services

This is a walk through everything the lab runs, one service at a time: what it's, what I use it for and where to find it. Everything except Tailscale runs in Docker, and the Customize panel sits next to it as a service of its own. Addresses use `pc.your-tailnet.ts.net` in place of your Tailscale name. Tailscale is the only way to reach any of them.

## Contents

- [Ports and addresses](#ports-and-addresses)
- [Network and access](#network-and-access)
- [Managing and watching the server](#managing-and-watching-the-server)
- [Files and photos](#files-and-photos)
- [Music](#music)
- [Movies and shows](#movies-and-shows)
- [Requests](#requests)
- [Where the data lives](#where-the-data-lives)
- [What runs by itself](#what-runs-by-itself)

## Ports and addresses

| Service | Port on the machine | Tailscale address |
| :--- | :--- | :--- |
| Homepage | 3001 | `https://pc.your-tailnet.ts.net:1000` |
| Portainer | 9000 and 9443 | `https://pc.your-tailnet.ts.net:1001` |
| Immich | 2283 | `https://pc.your-tailnet.ts.net:1002` |
| Beszel | 8090 | `https://pc.your-tailnet.ts.net:1003` |
| AdGuard Home | 3000 (web) and 53 (DNS) | `https://pc.your-tailnet.ts.net:1004` |
| Nextcloud | 8082 | `https://pc.your-tailnet.ts.net:1005` |
| FileBrowser | 8081 | `https://pc.your-tailnet.ts.net:1006` |
| Speedtest Tracker | 8088 | `https://pc.your-tailnet.ts.net:1007` |
| Netdata | 19999 | `https://pc.your-tailnet.ts.net:1008` |
| Customize panel | 8300 | `https://pc.your-tailnet.ts.net:1100` |
| Navidrome | 4533 | the local network, and Tailscale on its own port |
| AudioMuse-AI | 8100 | the local network, and Tailscale on its own port |
| NaviList | 8200 | the local network, and Tailscale on its own port |
| Jellyfin | 8096 (web) and 7359 (UDP, app discovery) | the local network, and Tailscale on its own port |
| Seerr | 5055 | the local network, and Tailscale on its own port |
| Radarr | 7878 | the local network, and Tailscale on its own port |
| Sonarr | 8989 | the local network, and Tailscale on its own port |
| Prowlarr | 9696 | the local network, and Tailscale on its own port |
| qBittorrent | 8085 (web) and 6881 (torrent traffic) | the local network, and Tailscale on its own port |
| Downtify | 8000 | the local network, and Tailscale on its own port |
| MeTube | 8185 | the local network, and Tailscale on its own port |

Each stack's Compose file is in [`stacks/`](../stacks/) and lists its ports and volumes. The dashboard is covered in the [dashboard guide](homepage.md).

**A service you already run.** If one of these services is already running when the installer starts (it looks for the container name or image, for example your own Immich, Nextcloud, Navidrome or Jellyfin), the installer leaves it as it's. It deploys no stack for it, creates no login in it and writes no widget key. The service keeps its own port, and its dashboard card and Tailscale address point at it. The card is a plain link without live numbers. AudioMuse-AI and NaviList aren't installed when Navidrome is yours, and the Beszel agent isn't installed when Beszel is yours, because they only work with the copy the installer sets up. The uninstaller keeps these containers, their images and their data.

## Network and access

### Tailscale

A private network between my devices. It's on the server, my PC and my phone, and it's the only way in. The server has no public address and no forwarded ports. Tailscale Serve gives each service its own HTTPS address (ports 1000 to 1008, plus 1100 for the panel), so every address has a valid certificate and the browser never complains. You switch HTTPS on once, in the Tailscale admin page.

Partway through the install you're asked once for a Tailscale access token, after the machine has joined your network. The token lets the Tailscale card on the dashboard fill in. Press Enter to skip it.

![The Tailscale machines page with the server and the other devices](images/Tailscale.png)

### AdGuard Home

DNS filtering for the whole house. Any device that uses the server as its DNS server gets ads, trackers and known bad domains blocked, with nothing installed on the device itself. The dashboard card shows how many queries it has blocked. The web page is on port 3000 and DNS is on port 53. AdGuard Home runs in host networking mode, so the installer frees port 53 from the built-in resolver first.

The installer asks whether you want AdGuard Home. If you said no, `sudo homelab-setup adguard` adds it later.

![The AdGuard Home dashboard with its query and block counts](images/Adguard-home.png)

### Speedtest Tracker

Runs a speed test on a schedule and keeps the history. I use it to see whether the speed drops at certain times of day, and whether the provider gives me what I pay for.

![Speedtest Tracker with its download, upload and ping results](images/Speedtest-Tracker.png)

## Managing and watching the server

### Portainer

The control panel for Docker. I deploy and update every service as a stack from here, and it shows logs, restarts and memory use. The stacks are built from the Compose files in this repository.

![The Portainer home page with the local environment](images/Portainer.png)

### Beszel

Simple server health. A small hub and an agent on the machine draw graphs of CPU, memory, disk and network over time, plus the temperature. It's lighter than Netdata, so it's what I check for a quick look.

![The Beszel hub with the server's CPU, memory and temperature](images/Beszel.png)

### Netdata

Live metrics, second by second. I open it when the server feels slow. It shows CPU, memory, disks, network and each container, so you can see what's keeping the machine busy.

![The Netdata dashboard with CPU, disk and network gauges](images/Netdata.png)

## Files and photos

### Immich

Phone photo backup, a lot like Google Photos. The Immich app on my phone sends every photo and video to the server over Tailscale, and you can browse them on a timeline, in albums and on a map. Photos are stored in the Main pool at `/mnt/storage/immich`. Immich runs four containers: the server, its machine learning, a database and a cache.

I switched off Immich's text recognition (OCR). On a small machine with a spinning drive it kept the drive busy for ages after the first upload. To turn it back on, go to Administration, Settings, Machine Learning in Immich.

Photos can also be sent from the dashboard, using the Upload card in the Customize panel.

**Graphics chip.** If the machine has one (`/dev/dri`), the installer passes it to the Immich server and switches the machine learning container to the OpenVINO build of the same release, so face and search models run on the chip instead of the processor. The installer also sets Immich's video conversion to Intel QuickSync, unless you already chose a method there. Photo thumbnails are still made by the processor. When you run `sudo homelab-setup refresh` on a machine set up before this, the Immich stack is deployed once more to add the chip, and the first start downloads the larger OpenVINO image.

**A busy processor during the first upload.** The first big upload makes Immich create thumbnails, read metadata and run the machine learning models for every photo, so the processor can stay near 100% until it is done. On a 4-core machine, lower the job limits in Immich under Administration, Settings, Job Settings: thumbnail generation 2, metadata extraction 2, smart search 1, face detection 1 and video conversion 1. The uploads take longer, and the machine stays responsive.

![The Immich photo timeline](images/Immich.png)

### Nextcloud

A private cloud, like Google Drive. It keeps documents and files in sync between a PC and a phone. It runs four containers: the app, a database, a cache and one for background jobs. Its files are stored in the Main pool at `/mnt/storage/nextcloud`. Photos and videos from the phone go through Immich, so photo upload is switched off in the Nextcloud app.

![The Nextcloud home screen](images/Nextcloud.png)

**Connecting a device.** Install the Nextcloud app from [nextcloud.com/install](https://nextcloud.com/install/), turn on Tailscale on that device and sign in with the server address `https://pc.your-tailnet.ts.net:1005`. Keep the `https://` and the `:1005`, and add nothing after it. On a computer, choose a folder to sync, such as Documents. If the app can't connect, check first that Tailscale is on and signed in to the same account.

Sync isn't a backup. If a file is deleted on one device, the deletion is copied to the others. The backups are what protect the files.

I've tested the Windows app, plus signing in and browsing in the iPhone app. Other platforms should work the way Nextcloud describes, but I haven't tried them.

![The Nextcloud desktop app with the synced folder](images/nextcloud-sync.png)

### FileBrowser

A web file manager for the backups. It shows one folder, `Backup-Pool`, with a folder inside for each backup drive, so you can browse, download or edit copies from any device. The FileBrowser project was archived in 2026 and gets no more updates, which is why it stays behind Tailscale.

![FileBrowser showing the backup folders](images/Filebrowser.png)

## Music

These services work as a chain. Songs land in one music folder, Navidrome plays them, and NaviList and AudioMuse-AI make it smarter. You can also add songs from the Upload card.

### Navidrome

The music server. It plays everything in the music folder on a phone or in a browser, with a Spotify-like theme by default. Any app that speaks the Subsonic protocol works with it too. The music folder is mounted read-only, so Navidrome can never change or delete a song. It rescans the folder every hour. A song deleted from the folder shows grayed out until it's removed on the Missing Files page in Navidrome's settings.

The dashboard has a Navidrome card with the whole player inside it.

### NaviList

Makes playlists in Navidrome from listening history on ListenBrainz and Last.fm, such as Weekly Jams, Weekly Exploration, Daily Jams and the Last.fm charts. It only adds songs that are already in the library and never downloads anything. It checks for new data on its own.

![NaviList, the playlist manager for Navidrome](images/navilist.png)

### AudioMuse-AI

Analyzes every song once and remembers how it sounds, so Navidrome can suggest songs that sound alike (Instant Mix). It's the one heavy music service. On a small machine the analysis can take hours, so it has memory and CPU limits and can't starve the other apps. It runs three containers: the web page, the worker and a database.

![AudioMuse-AI analyzing songs](images/audiomuse.png)

Last.fm, ListenBrainz, AudioMuse-AI and NaviList are optional. Each has a step-by-step guide in [Music extras](music-extras.md).

### Downtify

Saves songs into the music folder. You paste a link, and the song lands in the same folder Navidrome plays from. The Stats tab on the dashboard counts the songs and lists the newest ones.

Downtify and MeTube are one Portainer stack called `music-downloader` ([`stacks/music-downloader.yaml`](../stacks/music-downloader.yaml)), so Portainer can stop, edit and update them like the other services. If they were started by hand before, Portainer says "created outside of Portainer", and `sudo homelab-setup refresh` moves them into the stack. Songs, videos and Downtify's own data are kept.

Downtify has its own sign-in. A new Downtify starts with one account, `admin` with the password `downtify`. The installer renames that account to the name you chose and gives it the shared admin password, so the default login stops working. Until that's done, `homelab` and the bell show a warning. A Downtify whose password was already changed by hand, or whose sign-in is switched off, is never touched. Names can use letters, digits, dots, dashes and underscores (3 to 32 characters).

![The Downtify page](images/downtify.png)

### MeTube

Downloads videos from a link, and a small web page shows the queue. Everything lands in the `videos` folder on the Main pool. It's the other half of the `music-downloader` stack.

![The MeTube page](images/metube.png)

## Movies and shows

### Jellyfin

The server for movies and TV shows. It plays what is in the `movies` and `shows` folders on the Main pool, in a browser, in the Jellyfin app on a phone, and on a TV or streaming stick. Both folders are mounted read-only, so Jellyfin can never change or delete a file. The folders belong to your server login, so you can copy files into them from another computer with `scp` or any SFTP app. Jellyfin finds new files on its next scan.

The installer sets up the service, the folders and the login. When the Homepage widget is set up, it finishes Jellyfin's first-time setup with your admin name and the shared admin password, so you sign in with those. A later step, "Jellyfin look", then adds a Movies library at `/media/movies` and a Shows library at `/media/shows` when no library uses those folders yet. Open Jellyfin (port 8096) and sign in. Jellyfin finds titles by file name, so name them the usual way:

- Movies: `Movie Name (2019)/Movie Name (2019).mkv`
- Shows: `Show Name (2019)/Season 01/Show Name S01E01.mkv`

**Renaming files that are already there.** `sudo homelab-rename` reads the title, the year and the season and episode number from each name (and from its folder when the name lacks them), drops the resolution, source, codec and release group, and moves the file to the layout above. It shows the full list first and asks before it changes anything. `sudo homelab-rename --dry-run` only shows the list. Subtitle files next to a video move with it. A file whose new name is already taken, trailers, samples and extras folders, and files without a season and episode number are listed and left as they are. A season released in parts ("Season 2 Part 2 - E01") keeps counting after the first part, so if part 1 ends at episode 13, part 2 episode 1 becomes S02E14, the way the metadata sources number it. Nothing is deleted or overwritten, and `sudo homelab-rename undo` puts the files of the last run back. Afterwards, choose Scan All Libraries in Jellyfin (Dashboard, Libraries). The command reads names only, so check the list for a title it got wrong (for example a title with dots in it, such as S.W.A.T.) before you answer yes.

**TVs and streaming sticks.** Port 8096 is open on the home network, so any device at home reaches the server at `http://` followed by the machine's address and `:8096`. The server also answers the apps' automatic search (UDP port 7359). Away from home, use the Tailscale address on Jellyfin's dashboard card.

**Graphics chip.** If the machine has one (`/dev/dri`), the installer passes it into the container. Jellyfin does not use it until you switch it on: open Dashboard, Playback, Transcoding and choose Intel QuickSync (or VAAPI if QuickSync does not work). It only matters for files a device cannot play as they are, because those have to be converted while they play. Without the chip, Jellyfin converts on the processor. If the chip appears later, the next `sudo homelab-setup refresh` passes it in.

**Settings and backup.** Jellyfin's settings, users and watch history are in the `jellyfin` folder of the home folder. The nightly backup copies `jellyfin/config`. The picture and conversion cache in `jellyfin/cache` is left out because Jellyfin rebuilds it.

**Updates.** The stack uses the `12` image tag, so `sudo homelab-update` installs newer 12.x releases. A new major version is a change to `stacks/jellyfin.yaml`, and Jellyfin recommends a backup before such an upgrade.

**Look.** The "Jellyfin look" step gives Jellyfin a theme and a slideshow, so a new server does not start with the plain default. It does four things through Jellyfin's own settings, using the key made for the dashboard widget:

- It fills the Custom CSS box (Dashboard, Branding) with the [Jellyfish](https://github.com/n00bcodr/Jellyfish) theme in the Jellyflix colors, plus its add-ons for progress bars, watched badges, card buttons, button labels, scrollbars and the Streamberry logo. The theme files load from the jsDelivr CDN, so a computer that cannot reach the internet shows Jellyfin's normal look. The box is only filled when it is empty. CSS you wrote yourself is never replaced.
- It adds the plugin repository `https://www.iamparadox.dev/jellyfin/plugins/manifest.json` and installs the plugins File Transformation and Media Bar, which give the slideshow at the top of the home page. Jellyfin is restarted once so the plugins load. Plugins are built for one Jellyfin version at a time. If there is no build for the installed version, the step says so, leaves the slideshow out, and tries again after Jellyfin has been updated.
- It adds the Movies and Shows libraries, unless a library already uses those folders.
- It turns on Backdrops and Details Banner for the admin's display settings. Jellyfin may keep these per browser. If the picture backgrounds are missing, turn them on under your profile, Settings, Display.

The Custom CSS also ends with one rule that sets the slideshow height to zero when the page is exactly 1137 pixels wide. That is the width the dashboard draws its Jellyfin box at, so the slideshow is hidden there and shows everywhere else. The theme works in the browser and in the Jellyfin card on the dashboard. The phone and TV apps do not load it. Hard refresh the page (Ctrl+Shift+R) after the step has run. To skip the step, run `sudo homelab-setup skip jellyfin-look`. To remove the theme later, clear the Custom CSS box in Jellyfin and save.

**Dashboard widget.** The Jellyfin card on the dashboard shows the number of movies and shows and what is playing now. The installer makes the widget's API key (named `homepage`) after it has the Jellyfin login. The widget needs the card to be on the dashboard first. The card is added automatically within five minutes of Jellyfin starting, and the next `sudo homelab-setup refresh` then sets up the widget. If Jellyfin already has a login that the installer did not make, it cannot create the key. In that case open Jellyfin, go to Dashboard, API Keys, press `+`, name the key `homepage`, then run `sudo homelab-setup fill` and paste the key.

If you already run a Jellyfin of your own, the installer leaves it as it is and does not add a second one.

### Requests

An optional set of five apps that lets people ask for a movie or show. They are not part of the normal install, because together they use roughly 1 to 1.5 GB of memory. Set them up with:

```bash
sudo homelab-setup requests
```

It asks first, then installs one stack called `requests` ([`stacks/requests.yaml`](../stacks/requests.yaml)) and links the apps. It needs Jellyfin, and it asks for the admin password once.

- **Seerr** is the page people use. Everyone signs in with their Jellyfin login, searches for a title and presses Request.
- **Radarr** (movies) and **Sonarr** (shows) keep the list of what was asked for and file finished downloads into the `movies` and `shows` folders.
- **Prowlarr** keeps the indexers in one place and sends them to Radarr and Sonarr, so you add each one only once.
- **qBittorrent** is the download client. Its downloads go to the `downloads` folder on the Main pool.

The installer gives Radarr, Sonarr, Prowlarr and qBittorrent the admin login, adds the root folders and qBittorrent to Radarr and Sonarr, links Prowlarr to both, and signs Seerr in to Jellyfin and links it to Radarr and Sonarr. It adds no indexers and no download sources. Until you add your own in Prowlarr (Indexers), a request is only a note on a list. Each app gets its own dashboard card within a few minutes.

Radarr, Sonarr and qBittorrent see the Main pool as `/data`, so the downloads folder and the library are in one place. Keep the `downloads` folder on the same drive as `movies` and `shows` (the Move Folders option on the Drives screen does that), so finished files are moved into the library instead of copied.

The five images follow their newest version, so `sudo homelab-update` keeps them current. The settings are in the `requests` folder of the home folder.

| Command | What it does |
| :--- | :--- |
| `sudo homelab-setup requests` | Sets the apps up, or checks them and finishes anything that is missing |
| `sudo homelab-setup requests status` | Shows whether each app runs and is linked |
| `sudo homelab-setup requests remove` | Removes the five containers; their settings and the downloads folder stay |

## Where the data lives

| What | Where |
| :--- | :--- |
| Photos, videos, Nextcloud files, music, movies and shows | The Main pool, at `/mnt/storage` |
| Databases and app settings | The boot drive, in the home folder |
| The backup | The Backup pool, at `/mnt/backup`, once a backup drive is connected |

The Main pool uses mergerfs, so several drives show up as one folder. Drives are mounted by their ID, so they come back the same after a reboot. With no drive in Main, or while its drive is missing, the boot drive is the storage: `/mnt/storage` is a plain folder there and the services keep running. A small start-up check (`sudo drives guard`) makes sure of that before Docker starts. When a drive is in Main, the drive is the storage, and files the services saved on the boot drive in the meantime are copied onto it (see [When the Main drive is missing](maintenance.md#when-the-main-drive-is-missing)).

The nightly backup copies the Main pool and the lab's settings. Deleted or changed files are kept as older versions for 30 days by default, and the Nextcloud database is dumped every night (Immich makes its own database backups). More backups, to another computer or to the cloud, can be set up in the Backups card of the [Customize panel](homepage.md#drives).

`sudo drives status` shows the pools and the health of every drive. `sudo drives` is a menu for connecting, moving and replacing drives, and it asks before it erases anything.

In a pool of separate drives, each file lives whole on one drive. Nothing is split across drives, and the pool has no protection by itself: if a drive fails, the files on it are lost and the rest stay. New files go to the first drive until it is nearly full, then to the next. `sudo drives fillorder` can spread them by free space instead.

To give one drive to a few folders, for example the movies and shows on their own drive, use **Move Folders** on the Pool box of the Drives screen, or `sudo drives folders`. Choose the folders and the drive. Each file is copied and checked before the old copy is removed, and the pool looks the same afterwards. By default, new files of a moved folder keep going to that folder's drive, so new Jellyfin files stay on the Jellyfin drive. This needs a pool of separate drives with at least two drives, so it is not offered for SnapRAID, ZFS or RAID. Do not run `sudo drives balance` afterwards, because it spreads the folders over both drives again (it asks first).

## What runs by itself

| How often | What |
| :--- | :--- |
| Every 5 minutes | Makes a card for any new service, checks whether a backup task is due and refreshes the notification bell |
| Every 15 minutes | Reads the drives and the services to fill the Stats tab |
| Every hour | Checks whether the weekly look for newer service versions is due |
| Every night | The backup (at 6:00 server time) and the calendar update |
