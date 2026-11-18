# Music extras: Last.fm, ListenBrainz, AudioMuse-AI and NaviList

Navidrome plays whatever is in the music folder, and for most people that's enough. These four extras make it smarter. None of them is installed by default, since not everyone wants them. Each section below says what you get, what it needs, how to turn it on and how to take it off again. They don't depend on each other, so pick whichever you like.

## Contents

- [Before you start](#before-you-start)
- [What each one gives you](#what-each-one-gives-you)
- [Last.fm: similar songs](#lastfm-similar-songs)
- [ListenBrainz: listening history](#listenbrainz-listening-history)
- [AudioMuse-AI: songs that sound alike](#audiomuse-ai-songs-that-sound-alike)
- [NaviList: playlists from listening history](#navilist-playlists-from-listening-history)
- [If something doesn't work](#if-something-doesnt-work)

## Before you start

Navidrome is installed with the lab and already has its card on the dashboard. Downtify (see [the services](services.md#downtify)) saves songs into `/mnt/storage/music`, and Navidrome finds them within the hour, or right away if you press the scan button in Navidrome. The extras all need Navidrome, and they start working as soon as it has some songs.

You set up each extra from a terminal on the server with `sudo homelab-setup` and the name of the extra. Every command explains what it will do before it changes anything. The installer never saves the admin password. The keys and tokens you enter are kept in a root-only file, and `sudo homelab-setup secrets` shows them again.

## What each one gives you

| Extra | What you get | What it needs | What it costs |
| :--- | :--- | :--- | :--- |
| Last.fm key | **Instant Mix** in Navidrome: a queue of similar songs and artists | A free Last.fm account | Nothing runs. Two keys are stored |
| ListenBrainz | Navidrome reports what you play, and ListenBrainz builds recommendations from it | A free ListenBrainz account | Nothing runs on the server |
| AudioMuse-AI | Instant Mix based on how songs actually sound, including songs with no tags | A processor with AVX2, and 8 GB of memory is recommended | Three containers, a few GB to download and hours of analysis at first |
| NaviList | Navidrome playlists made from ListenBrainz (Weekly Jams, Weekly Exploration, Daily Jams) and Last.fm charts | Your ListenBrainz user name and token, and optionally Last.fm | One small container on port 8200 |

## Last.fm: similar songs

Last.fm knows which songs and artists people play together. With a free Last.fm key, Navidrome can use that for **Instant Mix**.

1. Sign in (or sign up) at [last.fm](https://www.last.fm).
1. Open [last.fm/api/account/create](https://www.last.fm/api/account/create). Enter an application name (for example `Home Lab`) and a short description. The other fields can stay empty.
1. The next page shows an **API key** and a **Shared secret**. Keep that page open.
1. On the server, run:
```bash
   sudo homelab-setup lastfm
```

1. Paste the API key, then the shared secret. Each is 32 letters and digits. The installer checks that they look right, saves them and deploys Navidrome again with them, which takes about a minute.
1. In Navidrome, open the menu of a song and choose **Instant Mix**.

If you also want to send played songs to Last.fm, click your user name in Navidrome, open **Personal** and link your Last.fm account there.

To take it off, run `sudo homelab-setup lastfm remove`. Navidrome is deployed again without the keys.

## ListenBrainz: listening history

ListenBrainz is a free, open service that records what you listen to and recommends music from it. Navidrome can report each song you play (a "scrobble"). Nothing is installed for this. It's a setting inside Navidrome, and it's also what [NaviList](#navilist-playlists-from-listening-history) reads.

1. Sign up at [listenbrainz.org](https://listenbrainz.org).
1. Open [listenbrainz.org/settings](https://listenbrainz.org/settings/) and copy the **User token**. It looks like `1b2c3d4e-0000-1111-2222-333344445555`. Your user name is the name you sign in with.
1. In Navidrome, click your user name at the top right and open **Personal**.
1. Switch on **Scrobble to ListenBrainz** and paste the token.
1. Play music as usual. ListenBrainz needs some listens before it can recommend anything, so the first playlists can take a few days.

To stop, switch the same setting off. The token is only a key to your ListenBrainz account, and you can make a new one on the settings page at any time.

## AudioMuse-AI: songs that sound alike

AudioMuse-AI listens to every song once and works out which ones sound alike. After that, Instant Mix builds its queue from songs that sound like the one you picked, and it works for songs with no tags at all. It's the one heavy extra, so read the requirements first.

Requirements:

- A processor with AVX2 (almost every processor since 2013). Without it, AudioMuse-AI won't start, and the installer says so before it changes anything.
- 8 GB of memory is recommended. On a smaller machine the installer shows a warning, and the limits below help.
- Navidrome must be running, and port 8100 must be free.

Steps:

1. On the server, run:
```bash
   sudo homelab-setup audiomuse
```

1. Read what it says it will do (three containers, a small Navidrome login for it, a plugin for Navidrome, and a worker limited in memory and processor cores) and answer `y`. The first download is a few GB, and Navidrome restarts once.
1. When it says AudioMuse-AI is set up, open its page (`http://SERVER-ADDRESS:8100`) and log in with the admin name. The password is `AUDIOMUSE_PASSWORD` in `sudo homelab-setup secrets`.
1. On the main page (**Analysis and Clustering**), press **Start Analysis**. You can close the page, and the analysis carries on. A few thousand songs take hours, and the processor stays busy meanwhile.
1. When it's done, open a song's menu in Navidrome and choose **Instant Mix**.

Looking after it:

| Command | What it does |
| :--- | :--- |
| `sudo homelab-setup audiomuse status` | Shows the containers and how far the analysis is |
| `sudo homelab-setup audiomuse pause` | Stops the worker, which frees its memory and processor (the web page and the database stay) |
| `sudo homelab-setup audiomuse resume` | Starts the worker again |
| `sudo homelab-setup audiomuse memory` | Shows the worker's memory limit (with suggestions for 8 GB and 16 GB machines) and how to change it |
| `sudo homelab-setup audiomuse remove` | Removes the containers. Navidrome keeps working |

## NaviList: playlists from listening history

NaviList turns ListenBrainz recommendations (Weekly Jams, Weekly Exploration, Daily Jams) and Last.fm charts into Navidrome playlists. It only uses songs that are already in the library and never downloads anything. It checks Navidrome every 5 minutes, and ListenBrainz and Last.fm every 30.

What you need first:

- A ListenBrainz account, with the user name and the token (see [ListenBrainz](#listenbrainz-listening-history)).
- Optional, for the Last.fm charts: the Last.fm key from [the Last.fm section](#lastfm-similar-songs) (`sudo homelab-setup lastfm`) and your Last.fm user name. Without the key, the Last.fm charts are left out, and you can run the command again later.
- Navidrome must be running, and port 8200 must be free.

Steps:

1. On the server, run:
```bash
   sudo homelab-setup navilist
```

1. Read what it says it will do (one small container and a small Navidrome login for it) and answer `y`.
1. Type your ListenBrainz user name, then paste the token. Press Enter on a question to keep what is already saved. If a Last.fm key is saved, it also asks for your Last.fm user name, and Enter skips the Last.fm charts.
1. The installer starts the container and subscribes to the playlists that already exist. Playlists that don't exist yet (ListenBrainz only makes them after it has some listening history) are listed as "not there yet". That's normal.
1. One last step, done once: Navidrome must report your played songs to ListenBrainz, or there is nothing to recommend from. In Navidrome, click your user name, open **Personal**, switch on **Scrobble to ListenBrainz** and paste the same token. If you use Last.fm, link that account there too.
1. Play music as usual. In a few days the playlists appear in Navidrome by themselves.

NaviList has its own page at `http://SERVER-ADDRESS:8200`, where you can pick other playlists.

Looking after it:

| Command | What it does |
| :--- | :--- |
| `sudo homelab-setup navilist status` | Shows the container, which accounts are used and which playlists are subscribed |
| `sudo homelab-setup navilist subscribe` | Tries again to subscribe to the playlists that weren't there yet |
| `sudo homelab-setup navilist` | Run it again to change the names or the token |
| `sudo homelab-setup navilist remove` | Removes the container. The playlists it made stay in Navidrome |

## If something doesn't work

- If it says "This machine has no Navidrome": a lab built by hand, outside this installer, is only read, so the installer never adds Navidrome there. On a lab the installer built, run `sudo homelab-setup refresh` and try again.
- If a command asks for the admin password: a few steps (making the small Navidrome logins) need the password you chose at the start of the install. It's used for that run only and isn't saved.
- If port 8100 or 8200 is already used, the message names the container that has it. Nothing was changed.
- If a playlist is missing: ListenBrainz only makes playlists after it has some listening history. Wait a few days, then run `sudo homelab-setup navilist subscribe`.
- If Instant Mix is empty, it needs Last.fm (see above) or a finished AudioMuse-AI analysis, and the song has to be known to them.
- Every extra has a `remove` word (for ListenBrainz it's a switch in Navidrome), and removing one never deletes any songs.

More about the music services is in [Services](services.md#music). General problems are in [Troubleshooting](troubleshooting.md).



