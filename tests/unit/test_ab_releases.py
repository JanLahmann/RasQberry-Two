"""
Tests for RQB2-bin/rq_ab_releases.sh (R-049): the release lists behind the
Slot Manager's update picker.

- The default offer is the latest A/B image of the device's OWN channel
  (Jan, Q6: keep the other channels, default to the own one).
- Only A/B images are offered, never the standard image.
- "dev" covers development-* and dev-* builds, "stable" the v* tags of main.
- Every release on GitHub counts, not only the first API page.
- A GitHub rate limit is reported as such, not as "no internet".
"""

import hashlib
import json
import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "..", "RQB2-bin", "rq_ab_releases.sh")

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required",
)

GH = "https://github.com/JanLahmann/RasQberry-Two/releases/download"

MANIFEST = {
    "streams": {
        "stable": {"tag": None},
        "beta": {
            "tag": "beta-2026-09-30-221656",
            "image_url": f"{GH}/beta-2026-09-30-221656/rasqberry-beta-2026-09-30.img.xz",
            "ab_image_url": f"{GH}/beta-2026-09-30-221656/rasqberry-beta-2026-09-30-ab.img.xz",
            "release_date": "2026-09-30",
            "ab_image_download_size": 1671527604,
            "ab_image_sha256": "b7bb26a9" + "0" * 56,
        },
        "dev": {
            "tag": "development-2026-10-01-083408",
            "image_url": f"{GH}/development-2026-10-01-083408/rasqberry-development-2026-10-01-083408.img.xz",
            "ab_image_url": f"{GH}/development-2026-10-01-083408/rasqberry-development-2026-10-01-083408-ab.img.xz",
            "release_date": "2026-10-01 08:34",
            "ab_image_download_size": 2058162296,
        },
    }
}


def _digest(tag):
    return hashlib.sha256(tag.encode()).hexdigest()


def _release(tag, created, ab=True, standard=True, draft=False, digest=True):
    assets = []
    if standard:
        assets.append({"name": f"rasqberry-{tag}.img.xz", "size": 1,
                       "browser_download_url": f"{GH}/{tag}/rasqberry-{tag}.img.xz"})
    if ab:
        assets.append({"name": f"rasqberry-{tag}-ab.img.xz", "size": 1700000000,
                       "browser_download_url": f"{GH}/{tag}/rasqberry-{tag}-ab.img.xz",
                       "digest": f"sha256:{_digest(tag)}" if digest else None})
    return {"tag_name": tag, "created_at": created, "published_at": created,
            "draft": draft, "assets": assets}


GITHUB = [
    _release("development-2026-10-01-083408", "2026-10-01T08:34:08Z"),
    _release("dev-qiskit-compat-2026-10-01-081207", "2026-10-01T08:12:07Z"),
    _release("dev-standard-only-2026-10-01-070000", "2026-10-01T07:00:00Z", ab=False),
    _release("dev-draft-2026-10-01-060000", "2026-10-01T06:00:00Z", draft=True),
    _release("beta-2026-09-30-221656", "2026-09-30T22:16:56Z"),
    _release("beta-2025-12-30-211449", "2025-12-30T21:14:49Z"),
    _release("beta-2025-06-01-000000", "2025-06-01T00:00:00Z", digest=False),
    _release("v1.0.0", "2026-11-01T10:00:00Z"),
] + [_release(f"dev-x-2026-09-{d:02d}-000000", f"2026-09-{d:02d}T00:00:00Z") for d in range(1, 29)]


def _run(tmp_path, version, *args, releases=MANIFEST, github=GITHUB):
    (tmp_path / "version").write_text(version + "\n")
    (tmp_path / "releases.json").write_text(json.dumps(releases))
    (tmp_path / "github.json").write_text(json.dumps(github))
    env = dict(os.environ,
               RQ_VERSION_FILE=str(tmp_path / "version"),
               RQ_RELEASES_FILE=str(tmp_path / "releases.json"),
               RQ_GITHUB_RELEASES_FILE=str(tmp_path / "github.json"))
    return subprocess.run(["bash", _SCRIPT, *args], capture_output=True, text=True, env=env)


