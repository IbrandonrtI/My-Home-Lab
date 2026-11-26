

def cmd_requests(rest):
    """`requests`: set up Seerr, Radarr, Sonarr, Prowlarr and qBittorrent so people can ask for a movie or show. Also handles status and remove."""
    load_all()
    if Mode.existing:
        say("This machine was built by hand, so the installer only reads it. The request apps are not set up here.")
        return
    if not State.exists():
        raise Abort("The installer has not run on this machine yet. Run `sudo homelab-setup install`.")
    word = rest[0] if rest else ""
    if word == "status":
        return requests_status()
    if word == "remove":
        return requests_remove()
    if rest:
        raise Abort("Unknown word '%s'. Use: homelab-setup requests   or   requests status | remove" % word)
    if not jellyfin_wanted():
        raise Abort("The request apps work together with Jellyfin, and this machine has no Jellyfin of its own. Nothing was changed.")
    if not State.data.get("requests"):
        for app in REQUESTS_PARTS:
            other = port_taken_by(PORTS[app], mine=STACKS["requests"][1])
            if other:
                raise Abort("Port %d is already used by the container %s, and %s needs it for its web page. Nothing was changed." % (PORTS[app], other, REQUESTS_LABELS[app]))
    say("This adds the request apps, roughly 1 to 1.5 GB of memory in total:\n"
        "  - Seerr: where you search for a movie or show and ask for it. Everyone signs in with their Jellyfin login.\n"
        "  - Radarr and Sonarr: keep the list of movies and shows that were asked for, and put finished files in the Jellyfin folders.\n"
        "  - Prowlarr: keeps the indexers in one place and sends them to Radarr and Sonarr.\n"
        "  - qBittorrent: the download client. Radarr and Sonarr are linked to it, and its downloads go to %s.\n"
        "The installer links the apps to each other and gives each one the admin login. It adds no download sources and no indexers; "
        "that part is up to you." % DOWNLOADS_FOLDER)
    if State.data.get("requests"):
        say("The request apps are already set up; this checks them again and finishes anything that is missing.")
    elif not yesno("Set up the request apps now?", True):
        say("Nothing was changed.")
        return
    State.data["requests"] = True
    State.save()
    cmd_refresh()
    done = State.data.get("requests_linked") or {}
    if not State.data.get("requests_stack") or not all(done.get(a) for a in REQUESTS_PARTS):
        warn("The setup did not finish. Read the message above, then run `sudo homelab-setup refresh` to continue.")
        return
    good("The request apps are set up.")
    say("Open Seerr at %s and sign in with your Jellyfin login. Radarr is at %s, Sonarr at %s, Prowlarr at %s and qBittorrent at %s; each uses the admin login.\n"
        "Nothing will download until you add a source of your own in Prowlarr (Indexers); Prowlarr passes it on to Radarr and Sonarr."
        % (url("seerr"), url("radarr"), url("sonarr"), url("prowlarr"), url("qbittorrent")))


def requests_status():
    if not requests_wanted():
        say("The request apps are not set up on this machine. `sudo homelab-setup requests` sets them up.")
        return
    up = containers_running()
    done = State.data.get("requests_linked") or {}
    for app in REQUESTS_PARTS:
        out("      %-14s %-12s %-10s %s" % (REQUESTS_LABELS[app], "running" if app in up else "not running", "linked" if done.get(app) else "not linked", url(app)))


def requests_remove():
    """`requests remove`: remove the five containers. Their settings and the downloads folder are kept."""
    if not requests_wanted():
        say("The request apps are not set up. Nothing to remove.")
        return
    if Opt.dry:
        say("This is a dry run: it would remove the five request containers. Nothing was changed.")
        return
    if not yesno("Remove Seerr, Radarr, Sonarr, Prowlarr and qBittorrent (their settings and the downloads folder stay on the drive)?", False):
        say("Nothing was changed.")
        return
    if not Portainer.delete("requests"):
        raise Abort("Portainer could not remove the stack 'requests'. Remove it in Portainer (Stacks), then run this again.")
    for k in ("requests", "requests_stack", "requests_linked"):
        State.data.pop(k, None)
    State.save()
    for app in REQUESTS_PARTS:
        forget_card(app)
    good("The request apps are removed.")
    say("Their settings are still in %s/requests and the downloads in %s. To free the space: sudo rm -rf %s/requests" % (Ctx.home, DOWNLOADS_FOLDER, Ctx.home))
    cmd_refresh()
