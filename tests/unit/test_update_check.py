"""
Tests for RQB2-bin/rq_update_check.sh (issue #139): is a newer image
published for this image's channel?
"""

import json
import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "..", "RQB2-bin", "rq_update_check.sh")

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required",
)

RELEASES = {
    "streams": {
        "stable": {"tag": None},
        "beta": {"tag": "beta-2026-10-01-120000"},
        "dev": {"tag": "development-2026-09-30-103242"},
    }
}


def _run(tmp_path, version, *args):
    (tmp_path / "version").write_text(version + "\n")
    (tmp_path / "releases.json").write_text(json.dumps(RELEASES))
    env = dict(
        os.environ,
        RQ_VERSION_FILE=str(tmp_path / "version"),
        RQ_RELEASES_FILE=str(tmp_path / "releases.json"),
        RQ_UPDATE_STATE=str(tmp_path / "state"),
    )
    return subprocess.run(["bash", _SCRIPT, *args], capture_output=True, text=True, env=env)


@pytest.mark.parametrize("version,rc", [
    ("development-2026-09-11-000349", 10),   # older dev image
    ("development-2026-09-30-103242", 0),    # the latest itself
    ("dev-backlog-2026-09-30-085733", 10),   # feature-branch build, older than latest dev
    ("beta-2025-12-30-211449", 10),          # older beta
    ("beta-2026-10-01-120000", 0),
    ("v1.0.0", 0),                           # stable channel, nothing published
])
def test_channel_and_date_comparison(tmp_path, version, rc):
    proc = _run(tmp_path, version)
    assert proc.returncode == rc, proc.stdout + proc.stderr


def test_feature_branch_build_is_explained(tmp_path):
    assert "feature branch" in _run(tmp_path, "dev-backlog-2026-09-30-085733").stdout


def test_refresh_then_notice(tmp_path):
    assert _run(tmp_path, "beta-2025-12-30-211449", "--refresh").returncode == 10
    notice = _run(tmp_path, "beta-2025-12-30-211449", "--notice").stdout
    assert "beta-2026-10-01-120000" in notice


def test_notice_is_silent_when_up_to_date(tmp_path):
    _run(tmp_path, "beta-2025-12-30-211449", "--refresh")
    assert _run(tmp_path, "beta-2026-10-01-120000", "--refresh").returncode == 0
    assert _run(tmp_path, "beta-2026-10-01-120000", "--notice").stdout == ""


def test_refresh_prints_the_result_for_the_menu(tmp_path):
    # R-048: the menu's CHECK shows what --refresh prints; it used to print
    # nothing, so the box was empty when up to date
    up_to_date = _run(tmp_path, "beta-2026-10-01-120000", "--refresh")
    assert up_to_date.returncode == 0
    assert "This image is up to date." in up_to_date.stdout
    newer = _run(tmp_path, "beta-2025-12-30-211449", "--refresh")
    assert newer.returncode == 10
    assert "beta-2025-12-30-211449" in newer.stdout      # both versions
    assert "beta-2026-10-01-120000" in newer.stdout


def test_offline_says_so(tmp_path):
    (tmp_path / "version").write_text("beta-2025-12-30-211449\n")
    env = dict(os.environ, RQ_VERSION_FILE=str(tmp_path / "version"),
               RQ_RELEASES_URL="http://127.0.0.1:9/RQB-releases.json",
               RQ_UPDATE_STATE=str(tmp_path / "state"))
    proc = subprocess.run(["bash", _SCRIPT, "--refresh"], capture_output=True, text=True, env=env)
    assert proc.returncode == 1
    assert "Could not reach rasqberry.org" in proc.stdout
    assert "network" in proc.stdout