def _rows(proc):
    return [line.split("\t") for line in proc.stdout.splitlines()]


@pytest.mark.parametrize("version,channel", [
    ("beta-2026-09-30-221656", "beta"),
    ("development-2026-09-11-000349", "dev"),
    ("dev-backlog-2026-09-30-085733", "dev"),
    ("v1.0.0", "stable"),
])
def test_channel_of_this_image(tmp_path, version, channel):
    assert _run(tmp_path, version, "channel").stdout.strip() == channel


def test_latest_defaults_to_the_own_channel_and_the_ab_image(tmp_path):
    proc = _run(tmp_path, "beta-2025-12-30-211449", "latest")
    assert proc.returncode == 0, proc.stderr
    (row,) = _rows(proc)
    assert row[0] == "beta-2026-09-30-221656"
    assert row[1].endswith("-ab.img.xz")
    assert row[2:] == ["2026-09-30", "1671527604", "b7bb26a9" + "0" * 56]


def test_latest_for_a_dev_device_is_the_development_head(tmp_path):
    (row,) = _rows(_run(tmp_path, "dev-backlog-2026-09-30-085733", "latest"))
    assert row[0] == "development-2026-10-01-083408"
    assert row[2] == "2026-10-01"


def test_latest_of_an_empty_channel(tmp_path):
    proc = _run(tmp_path, "beta-2026-09-30-221656", "latest", "stable")
    assert proc.returncode == 2
    assert "No stable release is published yet" in proc.stderr


def test_latest_without_an_ab_image_is_not_offered(tmp_path):
    releases = json.loads(json.dumps(MANIFEST))
    del releases["streams"]["beta"]["ab_image_url"]
    proc = _run(tmp_path, "beta-2026-09-30-221656", "latest", releases=releases)
    assert proc.returncode == 2
    assert "has no A/B image" in proc.stderr
    assert proc.stdout == ""


def test_beta_list_reaches_old_releases_and_only_ab_images(tmp_path):
    rows = _rows(_run(tmp_path, "beta-2026-09-30-221656", "list", "beta"))
    assert [r[0] for r in rows] == ["beta-2026-09-30-221656", "beta-2025-12-30-211449"]
    assert all(r[1].endswith("-ab.img.xz") for r in rows)
    # each with the SHA256 GitHub keeps for the asset; beta-2025-06-01 has
    # none, so it cannot be verified and is not offered (H-34)
    assert rows[1][4] == _digest("beta-2025-12-30-211449")


def test_dev_list_covers_development_and_feature_builds_newest_first(tmp_path):
    rows = _rows(_run(tmp_path, "development-2026-09-11-000349", "list", "dev"))
    tags = [r[0] for r in rows]
    assert tags[:2] == ["development-2026-10-01-083408", "dev-qiskit-compat-2026-10-01-081207"]
    assert "dev-standard-only-2026-10-01-070000" not in tags   # no A/B image
    assert "dev-draft-2026-10-01-060000" not in tags           # draft
    assert len(tags) == 15                                      # capped


def test_stable_list_matches_main_release_tags(tmp_path):
    rows = _rows(_run(tmp_path, "beta-2026-09-30-221656", "list", "stable"))
    assert [r[0] for r in rows] == ["v1.0.0"]


def test_rate_limit_is_named(tmp_path):
    limited = {"message": "API rate limit exceeded for 1.2.3.4.", "documentation_url": "x"}
    proc = _run(tmp_path, "beta-2026-09-30-221656", "list", "beta", github=limited)
    assert proc.returncode == 1
    assert "60 release lookups per hour" in proc.stderr


def test_unknown_repository(tmp_path):
    proc = _run(tmp_path, "beta-2026-09-30-221656", "list", "beta", "--repo", "x/y",
                github={"message": "Not Found"})
    assert proc.returncode == 1
    assert "no repository x/y" in proc.stderr


def test_bad_repository_format(tmp_path):
    proc = _run(tmp_path, "beta-2026-09-30-221656", "list", "beta", "--repo", "nonsense")
    assert proc.returncode == 1
    assert "USER/REPO" in proc.stderr
