#!/usr/bin/env python3
"""
Unit tests for the external-demo mechanics (EXTERNAL_DEMOS.md).

These exercise the shell tooling directly, with no Raspberry Pi and no
installed system:

  * rq_demo_validate.sh --external accepts a well-formed external manifest and
    rejects the forbidden patterns (launcher / patch_file / command, path
    traversal, non-https repo_url, bad entrypoint type, missing marker_file).
  * The manifest search path (rq_common.sh helpers) dedupes by id with the
    shipped directory winning over the user directory.

Run with:
    python3 -m pytest tests/unit/ -q

Skipped automatically if bash or jq are unavailable.
"""

import json
import os
import shutil
import subprocess

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BIN = os.path.join(_REPO_ROOT, "RQB2-bin")
_VALIDATE = os.path.join(_BIN, "rq_demo_validate.sh")
_COMMON = os.path.join(_BIN, "rq_common.sh")

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required for the external-demo shell tests",
)


def _write_manifest(path, obj):
    with open(path, "w") as fh:
        json.dump(obj, fh)


def _run_external_validate(manifest_path):
    """Run rq_demo_validate.sh --external on one file, return (rc, output)."""
    proc = subprocess.run(
        [_VALIDATE, "--external", manifest_path],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


# ---------------------------------------------------------------------------
# Fixture manifests
# ---------------------------------------------------------------------------

def _good_manifest():
    return {
        "id": "good-ext",
        "name": "Good External Demo",
        "category": "visualization",
        "description": "A valid external demo",
        "entrypoint": {
            "type": "web-static",
            "working_dir": "good-ext",
            "serve_dir": "build",
            "port": 8090,
        },
        "install": {
            "repo_url": "https://github.com/example/good-ext.git",
            "marker_file": "README.md",
        },
    }


# Each bad case is (name, mutator) where mutator edits a good manifest in place.
def _mut_launcher(m):
    m["entrypoint"]["launcher"] = "rq_something.sh"


def _mut_patch_file(m):
    m["install"]["patch_file"] = "some.patch"


def _mut_command(m):
    m["entrypoint"]["command"] = "python3"


def _mut_traversal(m):
    m["entrypoint"]["working_dir"] = "../etc"


def _mut_leading_slash(m):
    m["entrypoint"]["script"] = "/etc/passwd"


def _mut_http_url(m):
    m["install"]["repo_url"] = "http://github.com/example/good-ext.git"


def _mut_bad_type(m):
    m["entrypoint"]["type"] = "script"


def _mut_missing_marker(m):
    del m["install"]["marker_file"]


_BAD_CASES = [
    ("launcher", _mut_launcher),
    ("patch_file", _mut_patch_file),
    ("command", _mut_command),
    ("path_traversal", _mut_traversal),
    ("leading_slash", _mut_leading_slash),
    ("http_url", _mut_http_url),
    ("bad_type", _mut_bad_type),
    ("missing_marker", _mut_missing_marker),
]


# ---------------------------------------------------------------------------
# Tests: --external validation
# ---------------------------------------------------------------------------

def test_good_external_manifest_passes(tmp_path):
    path = tmp_path / "rq_demo_good-ext.json"
    _write_manifest(path, _good_manifest())
    rc, out = _run_external_validate(str(path))
    assert rc == 0, f"good external manifest should pass, got rc={rc}\n{out}"


def test_external_manifest_named_rqb_demo_json_passes(tmp_path):
    # External manifests are validated inside the demo repo checkout, where
    # the file is named rqb-demo.json (registry manifest_path) - the
    # rq_demo_<id>.json naming only applies after the add-flow copies it.
    # Regression: the internal id-matches-filename rule must not apply.
    path = tmp_path / "rqb-demo.json"
    _write_manifest(path, _good_manifest())
    rc, out = _run_external_validate(str(path))
    assert rc == 0, f"rqb-demo.json-named manifest should pass, got rc={rc}\n{out}"


@pytest.mark.parametrize("name,mutator", _BAD_CASES, ids=[c[0] for c in _BAD_CASES])
def test_bad_external_manifest_rejected(tmp_path, name, mutator):
    m = _good_manifest()
    mutator(m)
    path = tmp_path / "rq_demo_good-ext.json"
    _write_manifest(path, m)
    rc, out = _run_external_validate(str(path))
    assert rc != 0, f"external manifest with bad '{name}' should be rejected\n{out}"


# ---------------------------------------------------------------------------
# Tests: manifest search-path dedup (shipped wins)
# ---------------------------------------------------------------------------

def _run_helper(snippet, user_home, extra_env=None):
    env = dict(os.environ)
    env["USER_HOME"] = user_home
    if extra_env:
        env.update(extra_env)
    script = f'. "{_COMMON}"\n{snippet}\n'
    proc = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, env=env
    )
    return proc.returncode, proc.stdout, proc.stderr


def _make_manifest_file(directory, demo_id, name):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"rq_demo_{demo_id}.json")
    _write_manifest(
        path,
        {
            "id": demo_id,
            "name": name,
            "category": "tool",
            "description": "x",
            "entrypoint": {"type": "python", "working_dir": demo_id, "script": "m.py"},
        },
    )
    return path


def test_search_path_shipped_wins_on_collision(tmp_path):
    shipped = tmp_path / "shipped"
    user_home = tmp_path / "home"
    user_dir = user_home / ".local" / "config" / "demo-manifests"

    shipped_file = _make_manifest_file(str(shipped), "dup", "Shipped Version")
    _make_manifest_file(str(user_dir), "dup", "User Version")
    # A user-only demo that does NOT collide - it should still be listed.
    user_only = _make_manifest_file(str(user_dir), "useronly", "User Only")

    # rq_list_manifests: shipped 'dup' present, user 'dup' shadowed, 'useronly' kept
    rc, out, err = _run_helper(f'rq_list_manifests "{shipped}"', str(user_home))
    assert rc == 0
    listed = [ln for ln in out.splitlines() if ln.strip()]
    assert shipped_file in listed, f"shipped dup should be listed:\n{out}"
    assert user_only in listed, f"non-colliding user demo should be listed:\n{out}"
    # The shadowed user 'dup' file path must NOT appear
    user_dup = os.path.join(str(user_dir), "rq_demo_dup.json")
    assert user_dup not in listed, f"shadowed user dup should be excluded:\n{out}"
    # Exactly one 'dup' entry total
    dup_entries = [p for p in listed if p.endswith("rq_demo_dup.json")]
    assert dup_entries == [shipped_file]

    # rq_find_manifest resolves 'dup' to the shipped file
    rc, out, err = _run_helper(f'rq_find_manifest "{shipped}" "dup"', str(user_home))
    assert rc == 0
    assert out.strip() == shipped_file


def test_search_path_degrades_to_shipped_only_without_user_home(tmp_path):
    shipped = tmp_path / "shipped"
    shipped_file = _make_manifest_file(str(shipped), "only", "Shipped Only")

    # No USER_HOME -> user dir helper returns nothing -> shipped-only, no error
    env = dict(os.environ)
    env.pop("USER_HOME", None)
    script = f'. "{_COMMON}"\nrq_list_manifests "{shipped}"\n'
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)
    assert proc.returncode == 0
    listed = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert listed == [shipped_file]
