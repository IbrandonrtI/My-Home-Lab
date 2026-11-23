"""Shared helpers for the tests: where the repository is and how to load its scripts without running them."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_loaded = {}


def load_script(name, relpath, env=None):
    """Load a script that has no .py ending as a module. env is set first, because some scripts read it when they are loaded."""
    if name in _loaded:
        return _loaded[name]
    for k, v in (env or {}).items():
        os.environ[k] = v
    loader = importlib.machinery.SourceFileLoader(name, os.path.join(ROOT, relpath))
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    _loaded[name] = mod
    return mod


def installer():
    """The installer in its FAKE mode, which never touches the machine it runs on."""
    return load_script("homelab_setup", "installer/homelab-setup",
                       {"HLS_FAKE": "1", "HLS_ROOT": tempfile.mkdtemp(prefix="hls-test-")})


def panel():
    """The Customize panel with its folders pointed at empty temporary ones."""
    base = tempfile.mkdtemp(prefix="hlp-test-")
    return load_script("homelab_panel", "scripts/homelab-panel",
                       {"HLP_HOME": base, "HLP_STATE": os.path.join(base, "state"), "HLP_UI": os.path.join(base, "ui"),
                        "HLP_NO_DOCKER": "1"})
