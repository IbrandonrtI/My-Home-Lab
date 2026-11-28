# Edit mode: live test on the server

This file is the full task for a Claude Code session that runs on the lab server (`homelab`, user `brandon`). The session tests the Edit button on the real dashboard in a headless browser and writes a report. It does not change any repository file. Brandon takes the report back to be fixed.

## Start it (Brandon)

```bash
cd ~/My-Home-Lab && git pull
sudo homelab-setup refresh
tmux new -s edittest
read -rs HLP_PW; export HLP_PW; echo
claude "Read ~/My-Home-Lab/dev/edit-mode-live-test.md and do the task in it."
```

Type the control panel password at the `read` prompt. It is kept in the shell variable `HLP_PW` only and is never written to a file. Leave the tmux session with `Ctrl+B`, then `D`. Come back with `tmux attach -t edittest`. When the session says it is done, the report is in `~/edit-mode-report.md` and the screenshots are in `~/edit-mode-shots/`.

## Rules for the session

- Do not edit anything in `~/My-Home-Lab`. Only read it. Only write the report, the screenshots, the test script and the backup folder named below.
- Never print `HLP_PW`, never write it to a file, never pass it on a command line. Read it in the test script from the environment.
- Before the first Save, back up the live dashboard files: copy `services.yaml`, `settings.yaml`, `custom.css`, `custom.js` and `bookmarks.yaml` from `~/homepage-config` to `~/edit-test-backup/` (keep the file modes). At the end, put the arrangement back to how it was and show that `diff -r` against the backup has no difference in `services.yaml` and `settings.yaml`. If a restore is needed, copy the files back, or use Undo in the Customize panel. After copying files back by hand, run `docker restart homepage`, because Homepage keeps its own copy of the card list.
- Test only through the browser, as a person would. Do not call the panel's API directly, except to read the files and the state for checking.
- A test that cannot be run is reported as BLOCKED with the reason. Never mark a test PASS without having checked it.
- If something looks dangerous (a card disappears, a file looks cut off), stop, restore the backup, and report it first.

## Setup

1. Find the dashboard address the way a browser sees it: the Tailscale name and port that serves the Homepage (`tailscale serve status`), and the local port (`docker ps`). Use the Tailscale name for the tests.
2. Check that the files on the server are the new ones: `~/homepage-config/custom.js` must contain `homelab edit`, and `~/homepage-config/custom.css` must contain `#hl-editbtn`. If not, report it as the first finding and stop.
3. Use Python Playwright with Chromium (`pip install playwright --break-system-packages` and `playwright install chromium`, or whatever works here). Use one script, `~/edit-test/run.py`, with one function per test below, so the tests can be run again.
4. Window size for the main run: 1440 by 900. Take a screenshot at every step that matters and name it with the test number.

## Tests

For each one write PASS, FAIL or BLOCKED, what was done, and what was seen.

**A. The button**

- **1.** Open the Home tab. The Edit button is in the tab bar, after the tabs, bell, search and icons. The "All services are healthy" pill is not there.
- **2.** Open the Stats tab, then the Links tab, then Customize. Say on which tabs the Edit button shows (it should show on tabs that have groups of cards).
- **3.** Resize the window to 800, 700 and 600 wide. The button is gone at 700 and below.
- **4.** Scroll the Home tab to the bottom and back. Say if the Edit button stays in the bar at the top (it scrolls away with the bar) and that nothing else sits where it should be.

**B. Starting to edit**

- **5.** Press Edit. The login box appears over the page. Cancel closes it and nothing changes.
- **6.** Press Edit again, enter the password, press Enter. The button now says Editing, a bar with Save and Cancel shows at the bottom right of the window, and the handles show on cards and groups.
- **7.** Count the handles. The Navidrome group, the Calendar group, and the Customize, Edit Links and Terminal cards have none. Name every card and group that has a handle and every one that has not.
- **8.** Scroll the page down and up while editing. The Save and Cancel bar stays at the bottom right every time. Give its measured position at the top, middle and end of the page.
- **9.** While editing, the tab buttons are locked, clicking a card does not open its service, and the Jellyfin library and the music player do not react to the mouse.

**C. Moving**

