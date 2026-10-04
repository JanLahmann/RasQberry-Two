"""
Tests for RQB2-bin/rq_release_notice.py (#242): which newer release a Pi is
told about, when (grace period, staged rollout, withdrawn releases), where it
would go (ping-pong: the slot that is not running) and what the warnings say
(downgrade, last beta/stable system on the card).

All times and serial numbers are fixed; data comes from temp files or a
local HTTP server, never from rasqberry.org.
"""

import hashlib
import http.server
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_BIN = os.path.join(_HERE, "..", "..", "RQB2-bin")
_SCRIPT = os.path.join(_BIN, "rq_release_notice.py")

_spec = importlib.util.spec_from_file_location("rq_release_notice", _SCRIPT)
rn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rn)

UTC = timezone.utc
FAR = datetime(2027, 1, 1, tzinfo=UTC)          # every grace period is over
SERIAL = "30a7eed9fd5d24ea"

DEV_OLD = "development-2026-10-04-040217"
DEV_NEW = "development-2026-10-12-010101"
BETA_OLD = "beta-2026-10-03-095636"
BETA_NEW = "beta-2026-10-10-120000"
STABLE = "v1.0.0"

RELEASES = {"streams": {
    "stable": {"tag": STABLE, "release_date": "2026-11-01", "release_url": "https://x/stable"},
    "beta": {"tag": BETA_NEW, "release_date": "2026-10-10", "release_url": "https://x/beta",
             "ab_image_download_size": 1668588980,
             "highlights": ["Bump version to beta-2026-10-10-120000", "From the release list"]},
    "dev": {"tag": DEV_NEW, "release_date": "2026-10-12 01:01", "release_url": "https://x/dev",
            "highlights": ["Merge remote-tracking branch 'origin/development'", "A dev change"]},
}}
NO_STABLE = {"streams": dict(RELEASES["streams"], stable={"tag": None})}


def ab(current, version, other_version):
    return {"ab": True, "current": current, "version": version, "other_version": other_version}


def single(version):
    return {"ab": False, "current": None, "version": version, "other_version": ""}


def kinds(advices):
    return [(a["kind"], a["tag"]) for a in advices]


# ---------------------------------------------------------------------------
# Versions and times
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("version,stream", [
    ("beta-2026-10-03-095636", "beta"),
    ("development-2026-10-04-040217", "dev"),
    ("dev-slot-indicator-2026-10-04-101010", "dev"),
    ("v1.0.0", "stable"),
    ("1.0.0", "stable"),                 # VERSION on main has no "v"
    ("stable-2026-12-01-000000", "stable"),
    # no known stream: unknown, like rq_slot_manager.sh plan-update (not stable)
    ("my-build-2026-10-10", "unknown"), ("main", "unknown"), ("version-1.0", "unknown"),
    ("EMPTY", None), ("INCOMPLETE", None), ("UNKNOWN", None), ("SYSTEM", None), ("", None),
])
def test_stream_of(version, stream):
    assert rn.stream_of(version) == stream


@pytest.mark.parametrize("text,expected", [
    ("2026-10-12T08:00:00Z", datetime(2026, 10, 12, 8, tzinfo=UTC)),
    ("2026-10-12T10:00:00+02:00", datetime(2026, 10, 12, 8, tzinfo=UTC)),
    ("2026-10-04 01:43", datetime(2026, 10, 4, 1, 43, tzinfo=UTC)),
    ("2026-10-03", datetime(2026, 10, 3, tzinfo=UTC)),
    ("soon", None), ("", None), (None, None), (42, None),
])
def test_parse_time(text, expected):
    assert rn.parse_time(text) == expected


def test_release_time_is_the_later_of_date_and_tag():
    # a date-only release_date is midnight; the tag has the build time
    assert rn.release_time(BETA_NEW, {"release_date": "2026-10-10"}) == datetime(2026, 10, 10, 12, tzinfo=UTC)
    assert rn.release_time(STABLE, {"release_date": "2026-11-01"}) == datetime(2026, 11, 1, tzinfo=UTC)
    assert rn.release_time(STABLE, {}) is None


