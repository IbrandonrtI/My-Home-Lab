# Decisions

Choices that are costly to undo, or easy to undo by mistake, and the reason for each. Add an entry when a choice like this is made. Each entry says where its reason comes from, and what is not known.

## Jellyfin follows the `12` tag

**Decision.** `stacks/jellyfin.yaml` uses the image `jellyfin/jellyfin:12`.
**Why.** `sudo homelab-update` then installs new 12.x releases. A new major version is a deliberate change to the stack file, and Jellyfin recommends a backup before one.
**Source.** `docs/services.md`, section Jellyfin, Updates.

## Jellyfin uses the Jellyfish theme in the Jellyflix colors

**Decision.** The Jellyfin look step writes `@import` lines for the [Jellyfish](https://github.com/n00bcodr/Jellyfish) theme into Jellyfin's Custom CSS.
**Why.** Ultrachromic and ElegantFin were tried first and did not display on Jellyfin 12.4. Jellyfish states support for version 12 and displayed correctly.
**Source.** Tried on the real server, November 2026. It has not been tested on other Jellyfin versions.

## The Custom CSS box is only filled when it is empty

**Decision.** `jf_set_css()` writes the theme only when the box is empty, or already holds Jellyfish lines. CSS written by hand is never replaced, and the step prints a note instead.
**Why.** Replacing CSS a person wrote would lose their work. A theme that is already there is not rewritten, so a re-run changes nothing.
**Consequence.** A server that already has CSS does not get later changes to the theme lines. Those must be pasted in by hand (Dashboard, Branding).
**Source.** Chosen when the step was designed, from two options: fill the box only when it is empty, or always replace it. The step runs by default and can be skipped.

## The Jellyfin box is drawn at 1137 pixels

**Decision.** `custom.js` draws the Jellyfin box exactly `JF_WIDE` (1137) pixels wide and scales it to fit the card. The installer's Custom CSS ends with a rule for that exact width that sets `--slideshow-height: 0px`.
**Why.** In a narrow card Jellyfin switches to its small-screen layout. The slideshow never filled in even at a desktop width, and it left an empty space at the top of the box, so it is hidden there. In a normal tab it still shows.
**Linked values.** `JF_WIDE` in `homepage-config/custom.js` and the `width` in `JELLYFIN_BOX_CSS` in `src/installer/45_jellyfin_look.py` must be equal. `tests/test_repo_consistency.py` checks this.
**Not known.** Whether `--slideshow-height` is the variable the theme and plugin really use is not confirmed. If the empty space returns, inspect the slideshow's element in a normal tab and write a rule for its real id or class.
**Source.** Tried on the real server, November 2026.

## The slideshow plugins are installed in a fixed order, with one restart

**Decision.** File Transformation is installed before Media Bar, from the repository `https://www.iamparadox.dev/jellyfin/plugins/manifest.json`. Jellyfin restarts once afterwards.
**Why.** Media Bar needs File Transformation. Plugins are built for one Jellyfin version, so when there is no build for the installed version the step leaves the slideshow out and tries again after Jellyfin has been updated.
**Source.** The plugin's published instructions, and `docs/services.md`.

## Embedded frames lock the page's scroll while the pointer is over them

**Decision.** `custom.js` stops the dashboard page from scrolling while the pointer is over the Jellyfin box, Navidrome, the terminal, the Customize panel or the Edit Links panel.
**Why.** When a frame reached its end, the whole page started to scroll.
**Source.** Reported on the real server, November 2026.

## The panel listens on this machine only

**Decision.** By default the Customize panel binds to `127.0.0.1`. Tailscale Serve gives it an HTTPS address that only the private network can reach. It has its own password, stored hashed.
**Why.** It can change files and reach the drives tool, so it must not be open to the home network.
**Source.** `scripts/homelab-panel`, the opening description, and `docs/homepage.md`.

## Seven files are built from pieces

**Decision.** `installer/homelab-setup`, `scripts/drives`, `scripts/homelab`, `scripts/homelab-update`, `scripts/homelab-panel`, `panel/ui/app.js` and `homepage-config/custom.js` are generated from `src/` by `tools/build.py`. The GitHub Action fails when a built file differs from its pieces. The built files stay in the repository, so uploading and installing work as before.
**Why.** The first four were already large. The panel script (about 5,000 lines) and the two page scripts (3,000 and 1,750 lines) became too long to read in one piece, so they were split at the same kind of boundaries: whole functions, never the inside of one. The pieces of the two page scripts are not complete scripts on their own (a piece can start inside the wrapper function that the next piece finishes), so only the built file is run or checked.
**Source.** `tools/build.py`, `.github/workflows/checks.yml`.

## Some images follow a moving tag

**Decision.** Most images are pinned to an exact version. These are not: Downtify and MeTube (`latest`), Immich (`release`), Netdata (`stable`), Portainer (`latest`, set by the installer), Redis in the Nextcloud stack (`alpine`).
**Why.** Not recorded. The pinned ones follow the rule in the entry on Jellyfin. `homelab-update` compares image digests, so it still notices a newer image behind a moving tag.
**Consequence.** `docs/maintenance.md` says which images follow a moving name. `tests/test_repo_consistency.py` fails when a new image without a fixed version is added, unless it is listed on purpose.

## Navidrome allows being shown inside the dashboard

**Decision.** `stacks/navidrome.yaml` sets `ND_HTTPHEADERS_FRAMEOPTIONS: "ALLOWALL"`.
**Why.** The Navidrome card on the dashboard shows Navidrome in a frame. Navidrome refuses that by default, and its setting has no value that means "only this dashboard", so the frame would stay blank.
**Consequence.** Any page can show Navidrome in a frame. Navidrome is reachable only on the private network, and a page that frames it still needs the Navidrome login. Tightening it needs a reverse proxy that sets a `Content-Security-Policy: frame-ancestors` header for the dashboard address only.
**Source.** `stacks/navidrome.yaml`.

## A copy between drives never replaces a different file

**Decision.** The copies in the drives tool that are followed by removing the originals share two checks, `copy_conflicts` and `copy_check`. Drain, balance and adding a drive that finds files in the plain pool folder stop before copying when a file exists on both sides with different content, and name it. Their copies and final checks use `--update`, so a file that a service changed during the copy is not replaced by the older copy, and the final check counts everything still waiting, including links. Restore uses `copy_check` for its final check. Moving files saved on the boot drive keeps the pool's version and reports the difference.
**Why.** There were six separate copy-and-check routines of different strictness. Tests on loop devices showed that two of them could replace newer data with older data (a drain or balance while a service wrote to the pool) and that adding a drive could delete a boot-drive file that differed from the file on the drive.
**Source.** `src/drives/10_helpers.sh`, `tests/drives/`.

## The drives tool is tested on loop devices

**Decision.** `tests/drives/` builds real ext4 drives out of files (loop devices) and a real mergerfs pool in a temporary folder, using the tool's own test mode, and runs the flows on them. `tests/test_drives_loop.py` runs every scenario when it can (root, loop devices, FUSE, mergerfs, rsync, parted) and skips otherwise.
**Why.** The tool moves people's files and could only be tried on a real server.
**Source.** `tests/drives/lab.sh`.

## The update tool can change a version that is kept in a variable

**Decision.** When an image in a stack file has its version as a variable (`${IMMICH_VERSION:-release}`), `homelab-update` sets the variable and its default to the new version, instead of refusing.
**Why.** Immich's version is a variable. Images pinned to a version number would otherwise have to be updated by hand in Portainer. Immich and Redis follow a moving name by choice, because the owner does not want the lab tied to one version, so this only matters if the owner pins Immich later.
**Source.** `src/homelab-update/20_portainer.sh` and `tests/test_update_portainer.py`.
