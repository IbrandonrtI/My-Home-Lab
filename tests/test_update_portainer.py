"""homelab-update's Portainer helper: changing the version of an image whose version is a variable (Immich)."""
import os
import re
import unittest

import helpers

STACK = """services:
  immich-server:
    image: ghcr.io/immich-app/immich-server:${IMMICH_VERSION:-v3.4.2}
  immich-machine-learning:
    image: ghcr.io/immich-app/immich-machine-learning:${IMMICH_VERSION:-v3.4.2}
  redis:
    image: valkey/valkey:9
"""


def load_helper():
    """The Python inside scripts/homelab-update, without running its main()."""
    with open(os.path.join(helpers.ROOT, "scripts", "homelab-update"), encoding="utf-8") as f:
        text = f.read()
    code = re.search(r"read -r -d '' PYLIB <<'PY' \|\| true\n(.*?)\nPY\n", text, re.S).group(1)
    code = code.replace("sys.exit(main(sys.argv[1:]))", "")
    ns = {"__name__": "pylib"}
    exec(compile(code, "homelab-update-pylib", "exec"), ns)  # noqa: S102
    return ns


class VariableVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = load_helper()

    def run_update(self, stack_text, env, pairs):
        sent = {}

        def fake_pt(method, path, body=None):
            if method == "GET" and path.startswith("/api/stacks/") and "/file" in path:
                return {"StackFileContent": stack_text}
            if method == "GET":
                return [{"Id": 7, "Name": "immich", "EndpointId": 1, "Env": env}]
            sent.update(body)
            return {}

        self.lib["pt"] = fake_pt
        self.lib["stack_update"]("immich", pairs)
        return sent

    def test_a_version_in_a_variable_is_changed_in_the_variable_and_its_default(self):
        server, ml = "ghcr.io/immich-app/immich-server", "ghcr.io/immich-app/immich-machine-learning"
        sent = self.run_update(STACK, [{"name": "IMMICH_VERSION", "value": "v3.4.2"}, {"name": "DB_PASSWORD", "value": "x"}],
                               [(server + ":v3.4.2", server + ":v3.5.0"), (ml + ":v3.4.2", ml + ":v3.5.0")])
        self.assertEqual({e["name"]: e["value"] for e in sent["env"]}, {"IMMICH_VERSION": "v3.5.0", "DB_PASSWORD": "x"})
        self.assertIn(server + ":${IMMICH_VERSION:-v3.5.0}", sent["stackFileContent"])
        self.assertIn(ml + ":${IMMICH_VERSION:-v3.5.0}", sent["stackFileContent"])
        self.assertIn("valkey/valkey:9", sent["stackFileContent"])

    def test_the_variable_is_added_when_the_stack_has_none_saved(self):
        server = "ghcr.io/immich-app/immich-server"
        sent = self.run_update(STACK, [], [(server + ":v3.4.2", server + ":v3.5.0")])
        self.assertEqual(sent["env"], [{"name": "IMMICH_VERSION", "value": "v3.5.0"}])

    def test_a_plain_image_line_is_still_replaced_as_text(self):
        sent = self.run_update(STACK, [], [("valkey/valkey:9", "valkey/valkey:10")])
        self.assertIn("valkey/valkey:10", sent["stackFileContent"])

    def test_an_image_that_is_not_in_the_file_at_all_is_refused(self):
        with self.assertRaises(RuntimeError):
            self.run_update(STACK, [], [("nginx:1", "nginx:2")])


if __name__ == "__main__":
    unittest.main()