@pytest.mark.parametrize("tag,entry,version,newer", [
    (DEV_NEW, {}, DEV_OLD, True),
    (DEV_OLD, {}, DEV_NEW, False),
    (DEV_OLD, {}, DEV_OLD, False),
    (BETA_NEW, {}, DEV_OLD, True),            # other stream, by build time
    ("v1.1.0", {}, "v1.0.0", True),
    ("v1.0.0", {}, "1.0.0", False),           # the same release
    ("v0.9.0", {}, "1.0.0", False),
    (STABLE, {"release_date": "2026-11-01"}, BETA_OLD, True),
    (STABLE, {"release_date": "2026-01-01"}, BETA_OLD, False),
    (STABLE, {}, BETA_OLD, False),            # no date: unsure means no
    (BETA_NEW, {}, "UNKNOWN", False),
    (BETA_NEW, {}, "", False),
])
def test_newer(tag, entry, version, newer):
    assert rn.is_newer(tag, entry, version) is newer


# ---------------------------------------------------------------------------
# Grace period, staged rollout, withdrawn
# ---------------------------------------------------------------------------

BETA_AT = datetime(2026, 10, 10, 12, tzinfo=UTC)     # BETA_NEW's build time
_BUCKET = rn.rollout_bucket(SERIAL, BETA_NEW)


@pytest.mark.parametrize("stream,tag,controls,now,ok,why", [
    ("beta", BETA_NEW, {}, BETA_AT + timedelta(days=2, hours=23), False, "not yet"),
    ("beta", BETA_NEW, {}, BETA_AT + timedelta(days=3), True, ""),
    ("dev", DEV_NEW, {}, datetime(2026, 10, 12, 1, 1, 1, tzinfo=UTC), True, ""),   # dev: no wait
    ("dev", DEV_NEW, {}, datetime(2026, 10, 12, 1, 0, tzinfo=UTC), False, "not yet"),
    ("stable", STABLE, {}, datetime(2026, 11, 7, 23, tzinfo=UTC), False, "not yet"),
    ("stable", STABLE, {}, datetime(2026, 11, 8, tzinfo=UTC), True, ""),
    # notify_after replaces the default grace, both ways
    ("beta", BETA_NEW, {BETA_NEW: {"notify_after": "2026-10-10T13:00:00Z"}},
     datetime(2026, 10, 10, 13, tzinfo=UTC), True, ""),
    ("beta", BETA_NEW, {BETA_NEW: {"notify_after": "2026-10-20T00:00:00Z"}},
     datetime(2026, 10, 19, tzinfo=UTC), False, "not yet"),
    ("beta", BETA_NEW, {BETA_NEW: {"notify_after": "not a time"}},
     BETA_AT + timedelta(days=3), True, ""),               # unreadable: default grace
    # staged rollout: this Pi's number decides
    ("beta", BETA_NEW, {BETA_NEW: {"rollout": 0}}, FAR, False, "rollout"),
    ("beta", BETA_NEW, {BETA_NEW: {"rollout": 100}}, FAR, True, ""),
    ("beta", BETA_NEW, {BETA_NEW: {"rollout": _BUCKET}}, FAR, False, "rollout"),
    ("beta", BETA_NEW, {BETA_NEW: {"rollout": _BUCKET + 1}}, FAR, True, ""),
    ("beta", BETA_NEW, {"releases": {BETA_NEW: {"rollout": 0}}}, FAR, False, "rollout"),
    ("beta", BETA_NEW, {BETA_NEW: {"rollout": "lots"}}, FAR, True, ""),
    # withdrawn wins over everything
    ("beta", BETA_NEW, {BETA_NEW: {"withdrawn": True, "rollout": 100}}, FAR, False, "withdrawn"),
    ("beta", BETA_NEW, {BETA_NEW: {"withdrawn": False}}, FAR, True, ""),
    # feature-branch builds are never announced
    ("dev", "dev-foo-2026-10-12-010101", {}, FAR, False, "feature-branch build"),
])
def test_eligible(stream, tag, controls, now, ok, why):
    entry = RELEASES["streams"].get(stream, {}) if tag in (BETA_NEW, DEV_NEW, STABLE) else {}
    assert rn.eligible(stream, tag, entry, controls, SERIAL, now) == (ok, why)