- **10.** Drag one card into another group and back (do not save). Save stays off until something changes, and turns on after a move.
- **11.** Drag Jellyfin and Navidrome so they swap places. Say what the page looks like during and after the drag. Look for broken layout, overlapping cards, the Jellyfin library frame in the wrong place, red "Service Unavailable" boxes that were not there before, and the music player restarting.
- **12.** Count how many times the Navidrome player frame and the Jellyfin frame load again during one drag. Report the numbers.
- **13.** Drag a group (for example Monitoring & Management) to another place. Say what happens when it is dropped past the last group.
- **14.** Use the keyboard: focus a handle and press the arrow keys. The card or group moves one place at a time.
- **15.** Drag a card to near the top and bottom edge of the window. The page scrolls while dragging.
- **16.** Press Cancel. It asks once more (Discard changes?). Press it again. The page returns to its first arrangement and no file changed (`diff` against the backup).

**D. Saving**

- **17.** Swap Jellyfin and Navidrome again and press Save. The page reloads with the new order. Check `services.yaml`: the order changed and nothing else in the file did (compare the two files with `diff`). Check that the cards keep their widgets, ids and every other line.
- **18.** Open the Customize panel, Cards. The new order shows there, and Undo is offered. Do not press Undo yet.
- **19.** Run `sudo homelab-setup refresh`. Ask Brandon to type the sudo password if it is needed. After it, the saved order is still in place (the installer must not put the cards back).
- **20.** Move a group and save. Check the order of the groups in `settings.yaml` for the Home tab.
- **21.** Use Undo in the panel. The group order comes back in one step.
- **22.** Put everything back to how it was in the backup (swap Jellyfin and Navidrome back through Edit mode, then save). Show that `diff` against the backup has no difference in `services.yaml` and `settings.yaml`.

**E. Errors and edge cases**

- **23.** List the browser console errors and warnings from the whole run, with the page and the step. Separate the ones that also appear without Edit mode (open the page, do nothing, read the console) from the new ones.
- **24.** Wait until the panel login has run out (or clear the panel cookie), press Save. The login box comes back. The first password typed is accepted (no "The request is not valid."), and the save then goes through. Try it at least five times, because the old fault did not show every time.
- **25.** Press Save while the cards in the file differ from the page (change `services.yaml` by hand in the test by adding a harmless blank card through the panel in a second browser context, then Save in the first one). The save is refused with a clear message and nothing is lost.
- **26.** Reload the page in the middle of an edit with changes made. The browser asks before leaving.
- **27.** Load the page at 1024 and 768 wide, press Edit, move a card, cancel. Say if anything breaks.

**F. Added after the first live run** (the first run found that cards with the same name on Home and on Stats were mixed up by Save)

- **28.** Save on the Stats tab. Open Stats, press Edit, drag one card to a new place in its group, Save. Then compare `services.yaml` with the backup: only that card moved, and the cards on Home with the same names (Jellyfin, Downtify, Immich, Nextcloud) are still in their Home groups with their ids. Then put it back.
- **29.** Save a group move on Home. Drag one group to another place and Save. `services.yaml` must show no difference against the backup, and the group order for Home in `settings.yaml` changed. Then put it back.
- **30.** Save a card that has the same name as a card on Stats. Move Jellyfin (Home) into another group on Home and Save. The Stats copy (id `stat-jellyfin`) stays in Library Totals. Then put it back.
- **31.** Cancelled sign-in. With no panel login: press Edit, press Cancel on the login box, press Edit again. The login box comes back at once.
- **32.** Hold the pointer still. Start dragging a card, move to the bottom edge of the window and stop moving the mouse for two seconds. The page keeps scrolling. Let go, and it stops.
- **33.** Narrow windows. At 701, 768, 800 and 860 px wide, with and without Edit mode, the page has no sideways scroll and the whole Edit button is inside the window (on a very narrow window it may sit on a second row).
- **34.** Drop on the middle. In a group with several cards, drag a card exactly onto the middle of another one. It takes that card's place. Do this in a one-column group and in Media & Entertainment, where the cards sit side by side, and in both directions (a later card onto an earlier one, and the reverse).
- **35.** After a save, the page waits for Homepage. Move Jellyfin into Files & Photos and Save. Record the network requests of the reloaded page: there is no 403 or 400 for Jellyfin's widget or site monitor, and the page never shows Jellyfin in its old group. Then put it back.

## Report

Write `~/edit-mode-report.md` with:

1. A short summary: how many tests passed, failed and were blocked, and the three most important findings.
2. A table of all tests with the result.
3. For every FAIL and every odd thing you saw: the steps, what was expected, what happened, the screenshot name, the console message if any, and your guess at the cause in one line. Do not fix anything.
4. The dashboard address, the window size, the browser version and the commit of `~/My-Home-Lab` (`git log -1 --oneline`).
5. The result of the final `diff` against the backup.

Finish by saying where the report and the screenshots are.
