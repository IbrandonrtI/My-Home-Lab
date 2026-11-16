def installer_path_trusted(path, user):
    """True when only root or the sudo user can change the file and every folder above it. A file or folder that other users can write is not used."""
    try:
        pw = pwd.getpwnam(user)
        others = {u.pw_name for u in pwd.getpwall() if u.pw_gid == pw.pw_gid and u.pw_name != user}
        others |= {m for m in grp.getgrgid(pw.pw_gid).gr_mem if m != user}
        p = os.path.realpath(path)
        while True:
            st = os.stat(p)
            sticky_dir = stat.S_ISDIR(st.st_mode) and st.st_mode & stat.S_ISVTX
            if st.st_uid not in (0, pw.pw_uid) or (st.st_mode & 0o002 and not sticky_dir):
                return False
            if st.st_mode & 0o020 and not (st.st_gid in (0, pw.pw_gid) and not others):
                return False
            if p == "/":
                return True
            p = os.path.dirname(p)
    except (OSError, KeyError):
        return False


def reexec_newer_installer(cmd, args):
    """After `git pull` the repository holds a newer installer than the one installed in /usr/local/sbin. When a person types `sudo homelab-setup refresh` (or install) at a terminal, run the newer one, so a single refresh uses the fixes that were just downloaded. Background jobs, the control panel and the drives tool never hand over: the repository belongs to the user, so its code must not run as root without a person asking for it."""
    if FAKE or cmd not in ("refresh", "install") or os.environ.get("HLS_REEXEC"):
        return
    if not os.environ.get("SUDO_USER") or not interactive():
        return
    try:
        State.load()
        repo = Opt.repo or State.data.get("repo")
        new = os.path.join(repo, "installer", "homelab-setup") if repo else ""
        me = os.path.abspath(sys.argv[0])
        if not new or not os.path.isfile(new) or os.path.realpath(new) == os.path.realpath(me):
            return
        if not installer_path_trusted(new, os.environ["SUDO_USER"]):
            say("The installer in %s can be changed by other users, so it was not used. Check who may write there, then run the command again." % repo)
            return
        text = read_file(new)
        if not text or text == read_file(me):
            return
        compile(text, new, "exec")
    except (OSError, SyntaxError, ValueError, KeyError):
        return
    say("Using the newer installer from %s." % repo)
    env = dict(os.environ, HLS_REEXEC="1")
    os.execve(sys.executable, [sys.executable, new] + list(args), env)


def main(argv):
    """Read the command line and run the requested command."""
    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (AttributeError, ValueError):
        pass
    args = list(argv[1:])
    i = 0
    cmd = None
    pos = []
    while i < len(args):
        a = args[i]
        if a in ("--dry-run", "-n"):
            Opt.dry = True
        elif a in ("--yes", "-y"):
            Opt.yes = True
        elif a == "--no-restore":
            Opt.no_restore = True
        elif a == "--no-background":
            Opt.no_background = True
        elif a == "--force-existing":
            Opt.force_existing = True
        elif a == "--backup" and i + 1 < len(args):
            i += 1
            Opt.backup = args[i]
        elif a == "--repo" and i + 1 < len(args):
            i += 1
            Opt.repo = args[i]
        elif a in ("-h", "--help", "help"):
            out(HELP % VERSION)
            return 0
        elif a in ("--version", "version"):
            out("homelab-setup " + VERSION)
            return 0
        elif a in ("--quiet", "--background"):
            pass
        elif a == "--wipe-data":
            Opt.wipe_data = True
        elif a == "--wipe-drives":
            Opt.wipe_drives = True
        elif a in ("--all", "-a"):
            Opt.all = True
        elif a in ("--details", "-d"):
            Opt.details = True
        elif a.startswith("-"):
            out("Unknown option %s, so nothing was done. Try: homelab-setup help" % a)
            return 2
        else:
            pos.append(a)
        i += 1
    cmd = pos[0] if pos else "checklist"
    if cmd not in COMMANDS and cmd not in ("done", "skip", "unskip", "cards", "lastfm", "audiomuse", "navilist"):
        out("Unknown command '%s', so nothing was done. Try: homelab-setup help" % cmd)
        return 2
    if len(pos) > 1 and cmd not in ("done", "skip", "unskip", "cards", "lastfm", "audiomuse", "navilist"):
        out("'%s' does not take the word '%s', so nothing was done. Try: homelab-setup help" % (cmd, pos[1][:40]))
        return 2
    if (Opt.wipe_data or Opt.wipe_drives) and cmd != "uninstall":
        out("%s only belongs to the uninstall command, so '%s' was not run. Try: homelab-setup help" % ("--wipe-data" if Opt.wipe_data else "--wipe-drives", cmd))
        return 1
    if Opt.backup and not os.path.isdir(Opt.backup):
        out("The backup folder %s does not exist, so '%s' was not run." % (Opt.backup, cmd))
        return 1
    ensure_root()
    reexec_newer_installer(cmd, args)
    try:
        take_command_lock(cmd, pos[1:])
        if cmd in ("done", "skip", "unskip"):
            if len(pos) < 2:
                out("Which step? Example: homelab-setup %s reboot-test" % cmd)
                return 1
            cmd_mark("ack" if cmd == "done" else cmd, pos[1])
        elif cmd == "cards":
            return cmd_cards(pos[1:])
        elif cmd == "lastfm":
            return cmd_lastfm(pos[1:])
        elif cmd == "audiomuse":
            return cmd_audiomuse(pos[1:])
        elif cmd == "navilist":
            return cmd_navilist(pos[1:])
        else:
            if COMMANDS[cmd]() and cmd == "verify":
                return 1
    except Abort as e:
        Live.close()
        out("")
        bad(str(e))
        return 1
    except KeyboardInterrupt:
        Live.close()
        out("")
        say("Stopped. Finished steps stay finished; run the same command again to continue.")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