def test_rollout_number_is_sha256_of_serial_and_tag():
    expected = int(hashlib.sha256(f"{SERIAL}:{BETA_NEW}".encode()).hexdigest(), 16) % 100
    assert rn.rollout_bucket(SERIAL, BETA_NEW) == expected == 72
    # spread: many tags land all over 0-99
    numbers = {rn.rollout_bucket(SERIAL, f"beta-2026-10-{d:02d}-120000") for d in range(1, 29)}
    assert len(numbers) > 15 and all(0 <= n < 100 for n in numbers)


def test_serial_comes_from_the_board_then_machine_id(tmp_path, monkeypatch):
    monkeypatch.delenv("RQ_SERIAL", raising=False)
    dt, cpu, mid = tmp_path / "serial-number", tmp_path / "cpuinfo", tmp_path / "machine-id"
    dt.write_bytes(b"30a7eed9fd5d24ea\0")
    cpu.write_text("Hardware\t: BCM2835\nSerial\t\t: 10000000f8d51e63\n")
    mid.write_text("0fab9f69efc14e1592bb75edd04fda7b\n")
    args = dict(dt_path=str(dt), cpuinfo=str(cpu), machine_id=str(mid))
    assert rn.device_serial(**args) == "30a7eed9fd5d24ea"
    dt.write_bytes(b"0000000000000000\0")
    assert rn.device_serial(**args) == "10000000f8d51e63"
    cpu.write_text("Serial\t\t: 0000000000000000\n")
    assert rn.device_serial(**args) == "0fab9f69efc14e1592bb75edd04fda7b"
    mid.unlink()
    assert rn.device_serial(**args) == ""


# ---------------------------------------------------------------------------
# Who hears about what (running slot, other slot, held releases)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("device,releases,expected", [
    # dev system: newer dev build and newer beta; A's older beta too
    (ab("B", DEV_OLD, BETA_OLD), NO_STABLE,
     [("beta", True, "A"), ("dev", True, None)]),
    # the newest dev build runs already: only the beta (and for Slot A)
    (ab("B", DEV_NEW, BETA_OLD), NO_STABLE, [("beta", False, "A")]),
    # Slot A already holds the newest beta: not offered again
    (ab("B", DEV_OLD, BETA_NEW), NO_STABLE, [("dev", True, None)]),
    # beta system: no dev builds, stable yes
    (ab("A", BETA_OLD, DEV_OLD), RELEASES, [("stable", True, None), ("beta", True, None)]),
    # stable system: only stable
    (ab("A", "v0.9.0", "EMPTY"), RELEASES, [("stable", True, None)]),
    (ab("A", STABLE, "EMPTY"), RELEASES, []),
    # the other slot's dev system is not looked after
    (ab("B", BETA_NEW, DEV_OLD), NO_STABLE, []),
    # other slot unknown (no status file yet): only the running system counts
    (ab("A", BETA_OLD, "UNKNOWN"), NO_STABLE, [("beta", True, None)]),
    # one system on the card: no other slot, no target
    (single(BETA_OLD), NO_STABLE, [("beta", True, None)]),
    (single(""), RELEASES, []),
])
def test_who_hears_about_what(device, releases, expected):
    got = rn.advise(device, releases, {}, SERIAL, FAR)
    assert [(a["stream"], a["for_running"], a["other"]) for a in got] == expected
    for a in got:
        assert a["target"] == ({"A": "B", "B": "A"}.get(device["current"]) if device["ab"] else None)


def test_no_promote_ever_ping_pong():
    # Running Slot B with the newest beta, Slot A an older beta: nothing to
    # download, and PROMOTE is gone from the update model
    got = rn.advise(ab("B", BETA_NEW, BETA_OLD), NO_STABLE, {}, SERIAL, FAR)
    assert got == []
    for case in [ab("B", DEV_OLD, BETA_OLD), ab("A", BETA_OLD, DEV_OLD), single(BETA_OLD)]:
        assert {a["kind"] for a in rn.advise(case, RELEASES, {}, SERIAL, FAR)} <= {"update", "withdrawn"}


