# My Home Lab

[![checks](https://github.com/IbrandonrtI/My-Home-Lab/actions/workflows/checks.yml/badge.svg)](https://github.com/IbrandonrtI/My-Home-Lab/actions/workflows/checks.yml)

This is the home server I run, plus the installer and tools I use to build it and look after it. It blocks ads for the whole house, backs up my phone's photos, stores files, plays music, movies and shows, and keeps an eye on its own health. It all ends up on one dashboard that works on a phone or a PC. Nothing is open to the internet. I get to everything through Tailscale.

![The Home tab of the dashboard on a desktop screen](docs/images/homepage-home.png)

<img src="docs/images/homepage-phone.png" alt="The dashboard on a phone" width="300">

## Contents

- [What it does](#what-it-does)
- [How it fits together](#how-it-fits-together)
- [Services](#services)
- [Hardware](#hardware)
- [Data and backups](#data-and-backups)
- [Installing it](#installing-it)
- [Everyday commands](#everyday-commands)
- [Guides](#guides)
- [What is in this repository](#what-is-in-this-repository)
- [Security](#security)
- [Built with Claude](#built-with-claude)

## What it does

- A [Homepage](https://gethomepage.dev) dashboard with a card for every service, live numbers, ten themes that can switch between day and night, gentle motion, small graphs, a search palette and a music player built in.
- The Customize tab is a control panel. It changes the look, manages drives, runs and restores backups, uploads photos and songs, and installs updates.
- A bell lists what needs attention (a service that's down, an update waiting, a backup that failed) and links to the screen that fixes it. A small ring shows how far long jobs have got.
- No port is forwarded on the router. Each service gets its own HTTPS address on my Tailscale network.
- `setup.sh` builds the whole lab on a fresh Ubuntu, Mint or Debian machine. It skips what's already done and never formats a drive.

## How it fits together

My phone and PC reach the server through Tailscale, and Tailscale Serve gives each app its own HTTPS address. Other devices at home just use it for DNS. The apps run in Docker, with Portainer to manage them, and keep their data on the boot drive and the storage pools. The Customize panel sits next to Docker as a small service of its own.

## Services

| Service | What it is for | More |
| :--- | :--- | :--- |
| **Homepage** | The dashboard: a card per service, live numbers and four tabs | [Dashboard guide](docs/homepage.md) |
| **Customize panel** | Look, layout, cards, drives, backups, uploads and updates | [Dashboard guide](docs/homepage.md#the-customize-panel) |
| **Notification bell** | What needs attention, with a button to fix it | [Dashboard guide](docs/homepage.md#the-notification-bell) |
| **Tailscale** | The private network. Gives each service an HTTPS address | [Services](docs/services.md#tailscale) |
| **AdGuard Home** | Blocks ads and trackers for every device on the network | [Services](docs/services.md#adguard-home) |
| **Speedtest Tracker** | Tests the internet speed on a schedule and keeps the history | [Services](docs/services.md#speedtest-tracker) |
| **Portainer** | Manages Docker, where everything runs | [Services](docs/services.md#portainer) |
| **Beszel** | Server health graphs: CPU, memory, disk and temperature | [Services](docs/services.md#beszel) |
| **Netdata** | Live system metrics, second by second | [Services](docs/services.md#netdata) |
| **Immich** | Backs up phone photos and videos, like Google Photos | [Services](docs/services.md#immich) |
| **Nextcloud** | Keeps files in sync between devices, like Google Drive | [Services](docs/services.md#nextcloud) |
| **FileBrowser** | Browses the backups in a web page | [Services](docs/services.md#filebrowser) |
| **Navidrome** | Music server for the phone and the browser | [Services](docs/services.md#navidrome) |
| **NaviList** | Makes Navidrome playlists from listening history | [Services](docs/services.md#navilist) |
| **AudioMuse-AI** | Analyzes songs so Navidrome can suggest ones that sound alike | [Services](docs/services.md#audiomuse-ai) |
| **Jellyfin** | Plays movies and TV shows on a phone, a TV or in the browser | [Services](docs/services.md#jellyfin) |
| **Downtify** | Saves songs into the music folder | [Services](docs/services.md#downtify) |
| **MeTube** | Downloads videos from a link | [Services](docs/services.md#metube) |

Everything except Tailscale runs in Docker. Each stack has a Compose file in [`stacks/`](stacks/). Most images are pinned to a version, so nothing changes until I change the version. A few follow a moving tag instead:

- Downtify and MeTube (the `music-downloader` stack) follow `latest` on purpose, because the sites they download from change often and old versions stop working.
- Immich follows its `release` tag, and Netdata follows `stable`.
- Jellyfin follows its version 12 line (`jellyfin/jellyfin:12`), so it gets the 12.x fixes when the images are updated but never jumps to a new major version by itself.

`sudo homelab-update check` shows which services have a newer version.

## Hardware

| Part | Details |
| :--- | :--- |
| Computer | HP ProDesk 600 G3 Desktop Mini, Intel Core i5-7500T (4 cores) |
| Memory | 8 GB DDR4 |
| Boot drive | 750 GB 2.5-inch hard drive in the internal bay. The system and the app data live here |
| Data drive | 1 TB 2.5-inch hard drive on a SATA to USB 3.0 adapter. It is the first drive of the Main pool |
| Backup drive | None yet. The Backup pool is ready and waits for one |
| Network | Wired Ethernet, with a fixed address reserved in the router |
| Operating system | Ubuntu Server on LVM, without disk encryption |

![The Drives screen of the Customize panel](docs/images/drives-tab.png)

## Data and backups

Photos, files, music, movies and shows live in the Main pool. It uses mergerfs, so a few drives look like one folder. Databases and app settings stay on the boot drive.

A backup runs every night at 6:00 server time. It copies the Main pool and the lab's settings to the Backup pool, keeps older versions of changed files for 30 days and dumps the databases. The backup runs only while a drive is connected in the Backup pool, so until I add one nothing is backed up. A backup drive is the next thing I need to add. Restores and rebuilds are in [Maintenance](docs/maintenance.md#backups).

## Installing it

**You need** a machine running Ubuntu 22.04, 24.04 or 26.04, Linux Mint 21, 22 or 23, or Debian 12 or 13, with an internet connection. The install takes about 30 to 60 minutes and downloads around 10 GB. It asks a few questions along the way.

```bash
sudo apt update && sudo apt upgrade && sudo apt install -y git
git clone https://github.com/IbrandonrtI/My-Home-Lab.git
cd My-Home-Lab
sudo bash setup.sh install --dry-run     # shows what it would do, changes nothing
sudo bash setup.sh install               # asks a few questions, then builds the lab
```

A few things to know:

- Use the machine's own screen and keyboard, not SSH through Tailscale. The installer frees port 53 for AdGuard Home and restarts Tailscale, which would cut your session. SSH over your home network is fine.
- The dashboard comes up first. Homepage and the small services are ready quickly, while Immich, Nextcloud, the Beszel and widget keys and the system upgrade finish in a background job after the installer says it's done. `sudo homelab-setup status` shows where that job is.
- Passwords are generated for you and kept in a root-only file. `sudo homelab-setup secrets` shows them, so have a password manager ready.
- The time zone and weather city come from your internet connection. You can change either on the Look screen of the Customize panel.
- You don't need to run `refresh` yourself. A quiet job checks every few minutes and picks up whatever became possible, like the Tailscale addresses once you turn on HTTPS in the Tailscale admin page. When nothing is left, it removes itself.
- Services you already run are left alone. If a container for one of the lab's services is already on the machine, the installer says so at the start and doesn't touch it. Its card links to your copy without live numbers, and the uninstaller keeps it too.

To join Tailscale without opening a login link, for example on a machine with no screen, save a Tailscale auth key in a file only you can read and run the installer as your normal user. Don't use `sudo` here, because the script asks for it by itself and passes the key along. The key starts with `tskey-auth-` and is created in the Tailscale admin page under Settings, Keys. Delete it afterwards.

```bash
TS_AUTHKEY_FILE=~/tailscale-key bash setup.sh install
```

> **Placeholders.** Names in this repository are stand-ins: `your-username` is the Linux user, `192.168.X.X` is the server's address at home and `your-tailnet.ts.net` is your Tailscale network. The installer fills in your own values.

## Everyday commands

Opening a terminal on the server prints a short summary: the pools, the last backup, the containers and the dashboard address.

| Command | What it does |
| :--- | :--- |
| `homelab` | The full status, with suggested next steps |
| `homelab commands` | Every command, in groups |
| `sudo drives status` | The pools, the drives, their health and the free space |
| `sudo homelab-backup` | Runs a backup now |
| `sudo homelab-backup verify` | Compares every backed-up file with the original (`verify --repair` fixes wrong copies) |
| `sudo homelab-update check` | Looks for newer versions of the services |
| `sudo homelab-setup status` | Shows the install steps that finish in the background |
| `sudo homelab-setup upgrade` | Brings the lab up to date with this repository |
| `sudo homelab-setup uninstall` | Takes the lab off the machine and asks what to keep |

![The screen that appears when a terminal opens](docs/images/login-screen.png)

## Guides

| Guide | What is in it |
| :--- | :--- |
| [The dashboard](docs/homepage.md) | The tabs, the notification bell, the progress ring and the Customize panel |
| [The services](docs/services.md) | What each service does, where its data is and how to use it |
| [Music extras](docs/music-extras.md) | Setting up Last.fm, ListenBrainz, AudioMuse-AI and NaviList |
| [Maintenance](docs/maintenance.md) | Checking, updating, backups, restores, power loss, rebuilding and secrets |
| [Troubleshooting](docs/troubleshooting.md) | Common problems, each with its cause and fix |

## What is in this repository

```text
README.md        this page
CLAUDE.md        working rules for Claude when it edits this repository
docs/            the guides and their images
setup.sh         starts the installer
installer/       homelab-setup, the installer (built from src/)
src/             the pieces the installer and the longer scripts are built from
stacks/          one Compose file for each stack
homepage-config/ the dashboard's settings, widgets and styles
panel/           the Customize panel's web page
scripts/         the commands that run on the server (homelab, drives, backups, ...)
theme-pictures/  the background pictures for the dashboard themes
tools/           the script that builds the installer and the longer scripts from src/
tests/           automated tests (Python unittest)
dev/             notes for whoever edits the code: a glossary and a list of decisions
ruff.toml        settings for the Python linter
```

The installer, `drives`, `homelab` and `homelab-update` are built from small pieces in `src/`. Change the pieces, then run `bash tools/build.sh` to rebuild them, and `bash tools/build.sh --check` to confirm nothing is out of date.

Two workflows run on every push. [`checks.yml`](.github/workflows/checks.yml) covers the shell scripts, the installer build, the Python style, the links and the Markdown. [`tests.yml`](.github/workflows/tests.yml) runs the tests in `tests/`. They cover the Jellyfin look, the panel's sign-in and whether the repository agrees with itself. They don't run the installer on a real machine, so I still check changes on the server.

## Security

- No port is forwarded. Every service is reached through Tailscale, and secrets stay out of Git.
- Each integration has its own key. Most container images are pinned to a version, and the ones that follow a moving tag are listed under [Services](#services).
- Portainer, Homepage and the Beszel agent all mount the Docker socket (Homepage and Beszel read-only), so anyone who gets into them can reach Docker. They stay behind Tailscale, with strong passwords.
- Nothing on the boot drive or in the backups is encrypted. For a machine at home I'm fine with that.
- FileBrowser's project was archived and gets no more security fixes, so it's reachable only over Tailscale.
