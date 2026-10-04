"""
Tests for RQB2-bin/rq_umami_event.py: the anonymous usage counts the Pi sends
to the project's Umami statistics, and where they are sent from (health check,
daily update check, taskbar notice, demo engine, learning paths, LED stall).

Every request goes to a local HTTP server (RQ_UMAMI_URL); the files the
module reads (version, board, RAM, CONFIG partition, slot status, release
cache) are temp files.
"""

import importlib.util
import json
import os
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_SYS = os.path.join(_ROOT, "RQB2-system")
_SCRIPT = os.path.join(_BIN, "rq_umami_event.py")
_COMMON = os.path.join(_BIN, "rq_common.sh")

BETA = "beta-2026-10-03-095636"
BETA_NEW = "beta-2026-10-10-120000"
SERIAL = "10000000deadbeef"
MACHINE_ID = "0123456789abcdef0123456789abcdef"
PI_HOSTNAME = "classroom-pi-07"
PAYLOAD_KEYS = {"website", "hostname", "url", "name", "data", "language"}
# What must never appear as a key, anywhere in a request
FORBIDDEN_KEYS = {"serial", "machine-id", "machine_id", "machineid", "ip", "ip_address",
                  "userAgent", "id", "user", "username", "mac"}
# Words isbot (Umami's bot check) matches; none may be in the user agent
BOT_WORDS = ("bot", "python", "urllib", "curl", "wget", "http", "url", "spider", "crawl",
             "fetch", "headless", "java", "okhttp", "libwww", "scrape", "check")

needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _exe(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


# ---------------------------------------------------------------------------
# A local Umami
# ---------------------------------------------------------------------------

class Umami:
    """Records each POST (user agent, JSON body); answers like Umami."""

    def __init__(self, delay=0.0, status=200):
        self.requests = []
        self.delay, self.status = delay, status
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                outer.requests.append({"path": self.path, "agent": self.headers.get("User-Agent", ""),
                                       "raw": body.decode(), "body": json.loads(body)})
                time.sleep(outer.delay)
                reply = json.dumps({"cache": "token", "sessionId": "s", "visitId": "v"}).encode()
                try:
                    self.send_response(outer.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(reply)))
                    self.end_headers()
                    self.wfile.write(reply)
                except OSError:
                    pass

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/api/send"
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02},
                         daemon=True).start()

    def events(self, name=None):
        out = [r["body"]["payload"] for r in self.requests]
        return [p for p in out if name is None or p["name"] == "RasQberry Two: " + name]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def _closed_port_url():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return f"http://127.0.0.1:{port}/api/send"


@pytest.fixture
def umami():
    server = Umami()
    yield server
    server.close()


@pytest.fixture
def pi(tmp_path, monkeypatch, umami):
    """A Pi 5 with 8 GB running BETA (standard image unless a test adds CONFIG)."""
    files = {
        "version": BETA + "\n",
        "model": "Raspberry Pi 5 Model B Rev 1.0\0",
        "meminfo": "MemTotal:        8245328 kB\nMemFree:  100 kB\n",
    }
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    (tmp_path / "config").mkdir()
    env = {"RQ_UMAMI_URL": umami.url, "RQ_UMAMI_STATE": str(tmp_path / "state"),
           "RQ_UMAMI_RUN_DIR": str(tmp_path / "run"), "RQ_UMAMI_ENV_FILE": str(tmp_path / "env"),
           "RQ_VERSION_FILE": str(tmp_path / "version"), "RQ_DT_MODEL": str(tmp_path / "model"),
           "RQ_MEMINFO": str(tmp_path / "meminfo"),
           "RQ_HEALTH_STATUS": str(tmp_path / "health.status"),
           "RQ_IMAGER_STATE": str(tmp_path / "imager"),
           "RQ_SLOT_STATUS_FILE": str(tmp_path / "slot-status"),
           "RQ_SYSTEM_CACHE_DIR": str(tmp_path / "cache"), "RQ_SERIAL": SERIAL,
           "RQ_NOW": "2026-10-20T12:00:00Z"}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("RQ_UMAMI", raising=False)
    (tmp_path / "run").mkdir()
    mod = _load("rq_umami_event", _SCRIPT)
    # never the real slot manager
    monkeypatch.setattr(mod.rn, "SLOT_MANAGER", str(tmp_path / "no-slot-manager"))
    mod.tmp, mod.config, mod.umami = tmp_path, tmp_path / "config", umami
    return mod


def _ab(pi, current="A", slot_a=BETA, slot_b="EMPTY", card_mode="dual", history=None):
    """Make the Pi an A/B card: CONFIG with autoboot.txt, the slot status."""
    (pi.config / "autoboot.txt").write_text("[all]\ntryboot_a_b=1\nboot_partition=2\n")
    for name, text in (history or {}).items():
        (pi.config / name).write_text(text + "\n")
    (pi.tmp / "slot-status").write_text(
        f"layout=ab\ncurrent={current}\nslot_a={slot_a}\nslot_b={slot_b}\ncard_mode={card_mode}\n")


def _boot(pi, probation=None, running=None, confirmed=True):
    """One start as the health check sees it."""
    ctx = pi.boot_started(pi.config, probation)
    pi.boot_finished(ctx, pi.config, running, confirmed)
    return ctx


# ---------------------------------------------------------------------------
# The request
# ---------------------------------------------------------------------------

def test_payload_shape(pi):
    body = pi.build_payload("first start", {"version": BETA, "stream": "beta", "model": "pi5-8gb",
                                            "card": "standard", "imager": "no",
                                            "serial": SERIAL, "hostname": PI_HOSTNAME})
    assert body == {"type": "event", "payload": {
        "website": "97f347ac-e7ba-4be3-b26f-ab4b328bdbf2", "hostname": "rasqberry.org",
        "url": "/pi/first-start", "name": "RasQberry Two: first start", "language": "en",
        "data": {"version": BETA, "stream": "beta", "model": "pi5-8gb", "card": "standard",
                 "imager": "no"}}}


@pytest.mark.parametrize("event,url", [
    ("first start", "/pi/first-start"), ("update check", "/pi/update-check"),
    ("update result", "/pi/update-result"), ("update notice", "/pi/update-notice"),
    ("demo start", "/pi/demo-start"), ("learning path", "/pi/learning-path"),
    ("LED stall", "/pi/led-stall"), ("test event", "/pi/test-event")])
def test_every_event_has_its_name_and_url(pi, event, url):
    payload = pi.build_payload(event, {})["payload"]
    assert payload["url"] == url and payload["name"] == "RasQberry Two: " + event
    assert set(payload) == PAYLOAD_KEYS


def test_an_unknown_event_is_not_sent(pi):
    with pytest.raises(ValueError):
        pi.build_payload("serial number", {})
    assert pi.send("serial number", {"serial": SERIAL}) is False
    assert pi.umami.requests == []


