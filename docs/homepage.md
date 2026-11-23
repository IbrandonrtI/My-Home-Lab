# The dashboard

The dashboard is the front door of the lab. It's a [Homepage](https://gethomepage.dev) page with my own styling on top: frosted-glass cards, a status dot on every card and live numbers from the services. It fits anything from a phone to a big monitor. The installer sets it all up, and you can change the look and the layout from the Customize panel.

## Contents

- [The top bar](#the-top-bar)
- [The four tabs](#the-four-tabs)
- [The notification bell](#the-notification-bell)
- [The progress ring](#the-progress-ring)
- [Motion, graphs and search](#motion-graphs-and-search)
- [On a phone](#on-a-phone)
- [The Customize panel](#the-customize-panel)
- [Keeping it simple](#keeping-it-simple)
- [Where the files are](#where-the-files-are)

![The Home tab of the dashboard on a desktop screen](images/homepage-home.png)

## The top bar

Along the top is a row of small widgets:

- HomeLab shows CPU, memory, CPU temperature and how long the machine has been up.
- Main Pool and Backup Pool show how full each pool is. The backup one says "Connect Backup Drive" until a backup drive is connected.
- Network shows how much data is going in and out.
- Next come the date and time, and the weather for your city.
- The last one is a search box that searches the web.

Quick Launch also works: start typing anywhere on the page and it jumps to a card, searches the web or opens an address.

## The four tabs

### Home

This is where the services live, in groups:

| Group | Cards |
| :--- | :--- |
| Network and DNS | Tailscale, AdGuard Home, Speedtest Tracker |
| Monitoring and Management | Portainer, Beszel, Netdata |
| Files and Photos | Immich, Nextcloud, FileBrowser |
| Media and Entertainment | Navidrome, Jellyfin, MeTube, Downtify |
| Calendar | This Month and Coming Up |

Each card has a dot that shows whether the service is up, and most show live numbers. The AdGuard card shows how many queries it has blocked, the Immich card counts photos and videos, and so on. Click a card to open the service.

The Navidrome card is a bit different. It sits at the top over the full width and has the music player inside it, so songs play without leaving the dashboard. One small button shrinks the player and another changes its height.

![The Navidrome card with the player open](images/navidrome-card.png)

The calendar shows holidays, any online calendars you add (Google, school) and your own events. Add them from the terminal with `homelab event add` and `homelab calendar add`.

New services get a card automatically. Every few minutes the lab looks for containers with a web page and makes a card for any that don't have one yet.

### Stats

The numbers tab. It refreshes by itself every few minutes:

| Group | What it shows |
| :--- | :--- |
| Preview | Library size, storage used, when the last backup ran and how many containers are running |
| Music Library | How many songs Downtify saved, and the newest ones |
| Library Totals | Photos and videos in Immich, files and shares in Nextcloud |
| Storage | The Main pool, the Backup pool and the temperature of every drive |
| Backup and Updates | How the last backup went, and which containers have an update waiting |
| Folder Sizes | How big each folder is, counted again only when something changed |

Above these groups, two charts show **Docker CPU** and **Docker memory** for the last hour, one stacked area per container. The six busiest containers get their own color and the rest are added together as "other". Point at a chart to see every container's value at that minute. CPU is shown as a share of the whole machine (all cores together), so 100 % means every core is busy. The control panel samples `docker stats` once a minute and keeps the last 60 readings in `homepage-config/images/docker-trends.json` (a few KB). The charts start empty after an update and fill in over the first hour.

![The Stats tab](images/homepage-stats.png)

### Links

Bookmarks, in groups, each with its logo. The Edit Links box adds, changes or removes bookmarks without editing a file. Drag a link by its handle to change the order, or drop it on another group to move it. The arrows do the same one step at a time. Nothing changes on the dashboard until you press **Save** in the bar at the top of the box, which stays in view while the list scrolls. One save is one reload of the dashboard, and **Discard Changes** goes back to the saved list. A new link gets the color of the other links in its group, so it matches your theme. From the terminal, use `homelab bookmark add NAME URL`. If an older version gave a bookmark a shared logo link that no longer works, `homelab bookmark icons` lists it and `homelab bookmark icons --apply` switches it to a built-in icon.

> **Photo to add:** A screenshot of the Links tab with its groups and the link editor. Save it in `docs/images/` as `homepage-links.png`.

### Customize

The control panel and a web terminal. Both are covered below.

## The notification bell

Next to the Customize tab sits a small bell. It borrows the colors and shape of the tabs, so it follows the theme. It stays quiet while everything is fine. When something needs attention, a badge shows how many items there are, and the badge color shows how serious they are: red for something broken, yellow for a warning, blue for information.

Click the bell to open the list. The server checks these things every five minutes:

| What | When it shows up |
| :--- | :--- |
| A service is down | A container stopped or reports that it isn't healthy |
| Updates | New container versions or system updates are waiting, or the machine needs a restart |
| Drives and backups | A pool is missing or almost full, a drive reports a problem, or the last backup failed or is more than a day old |
| Disk space | The boot drive is getting full |
| Tailscale | Tailscale is not connected, so the lab can't be reached from outside |
| Temperature | A drive is running hot |
| Files being written | Something is writing to a storage pool, such as an upload. Updates and drive changes wait until it stops |

The Refresh button in the list looks at everything again right away instead of waiting for the next check. It needs the panel to be running. If the panel doesn't answer, the list says so and keeps showing the last saved result.

An item you can fix from the panel has a button. Update opens the Updates screen, and the drive and backup items open the Drives screen. The bell only reads what the server writes down, and it never changes anything on its own.

![The notification bell with its list open](images/bell.png)

## The progress ring

To the right of the bell, a small ring shows up while something slow is running and goes away when it's done. Click it to see what's running, with a percent, a bar and the current step.

It covers the last install steps that finish in the background (for example `6 of 19 steps done`), updates, drive changes, backups and restores started from the panel, and RAID arrays that build or check themselves for hours. The time left only appears when it can be worked out, and it's a rough guide. A check or a restart can't tell how far along it's, so the ring just turns.

The ring turns amber when an install step failed, is waiting for something you need to do, or hasn't changed for about 20 minutes. The list then names the step and the command to run, `sudo homelab-setup status`. Work of unknown size, such as an upload, gets no ring. The bell says that files are being written instead.

## Motion, graphs and search

A few touches make the page feel alive. All of them follow the theme and can be turned down or off under **Look → Motion, Icons and Greeting**.

- Cards lift a little when you point at them, and a soft light follows the pointer across the glass.
- A slow glow drifts behind the cards, tinted with the colors of the theme.
- The small status dot on a card pulses green while the service is up and red when it is down.
- Numbers count up to their value when they first show, and glide to a new value when it changes.
- The system numbers in the top panel are drawn as round gauges for CPU, memory, temperature and storage, with the network speeds (and a small graph of the last hour) and the uptime beside them. Each one has a slot of equal width, so nothing shifts when a number gets longer or shorter. The temperature ring is out of 100 °C and shifts from green to yellow to red as the CPU gets hotter. The backup drive shows only while it is connected. The original widgets stay in the page, hidden, and supply the values. The control panel keeps the history in `homepage-config/images/trends.json` (about 3 KB, a new point every 30 seconds).
- While the page is new, or Homepage has just restarted, a tile that cannot reach its service yet shows a moving placeholder instead of a red "API Error". If the error is still there after about 25 seconds, it shows as before.
- The top of the page is one panel. It holds your name (the admin name you typed in the installer, or the name you set under Look; no "Good evening" in front), the clock and weather, and the system numbers. On a wide screen (1760 pixels or more) all of that fits in one slim row; on a narrower one the name, clock and weather sit above the numbers. Below it is one bar with the tabs, the notification bell, the search icon and a row of small icons that opens your favorite services with one click, each part separated by a thin line.
- The five icons start with Jellyfin, Immich, Nextcloud, FileBrowser and Portainer. Once you have opened a service at least three times, the services you open most often move to the front. The counts are kept in the browser, so each browser and person has their own. The icons stay in the bar on every tab. The small three-dot menu at the end of the row lets you change the row in this browser: add a service or bookmark from the dashboard, add your own link (a name and a web address), move icons earlier or later, or remove them. **Use Most Visited** in that menu goes back to the automatic row.
- The Jellyfin card leaves out the Songs count. The small arrow on the card (the same one Navidrome has) opens Jellyfin's own movies and shows library inside the card. While it is open the Jellyfin card sits to the right of the music player, the other services move below the two, the calendar fills the space beside the next group, and the card's counts are hidden (sign in to Jellyfin once in that box). The library is drawn at a fixed desktop width (1137 pixels) and scaled to fit the card, because Jellyfin switches to its small-screen layout in a narrow box. The home slideshow is hidden in this box, so there is no empty gap at the top. It still shows in a normal Jellyfin tab. Select the arrow again to close the library: the card goes back to its normal place and shows its counts. The choice is kept in the browser. On a narrow window the two cards stack.
- Pointing at the Jellyfin library, the music player, Terminal, Customize or Edit Links keeps the page itself still, so scrolling to the top or bottom of one of them does not move the dashboard. Move the pointer off the frame to scroll the page again.
- Press `Ctrl+K` (or select the search icon in the bar) to search every card, bookmark and tab, then `Enter` to open it. This is in addition to the Quick Launch that starts when you type.

Motion is Subtle by default. A device that is set to reduce motion always gets none of the movement. The greeting, the quick launch row and the magnifier are hidden on a phone, where the page's own search bar stays.

## On a phone

On a phone the cards stack in one column. It's the same dashboard, so the services and the player work the same way.

<img src="images/homepage-phone.png" alt="The dashboard on a phone" width="300">

## The Customize panel

The Customize tab is a small control panel. It uses the admin password you chose at the start of the install (change it later with `homelab panel password`), and it only runs on the server. You can also open it directly at `https://pc.your-tailnet.ts.net:1100`. It has five screens: Look, Layout, Cards, Drives and Updates.

### Look

Everything about how the dashboard looks.

- Themes: there are ten ready-made looks: Pastel Night, Violet Glow, Arctic Slate, City Lights, Retro Amber, Deep Teal, Frosted Wave, Mica Blue, Crystal Glass (light, clear glass with raised edges and dark text) and Crystal Night (the same glass in a dark version). Several are based on well-known color schemes (Catppuccin Mocha, Dracula, Nord, Tokyo Night, Gruvbox and Solarized Dark). A theme sets the colors, the glass, the shapes, the text style, the background picture and the panel itself. A look saved with an older theme keeps working until another theme is chosen.
- Day and Night: the dashboard switches to one theme by day and another at night, for everyone who has it open. It uses sunrise and sunset at the weather city (or two fixed times). The switch is made by the control panel, so it works while no browser is open. Names, the logo, motion and quick launch are never changed by it, and a theme you choose yourself stays until the next switch. Its settings are in `homepage-config/.panel-schedule.json`.
- Motion, Icons and Greeting: Off, Subtle or Lively motion; every icon on the same glass tile or shown as it is; the name at the top and which name it shows; and which cards are in the quick launch row (the most visited services, or up to 12 that you choose, or off).
- Your own themes: *Make a Theme from These Settings* saves the current look under *Your Themes*, optionally with the background, the layout and the list of cards. Choosing one asks first, and Undo reverts the layout and cards in one step. A theme never overwrites a card's address or widget settings. Custom themes live in `homepage-config/.panel-themes.json`, so a backup of that folder keeps them.
- Shape and colors: sliders for rounded corners, glass clarity and blur, the shine and the raised edge of the glass, a glow around the cards, and how dark the layer over the picture is, with a live preview. A Light or Dark choice and a text style (Apple, Windows, monospace or rounded, using fonts already on the device) are there too. You can set one color for everything or a different color for a single card, tile, bookmark or group label.
- Names and Logo: your own names for the server and the drives, and a logo at the top left.
- Time Zone and City: the install finds both from your internet connection. This card changes the clock's time zone and the weather city.
- Background Picture: pick a picture and set how blurry, bright and colorful it's. The installer stores all ten theme pictures (kept in the `theme-pictures` folder of the repository) before Homepage starts, so picking a theme doesn't restart the dashboard. If one is missing, the dashboard loads it from its web address until `sudo homelab-setup refresh` stores them all (that restarts Homepage once). Choosing a theme never restarts the dashboard.

Nothing is saved until you press Save, so you can try things freely.

![The Look screen of the Customize panel](images/panel-look.png)

### Layout

Each box is a tab of the dashboard. Drag groups to change their order or move them to another tab, and set each group to show its cards in a row.

> **Photo to add:** A screenshot of the Layout screen with its tabs and groups. Save it in `docs/images/` as `panel-layout.png`.

### Cards

The cards of the dashboard. Add a card for any web page, change names, descriptions and icons, move cards between groups, reorder them or remove them.

Some cards read live numbers from their service with a key or a password: an API key for Tailscale, Speedtest Tracker, Portainer, Immich and Nextcloud, and a password for AdGuard Home, Beszel and FileBrowser. On those cards the *Change* window has a box for it right under *Web address*.

- The panel never shows a saved key. The box starts empty and says whether one is saved.
- Type or paste a new key and press *Save* to replace the old one. Leave the box empty to keep the saved one. *Show what I type* lets you check what you pasted before you save.
- The card uses the new key the next time it refreshes. The panel doesn't test the key. If the card shows an error afterwards, check the key in the service, or run `sudo homelab-setup fill`, which tests a key before it saves it.
- *Undo* puts the old key back.
- The Upload card keeps its own copy of the Immich key (see [Drives](#drives)), so changing it there is a separate step.

Cards you add yourself and the number cards that HomeLab fills in have no key box.

> **Photo to add:** Two screenshots: the Cards screen, and the *Change* window of a card with a key box. Leave the key box empty, or take the picture before you paste a key. Save them in `docs/images/` as `panel-cards.png` and `panel-card-change.png`.

The number cards and the calendar that HomeLab fills in (Preview, Music Library, Library Totals, Storage, Backup & Updates, Folder Sizes and Calendar) are listed too, marked *Filled in by HomeLab*. You can rename, restyle, move and hide them. *Add From HomeLab's List* brings back a hidden card and offers extra single-number cards (Photos, Videos, Songs, Updates Waiting, Pool Health and more). *Put HomeLab's Cards Back* resets every default card and keeps your own. The first change marks the block in `services.yaml` as `customized`, so `sudo homelab-setup upgrade` stops rewriting it, and cards added in later versions appear in *Add From HomeLab's List*.

### Drives

A picture of the storage, in the style of TrueNAS.

- The Main pool and Backup pool boxes, with a tile for each drive showing its name, size, how full it's, its temperature, its health and whether it's asleep.
- Drives that are connected but not in a pool wait at the top. Drag one into a pool to add it, or select it to see its details and buttons: the model, serial number, file system and how much of it's used. The panel looks at the drive read-only for a moment to count, and changes nothing on it. A USB stick or memory card has no health report and no motor, so its card says "Not Reported" and "Always On".
- Configure Drives builds ready-made setups: a plain pool, a mirror, SnapRAID, ZFS and RAID.
- Taking a drive out copies its files to the other drives first. Every action that could erase something asks for confirmation.
- Fix Drives mounts the pools again after a power loss or a disconnection, checks that Immich and Nextcloud can find their files and starts the containers. If a drive is gone, a warning card keeps those two stopped and offers **Restore From Backup** or **Start on Empty Folders** ([details](maintenance.md#if-a-data-drive-fails-or-goes-missing)). A restore shows a progress bar and a **Cancel** button that removes what it copied. Fix Drives also makes sure the music folder is writable, so song uploads work.

![The Drives screen of the Customize panel](images/panel-drives.png)

Two more cards sit under the drives.

The Upload card sends photos and videos straight to Immich, and songs straight to the music folder, from any device. Photos go through an Immich key that you paste once, and the panel keeps it in a private file on the server. Songs are saved as they are, and a song with the same name is never replaced. Navidrome picks up new songs at its next scan, within the hour.

![The Upload card](images/panel-upload.png)

The Backups card is a task list like the one in TrueNAS. A task copies a folder somewhere on a schedule, and every run keeps a version that can be restored. The destination can be a drive, another computer over SSH, or the cloud (Backblaze B2, S3, Google Drive and others). You can run a task right away, and browse and restore its versions.

For a backup kept on a drive of this computer there is also a **Download** button. It opens a small browser of the backup where you can save a single file, or a whole folder as a `.zip`, to the device you are using. That's the way out when nothing else works. The schedule can be every hour, every day, every few days (2 to 30), every week or every month. The nightly backup of the files is the first task in the list. Its **Edit** window has the same schedule choices and a setting for how many days deleted or replaced files are kept (30 by default).

![The Backups card with a nightly task](images/panel-backups.png)

### Updates

One page for everything that's waiting to be updated, with a button for each.

- Containers: shows which services have a newer version. **Check Now** looks again. **Update Containers** dumps the databases first and then updates the services one by one. If an upload or a backup is running, nothing is updated. The row says why and offers **Update Anyway**, but it's better to wait and press **Update Containers** again.
- System: the packages from Ubuntu or Mint. **Update System** installs them, which can take several minutes. Ubuntu sometimes holds a few packages back. The screen says how many, and they don't count as waiting. `sudo apt full-upgrade` installs them anyway.
- Restart: shown only when a system update needs it. **Restart Machine** asks first.

A loading bar fills as an update runs, with the log under it. For containers it counts the steps, and for the system update it counts the packages, using what the update tools actually print. **Check Now** and **Restart Machine** can't tell how far along they are, so their bar just pulses. The update carries on if you close the page.

![The Updates screen](images/panel-updates.png)

### The web terminal

Below the panel is a terminal in the browser. It's a shell on the server, signed in as the server user, so you can run commands from a phone. It uses the same password as the panel.

![The web terminal showing the homelab screen](images/panel-terminal.png)

## Keeping it simple

`homelab simple on` hides the small description text under every card name, for a calmer page. `homelab simple off` brings it back.

## Where the files are

| What | Where |
| :--- | :--- |
| The dashboard's settings, cards, widgets and styles | [`homepage-config/`](../homepage-config/) |
| The control panel's web page | [`panel/`](../panel/) |
| The program behind the panel | [`scripts/homelab-panel`](../scripts/homelab-panel) |
| The Homepage stack | [`stacks/homepage.yaml`](../stacks/homepage.yaml) |
