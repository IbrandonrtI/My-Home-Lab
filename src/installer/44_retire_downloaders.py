# One-time cleanup of Seerr, Radarr, Sonarr, Prowlarr, FlareSolverr and qBittorrent. They are no longer part of HomeLab.
# It only runs on a machine where an earlier version of the installer set them up. Their settings folder and all media files are left alone.
# Once every machine has been refreshed, this file can be deleted.

RETIRED_APPS = ("seerr", "radarr", "sonarr", "prowlarr", "flaresolverr", "qbittorrent")
RETIRED_STACK = "requests"
RETIRED_IMAGES = ("ghcr.io/seerr-team/seerr:latest", "lscr.io/linuxserver/radarr:latest", "lscr.io/linuxserver/sonarr:latest", "lscr.io/linuxserver/prowlarr:latest",
                  "ghcr.io/flaresolverr/flaresolverr:latest", "lscr.io/linuxserver/qbittorrent:latest")
RETIRED_STATE_KEYS = ("requests", "requests_stack", "requests_linked", "flaresolverr_card_allowed")


def retired_wanted():
    """True only when the installer itself set the apps up. Apps the person runs by hand are never touched."""
    return bool(State.data.get("requests")) and not Mode.existing


@step
class RetireDownloaders(Step):
    id, group = "retire-downloaders", "Services"
    title = "Remove Seerr, Radarr, Sonarr, Prowlarr, FlareSolverr and qBittorrent (containers, images and dashboard cards; settings and media files stay)"
    needs = ("portainer-token",)

    def applies(self):
        return retired_wanted()

    def probe(self):
        return "todo"

    def run(self):
        if Opt.dry:
            out("      would remove the six containers, their images and their dashboard cards. Their settings folder and all media files stay.")
            return
        if not Portainer.delete(RETIRED_STACK):
            raise Abort("Portainer could not remove the stack '%s'. Remove it in Portainer (Stacks), then run `sudo homelab-setup refresh` again." % RETIRED_STACK)
        left = containers_all()
        for name in RETIRED_APPS:
            if name in left:
                docker("rm", "-f", name, timeout=120)
        for image in RETIRED_IMAGES:
            docker("rmi", image, timeout=120)
        for name in RETIRED_APPS:
            forget_card(name)
        for key in RETIRED_STATE_KEYS:
            State.data.pop(key, None)
        State.save()
        good("The six apps are removed. Their settings are still in %s/requests and the downloads in /mnt/storage/downloads. To free the space, delete them yourself, for example: sudo rm -rf %s/requests" % (Ctx.home, Ctx.home))