def test_values_are_short_plain_strings(pi):
    data = pi.build_payload("demo start", {"demo": "x" * 80 + "<script>", "how": "menu"})["payload"]["data"]
    assert data["demo"] == "x" * 48 and data["how"] == "menu"


def test_the_user_agent_is_counted_not_dropped_as_a_bot(pi):
    assert pi.send("test event", {"source": "dev-test"})
    agent = pi.umami.requests[0]["agent"]
    assert agent == f"Mozilla/5.0 (X11; Linux aarch64) RasQberry/{BETA} (Raspberry Pi 5)"
    assert not any(w in agent.lower() for w in BOT_WORDS)


@pytest.mark.parametrize("version,shown", [
    ("development-2026-10-04-040217", "development-2026-10-04-040217"), ("v1.2.3", "v1.2.3"),
    ("dev-url-fix-2026-10-04-101010", "dev"), ("dev-bot-test-2026-10-04-101010", "dev"),
    ("my-own-build", "unknown")])
def test_a_feature_branch_name_never_reaches_the_user_agent(pi, version, shown):
    agent = pi.user_agent(version, "Raspberry Pi 4")
    assert agent == f"Mozilla/5.0 (X11; Linux aarch64) RasQberry/{shown} (Raspberry Pi 4)"
    assert not any(w in agent.lower() for w in BOT_WORDS)


@pytest.mark.parametrize("model,kb,expected", [
    ("Raspberry Pi 5 Model B Rev 1.0\0", 8245328, ("pi5-8gb", "Raspberry Pi 5")),
    ("Raspberry Pi 5 Model B Rev 1.1\0", 16400000, ("pi5-16gb", "Raspberry Pi 5")),
    ("Raspberry Pi 4 Model B Rev 1.5\0", 3880000, ("pi4-4gb", "Raspberry Pi 4")),
    ("Raspberry Pi 4 Model B Rev 1.4\0", 1900000, ("pi4-2gb", "Raspberry Pi 4")),
    ("Raspberry Pi 400 Rev 1.0\0", 3880000, ("pi400-4gb", "Raspberry Pi 400")),
    ("Raspberry Pi Compute Module 4 Rev 1.1\0", 960000, ("cm4-1gb", "Raspberry Pi Compute Module 4")),
    ("", 0, ("other", "Raspberry Pi"))])
def test_board_is_model_and_ram_only(pi, model, kb, expected):
    (pi.tmp / "model").write_text(model)
    (pi.tmp / "meminfo").write_text(f"MemTotal: {kb} kB\n" if kb else "")
    assert pi.board() == expected


# ---------------------------------------------------------------------------
# No IDs, anywhere
# ---------------------------------------------------------------------------