def test_feature_branch_head_is_never_offered():
    releases = {"streams": {"dev": {"tag": "dev-foo-2026-10-12-010101", "release_date": "2026-10-12"}}}
    assert rn.advise(ab("B", DEV_OLD, "EMPTY"), releases, {}, SERIAL, FAR) == []


def test_withdrawn_release_is_never_announced_and_the_running_one_is_flagged():
    controls = {BETA_NEW: {"withdrawn": True, "reason": "slot switch fails on the Pi 4"},
                BETA_OLD: {"withdrawn": True, "reason": "LED driver bug"}}
    got = rn.advise(ab("A", BETA_OLD, "EMPTY"), NO_STABLE, controls, SERIAL, FAR)
    assert kinds(got) == [("withdrawn", BETA_OLD)]
    assert got[0]["reason"] == "LED driver bug"


def test_grace_and_rollout_apply_to_both_slots():
    device = ab("B", DEV_OLD, BETA_OLD)
    assert rn.advise(device, NO_STABLE, {BETA_NEW: {"rollout": 0}, DEV_NEW: {"rollout": 0}},
                     SERIAL, FAR) == []
    early = datetime(2026, 10, 11, tzinfo=UTC)       # beta in its grace, dev not built yet
    assert rn.advise(device, NO_STABLE, {}, SERIAL, early) == []


# ---------------------------------------------------------------------------
# The guard (same rules as rq_slot_manager.sh plan-update)
# ---------------------------------------------------------------------------

# One table for both copies of the rules: rq_slot_manager.sh plan-update and
# plan_update here - see the file's "about"
with open(os.path.join(_HERE, "data", "plan_update_cases.json")) as _f:
    PLAN_CASES = json.load(_f)["cases"]


@pytest.mark.parametrize("case", PLAN_CASES, ids=[c["why"] for c in PLAN_CASES])
def test_plan_update_shared_cases(case):
    assert rn.plan_update(case["tag"], case["target"], case["running"]) == case["expect"]


def test_plan_update_when_the_other_slot_cannot_be_read():
    # as the desktop user the other slot may be UNKNOWN (plan-update itself
    # needs root there): no warning
    assert rn.plan_update(BETA_NEW, "UNKNOWN", DEV_OLD) == {
        "target_holds": "unknown unknown", "running_holds": f"dev {DEV_OLD}",
        "new": f"beta {BETA_NEW}", "downgrade": "none", "last_safe_slot": "no"}


# Pairs for version_older, checked against `sort -V | head -n 1` - what
# rq_slot_manager.sh version_older runs
VERSION_PAIRS = [
    ("1.9.0", "1.10.0"), ("1.2", "1.2.3"), ("1.10", "1.9.9"), ("1.0.0", "1.0.0-rc1"),
    ("1.0.0", "1.0.0a"), ("1.02", "1.2"), ("2026-09-30-221656", "2026-10-03-095636"),
    ("2026-10-03-095636", "2026-10-03-095637"), ("1.10.0", "2026-12-01-000000"),
    ("1.0.0", "1.0.0"), ("v1.9.0", "1.10.0"), ("beta-2026-09-30-221656", "beta-2026-10-03-095636"),
    ("stable-1.9.5", "1.10.0"), ("1.0.0~rc1", "1.0.0"), ("1.a", "1.b"), ("1.0.tar", "1.0"),
]


@pytest.mark.skipif(not shutil.which("sort"), reason="sort required")
@pytest.mark.parametrize("a,b", VERSION_PAIRS)
def test_version_older_matches_sort_v(a, b):
    script = ('a=$1 b=$2; a=${a#beta-}; a=${a#stable-}; a=${a#v}; b=${b#beta-}; b=${b#stable-}; '
              'b=${b#v}; [ "$a" != "$b" ] || exit 1; '
              '[ "$(printf "%s\\n%s\\n" "$a" "$b" | sort -V | head -n 1)" = "$a" ]')
    for x, y in ((a, b), (b, a)):
        shell = subprocess.run(["bash", "-c", script, "-", x, y]).returncode == 0
        assert rn.version_older(x, y) is shell, (x, y)


