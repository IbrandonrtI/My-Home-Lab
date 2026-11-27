"""The one-time cleanup of Seerr, Radarr, Sonarr, Prowlarr, FlareSolverr and qBittorrent: it removes the containers, the images and the dashboard cards on a machine where the installer set them up,
and it never touches the settings folder, the media files or anything the person runs by hand. Docker and Portainer are replaced by recorders."""
import os
import shutil
import unittest
from unittest import mock

import helpers

SIX = ("seerr", "radarr", "sonarr", "prowlarr", "flaresolverr", "qbittorrent")


class RetireDownloaders(unittest.TestCase):
    def setUp(self):
        self.m = helpers.installer()
        m = self.m
        self.events, self.present, self.portainer_ok = [], set(SIX) | {"metube", "downtify", "jellyfin"}, True
        self.state = {"requests": True, "requests_stack": "abc", "requests_linked": {"radarr": True}, "flaresolverr_card_allowed": True, "share": True}

        def fake_delete(name):
            self.events.append(("portainer-delete", name))
            return self.portainer_ok

        def fake_docker(*args, **kw):
            self.events.append(("docker",) + tuple(args))
            return 0, ""

        for patcher in (mock.patch.object(m.State, "data", self.state), mock.patch.object(m.State, "save", lambda *a, **k: self.events.append(("save",))),
                        mock.patch.object(m.Mode, "existing", False), mock.patch.object(m.Ctx, "home", "/home/test"),
                        mock.patch.object(m.Portainer, "delete", staticmethod(fake_delete)), mock.patch.object(m, "docker", fake_docker),
                        mock.patch.object(m, "containers_all", lambda: set(self.present)),
                        mock.patch.object(m, "forget_card", lambda name: self.events.append(("forget", name)))):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.step = m.BY_ID["retire-downloaders"]
        for d in ("/home/test/requests/sonarr", "/mnt/storage/downloads", "/mnt/storage/movies", "/mnt/storage/shows"):
            os.makedirs(m.P(d), exist_ok=True)
            self.addCleanup(shutil.rmtree, m.P(d), True)
        with open(m.P("/mnt/storage/shows/episode.mkv"), "w") as f:
            f.write("video")

    def docker_calls(self, verb):
        return [e[2:] for e in self.events if e[0] == "docker" and e[1] == verb]

    def test_it_runs_only_where_the_installer_set_the_apps_up(self):
        self.assertTrue(self.step.applies())
        del self.state["requests"]
        self.assertFalse(self.step.applies(), "apps the person runs by hand must not be touched")

    def test_it_never_runs_on_a_machine_that_was_built_by_hand(self):
        with mock.patch.object(self.m.Mode, "existing", True):
            self.assertFalse(self.step.applies())

    def test_it_removes_the_stack_first_then_the_six_containers_and_images_and_the_cards(self):
        self.step.run()
        self.assertEqual(self.events[0], ("portainer-delete", "requests"))
        self.assertEqual([c[0] for c in self.docker_calls("rm")], ["-f"] * 6)
        self.assertEqual(sorted(c[1] for c in self.docker_calls("rm")), sorted(SIX))
        images = [c[0] for c in self.docker_calls("rmi")]
        self.assertEqual(len(images), 6)
        for app in SIX:
            self.assertTrue(any(app in i for i in images), "the image of %s is not removed" % app)
        self.assertEqual([e[1] for e in self.events if e[0] == "forget"], list(SIX))

    def test_only_containers_that_exist_are_removed(self):
        self.present = {"sonarr", "metube"}
        self.step.run()
        self.assertEqual([c[1] for c in self.docker_calls("rm")], ["sonarr"])

    def test_other_containers_are_left_alone(self):
        self.step.run()
        touched = {c[1] for c in self.docker_calls("rm")}
        for keep in ("metube", "downtify", "jellyfin"):
            self.assertNotIn(keep, touched)
        self.assertEqual([e[1] for e in self.events if e[0] == "forget" and e[1] in ("metube", "downtify", "jellyfin")], [])

    def test_the_settings_and_every_media_file_stay(self):
        self.step.run()
        for path in ("/home/test/requests/sonarr", "/mnt/storage/downloads", "/mnt/storage/movies", "/mnt/storage/shows/episode.mkv"):
            self.assertTrue(os.path.exists(self.m.P(path)), "%s was removed" % path)
        self.assertFalse([e for e in self.events if e[0] == "docker" and e[1] in ("volume", "system")])

    def test_the_stored_setup_is_forgotten_so_the_step_does_not_run_again(self):
        self.step.run()
        for key in ("requests", "requests_stack", "requests_linked", "flaresolverr_card_allowed"):
            self.assertNotIn(key, self.state)
        self.assertEqual(self.state, {"share": True}, "other settings must stay")
        self.assertIn(("save",), self.events)
        self.assertFalse(self.step.applies())

    def test_when_portainer_cannot_remove_the_stack_nothing_else_happens(self):
        self.portainer_ok = False
        with self.assertRaises(self.m.Abort):
            self.step.run()
        self.assertEqual(self.docker_calls("rm"), [])
        self.assertEqual([e for e in self.events if e[0] == "forget"], [])
        self.assertIn("requests", self.state, "the step must be tried again on the next refresh")
        self.assertTrue(self.step.applies())

    def test_a_dry_run_changes_nothing(self):
        self.m.Opt.dry = True
        self.addCleanup(setattr, self.m.Opt, "dry", False)
        self.step.run()
        self.assertEqual(self.events, [])
        self.assertIn("requests", self.state)

    def test_the_images_are_the_ones_the_old_stack_used(self):
        self.assertEqual(len(self.m.RETIRED_IMAGES), 6)
        for app in SIX:
            self.assertEqual(sum(app in i for i in self.m.RETIRED_IMAGES), 1)

    def test_it_waits_for_the_portainer_login_the_installer_uses(self):
        self.assertIn("portainer-token", self.step.needs)
        self.assertIn("portainer-token", self.m.BY_ID)

    def test_nothing_of_the_old_setup_is_left_in_the_installer_except_this_cleanup(self):
        for gone in ("requests", "qbittorrent", "radarr", "sonarr", "prowlarr", "flaresolverr", "seerr"):
            self.assertNotIn(gone, self.m.STACKS)
            self.assertNotIn(gone, self.m.PORTS)
        self.assertFalse([s.id for s in self.m.STEPS if s.id.startswith(("requests", "stack-requests"))])
        self.assertFalse(hasattr(self.m, "cmd_requests"))
        self.assertNotIn("requests", self.m.LOCKED_COMMANDS)


if __name__ == "__main__":
    unittest.main()