def test_no_identifiers_in_any_event(pi, monkeypatch):
    machine_id = pi.tmp / "machine-id"
    machine_id.write_text(MACHINE_ID + "\n")
    monkeypatch.setattr(socket, "gethostname", lambda: PI_HOSTNAME)
    # a new A/B card, then an update that worked, a failed one, the daily check
    _ab(pi, slot_b=BETA_NEW)
    (pi.tmp / "imager").mkdir()
    (pi.tmp / "imager" / "imager-customised").write_text("x")
    _boot(pi, running="A")
    (pi.config / "slot-B-updated").write_text(f"version={BETA_NEW}\ntag={BETA_NEW}\n")
    _boot(pi, probation="B", running="B")
    (pi.config / "last-switch-failed").write_text(
        f"slot=A\nreason=virtual environment missing\ntime=2026-10-20 10:00:00\nupdate=yes\nversion={BETA}\n")
    _boot(pi, running="B")
    _cache(pi, {"beta": {"tag": BETA_NEW, "release_date": "2026-10-10"}})
    assert pi.daily()
    pi.main(["update-notice", "whats-new", BETA_NEW])
    pi.main(["demo-start", "led-demos:ibm-logo", "desktop"])
    pi.main(["learning-path", "first-15-minutes", "finish"])
    pi.main(["led-stall", "0.4"])
    names = [p["name"] for p in pi.umami.events()]
    assert sorted(set(names)) == sorted("RasQberry Two: " + e for e in pi.DATA_KEYS if e != "test event")

    def keys(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                yield from keys(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from keys(v)

    for r in pi.umami.requests:
        payload = r["body"]["payload"]
        assert set(r["body"]) == {"type", "payload"} and set(payload) == PAYLOAD_KEYS
        assert payload["hostname"] == "rasqberry.org"
        event = payload["name"].split(": ", 1)[1]
        assert set(payload["data"]) <= set(pi.DATA_KEYS[event])
        assert not FORBIDDEN_KEYS & set(keys(r["body"]))
        for secret in (SERIAL, MACHINE_ID, PI_HOSTNAME, os.environ.get("USER", "rasqberry"),
                       socket.gethostname(), "127.0.0.1"):
            assert secret not in r["raw"] and secret not in r["agent"], secret


# ---------------------------------------------------------------------------
# First start: once per newly written card
# ---------------------------------------------------------------------------

def test_first_start_once_on_the_standard_image(pi):
    _boot(pi)
    [event] = pi.umami.events("first start")
    assert event["data"] == {"version": BETA, "stream": "beta", "model": "pi5-8gb",
                             "card": "standard", "imager": "no"}
    for _ in range(3):
        _boot(pi)
        pi.daily()
    assert len(pi.umami.events("first start")) == 1


def test_first_start_says_whether_imager_customised_the_card(pi):
    (pi.tmp / "imager").mkdir()
    (pi.tmp / "imager" / "imager-customised").write_text("2026-10-20 10:00:00\n")
    _boot(pi)
    assert pi.umami.events("first start")[0]["data"]["imager"] == "yes"


@pytest.mark.parametrize("card_mode,card", [("dual", "ab-dual"), ("dual-pending", "ab-dual"),
                                            ("single", "ab-single")])
def test_first_start_of_a_new_ab_card(pi, card_mode, card):
    _ab(pi, card_mode=card_mode)
    _boot(pi, running="A")
    [event] = pi.umami.events("first start")
    assert event["data"]["card"] == card


@pytest.mark.parametrize("history", [
    {"target-slot": "B", "current-slot": "A"},
    {"slot-confirmed": "2026-10-03T10:00:00+02:00\nA", "current-slot": "A"},
    {"current-slot": "B"}], ids=["updated-slot-trial", "confirmed-before", "rolled-back"])
def test_a_slot_written_by_an_update_is_not_a_new_card(pi, history):
    # the updated slot starts with an empty /var/lib, but CONFIG remembers the card
    _ab(pi, current="B", slot_b=BETA_NEW, history=history)
    _boot(pi, running="B")
    _boot(pi, running="B")
    assert pi.umami.events("first start") == []
    assert (pi.tmp / "state" / "first-start").read_text().strip() == "not-new"


def test_a_system_brought_up_to_date_in_place_is_not_new(pi):
    # "Update from GitHub Branch" on an older standard image: the health check ran before
    (pi.tmp / "health.status").write_text("success: True\n")
    _boot(pi)
    assert pi.umami.events("first start") == []


def test_the_decision_is_taken_before_the_slot_is_confirmed(pi):
    # boot_started() sees the new card; confirming then writes CONFIG markers
    _ab(pi)
    ctx = pi.boot_started(pi.config, None)
    (pi.config / "slot-confirmed").write_text("now\nA\n")
    (pi.config / "current-slot").write_text("A\n")
    pi.boot_finished(ctx, pi.config, "A", True)
    assert len(pi.umami.events("first start")) == 1


def test_first_start_waits_while_offline_and_is_sent_once_later(pi, monkeypatch):
    monkeypatch.setenv("RQ_UMAMI_URL", _closed_port_url())
    _boot(pi)
    assert len(pi.queued()) == 1
    _boot(pi)                                   # still offline: kept, not queued twice
    assert len(pi.queued()) == 1
    monkeypatch.setenv("RQ_UMAMI_URL", pi.umami.url)
    pi.daily()
    pi.daily()
    _boot(pi)
    assert len(pi.umami.events("first start")) == 1 and pi.queued() == []


def test_a_failed_health_check_still_counts_the_first_start_later(pi):
    pi.boot_started(pi.config, None)            # the check then failed: no boot_finished
    assert pi.umami.events() == []
    pi.daily()
    assert len(pi.umami.events("first start")) == 1


def test_the_queue_drops_old_events(pi):
    pi.queue_event("update result", {"result": "worked"}, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    pi.queue_event("update result", {"result": "worked", "reason": "health-check"})
    pi.flush()
    assert pi.queued() == [] and len(pi.umami.events()) == 1


def test_the_queue_stays_small(pi):
    for i in range(pi.QUEUE_MAX + 5):
        pi.queue_event("update result", {"result": "worked", "reason": str(i)})
    assert len(pi.queued()) == pi.QUEUE_MAX
    assert pi.queued()[0][1]["data"]["reason"] == "5"      # the oldest went


# ---------------------------------------------------------------------------
# Update results
# ---------------------------------------------------------------------------

def _updated(pi, slot="B", version=BETA_NEW):
    (pi.config / f"slot-{slot}-updated").write_text(
        f"version={version}\ntag={version}\ntime=2026-10-20 09:00:00\n")


def test_an_update_that_worked_is_sent_by_the_updated_slot(pi):
    _ab(pi, current="B", slot_a=BETA, slot_b=BETA_NEW,
        history={"target-slot": "B", "slot-confirmed": "x\nA", "current-slot": "A"})
    _updated(pi)
    _boot(pi, probation="B", running="B")
    [event] = pi.umami.events("update result")
    assert event["data"] == {"from": BETA, "to": BETA_NEW, "result": "worked",
                             "reason": "health-check"}


def test_a_plain_switch_is_not_an_update_result(pi):
    _ab(pi, current="B", slot_b=BETA_NEW, history={"target-slot": "B", "current-slot": "A"})
    _boot(pi, probation="B", running="B")
    assert pi.umami.events("update result") == []


def test_an_unconfirmed_trial_is_not_counted_as_worked(pi):
    _ab(pi, current="B", slot_b=BETA_NEW, history={"target-slot": "B", "current-slot": "A"})
    _updated(pi)
    _boot(pi, probation="B", running="B", confirmed=False)
    assert pi.umami.events("update result") == []


def _failed(pi, reason, slot="B", update="yes", time_="2026-10-20 10:00:00"):
    (pi.config / "last-switch-failed").write_text(
        f"slot={slot}\nreason={reason}\ntime={time_}\nupdate={update}\nversion={BETA_NEW}\n")


def test_an_update_that_did_not_work_is_sent_once_by_the_slot_running_again(pi):
    _ab(pi, current="A", slot_b=BETA_NEW, history={"slot-confirmed": "x\nA", "current-slot": "A"})
    _failed(pi, "the desktop did not come up within 300 s (display-manager: inactive)")
    for _ in range(3):
        _boot(pi, running="A")
        pi.daily()
    [event] = pi.umami.events("update result")
    assert event["data"] == {"from": BETA, "to": BETA_NEW, "result": "didn't work",
                             "reason": "desktop-timeout"}
    # the next failed update is a new notice
    _failed(pi, "Slot B was tried twice without success", time_="2026-10-21 08:00:00")
    _boot(pi, running="A")
    assert [e["data"]["reason"] for e in pi.umami.events("update result")] == [
        "desktop-timeout", "no-boot"]


@pytest.mark.parametrize("slot,update", [("B", "no"), ("A", "yes")],
                         ids=["plain-switch", "failed-slot-is-running"])
def test_no_result_for_a_plain_switch_or_without_a_rollback(pi, slot, update):
    _ab(pi, current="A", history={"current-slot": "A"})
    _failed(pi, "virtual environment missing", slot=slot, update=update)
    _boot(pi, running="A")
    assert pi.umami.events("update result") == []


def test_failure_reasons_match_the_health_check(pi):
    # the reason texts rq_health_check.py writes into last-switch-failed
    source = open(os.path.join(_BIN, "rq_health_check.py")).read()
    for text in ("virtual environment missing", "Qiskit check failed (",
                 "the desktop did not come up within", "not confirmed {DEADLINE_MINUTES} minutes after start",
                 "was tried twice without success"):
        assert text in source, text
    assert pi.failure_reason("virtual environment missing") == "health-check"
    assert pi.failure_reason("Qiskit check failed (pip list timeout)") == "health-check"
    assert pi.failure_reason("the desktop did not come up within 300 s (display-manager: failed)") \
        == "desktop-timeout"
    assert pi.failure_reason("not confirmed 15 minutes after start (start-up hung or the health "
                             "check could not run)") == "start-timeout"
    assert pi.failure_reason("Slot B was tried twice without success") == "no-boot"
    assert pi.failure_reason("") == "other"


# ---------------------------------------------------------------------------
# Daily update check
# ---------------------------------------------------------------------------

def _cache(pi, streams, controls=None):
    cache = pi.tmp / "cache"
    cache.mkdir(exist_ok=True)
    (cache / "releases.json").write_text(json.dumps({"streams": streams}))
    (cache / "controls.json").write_text(json.dumps(controls or {}))


def test_update_check_once_per_day(pi, monkeypatch):
    _cache(pi, {"beta": {"tag": BETA, "release_date": "2026-10-03"}})
    assert pi.daily() is True
    assert pi.daily() is False
    monkeypatch.setenv("RQ_NOW", "2026-10-21T00:30:00Z")
    assert pi.daily() is True
    events = pi.umami.events("update check")
    assert len(events) == 2
    assert events[0]["data"] == {"version": BETA, "stream": "beta", "model": "pi5-8gb",
                                 "card": "standard", "update": "none"}


def test_an_offline_day_is_tried_again(pi, monkeypatch):
    monkeypatch.setenv("RQ_UMAMI_URL", _closed_port_url())
    assert pi.daily() is False
    monkeypatch.setenv("RQ_UMAMI_URL", pi.umami.url)
    assert pi.daily() is True


@pytest.mark.parametrize("streams,controls,expected", [
    ({"beta": {"tag": BETA_NEW, "release_date": "2026-10-10"}}, {}, "available"),
    ({"beta": {"tag": BETA_NEW, "release_date": "2026-10-10"}},
     {BETA_NEW: {"withdrawn": True}}, "withdrawn-seen"),
    ({"beta": {"tag": BETA, "release_date": "2026-10-03"}}, {BETA: {"withdrawn": True}},
     "withdrawn-seen"),
    ({"beta": {"tag": BETA, "release_date": "2026-10-03"}}, {}, "none"),
    ({"dev": {"tag": "development-2026-10-19-010101"}}, {}, "none"),
], ids=["newer-beta", "newer-withdrawn", "running-withdrawn", "up-to-date", "only-dev-newer"])
def test_update_status(pi, streams, controls, expected):
    _cache(pi, streams, controls)
    pi.daily()
    assert pi.umami.events("update check")[0]["data"]["update"] == expected


def test_the_timer_sends_the_daily_count():
    unit = open(os.path.join(_SYS, "etc/systemd/system/rasqberry-update-check.service")).read()
    lines = [l for l in unit.splitlines() if l.startswith("ExecStart")]
    # after the fetch it reads, and never failing the unit
    assert lines[-1] == "ExecStart=-/usr/bin/rq_umami_event.py daily"
    assert os.access(_SCRIPT, os.X_OK)


# ---------------------------------------------------------------------------
# Offline, slow, broken: never an exception, never a long wait
# ---------------------------------------------------------------------------

def test_offline_returns_false_at_once(pi, monkeypatch):
    monkeypatch.setenv("RQ_UMAMI_URL", _closed_port_url())
    start = time.monotonic()
    assert pi.send("test event", {"source": "dev-test"}) is False
    assert time.monotonic() - start < 2


def test_a_hanging_server_costs_at_most_the_timeout(pi, monkeypatch):
    slow = Umami(delay=10)
    try:
        monkeypatch.setenv("RQ_UMAMI_URL", slow.url)
        start = time.monotonic()
        assert pi.send("test event", {"source": "dev-test"}, timeout=1) is False
        assert time.monotonic() - start < 2.5
    finally:
        slow.close()


def test_a_hanging_name_lookup_costs_at_most_the_timeout(pi, monkeypatch):
    def stuck(*args, **kwargs):
        time.sleep(10)
    monkeypatch.setattr(pi, "_post", stuck)
    start = time.monotonic()
    assert pi.send("test event", {"source": "dev-test"}, timeout=1) is False
    assert time.monotonic() - start < 2.5


@pytest.mark.parametrize("url", ["http://rasqberry-umami-test.invalid/api/send", "not a url"])
def test_unreachable_or_bad_endpoints_never_raise(pi, monkeypatch, url):
    monkeypatch.setenv("RQ_UMAMI_URL", url)
    assert pi.send("test event", {"source": "dev-test"}) is False


def test_http_errors_are_not_success(pi, monkeypatch):
    failing = Umami(status=500)
    try:
        monkeypatch.setenv("RQ_UMAMI_URL", failing.url)
        assert pi.send("test event", {"source": "dev-test"}) is False
    finally:
        failing.close()


def test_nothing_raises_with_a_broken_state_directory(pi, monkeypatch):
    (pi.tmp / "not-a-dir").write_text("")
    monkeypatch.setenv("RQ_UMAMI_STATE", str(pi.tmp / "not-a-dir"))
    monkeypatch.setattr(pi, "_post", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    pi.boot_finished({}, pi.config, None, True)
    assert pi.main(["daily"]) == 0
    assert pi.main(["flush"]) == 0
    assert pi.main(["demo-start", "x"]) == 0


def test_wrong_usage_sends_nothing(pi):
    assert pi.main([]) == 2
    assert pi.main(["update-notice", "uninstall", BETA]) == 2
    assert pi.main(["learning-path", "first-15-minutes", "abandon"]) == 2
    assert pi.umami.requests == []


# ---------------------------------------------------------------------------
# RQ_UMAMI=0
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["0", "false", "off", "no"])
def test_rq_umami_0_sends_nothing(pi, monkeypatch, value):
    monkeypatch.setenv("RQ_UMAMI", value)
    _ab(pi, slot_b=BETA_NEW)
    _updated(pi)
    _boot(pi, probation="B", running="B")
    _cache(pi, {"beta": {"tag": BETA_NEW, "release_date": "2026-10-10"}})
    assert pi.daily() is False
    for argv in (["update-notice", "install", BETA_NEW], ["demo-start", "grok-bloch", "menu"],
                 ["learning-path", "first-15-minutes", "start"], ["led-stall", "0.4"]):
        pi.main(argv)
    assert pi.main(["test"]) == 1
    assert pi.umami.requests == [] and not (pi.tmp / "state").exists()


def test_rq_umami_0_in_the_environment_file(pi):
    # rig and development Pis: one line reaches the timers and the desktop too
    (pi.tmp / "env").write_text("LED_LAYOUT=quad\nRQ_UMAMI=0\n")
    assert not pi.enabled()
    pi.main(["demo-start", "grok-bloch"])
    assert pi.umami.requests == []
    (pi.tmp / "env").write_text('RQ_UMAMI="1"\n')
    assert pi.enabled()


def test_the_environment_variable_wins(pi, monkeypatch):
    (pi.tmp / "env").write_text("RQ_UMAMI=0\n")
    monkeypatch.setenv("RQ_UMAMI", "1")
    assert pi.enabled()


# ---------------------------------------------------------------------------
# Where the events are sent from
# ---------------------------------------------------------------------------

@pytest.fixture
def hc(monkeypatch, tmp_path):
    mod = _load("rq_health_check", os.path.join(_BIN, "rq_health_check.py"))
    monkeypatch.setattr(mod, "BOOT_CONFIG_DIR", tmp_path)
    return mod


def test_the_health_check_decides_before_confirming_and_sends_at_the_end(hc, monkeypatch):
    calls = []

    class Counts:
        def boot_started(self, config, probation):
            calls.append(("started", probation))
            return {"ctx": 1}

        def boot_finished(self, ctx, config, running, confirmed):
            calls.append(("finished", ctx, confirmed))

    monkeypatch.setattr(hc, "usage_counts", Counts())
    monkeypatch.setattr(hc, "probation_slot", lambda: None)
    monkeypatch.setattr(hc, "load_environment", lambda: {})
    monkeypatch.setattr(hc, "check_venv_exists", lambda env: (True, "/venv"))
    monkeypatch.setattr(hc, "check_qiskit_installed", lambda venv: (True, "qiskit 2.2"))
    monkeypatch.setattr(hc, "confirm_boot_slot", lambda: calls.append("confirm") or True)
    monkeypatch.setattr(hc, "report_status", lambda *a: None)
    monkeypatch.setattr(hc, "write_slot_status", lambda: calls.append("slot-status"))
    monkeypatch.setattr(hc, "disarm_probation_watchdog", lambda: None)
    monkeypatch.setattr(sys, "argv", ["rq_health_check.py"])
    with pytest.raises(SystemExit) as done:
        hc.main()
    assert done.value.code == 0
    assert calls == [("started", None), "confirm", "slot-status", ("finished", {"ctx": 1}, True)]


def test_a_broken_counter_never_breaks_the_health_check(hc, monkeypatch):
    class Broken:
        def boot_started(self, *a):
            raise RuntimeError("boom")

        def boot_finished(self, *a):
            raise RuntimeError("boom")

    monkeypatch.setattr(hc, "usage_counts", Broken())
    assert hc.counts_started("B") == {}
    hc.counts_finished({}, True)
    monkeypatch.setattr(hc, "usage_counts", None)
    assert hc.counts_started("B") == {}
    hc.counts_finished({}, True)


def test_the_update_notice_counts_its_clicks(pi):
    ind = _load("rq_slot_indicator", os.path.join(_BIN, "rq_slot_indicator.py"))
    for action in ("whats-new", "install"):
        argv = ind.notice_count_argv(action, BETA_NEW)
        assert argv[1:] == [_SCRIPT, "update-notice", action, BETA_NEW]
        assert pi.main(argv[2:]) == 0
    assert [e["data"] for e in pi.umami.events("update notice")] == [
        {"action": "whats-new", "tag": BETA_NEW}, {"action": "install", "tag": BETA_NEW}]
    source = open(os.path.join(_BIN, "rq_slot_indicator.py")).read()
    assert 'self.spawn(notice_count_argv("whats-new", advice["tag"]))' in source
    assert 'self.spawn(notice_count_argv("install", advice["tag"]))' in source


@pytest.mark.parametrize("argv,data", [
    (["demo-start", "led-demos:ibm-logo", "desktop"],
     {"demo": "led-demos:ibm-logo", "how": "desktop", "version": BETA, "model": "pi5-8gb"}),
    (["demo-start", "grok-bloch", "learning-path"],
     {"demo": "grok-bloch", "how": "learning-path", "version": BETA, "model": "pi5-8gb"}),
    (["demo-start", "grok-bloch", "loop"], {"demo": "grok-bloch", "version": BETA, "model": "pi5-8gb"}),
    (["demo-start", "grok-bloch"], {"demo": "grok-bloch", "version": BETA, "model": "pi5-8gb"}),
])
def test_demo_start(pi, argv, data):
    assert pi.main(argv) == 0
    assert pi.umami.events("demo start")[0]["data"] == data


def test_learning_path(pi):
    pi.main(["learning-path", "first-15-minutes", "start"])
    pi.main(["learning-path", "first-15-minutes", "finish"])
    assert [e["data"] for e in pi.umami.events("learning path")] == [
        {"path": "first-15-minutes", "action": "start"},
        {"path": "first-15-minutes", "action": "finish"}]


def test_led_stall_at_most_once_per_start(pi):
    for _ in range(3):
        pi.main(["led-stall", "0.7"])
    assert [e["data"] for e in pi.umami.events("LED stall")] == [{"model": "pi5-8gb", "brightness": "0.7"}]
    # a restart empties /dev/shm
    (pi.tmp / "run" / "rasqberry-umami-led-stall").unlink()
    pi.main(["led-stall", "0.4"])
    assert len(pi.umami.events("LED stall")) == 2


# ---------------------------------------------------------------------------
# Shell side: rq_count_event, the demo engine, learning paths
# ---------------------------------------------------------------------------

def _python_stub(tmp_path, sleep=0):
    """A python3 on PATH that records rq_umami_event.py calls and runs
    anything else with the real Python."""
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    log = tmp_path / "counted"
    _exe(stubs / "python3", f'''#!/bin/sh
case "$1" in
    *rq_umami_event.py) sleep {sleep}; shift; echo "$*" >> "{log}"; exit 0 ;;
esac
exec "{sys.executable}" "$@"
''')
    return stubs, log


def _await(path, timeout=5):
    end = time.time() + timeout
    while time.time() < end and not (path.exists() and path.read_text()):
        time.sleep(0.05)
    return path.read_text() if path.exists() else ""


@needs_bash
def test_rq_count_event_runs_in_the_background(tmp_path):
    stubs, log = _python_stub(tmp_path, sleep=3)
    env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}")
    env.pop("RQ_UMAMI", None)
    start = time.monotonic()
    proc = subprocess.run(["bash", "-c", f'set -euo pipefail; . "{_COMMON}"; '
                           'rq_count_event demo-start grok-bloch menu; echo rc=$?'],
                          env=env, capture_output=True, text=True, timeout=30)
    assert proc.stdout.strip().endswith("rc=0") and time.monotonic() - start < 2.5
    assert _await(log, 6).split() == ["demo-start", "grok-bloch", "menu"]


@needs_bash
def test_rq_count_event_with_rq_umami_0_starts_nothing(tmp_path):
    stubs, log = _python_stub(tmp_path)
    env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", RQ_UMAMI="0")
    proc = subprocess.run(["bash", "-c", f'. "{_COMMON}"; rq_count_event learning-path x start'],
                          env=env, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0
    time.sleep(0.5)
    assert not log.exists()


def _box(tmp_path):
    """Environment for the demo engine: env file and env-config in tmp, stubs."""
    stubs, log = _python_stub(tmp_path)
    _exe(stubs / "chromium-browser", "#!/bin/sh\nexit 0\n")
    _exe(stubs / "ping", "#!/bin/sh\nexit 0\n")
    home = tmp_path / "home"
    home.mkdir()
    env_file = tmp_path / "rasqberry_environment.env"
    env_file.write_text(open(os.path.join(_CFG, "rasqberry_environment.env")).read())
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(open(os.path.join(_CFG, "rasqberry_env-config.sh")).read()
                          .replace("/usr/config/rasqberry_environment.env", str(env_file))
                          .replace('USER_HOME="$(eval echo ~${SUDO_USER})"', f'USER_HOME="{home}"'))
    env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", HOME=str(home),
               RQ_CONFIG_FILE=str(env_config), RQ_ENV_FILE=str(env_file), DISPLAY=":0",
               XDG_CACHE_HOME=str(tmp_path / "cache"))
    for k in ("RQ_UMAMI", "RQ_DEMO_HOW", "RQ_DEMO_COUNTED", "RQ_ERROR_FILE", "SUDO_USER"):
        env.pop(k, None)
    return env, log, env_file


@needs_bash
@pytest.mark.skipif(shutil.which("jq") is None, reason="jq required")
@pytest.mark.parametrize("extra,how", [({}, ""), ({"RQ_ERROR_FILE": "/dev/null"}, "menu"),
                                       ({"RQ_DEMO_HOW": "desktop"}, "desktop"),
                                       ({"RQ_DEMO_HOW": "learning-path", "RQ_ERROR_FILE": "/dev/null"},
                                        "learning-path")],
                         ids=["terminal", "menu", "desktop", "learning-path-from-the-menu"])
def test_the_demo_engine_counts_each_start_once(tmp_path, extra, how):
    env, log, _ = _box(tmp_path)
    env.update(extra)
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_demo_run.sh"), "composer"], env=env,
                          capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _await(log).splitlines() == [f"demo-start composer {how}".strip()]


@needs_bash
@pytest.mark.skipif(shutil.which("jq") is None, reason="jq required")
@pytest.mark.parametrize("extra", [{"RQ_DEMO_HOW": "loop"}, {"RQ_DEMO_COUNTED": "composer"}],
                         ids=["demo-loop", "re-run-of-a-counted-start"])
def test_the_demo_engine_does_not_count_loops_and_re_runs(tmp_path, extra):
    env, log, _ = _box(tmp_path)
    env.update(extra)
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_demo_run.sh"), "composer"], env=env,
                          capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    time.sleep(0.5)
    assert not log.exists()


@needs_bash
@pytest.mark.skipif(shutil.which("jq") is None, reason="jq required")
def test_the_demo_engine_respects_rq_umami_0_in_the_environment_file(tmp_path):
    env, log, env_file = _box(tmp_path)
    env_file.write_text(env_file.read_text() + "RQ_UMAMI=0\n")
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_demo_run.sh"), "composer"], env=env,
                          capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    time.sleep(0.5)
    assert not log.exists()


def test_the_engine_keeps_the_count_settings_when_it_drops_root():
    engine = open(os.path.join(_BIN, "rq_demo_run.sh")).read()
    keep = engine.split("drop_to_desktop_user() {", 1)[1].split("exec sudo", 1)[0]
    for var in ("RQ_DEMO_HOW", "RQ_DEMO_COUNTED", "RQ_UMAMI"):
        assert var in keep
    # counted after the install, before the demo runs (and the LED re-run with sudo -E)
    main = engine.split("\nmain() {", 1)[1]
    assert main.index("ensure_installed\n\n") < main.index("rq_count_event demo-start") \
        < main.index('case "$entrypoint_type" in')


def test_desktop_icons_learning_paths_and_the_loop_say_how():
    hold = open(os.path.join(_BIN, "rq_hold_on_error.sh")).read()
    assert 'export RQ_DEMO_HOW="${RQ_DEMO_HOW:-desktop}"' in hold
    loop = open(os.path.join(_BIN, "rq_demo_loop.sh")).read()
    assert loop.index("ensure_root") < loop.index("export RQ_DEMO_HOW=loop")
    paths = open(os.path.join(_BIN, "rq_learning_paths.sh")).read()
    start_step = paths.split("start_step() {", 1)[1].split("\n}\n", 1)[0]
    assert "local RQ_DEMO_HOW=learning-path" in start_step and "export RQ_DEMO_HOW" in start_step
    walk = paths.split("walk_path() {", 1)[1].split("\n}\n", 1)[0]
    assert 'rq_count_event learning-path "$P_ID" start' in walk
    # finish: on "Finish this path", before Keep going
    assert walk.index('rq_count_event learning-path "$P_ID" finish') < walk.index('keep_going "$i"')


# ---------------------------------------------------------------------------
# LED stall (rq_led_utils.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def led(monkeypatch):
    mod = _load("rq_led_utils_umami", os.path.join(_BIN, "rq_led_utils.py"))
    spawned = []

    class FakePopen:
        def __init__(self, argv, **kwargs):
            spawned.append((argv, kwargs))

    import subprocess as sp
    monkeypatch.setattr(sp, "Popen", FakePopen)
    monkeypatch.delenv("RQ_UMAMI", raising=False)
    monkeypatch.setattr(mod, "LED_STALL_FILE_PREFIX", "/nonexistent/stall-")
    mod.spawned = spawned
    return mod


def _stall_writer(led, stuck):
    def write(pin, buf):
        if stuck["on"]:
            time.sleep(led.LED_STALL_SECONDS + 0.05)
    return led._guarded_pi5_write(write, lambda: None)


def _await_spawn(led, n=1, timeout=3):
    end = time.time() + timeout
    while time.time() < end and len(led.spawned) < n:
        time.sleep(0.02)
    return led.spawned


def test_an_led_stall_is_counted_once_without_slowing_the_frames(led):
    led._stall_state["brightness"] = 0.4
    stuck = {"on": True}
    write = _stall_writer(led, stuck)
    start = time.monotonic()
    write(None, b"\0" * 12)
    # the stalled write and the reopened write: the count adds nothing measurable
    assert time.monotonic() - start < 2 * (led.LED_STALL_SECONDS + 0.05) + 0.2
    [(argv, kwargs)] = _await_spawn(led)
    assert argv[1:] == [os.path.join(_BIN, "rq_umami_event.py"), "led-stall", "0.4"]
    assert kwargs["start_new_session"] and kwargs["stdout"] == subprocess.DEVNULL
    # once per program (and the sender itself: once per start of the Pi)
    stuck["on"] = False
    write(None, b"\0" * 12)
    stuck["on"] = True
    write(None, b"\0" * 12)
    time.sleep(0.3)
    assert len(led.spawned) == 1


def test_no_led_stall_count_with_rq_umami_0(led, monkeypatch):
    monkeypatch.setenv("RQ_UMAMI", "0")
    _stall_writer(led, {"on": True})(None, b"\0" * 12)
    time.sleep(0.3)
    assert led.spawned == []


# ---------------------------------------------------------------------------
# Desktop icons that used to bypass the demo engine (Jan, 2026-10-04): they
# run through it now, so they are counted like every demo
# ---------------------------------------------------------------------------

_BOOKMARKS = os.path.join(_CFG, "desktop-bookmarks")
# icon -> (window title, the script it ran before, engine spec)
ROUTED_ICONS = {
    "led-ibm-demo.desktop": ("IBM LED Demo", "rq_led_ibm_demo.sh", "led-demos ibm-logo"),
    "led-test.desktop": ("LED Test", "rq_led_test.sh", "led-demos led-test"),
    "clear-leds.desktop": ("Clear All LEDs", "rq_clear_leds.sh", "led-demos clear-leds"),
    "rasq-led.desktop": ("RasQ-LED Demo", "rq_rasq_led.sh", "rasq-led"),
    "quantum-fractals.desktop": ("Quantum Fractals", "fractals.sh", "quantum-fractals"),
}


def _desktop(name):
    entry = {}
    for line in open(os.path.join(_BOOKMARKS, name)).read().splitlines():
        if "=" in line and not line.startswith("["):
            k, v = line.split("=", 1)
            entry[k] = v
    return entry


def _manifest(demo_id):
    with open(os.path.join(_CFG, "demo-manifests", f"rq_demo_{demo_id}.json")) as f:
        return json.load(f)


@pytest.mark.parametrize("icon", sorted(ROUTED_ICONS))
def test_the_icon_runs_its_old_script_through_the_engine(icon):
    title, script, spec = ROUTED_ICONS[icon]
    entry = _desktop(icon)
    assert entry["Exec"] == f'/usr/bin/rq_hold_on_error.sh -t "{title}" /usr/bin/rq_demo_run.sh {spec}'
    assert entry["TryExec"] == "/usr/bin/rq_demo_run.sh" and entry["Terminal"] == "true"
    demo_id, _, variant = spec.partition(" ")
    m = _manifest(demo_id)
    if variant:
        [v] = [v for v in m["variants"] if v["id"] == variant]
        launcher = v["entrypoint"]["launcher"]
    else:
        launcher = m["entrypoint"]["launcher"]
    # the same script as before, which the engine starts with exec: its own
    # stop hint, Ctrl+C and window-close handling stay as they were
    assert launcher == script and os.path.exists(os.path.join(_BIN, script))
    # built in: no consent dialog, no beta notice
    assert m["install"]["preinstalled"] is True and not m.get("maturity")
    assert not (variant and v.get("maturity"))


def test_no_terminal_icon_bypasses_the_engine_when_its_demo_has_a_manifest():
    launchers = {}
    for name in os.listdir(os.path.join(_CFG, "demo-manifests")):
        if name.startswith("rq_demo_") and "schema" not in name:
            m = json.load(open(os.path.join(_CFG, "demo-manifests", name)))
            for v in [m] + list(m.get("variants") or []):
                launcher = (v.get("entrypoint") or {}).get("launcher")
                if launcher:
                    launchers[launcher] = m["id"]
    for icon in sorted(os.listdir(_BOOKMARKS)):
        words = _desktop(icon).get("Exec", "").split()
        scripts = [os.path.basename(w) for w in words if w.startswith("/usr/bin/")]
        for s in scripts:
            assert s not in launchers, f"{icon} starts {s} directly; run it through rq_demo_run.sh"


def _engine_bin(tmp_path, launchers):
    """RQB2-bin and RQB2-config as links in tmp_path, with stub launchers that
    record how they were started."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in os.listdir(_BIN):
        if name not in launchers and not name.startswith("__"):
            os.symlink(os.path.join(_BIN, name), bin_dir / name)
    for name in launchers:
        _exe(bin_dir / name, f'#!/bin/bash\necho "LAUNCHED {name} $* counted=${{RQ_DEMO_COUNTED:-}}"\n')
    os.symlink(_CFG, tmp_path / "RQB2-config")
    return bin_dir


def _run_in_pty(argv, env, timeout=60):
    """Run argv with stdout on a pseudo terminal (stdin not a terminal):
    the window title escapes are printed then. Returns (exit code, output)."""
    import pty
    import select
    pid, fd = pty.fork()
    if pid == 0:  # pragma: no cover - child
        os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
        os.execvpe(argv[0], argv, env)
    out, end = b"", time.time() + timeout
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.2)
        if r:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                chunk = b""
            if chunk:
                out += chunk
                continue
        done, status = os.waitpid(pid, os.WNOHANG)
        if done:
            return os.waitstatus_to_exitcode(status), out.decode(errors="replace")
    os.kill(pid, 9)
    raise AssertionError(f"timed out: {out!r}")


@needs_bash
@pytest.mark.skipif(shutil.which("jq") is None, reason="jq required")
@pytest.mark.parametrize("icon", sorted(ROUTED_ICONS))
def test_a_routed_icon_starts_its_script_counts_once_and_keeps_its_title(tmp_path, icon):
    title, script, spec = ROUTED_ICONS[icon]
    env, log, _ = _box(tmp_path)
    bin_dir = _engine_bin(tmp_path, [script])
    hold = os.path.join(_BIN, "rq_hold_on_error.sh")
    rc, out = _run_in_pty(["bash", hold, "-t", title, str(bin_dir / "rq_demo_run.sh"), *spec.split()], env)
    assert rc == 0, out
    assert f"LAUNCHED {script}  counted={spec.split()[0]}" in out
    # every title the window gets is the icon's (not "LED Demos")
    titles = re.findall(r"\x1b\]0;([^\x07]*)\x07", out)
    assert titles and set(titles) == {title}, titles
    assert "Do you want to download" not in out and "This demo is new" not in out
    assert _await(log).splitlines() == [f"demo-start {spec.replace(' ', ':')} desktop"]


@needs_bash
def test_the_title_goes_only_to_the_engine_not_to_a_chooser(tmp_path):
    hold = open(os.path.join(_BIN, "rq_hold_on_error.sh")).read()
    assert '[ "$(basename "$1")" = "rq_demo_run.sh" ] && export RQ_WINDOW_TITLE="$title"' in hold
    engine = open(os.path.join(_BIN, "rq_demo_run.sh")).read()
    assert '"${RQ_WINDOW_TITLE:-$demo_name}"' in engine and "unset RQ_WINDOW_TITLE" in engine
    stub = tmp_path / "chooser.sh"
    _exe(stub, '#!/bin/sh\necho "title=${RQ_WINDOW_TITLE:-none}"\n')
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_hold_on_error.sh"), "-t", "Learning paths", str(stub)],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30,
                          env=dict(os.environ, XDG_CACHE_HOME=str(tmp_path)))
    assert proc.stdout.strip() == "title=none"


@needs_bash
@pytest.mark.skipif(shutil.which("jq") is None, reason="jq required")
def test_an_led_demo_re_run_with_sudo_is_counted_once(tmp_path):
    # run_python re-runs the engine as root for the GPIO (sudo -E): that pass
    # inherits RQ_DEMO_COUNTED and does not count again
    env, log, _ = _box(tmp_path)
    home = tmp_path / "home"
    manifests = home / ".local/config/demo-manifests"
    manifests.mkdir(parents=True)
    (manifests / "rq_demo_test-led.json").write_text(json.dumps({
        "id": "test-led", "name": "Test LED", "category": "led-demo",
        "entrypoint": {"type": "python", "script": "demo.py", "working_dir": "test-led"},
        "needs_hw": {"leds": True, "display": "none"}, "install": {"preinstalled": True}}))
    demo = home / "RasQberry-Two/demos/test-led"
    demo.mkdir(parents=True)
    (demo / "demo.py").write_text('import os\nprint("RAN uid", os.environ.get("FAKE_UID"))\n')
    venv = home / "RasQberry-Two/venv/RQB2/bin"
    venv.mkdir(parents=True)
    (venv / "activate").write_text("")
    os.symlink(sys.executable, venv / "python3")
    stubs = tmp_path / "stubs"
    _exe(stubs / "id", '#!/bin/sh\n[ "$1" = "-u" ] && { echo "${FAKE_UID:-1000}"; exit 0; }\nexec /usr/bin/id "$@"\n')
    _exe(stubs / "sudo", f'''#!/bin/sh
echo "sudo counted=${{RQ_DEMO_COUNTED:-}}" >> "{tmp_path}/sudo.log"
while [ "$1" = "-E" ] || [ "${{1#*=}}" != "$1" ]; do [ "$1" = "-E" ] || export "$1"; shift; done
FAKE_UID=0 exec "$@"
''')
    env.update(RQ_DEMO_HOW="desktop", SUDO_USER=os.environ.get("USER", "rasqberry"))
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_demo_run.sh"), "test-led"], env=env,
                          capture_output=True, text=True, timeout=90, stdin=subprocess.DEVNULL)
    assert "RAN uid 0" in proc.stdout, proc.stdout + proc.stderr
    assert (tmp_path / "sudo.log").read_text().splitlines()[0] == "sudo counted=test-led"
    time.sleep(0.5)
    assert _await(log).splitlines() == ["demo-start test-led desktop"]


@needs_bash
@pytest.mark.parametrize("extra,how", [({"RQ_DEMO_HOW": "desktop"}, "desktop"),
                                       ({"RQ_ERROR_FILE": "/dev/null"}, "menu"),
                                       ({"RQ_DEMO_HOW": "learning-path"}, "learning-path")])
def test_my_quantum_programs_counts_its_start(tmp_path, extra, how):
    env, log, _ = _box(tmp_path)
    bin_dir = _engine_bin(tmp_path, ["rq_learner_setup.sh"])
    env.update(extra)
    # no JupyterLab here: it stops after the count
    subprocess.run(["bash", str(bin_dir / "rq_my_programs.sh")], env=env, capture_output=True,
                   text=True, timeout=60, stdin=subprocess.DEVNULL)
    assert _await(log).splitlines() == [f"demo-start my-quantum-programs {how}"]


@needs_bash
def test_my_quantum_programs_from_root_counts_once(tmp_path):
    # started as root (a learning path in raspi-config), it re-runs itself as
    # the desktop user with a fresh environment: RQ_DEMO_COUNTED goes along
    env, log, _ = _box(tmp_path)
    stubs = tmp_path / "stubs"
    _exe(stubs / "id", '#!/bin/sh\n[ "$1" = "-u" ] && { echo 0; exit 0; }\nexec /usr/bin/id "$@"\n')
    _exe(stubs / "sudo", f'#!/bin/sh\nprintf "%s\\n" "$@" > "{tmp_path}/sudo-args"\n')
    env.update(RQ_DEMO_HOW="learning-path", SUDO_USER="rasqberry")
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_my_programs.sh")], env=env,
                          capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    assert proc.returncode == 0, proc.stderr
    assert "RQ_DEMO_COUNTED=my-quantum-programs" in (tmp_path / "sudo-args").read_text().split()
    assert _await(log).splitlines() == ["demo-start my-quantum-programs learning-path"]


@needs_bash
@pytest.mark.skipif(shutil.which("jq") is None, reason="jq required")
def test_closing_a_routed_icons_window_still_stops_its_demo(tmp_path):
    # C2: the engine starts the launcher with exec, so a closed window (the
    # TERM rq_hold_on_error.sh sends) reaches the launcher's own traps, as
    # when the icon started it directly
    lifecycle = _load("test_demo_lifecycle_for_umami", os.path.join(_HERE, "test_demo_lifecycle.py"))
    env, _, _ = _box(tmp_path)
    marker = tmp_path / "stopped"
    bin_dir = _engine_bin(tmp_path, [])
    os.unlink(bin_dir / "rq_rasq_led.sh")
    _exe(bin_dir / "rq_rasq_led.sh", f'#!/bin/bash\ntrap \'echo stopped > "{marker}"; exit 143\' TERM HUP\n'
                                     'echo READY\nwhile :; do sleep 0.2; done\n')
    _exe(tmp_path / "stubs" / "script", lifecycle._PTY_SCRIPT)
    hold = os.path.join(_BIN, "rq_hold_on_error.sh")
    p = lifecycle._Pty(f'exec bash "{hold}" -t "RasQ-LED Demo" "{bin_dir}/rq_demo_run.sh" rasq-led', env=env)
    assert p.read_until("READY", 30), p.out
    os.killpg(p.pid, signal.SIGHUP)          # the window is closed
    assert p.wait() == 143
    assert marker.read_text().strip() == "stopped"


@needs_bash
@pytest.mark.parametrize("args,log", [(["rasq-led"], "rasq-led"), (["led-demos", "ibm-logo"], "led-demos-ibm-logo"),
                                      (["fun-with-quantum", "coin-game"], "fun-with-quantum-coin-game")])
def test_an_icons_log_keeps_variants_apart_and_the_rig_finds_it(tmp_path, args, log):
    stub = tmp_path / "rq_demo_run.sh"
    _exe(stub, "#!/bin/sh\nexit 0\n")
    subprocess.run(["bash", os.path.join(_BIN, "rq_hold_on_error.sh"), "-t", "T", str(stub), *args],
                   capture_output=True, stdin=subprocess.DEVNULL, timeout=30,
                   env=dict(os.environ, XDG_CACHE_HOME=str(tmp_path / "cache")))
    hold = open(os.path.join(_BIN, "rq_hold_on_error.sh")).read()
    assert 'name="$2${3:+-$3}"' in hold
    # the rig's smoke test computes the same name to find the icon's window
    smoke = open(os.path.join(_ROOT, "tests", "rig", "pi", "demo_smoke.sh")).read()
    code = smoke.split("logname=$(python3 -c '", 1)[1].split("' \"$(sed", 1)[0]
    exec_line = f'/usr/bin/rq_hold_on_error.sh -t "T" /usr/bin/rq_demo_run.sh {" ".join(args)}'
    out = subprocess.run([sys.executable, "-c", code, exec_line], capture_output=True, text=True).stdout
    assert out.strip() == log