def _advice(device, tag, stream, other=None, for_running=True):
    target = {"A": "B", "B": "A"}.get(device["current"]) if device["ab"] else None
    return {"kind": "update", "tag": tag, "stream": stream, "entry": {}, "for_running": for_running,
            "other": other, "target": target,
            "plan": rn.plan_update(tag, device["other_version"], device["version"]) if target else None}


@pytest.mark.parametrize("device,tag,stream,text,strong", [
    # the coordinator's example: the last stable/beta system would go
    (ab("B", DEV_OLD, STABLE), DEV_NEW, "dev",
     "This replaces Slot A's stable system (v1.0.0), the only stable or beta system on this card. "
     "That is a downgrade to a development build. Safer: switch to Slot A first, then install "
     "into Slot B. Your files on /data are kept.", True),
    (ab("B", DEV_OLD, BETA_OLD), BETA_NEW, "beta",
     "This replaces Slot A's beta system (beta-2026-10-03-095636), the only stable or beta system "
     "on this card. Safer: switch to Slot A first, then install into Slot B. Your files on /data "
     "are kept.", True),
    # a downgrade, but the running slot is beta itself
    (ab("A", BETA_OLD, STABLE), BETA_NEW, "beta",
     "This replaces Slot B's stable system (v1.0.0). That is a downgrade to a beta. "
     "Your files on /data are kept.", False),
    (ab("A", BETA_OLD, "beta-2026-12-01-000000"), BETA_NEW, "beta",
     "This replaces Slot B's beta system (beta-2026-12-01-000000). That is a downgrade to an "
     "older beta. Your files on /data are kept.", False),
    # a plain replacement (the user may be using that system)
    (ab("A", BETA_OLD, DEV_OLD), BETA_NEW, "beta",
     "This replaces Slot B's development system (development-2026-10-04-040217). "
     "Your files on /data are kept.", False),
    (ab("A", BETA_OLD, "SYSTEM"), BETA_NEW, "beta",
     "This replaces the system in Slot B. Your files on /data are kept.", False),
    # a system of no known stream: named, but not safe and no downgrade
    (ab("A", DEV_OLD, "my-build-2026-10-10"), BETA_NEW, "beta",
     "This replaces the system in Slot B (my-build-2026-10-10). Your files on /data are kept.",
     False),
    # dev over dev never warns, even an older build
    (ab("A", BETA_OLD, DEV_NEW), DEV_OLD, "dev",
     "This replaces Slot B's development system (development-2026-10-12-010101). "
     "Your files on /data are kept.", False),
    (ab("A", BETA_OLD, "EMPTY"), BETA_NEW, "beta", "", False),
    (ab("A", BETA_OLD, "INCOMPLETE"), BETA_NEW, "beta", "", False),
    (single(BETA_OLD), BETA_NEW, "beta", "", False),
])
def test_warning_text(device, tag, stream, text, strong):
    assert rn.warning_text(_advice(device, tag, stream), device) == (text, strong)


@pytest.mark.parametrize("device,text", [
    (ab("A", BETA_OLD, DEV_OLD),
     "It goes into Slot B, the slot that is not running. After a good trial start, Slot B "
     "becomes the start slot and Slot A stays as the fallback."),
    (ab("B", DEV_OLD, BETA_OLD),
     "It goes into Slot A, the slot that is not running. After a good trial start, Slot A "
     "becomes the start slot and Slot B stays as the fallback."),
    (single(BETA_OLD),
     "This Pi has one system: write the new image to a card (rasqberry.org/latest/). "
     "Copy your notebooks and ~/.qiskit first."),
])
def test_route_text(device, text):
    assert rn.route_text(_advice(device, BETA_NEW, "beta"), device) == text


# ---------------------------------------------------------------------------
# Wording: headline, popup, login line, highlights
# ---------------------------------------------------------------------------

