# Glossary

The words this repository uses, and what each one means here. Use these words in code, messages and guides so the same thing always has the same name. When a new word is needed, add it here.

## The dashboard

**Homepage.** The dashboard program ([gethomepage.dev](https://gethomepage.dev)). It runs as the container `homepage`, and its files are in `~/homepage-config`.

**Card.** One service box on the dashboard. Cards are listed in `services.yaml`, and each has an id.

**Tile.** A small card for a statistic or the calendar. Its id starts with `stat-` or `cal-`.

**Look.** How the dashboard appears: theme, colors, picture, motion. It is saved as a marked block in `custom.css` and is changed on the Look screen of the Customize panel. Not to be confused with the installer step "Jellyfin look".

**Theme.** One of the ten ready-made looks. Each has a picture in `theme-pictures/`.

**Marked block.** A part of `custom.css` between a `/* >>> homelab NAME >>>` line and a `/* <<< homelab NAME <<< */` line. The panel rewrites the blocks named look, picture and theme. Text outside the markers is never touched.

**Bar.** The row at the top of the dashboard. Its order is: tabs, bell, search, install button, tray icons, then the three-dots menu.

**Bell.** The notification bell. It lists what needs attention (a service that is down, an update waiting, a failed backup).

**Tray.** The row of small link icons in the bar. The three-dots menu at its end adds, orders and removes them. Icons can be services, bookmarks or custom links. In the code it is the element `#hl-dock`, and the choice is kept in the browser under the key `hl-tray`.

**Jellyfin box.** The Jellyfin library shown inside the dashboard card when the card's arrow is opened (the element `#hl-jf-frame`). It is drawn at a fixed width, `JF_WIDE` in `custom.js`, and scaled to fit the card.

**Slideshow.** The banner at the top of Jellyfin's home page, made by the Media Bar plugin. It is hidden in the Jellyfin box and shown everywhere else.

**Scroll lock.** While the pointer is over an embedded frame (the Jellyfin box, Navidrome, the terminal, the Customize panel), the dashboard page does not scroll. It stops the page from moving when a frame reaches its end.

## The Customize panel

**Customize panel (the panel).** The small control panel (`scripts/homelab-panel`). It listens on port 8300 of this machine only. Tailscale Serve gives it an HTTPS address on port 1100. It has its own password. Its screens are Look, Layout, Cards, Drives and Updates.

## The installer

**Step.** One item of the installer's checklist. It has an id, a group, a title, the steps it needs, a `probe()` that says whether it is done, and a `run()` that does the work.

**Refresh.** `sudo homelab-setup refresh`. It goes through the checklist again and does only the steps that are not done.

**Optional step.** A step that can be skipped with `sudo homelab-setup skip ID` or marked finished by hand with `sudo homelab-setup done ID`.

**Jellyfin look.** The installer step `jellyfin-look`. It gives Jellyfin its theme, the slideshow plugins, the Movies and Shows libraries and its display settings. Not to be confused with the dashboard's Look.

**Jellyfin key.** The Jellyfin API key named `homepage`. The dashboard's widget and the Jellyfin look step both use it.

**FAKE mode.** The installer run with `HLS_FAKE=1` and `HLS_ROOT` pointing to a temporary folder. It changes nothing on the real machine. The tests use it.

**Built file.** A file joined from the pieces in `src/` by `tools/build.py`. See `CLAUDE.md` for the list.

## The machine

**Stack.** One Compose file in `stacks/`, run by Portainer. A stack can hold several containers.

**Main pool.** The storage pool at `/mnt/storage`. It holds photos, videos, Nextcloud files, music, movies and shows.

**Backup pool.** The pool at `/mnt/backup`. Backups go to it, and only while a backup drive is connected.

**Drives tool.** `sudo drives`. It manages the drives and pools, and asks for typed confirmation before anything destructive.

**Secrets.** The logins and keys the installer makes or is given. They are kept on the server and never in the repository.

**State file.** `/var/lib/homelab-setup/state.json`. The installer's record of its answers and the one-time steps it has done.

**Tailscale Serve.** The way each service gets its own HTTPS address on the private network (ports 1000 and up).

## The checks

**Selftest.** `sudo homelab-selftest`. A read-only check of the whole running lab that saves a report in the home folder.

**Repocheck.** `scripts/homelab-repocheck`. It checks the repository's files: links, YAML, code blocks and anything that looks like a real secret.
