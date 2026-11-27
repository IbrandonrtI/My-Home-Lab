def share_addresses():
    """Where File Explorer finds the shares: the local address and, when Tailscale is connected, the Tailscale name."""
    found = ["\\\\%s" % (Ctx.lan or Ctx.hostname)]
    if Ctx.fqdn:
        found.append("\\\\%s" % Ctx.fqdn)
    return found


def share_how_to_open():
    first = share_addresses()[0]
    say("In Windows open File Explorer and type %s\\movies in the address bar (or right-click This PC, Map network drive, and use that address). "
        "When it asks for a login, use the user name %s and the admin password. Tick the box to remember it. "
        "Away from home, use %s instead; the PC must be connected to Tailscale." % (first, Ctx.user, " or ".join(share_addresses()[1:]) or "the Tailscale name of this machine"))


def cmd_share(rest):
    """`share`: share the movies and shows folders with Windows. Also handles status, password and remove."""
    load_all()
    if Mode.existing:
        say("This machine was built by hand, so the installer only reads it. The folders are not shared here.")
        return
    if not State.exists():
        raise Abort("The installer has not run on this machine yet. Run `sudo homelab-setup install`.")
    word = rest[0] if rest else ""
    if word == "status":
        return share_status()
    if word == "remove":
        return share_remove()
    if word == "password":
        return share_password()
    if rest:
        raise Abort("Unknown word '%s'. Use: homelab-setup share   or   share status | password | remove" % word)
    say("This shares the movies and shows folders (the Jellyfin library) with Windows, so they open in File Explorer like normal folders. "
        "You can copy, rename and delete files in them from Windows. Files stay owned by %s, so the apps keep working. "
        "Only devices on your home network and on Tailscale can connect. The login is the user name %s with the admin password; "
        "Samba keeps its own scrambled copy of that password." % (Ctx.user, Ctx.user))
    if State.data.get("share"):
        say("The folders are already shared; this checks them again and finishes anything that is missing.")
    elif not yesno("Share the folders now?", True):
        say("Nothing was changed.")
        return
    State.data["share"] = True
    State.save()
    cmd_refresh()
    if not all(BY_ID[s].probe() == "done" for s in ("share-package", "share-folders", "share-config", "share-login")):
        warn("The setup did not finish. Read the message above, then run `sudo homelab-setup refresh` to continue.")
        return
    good("The folders are shared.")
    share_how_to_open()


def share_status():
    if not share_wanted():
        say("The folders are not shared. `sudo homelab-setup share` shares them.")
        return
    out("      %-14s %s" % ("Samba", "running" if share_running() else "not running"))
    out("      %-14s %s" % ("Login", "set for %s" % Ctx.user if State.data.get("share_login") == Ctx.user else "not set"))
    for name, path in SHARES:
        out("      %-14s %s" % (name, path))
    share_how_to_open()


def share_password():
    """`share password`: set the Windows login to the current admin password again, after the admin password was changed."""
    if not share_wanted():
        say("The folders are not shared, so there is no login to change. `sudo homelab-setup share` shares them.")
        return
    if Opt.dry:
        say("This is a dry run: it would set the Samba login of %s to the admin password. Nothing was changed." % Ctx.user)
        return
    why = share_set_login(need_password("to set the login for the shared folders"))
    if why:
        raise Abort(why)
    State.data["share_login"] = Ctx.user
    State.save()
    good("The login for the shared folders now uses the admin password.")


def share_remove():
    """`share remove`: stop sharing the folders. The files, the folders and the Samba package stay."""
    if not share_wanted():
        say("The folders are not shared. Nothing to remove.")
        return
    if Opt.dry:
        say("This is a dry run: it would stop sharing the two folders and remove the login. Nothing was changed.")
        return
    if not yesno("Stop sharing the movies and shows folders with Windows (the files stay where they are)?", False):
        say("Nothing was changed.")
        return
    main = read_file(P(SHARE_MAIN_CONF))
    write_file(P(SHARE_MAIN_CONF), "\n".join(l for l in main.split("\n") if l.strip() != SHARE_INCLUDE), 0o644)
    try:
        os.remove(P(SHARE_CONF))
    except OSError:
        pass
    run(["smbpasswd", "-x", Ctx.user])
    act(["systemctl", "restart", "smbd"])
    for k in ("share", "share_login"):
        State.data.pop(k, None)
    State.save()
    good("The folders are no longer shared. Samba itself is still installed; to remove it too: sudo apt remove samba")