def test_headline_and_popup():
    device = ab("B", DEV_NEW, BETA_OLD)
    running = _advice(device, BETA_NEW, "beta")
    other = _advice(device, BETA_NEW, "beta", other="A", for_running=False)
    assert rn.headline(running, device) == "New beta available: beta-2026-10-10-120000"
    assert rn.headline(other, device) == "Slot A (beta) can be updated to beta-2026-10-10-120000"
    assert rn.popup_text(running, device) == (
        "New beta available: beta-2026-10-10-120000. Click the RasQberry slot icon for what's new.")
    assert rn.headline(_advice(device, DEV_NEW, "dev"), device) == (
        "New development build available: development-2026-10-12-010101")
    assert rn.headline(_advice(device, STABLE, "stable"), device) == "New stable release available: v1.0.0"


@pytest.mark.parametrize("device,advice_args,line", [
    (ab("A", BETA_OLD, "EMPTY"), (BETA_NEW, "beta"),
     "New beta available: beta-2026-10-10-120000 (Software & Image Updates)"),
    (ab("B", DEV_OLD, "EMPTY"), (DEV_NEW, "dev"),
     "New development build: development-2026-10-12-010101 (Software & Image Updates)"),
])
def test_login_line_is_one_line_within_80_columns(device, advice_args, line):
    got = rn.login_line([_advice(device, *advice_args)], device)
    assert got == line and len(got) <= 80 and "\n" not in got
    assert rn.login_line([], device) == ""


def test_highlights_prefer_the_curated_list_and_drop_commit_noise():
    curated = {"beta": ["Curated one", "Curated two"], "stable": []}
    assert rn.highlight_lines("beta", RELEASES, curated) == ["Curated one", "Curated two"]
    assert rn.highlight_lines("beta", RELEASES, {}) == ["From the release list"]
    assert rn.highlight_lines("dev", RELEASES, curated) == ["A dev change"]
    assert rn.highlight_lines("stable", RELEASES, curated) == []


def test_size_and_date_text():
    entry = RELEASES["streams"]["beta"]
    assert rn.size_text(entry) == "about 1.7 GB"
    assert rn.size_text({}) == ""
    assert rn.date_text(BETA_NEW, entry) == "10 October 2026"


# ---------------------------------------------------------------------------
# Fetching with a cache (offline-tolerant, conditional GET, 404 = defaults)
# ---------------------------------------------------------------------------

class _Handler(http.server.BaseHTTPRequestHandler):
    files = {}
    seen = []

    def do_GET(self):
        self.seen.append((self.path, self.headers.get("If-None-Match")))
        body = self.files.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        etag = '"%s"' % hashlib.sha1(body).hexdigest()[:8]
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("ETag", etag)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server(monkeypatch):
    _Handler.files = {"/RQB-releases.json": json.dumps(RELEASES).encode(),
                      "/highlights.json": b'{"beta": ["Curated"]}',
                      "/broken.json": b"<html>not json</html>"}
    _Handler.seen = []
    httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    monkeypatch.setenv("RQ_RELEASES_URL", base + "/RQB-releases.json")
    monkeypatch.setenv("RQ_RELEASE_CONTROLS_URL", base + "/RQB-release-controls.json")
    monkeypatch.setenv("RQ_HIGHLIGHTS_URL", base + "/highlights.json")
    yield base
    httpd.shutdown()


def test_fetch_caches_and_asks_conditionally(server, tmp_path):
    cache = tmp_path / "cache"
    t1 = datetime(2026, 10, 14, tzinfo=UTC)
    assert rn.fetch_all(str(cache), t1)
    assert json.loads((cache / "releases.json").read_text())["streams"]["beta"]["tag"] == BETA_NEW
    assert json.loads((cache / "controls.json").read_text()) == {}      # 404 = defaults
    t2 = t1 + timedelta(days=1)
    assert rn.fetch("releases", str(cache), t2)
    assert _Handler.seen[-1][1] is not None                              # If-None-Match sent
    data, fetched = rn.load_cached("releases", [str(cache)])
    assert data["streams"]["beta"]["tag"] == BETA_NEW and fetched == t2


