"""
Tests for rq_release_channel and rq_update_channel (RQB2-bin/rq_common.sh).

Strict tags (Jan, 2026-10-04): a version or tag of no known stream is not
stable. rq_release_channel names the stream exactly as rq_slot_manager.sh
plan-update and rq_release_notice.py do (beta, dev, stable, unknown);
rq_update_channel says which channel an image takes its updates from, and an
image of no known channel follows dev.
"""

import json
import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_COMMON = os.path.join(_HERE, "..", "..", "RQB2-bin", "rq_common.sh")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")

with open(os.path.join(_HERE, "data", "plan_update_cases.json")) as _f:
    _CASES = json.load(_f)["cases"]


def _channels(func, tags):
    script = f'. "{_COMMON}"; for t in "$@"; do {func} "$t"; done'
    out = subprocess.run(["bash", "-c", script, "-", *tags], capture_output=True, text=True,
                         check=True).stdout
    return out.splitlines()


def test_release_channel_agrees_with_the_guard_table():
    # every tag and every slot version of the shared plan-update table
    expected = {}
    for case in _CASES:
        stream, tag = case["expect"]["new"].split(" ", 1)
        expected[tag] = stream
        for key in ("target_holds", "running_holds"):
            stream, version = case["expect"][key].split(" ", 1)
            if stream not in ("none",) and version not in ("system", "empty", "unfinished"):
                expected[version] = stream
    tags = sorted(expected)
    assert dict(zip(tags, _channels("rq_release_channel", tags))) == expected


@pytest.mark.parametrize("tag,channel,follows", [
    ("beta-2026-10-03-095636", "beta", "beta"),
    ("development-2026-10-04-040217", "dev", "dev"),
    ("dev-slot-indicator-2026-10-04-101010", "dev", "dev"),
    ("v1.0.0", "stable", "stable"),
    ("1.0.0", "stable", "stable"),
    ("stable-2026-12-01-000000", "stable", "stable"),
    # not stable any more: unknown, and its updates come from dev
    ("my-build-2026-10-10", "unknown", "dev"),
    ("main", "unknown", "dev"),
    ("version-1.0", "unknown", "dev"),
    ("", "unknown", "dev"),
])
def test_release_and_update_channel(tag, channel, follows):
    assert _channels("rq_release_channel", [tag]) == [channel]
    assert _channels("rq_update_channel", [tag]) == [follows]
