# Folder sharing: the movies, shows and downloads folders as Windows network folders (Samba), so File Explorer can open them.
# Installed only by `homelab-setup share`. Only the home network and Tailscale may connect, and the login is the lab user's name with the admin password.

SHARES = (("movies", "/mnt/storage/movies"), ("shows", "/mnt/storage/shows"), ("downloads", DOWNLOADS_FOLDER))
SHARE_CONF = "/etc/samba/homelab.conf"
SHARE_MAIN_CONF = "/etc/samba/smb.conf"
SHARE_INCLUDE = "include = " + SHARE_CONF
SHARE_ALLOWED = "127.0.0.1 ::1 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12 100.64.0.0/10 fd7a:115c:a1e0::/48"


def share_wanted():
    return bool(State.data.get("share")) and not Mode.existing


def share_config_text():
    """The Samba file for the three folders. Every file is created as the lab user, so Jellyfin, Radarr, Sonarr and qBittorrent can use what Windows adds."""
    out_lines = ["# Written by homelab-setup (sudo homelab-setup share). Changes made here are overwritten; remove the shares with: sudo homelab-setup share remove", ""]
    for name, path in SHARES:
        out_lines += ["[%s]" % name, "   path = %s" % path, "   browseable = yes", "   read only = no", "   valid users = %s" % Ctx.user,
                      "   force user = %s" % Ctx.user, "   force group = %s" % (grp_name(Ctx.gid) or Ctx.user), "   create mask = 0664", "   directory mask = 0775",
                      "   hosts allow = %s" % SHARE_ALLOWED, "   hosts deny = ALL", ""]
    return "\n".join(out_lines)


def grp_name(gid):
    try:
        return grp.getgrgid(gid).gr_name
    except (KeyError, OSError):
        return ""


def share_include_present():
    return any(l.strip() == SHARE_INCLUDE for l in read_file(P(SHARE_MAIN_CONF)).split("\n"))


def share_running():
    return run(["systemctl", "is-active", "smbd"])[1].strip() == "active"


def share_folders_not_ready():
    return [p for _, p in SHARES if not os.path.isdir(P(p)) or os.stat(P(p)).st_uid != Ctx.uid]


@step
class SharePackage(Step):
    id, group = "share-package", "Services"
    title = "Samba, the program that shares folders with Windows"
    needs = ("packages",)

    def applies(self):
        return share_wanted()

    def probe(self):
        return "done" if pkg_installed("samba") else "todo"

    def run(self):
        apt_install(["samba"])


@step
class ShareFolders(Step):
    id, group = "share-folders", "Services"
    title = "The movies, shows and downloads folders exist and belong to the lab user"
    needs = ("folders",)

    def applies(self):
        return share_wanted()

    def probe(self):
        return "done" if not share_folders_not_ready() else "todo"

    def run(self):
        if Opt.dry:
            out("      would create the missing folders and make them belong to %s" % Ctx.user)
            return
        for _, path in SHARES:
            make_folder(P(path))
        for path in share_folders_not_ready():
            chown(P(path), Ctx.uid, Ctx.gid)


@step
class ShareConfig(Step):
    id, group = "share-config", "Services"
    title = "Share the movies, shows and downloads folders (home network and Tailscale only)"
    needs = ("share-package", "share-folders")

    def applies(self):
        return share_wanted()

    def probe(self):
        same = read_file(P(SHARE_CONF)) == share_config_text()
        return "done" if same and share_include_present() and share_running() else "todo"

    def run(self):
        if Opt.dry:
            out("      would write %s, add it to %s and start Samba" % (SHARE_CONF, SHARE_MAIN_CONF))
            return
        previous = read_file(P(SHARE_CONF))
        write_file(P(SHARE_CONF), share_config_text(), 0o644)
        rc, txt = run(["testparm", "-s", P(SHARE_CONF)])
        if rc != 0:
            if previous:
                write_file(P(SHARE_CONF), previous, 0o644)
            else:
                os.remove(P(SHARE_CONF))
            raise Abort("Samba does not accept the share settings (%s). Nothing was changed." % txt.strip()[-200:])
        if not share_include_present():
            main = read_file(P(SHARE_MAIN_CONF))
            write_file(P(SHARE_MAIN_CONF), main + ("" if main.endswith("\n") or not main else "\n") + "\n" + SHARE_INCLUDE + "\n", 0o644)
        act(["systemctl", "enable", "--now", "smbd", "nmbd"])
        if previous != share_config_text():
            act(["systemctl", "restart", "smbd"])
        if not share_running():
            raise Abort("Samba does not run. Look at it with:  sudo systemctl status smbd")


def share_set_login(pw):
    """Give the lab user a Samba login with the admin password. Samba keeps its own scrambled copy. Returns None when it worked, else a short reason."""
    rc, txt = run(["smbpasswd", "-a", "-s", Ctx.user], input_text="%s\n%s\n" % (pw, pw), timeout=60)
    return None if rc == 0 else "Samba did not accept the login (%s)" % txt.strip()[-150:]


@step
class ShareLogin(Step):
    id, group = "share-login", "Services"
    title = "The Windows login for the shared folders (the lab user's name and the admin password)"
    needs = ("share-package",)

    def applies(self):
        return share_wanted()

    def probe(self):
        return "done" if State.data.get("share_login") == Ctx.user else "todo"

    def run(self):
        if Opt.dry:
            out("      would set the Samba login of %s to the admin password" % Ctx.user)
            return
        why = share_set_login(need_password("to set the login for the shared folders"))
        if why:
            raise Abort(why)
        State.data["share_login"] = Ctx.user
        State.save()