def test_offline_or_broken_keeps_the_last_good_copy(server, tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    assert rn.fetch("releases", str(cache))
    monkeypatch.setenv("RQ_RELEASES_URL", server + "/broken.json")
    assert not rn.fetch("releases", str(cache))
    monkeypatch.setenv("RQ_RELEASES_URL", "http://127.0.0.1:9/RQB-releases.json")
    assert not rn.fetch("releases", str(cache), timeout=3)
    assert rn.load_cached("releases", [str(cache)])[0]["streams"]["dev"]["tag"] == DEV_NEW


def test_file_urls_work_for_trials(tmp_path, monkeypatch):
    src = tmp_path / "releases.json"
    src.write_text(json.dumps(RELEASES))
    monkeypatch.setenv("RQ_RELEASES_URL", src.as_uri())
    assert rn.fetch("releases", str(tmp_path / "cache"))


def test_the_freshest_cache_wins(tmp_path):
    for name, tag, when in (("user", BETA_OLD, "2026-10-01T00:00:00+00:00"),
                            ("system", BETA_NEW, "2026-10-02T00:00:00+00:00")):
        d = tmp_path / name
        d.mkdir()
        (d / "releases.json").write_text(json.dumps({"streams": {"beta": {"tag": tag}}}))
        (d / "releases.meta.json").write_text(json.dumps({"fetched": when}))
    data, _ = rn.load_cached("releases", [str(tmp_path / "user"), str(tmp_path / "system")])
    assert data["streams"]["beta"]["tag"] == BETA_NEW
    assert rn.load_all([str(tmp_path / "nowhere")]) == {"releases": None, "controls": {}, "highlights": {}}


# ---------------------------------------------------------------------------
# Command line: the daily root check writes the login line
# ---------------------------------------------------------------------------

def _cli(tmp_path, *args, version=BETA_OLD, controls=None, status=None):
    (tmp_path / "releases.json").write_text(json.dumps(NO_STABLE))
    (tmp_path / "controls.json").write_text(json.dumps(controls or {}))
    (tmp_path / "version").write_text(version + "\n")
    (tmp_path / "status").write_text(status or
                                     "layout=ab\ncurrent=A\nslot_a=%s\nslot_b=EMPTY\ncard_mode=dual\n" % version)
    env = dict(os.environ,
               RQ_RELEASES_URL=(tmp_path / "releases.json").as_uri(),
               RQ_RELEASE_CONTROLS_URL=(tmp_path / "controls.json").as_uri(),
               RQ_HIGHLIGHTS_URL=(tmp_path / "nothing.json").as_uri(),
               RQ_SLOT_STATUS_FILE=str(tmp_path / "status"),
               RQ_VERSION_FILE=str(tmp_path / "version"),
               RQ_SYSTEM_CACHE_DIR=str(tmp_path / "syscache"),
               RQ_NOTICE_FILE=str(tmp_path / "update-notice"),
               XDG_CACHE_HOME=str(tmp_path / "usercache"),
               RQ_NOW="2027-01-01T00:00:00Z", RQ_SERIAL=SERIAL)
    return subprocess.run([sys.executable, _SCRIPT, *args], capture_output=True, text=True,
                          env=env, timeout=60)


def test_daily_check_writes_and_clears_the_login_line(tmp_path):
    proc = _cli(tmp_path, "--refresh", "--system")
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "update-notice").read_text() == (
        "New beta available: beta-2026-10-10-120000 (Software & Image Updates)\n")
    assert (tmp_path / "syscache" / "releases.json").exists()
    assert not (tmp_path / "usercache").exists()
    # withdrawn later: the line goes
    proc = _cli(tmp_path, "--refresh", "--system", controls={BETA_NEW: {"withdrawn": True}})
    assert proc.returncode == 0, proc.stderr
    assert not (tmp_path / "update-notice").exists()


def test_line_reads_only_the_cache(tmp_path):
    assert _cli(tmp_path, "--line").stdout == ""                 # nothing fetched yet
    _cli(tmp_path, "--refresh")
    assert _cli(tmp_path, "--line").stdout.strip().startswith("New beta available")


def test_bucket_command(tmp_path):
    assert _cli(tmp_path, "--bucket", BETA_NEW).stdout.strip() == "72"


def test_report_says_nothing_new_when_up_to_date(tmp_path):
    _cli(tmp_path, "--refresh", version=BETA_NEW)
    assert _cli(tmp_path, version=BETA_NEW).stdout.strip() == "Nothing new for this Pi."
