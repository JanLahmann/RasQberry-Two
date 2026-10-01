"""
Helpers shared by the Qiskit compatibility tests (tests/qiskit_compat).

Also holds the collector for deprecation-type warnings: conftest.py feeds it
from pytest's warning capture, the demo-subprocess tests feed it from stderr,
and conftest.py writes it out as markdown for the CI job summary.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
BIN_DIR = os.path.join(REPO_ROOT, "RQB2-bin")
CONFIG_DIR = os.path.join(REPO_ROOT, "RQB2-config")
MANIFEST_DIR = os.path.join(CONFIG_DIR, "demo-manifests")
PATCHES_DIR = os.path.join(CONFIG_DIR, "demo-patches")
PYTHON = sys.executable

DEPRECATION_CATEGORIES = ("DeprecationWarning", "PendingDeprecationWarning", "FutureWarning")
# "path:lineno: SomeDeprecationWarning: message" - the warnings module's format.
_STDERR_WARNING = re.compile(r"^(?P<loc>\S.*?:\d+): (?P<cat>[\w.]*(?:Deprecation|Future)Warning): "
                             r"(?P<msg>.*)$")

COLLECTED = {}  # (category, message, location) -> [sources]


def short_path(path):
    """Readable location: repo-relative, site-packages-relative or the last two parts."""
    if path.startswith(REPO_ROOT + os.sep):
        return os.path.relpath(path, REPO_ROOT)
    if "site-packages" + os.sep in path:
        return path.split("site-packages" + os.sep, 1)[1]
    return os.sep.join(path.split(os.sep)[-2:])


def record_warning(source, category, message, location):
    """Add one deprecation-type warning to the report (once)."""
    filename, _, lineno = location.rpartition(":")
    if filename:
        location = f"{short_path(filename)}:{lineno}"
    key = (category, " ".join(str(message).split())[:300], location)
    sources = COLLECTED.setdefault(key, [])
    if source not in sources:
        sources.append(source)


def record_subprocess_warnings(source, stderr):
    """Collect the deprecation-type warnings a demo subprocess printed to stderr."""
    for line in (stderr or "").splitlines():
        match = _STDERR_WARNING.match(line.strip())
        if match:
            record_warning(source, match.group("cat"), match.group("msg"), match.group("loc"))


def require(*modules):
    """Skip the calling test module unless all modules are importable."""
    for mod in modules:
        if importlib.util.find_spec(mod) is None:
            pytest.skip(f"{mod} not installed - Qiskit compatibility test skipped",
                        allow_module_level=True)


def manifest_install(manifest_name):
    """The install section of a demo manifest."""
    with open(os.path.join(MANIFEST_DIR, manifest_name), encoding="utf-8") as fh:
        return json.load(fh)["install"]


def fetch_pinned(manifest_name, dest, src_env=None):
    """Put the manifest's pinned ref into dest, as rq_demo_run.sh does.

    Same steps as fetch_pinned_repo (git init + shallow fetch of the ref +
    checkout). With src_env set and that environment variable naming a
    directory, that checkout is copied instead (offline runs). Skips the test
    if git or the network is unavailable. Returns the manifest's install section.
    """
    install = manifest_install(manifest_name)
    src = os.environ.get(src_env) if src_env else None
    if src:
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git"))
        subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
        return install
    if shutil.which("git") is None:
        pytest.skip("git not available")
    try:
        os.makedirs(dest)
        for cmd in (["git", "init", "-q"],
                    ["git", "fetch", "-q", "--depth", "1", install["repo_url"], install["ref"]],
                    ["git", "checkout", "-q", "FETCH_HEAD"]):
            subprocess.run(cmd, cwd=dest, check=True, capture_output=True, timeout=300)
    except (subprocess.SubprocessError, OSError) as exc:
        pytest.skip(f"could not fetch {install['repo_url']}: {exc}")
    return install


def apply_demo_patch(demo_dir, patch_file):
    """Apply a demo patch exactly as rq_demo_run.sh install_demo() does.

    It strips CR and trailing blanks from every file the patch targets
    (sed 's/\\r$//; s/[[:blank:]]*$//'), then tries `git apply` and falls back
    to `git apply -3`. A patch that does not apply is fatal there (the demo
    refuses to run), so it fails the test here.
    """
    patch = os.path.join(PATCHES_DIR, patch_file)
    with open(patch, encoding="utf-8") as fh:
        targets = [line[len("+++ b/"):].rstrip("\n") for line in fh if line.startswith("+++ b/")]
    for rel in targets:
        path = os.path.join(demo_dir, rel)
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="surrogateescape", newline="") as fh:
                lines = fh.read().split("\n")
            lines = [re.sub(r"[ \t]*$", "", re.sub(r"\r$", "", ln)) for ln in lines]
            with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
                fh.write("\n".join(lines))
    for cmd in (["git", "apply", patch], ["git", "apply", "-3", patch]):
        if subprocess.run(cmd, cwd=demo_dir, capture_output=True).returncode == 0:
            return
    pytest.fail(f"{patch_file} no longer applies to the pinned upstream ref "
                "(rq_demo_run.sh would refuse to run the demo)")


def subprocess_env(**extra):
    """Environment for demo subprocesses: our modules importable, no GPIO,
    deprecation warnings shown."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [BIN_DIR, env.get("PYTHONPATH")]))
    env["PYTHONWARNINGS"] = "default::DeprecationWarning,default::PendingDeprecationWarning"
    env["PYTHONUNBUFFERED"] = "1"
    env["MPLBACKEND"] = "Agg"
    env["LED_RENDER_MODE"] = "service"
    env.update(extra)
    return env
