"""
Tests for RQB2-bin/rq_slot_indicator.py (#242): the taskbar badge's state,
the tooltip and menu texts, the once-only notices, and that it stays away
from the standard image and single-system cards.

Only the pure functions run here (no D-Bus, no panel); the CONFIG
partition is a temp directory.
"""

import importlib.util
import os
import re
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, "..", "..")
_BIN = os.path.join(_ROOT, "RQB2-bin")

_spec = importlib.util.spec_from_file_location("rq_slot_indicator",
                                               os.path.join(_BIN, "rq_slot_indicator.py"))
ind = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ind)
rn = ind.rn

DEV = "development-2026-10-04-040217"
DEV_NEW = "development-2026-10-12-010101"
BETA = "beta-2026-10-03-095636"
BETA_NEW = "beta-2026-10-10-120000"

AUTOBOOT = {
    "A": "[all]\ntryboot_a_b=1\nboot_partition=2\nboot_partition_fallback=3\n\n"
         "[tryboot]\nboot_partition=3\nboot_partition_fallback=2\n",
    "B": "[all]\ntryboot_a_b=1\nboot_partition=3\nboot_partition_fallback=2\n\n"
         "[tryboot]\nboot_partition=2\nboot_partition_fallback=3\n",
}


# ---------------------------------------------------------------------------
# Where it runs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status,run", [
    ({"layout": "ab", "current": "B", "card_mode": "dual"}, True),
    ({"layout": "ab", "current": "A", "card_mode": "dual-pending"}, True),   # B not set up yet
    ({"layout": "ab", "current": "A", "card_mode": "single"}, False),        # card under 64 GB
    ({"layout": "ab", "current": "A", "card_mode": "single-pending"}, False),
    ({"layout": "single", "card_mode": "standard"}, False),                  # standard image
    ({"layout": "ab", "current": "UNKNOWN", "card_mode": "dual"}, False),
    ({}, False),                                                             # nothing known
])
def test_runs_only_on_cards_with_two_systems(status, run):
    assert ind.should_run(status) is run


def test_exits_at_once_on_a_standard_image(tmp_path):
    status = tmp_path / "status"
    status.write_text("layout=single\ncard_mode=standard\n")
    env = dict(os.environ, RQ_SLOT_STATUS_FILE=str(status), XDG_STATE_HOME=str(tmp_path / "state"))
    proc = subprocess.run(["python3", os.path.join(_BIN, "rq_slot_indicator.py")],
                          env=env, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert "not an A/B card with two systems" in (tmp_path / "state/rasqberry/slot-indicator.log").read_text()


# ---------------------------------------------------------------------------
# Reading the CONFIG partition
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,slot", [(AUTOBOOT["A"], "A"), (AUTOBOOT["B"], "B"), ("", ""),
                                       ("[all]\nboot_partition=7\n", "")])
def test_autoboot_default(text, slot):
    assert ind.autoboot_default(text) == slot


def test_read_live(tmp_path):
    (tmp_path / "autoboot.txt").write_text(AUTOBOOT["A"])
    (tmp_path / "target-slot").write_text("B\n")
    (tmp_path / "slot-B-incomplete").write_text("x\n")
    (tmp_path / "last-switch-failed").write_text("slot=B\nreason=r\ntime=2026-10-04 05:00:00\n")
    live = ind.read_live(str(tmp_path))
    assert live == {"present": True, "target": "B", "confirmed": False, "default": "A",
                    "failed": {"slot": "B", "reason": "r", "time": "2026-10-04 05:00:00"},
                    "incomplete": {"B"}}
    assert ind.read_live(str(tmp_path / "missing"))["present"] is False


def _status(current="B", a=DEV, b=DEV, **kw):
    s = {"layout": "ab", "current": current, "confirmed": "yes", "default": current,
         "pending": "", "slot_a": a, "slot_b": b, "card_mode": "dual"}
    s.update(kw)
    return s


def _live(target="", confirmed=True, default="B", failed=None, incomplete=()):
    return {"present": True, "target": target, "confirmed": confirmed, "default": default,
            "failed": failed or {}, "incomplete": set(incomplete)}


def test_live_files_win_over_the_status_snapshot():
    info = ind.slot_info(_status(confirmed="yes", default="B"),
                         _live(target="A", confirmed=False, default="B", incomplete="A"), DEV_NEW)
    assert (info["target"], info["confirmed"], info["default"]) == ("A", False, "B")
    assert info["contents"] == {"A": "INCOMPLETE", "B": DEV_NEW}    # running slot = /etc version
    # without the CONFIG partition the snapshot counts
    info = ind.slot_info(_status(confirmed="no", default="A", pending="A"), {"present": False}, DEV)
    assert (info["target"], info["confirmed"], info["default"]) == ("A", False, "A")


def test_fake_failure_only_for_trials():
    fake = {"slot": "A", "reason": "(trial)", "time": "t"}
    assert ind.slot_info(_status(), _live(), DEV, fake)["failure"] == fake
    real = {"slot": "A", "reason": "real", "time": "r"}
    assert ind.slot_info(_status(), _live(failed=real), DEV, fake)["failure"] == real


# ---------------------------------------------------------------------------
# The state machine (order matters)
# ---------------------------------------------------------------------------

FAIL = {"slot": "A", "reason": "Qiskit check failed", "time": "2026-10-04 05:00:00",
        "version": "development-2026-10-05-010101"}


@pytest.mark.parametrize("name,live,acked,state", [
    ("normal start", _live(), "", ("ok", "")),
    ("trial start of B", _live(target="B", confirmed=False, default="A"), "", ("checking", "")),
    ("switch to A requested", _live(target="A", confirmed=False, default="B"), "", ("pending", "A")),
    ("after a rollback", _live(confirmed=False, default="A"), "", ("pending", "A")),
    ("first start, not confirmed yet", _live(confirmed=False), "", ("checking", "")),
    ("confirmed, other start slot", _live(default="A"), "", ("pending", "A")),
    ("failed update, not seen", _live(failed=FAIL), "", ("failed", "")),
    ("failed update, seen in the menu", _live(failed=FAIL), FAIL["time"], ("ok", "")),
    ("failure beats a pending switch", _live(target="A", confirmed=False, failed=FAIL), "",
     ("failed", "")),
    ("seen failure, pending switch", _live(target="A", confirmed=False, failed=FAIL), FAIL["time"],
     ("pending", "A")),
    ("an older failure was seen, a new one not", _live(failed=FAIL), "2026-09-01 00:00:00",
     ("failed", "")),
])
def test_badge_state(name, live, acked, state):
    info = ind.slot_info(_status(current="B"), live, DEV)
    assert ind.badge_state(info, acked) == state, name


# ---------------------------------------------------------------------------
# The failure sentence (Jan: name the slots, never "didn't start")
# ---------------------------------------------------------------------------

FAILURE_CASES = [
    # (last-switch-failed, status current, slot_a, slot_b, running version, incomplete, sentence)
    ("slot=B\nreason=Qiskit check failed (Qiskit not installed)\ntime=2026-10-04 05:00:00\n"
     "version=development-2026-10-05-010101\n", "A", DEV, "development-2026-10-05-010101", DEV, "",
     "The update of Slot B to development-2026-10-05-010101 didn't work, so Slot A "
     "(development-2026-10-04-040217) is running again."),
    # tryboot lost twice after an update: no version= - what Slot A holds (root wrote the status)
    ("slot=A\nreason=Slot A was tried twice without success\n"
     "time=2026-10-04 05:00:00\nupdate=yes\n", "B", BETA, DEV, DEV, "",
     "The update of Slot A to beta-2026-10-03-095636 didn't work, so Slot B "
     "(development-2026-10-04-040217) is running again."),
    # a plain switch (no update wrote the slot): Jan's wording, no version of the target
    ("slot=A\nreason=Slot A was tried twice without success\n"
     "time=2026-10-04 05:00:00\nupdate=no\n", "B", BETA, DEV, DEV, "",
     "Switching to Slot A didn't work, so Slot B (development-2026-10-04-040217) is running again."),
    ("slot=B\nreason=Qiskit check failed\ntime=t\nupdate=no\nversion=" + BETA + "\n",
     "A", DEV, BETA, DEV, "",
     "Switching to Slot B didn't work, so Slot A (development-2026-10-04-040217) is running again."),
    ("slot=B\nreason=the desktop did not come up within 300 s\ntime=t\nupdate=no\n",
     "B", DEV, DEV, DEV, "",
     "Switching to Slot B didn't work: the desktop did not come up within 300 s."),
    # the other slot was left unfinished: no version to name
    ("slot=A\nreason=x\ntime=t\n", "B", BETA, DEV, DEV, "A",
     "The update of Slot A didn't work, so Slot B (development-2026-10-04-040217) is running again."),
    ("slot=A\nreason=x\ntime=t\n", "B", "UNKNOWN", DEV, DEV, "",
     "The update of Slot A didn't work, so Slot B (development-2026-10-04-040217) is running again."),
    # no way back (autoboot already started the failed slot): it is still running
    ("slot=B\nreason=the desktop did not come up within 300 s\ntime=t\n", "B", DEV, DEV, DEV, "",
     "The update of Slot B to development-2026-10-04-040217 didn't work: the desktop did not "
     "come up within 300 s."),
    # an old notice without slot=: the other slot
    ("reason=old\n", "A", DEV, BETA, DEV, "",
     "The update of Slot B to beta-2026-10-03-095636 didn't work, so Slot A "
     "(development-2026-10-04-040217) is running again."),
]


@pytest.mark.parametrize("notice,current,slot_a,slot_b,version,incomplete,sentence", FAILURE_CASES)
def test_failure_text_python_and_shell_agree(tmp_path, notice, current, slot_a, slot_b, version,
                                             incomplete, sentence):
    config = tmp_path / "config"
    config.mkdir()
    (config / "last-switch-failed").write_text(notice)
    if incomplete:
        (config / f"slot-{incomplete}-incomplete").write_text("x\n")
    status = tmp_path / "slot-status"
    status.write_text(f"layout=ab\ncurrent={current}\nslot_a={slot_a}\nslot_b={slot_b}\n")
    (tmp_path / "version").write_text(version + "\n")
    info = ind.slot_info(rn.read_kv(str(status)), ind.read_live(str(config)), version)
    assert ind.failure_text(info["failure"], info["current"], info["version"],
                            info["contents"]) == sentence
    env = dict(os.environ, RQ_BOOT_COMMON_DIR=str(config), RQ_SLOT_STATUS_FILE=str(status),
               RQ_VERSION_FILE=str(tmp_path / "version"))
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_slot_status.sh"), "failure-notice"],
                          env=env, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == sentence


def test_no_failure_no_sentence(tmp_path):
    env = dict(os.environ, RQ_BOOT_COMMON_DIR=str(tmp_path), RQ_SLOT_STATUS_FILE=str(tmp_path / "s"))
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_slot_status.sh"), "failure-notice"],
                          env=env, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0 and proc.stdout == ""


# ---------------------------------------------------------------------------
# Tooltip and menu
# ---------------------------------------------------------------------------

def _texts(items):
    return [p.get("label", "---") for _, p in items]


def test_tooltip_per_state():
    info = ind.slot_info(_status(), _live(), DEV)
    assert ind.tooltip(info, "ok", "", [], {}) == (
        "RasQberry - Slot B (confirmed)", "Version: development-2026-10-04-040217")
    assert ind.tooltip(info, "checking", "", [], {})[0] == "RasQberry - Slot B (being checked)"
    title, body = ind.tooltip(info, "pending", "A", [], {})
    assert title == "RasQberry - Slot B (restart pending)"
    assert body.endswith("Slot A starts at the next restart.")
    info = ind.slot_info(_status(current="A", a=DEV, b="development-2026-10-05-010101"),
                         _live(default="A", failed=dict(FAIL, slot="B")), DEV)
    title, body = ind.tooltip(info, "failed", "", [], {})
    assert title == "RasQberry - Slot A (the update didn't work)"
    assert "so Slot A (development-2026-10-04-040217) is running again" in body
    info["failure"] = dict(info["failure"], update="no")
    title, body = ind.tooltip(info, "failed", "", [], {})
    assert title == "RasQberry - Slot A (the switch didn't work)"
    assert body.endswith("Switching to Slot B didn't work, so Slot A "
                         "(development-2026-10-04-040217) is running again.")


def test_menu_for_a_confirmed_slot():
    info = ind.slot_info(_status(current="B", a=BETA), _live(), DEV)
    state = ind.badge_state(info)
    items = ind.menu_items(info, *state, [], ind.device_for_advice(info))
    assert _texts(items) == [
        "Running: Slot B (confirmed)",
        "Version: development-2026-10-04-040217",
        "Slot A: beta-2026-10-03-095636 (fallback)",
        "---",
        "System Info…",
        "Software & Image Updates…",
    ]
    assert all(p.get("enabled") is False for i, p in items if i < 10)
    assert [i for i, p in items if p.get("enabled", True) and p.get("type") != "separator"] == [11, 12]


def test_menu_with_a_failure_pending_switch_and_updates():
    info = ind.slot_info(_status(current="A", a=DEV, b="development-2026-10-05-010101"),
                         _live(target="B", confirmed=False, default="A", failed=dict(FAIL, slot="B")),
                         DEV)
    device = ind.device_for_advice(info)
    advices = [{"kind": "update", "tag": BETA_NEW, "stream": "beta", "entry": {}, "for_running": True,
                "other": None, "target": "B", "plan": None},
               {"kind": "withdrawn", "tag": DEV, "reason": "LED driver bug"}]
    state = ind.badge_state(info)
    texts = _texts(ind.menu_items(info, *state, advices, device))
    assert texts == [
        "Running: Slot A (restart pending)",
        "Version: development-2026-10-04-040217",
        "Slot B: development-2026-10-05-010101 (fallback)",
        "Slot B starts at the next restart",
        "The update of Slot B to development-2026-10-05-010101 didn't work,",
        "so Slot A (development-2026-10-04-040217) is running again.",
        "Reason: Qiskit check failed",
        "This release was withdrawn: LED driver bug",
        "New beta available: beta-2026-10-10-120000",
        "---",
        "System Info…",
        "Software & Image Updates…",
        "---",
        "What's new in beta-2026-10-10-120000…",
    ]


@pytest.mark.parametrize("status,live,line", [
    (_status(current="B", a="EMPTY"), _live(), "Slot A: empty"),
    (_status(current="B", a="UNKNOWN"), _live(), "Slot A: not known yet"),
    (_status(current="B", a="v1.0.0"), _live(), "Slot A: stable v1.0.0 (fallback)"),
    (_status(current="B", a=BETA), _live(target="B", confirmed=False, default="A"),
     "Slot A: beta-2026-10-03-095636 (start slot)"),
    (_status(current="A", b="EMPTY", card_mode="dual-pending"), _live(default="A"),
     "Slot B: not set up yet"),
    (_status(current="B", a=BETA), _live(incomplete="A"), "Slot A: unfinished update"),
])
def test_other_slot_line(status, live, line):
    assert ind.describe_other(ind.slot_info(status, live, DEV)) == line


def test_no_stable_testing_labels_and_no_promote():
    # ping-pong: no "stable/testing" slot labels, PROMOTE is gone
    for path in ("rq_slot_indicator.py", "rq_release_notice.py", "rq_slot_status.sh"):
        text = open(os.path.join(_BIN, path)).read()
        assert "PROMOTE" not in text and "promote" not in text.lower(), path
        assert not re.search(r"\((stable|testing)\)", text), path


# ---------------------------------------------------------------------------
# What's new window
# ---------------------------------------------------------------------------

def test_whats_new_window_text():
    releases = {"streams": {"beta": {"tag": BETA_NEW, "release_date": "2026-10-10",
                                     "release_url": "https://x/beta", "ab_image_download_size": 1668588980}}}
    info = ind.slot_info(_status(current="B", a=BETA), _live(), DEV)
    device = ind.device_for_advice(info)
    advice = rn.advise(device, releases, {}, "s", rn.parse_time("2027-01-01"))[0]
    text = ind.whats_new(advice, device, releases, {"beta": ["Line one", "Line two"]})
    assert text["title"] == "What's new in beta-2026-10-10-120000"
    assert text["heading"] == "New beta available: beta-2026-10-10-120000"
    assert text["meta"] == "Released 10 October 2026, about 1.7 GB"
    assert text["highlights"] == ["Line one", "Line two"]
    assert text["install_label"] == "Install into Slot A…"          # the slot not running
    assert text["strong"] is True                                     # Slot A: the only beta
    assert text["warning"].startswith("This replaces Slot A's beta system (beta-2026-10-03-095636), "
                                      "the only stable or beta system on this card.")
    assert text["release_url"] == "https://x/beta"
    assert ind.whats_new(advice, device, releases, {})["highlights"] == [
        "No summary yet: see the release notes."]


@pytest.mark.parametrize("status,live,wait", [
    # settled: the update can go ahead
    (_status(current="B"), _live(default="B"), ""),
    # first start, not confirmed yet, no trial: rq_update_slot.sh goes ahead too
    (_status(current="B"), _live(confirmed=False, default="B"), ""),
    # a switch to the other slot was asked for: not exit 28 either
    (_status(current="B"), _live(target="A", confirmed=False, default="B"), ""),
    # on trial: Slot A is the way back (exit 28)
    (_status(current="B"), _live(target="B", confirmed=False, default="A"),
     "Slot B, the system you are running, is still on trial. Updates wait until the health "
     "check has confirmed it, a few minutes after a good start."),
    # a rollback waits for its restart (exit 28)
    (_status(current="B"), _live(default="A"),
     "The next restart starts Slot A, not Slot B that is running now. Updates wait until "
     "then: restart first."),
    # from the status snapshot when the CONFIG files cannot be read
    (_status(current="A", confirmed="no", pending="A", default="B"), {"present": False},
     "Slot A, the system you are running, is still on trial. Updates wait until the health "
     "check has confirmed it, a few minutes after a good start."),
])
def test_update_wait_follows_exit_28(status, live, wait):
    assert ind.update_wait(ind.slot_info(status, live, DEV)) == wait


def test_whats_new_has_no_install_button_while_updates_wait():
    releases = {"streams": {"beta": {"tag": BETA_NEW, "release_date": "2026-10-10"}}}
    info = ind.slot_info(_status(current="B", a=BETA), _live(target="B", confirmed=False,
                                                            default="A"), DEV)
    device = ind.device_for_advice(info)
    advice = rn.advise(device, releases, {}, "s", rn.parse_time("2027-01-01"))[0]
    assert advice["target"] == "A"
    text = ind.whats_new(advice, device, releases, {}, wait=ind.update_wait(info))
    assert text["install_label"] == ""
    assert text["wait"].startswith("Slot B, the system you are running, is still on trial.")
    settled = ind.whats_new(advice, device, releases, {})
    assert settled["install_label"] == "Install into Slot A…" and settled["wait"] == ""


# ---------------------------------------------------------------------------
# Once per failure, once per release
# ---------------------------------------------------------------------------

def test_notice_book(tmp_path):
    book = ind.NoticeBook(str(tmp_path))
    assert book.failure_to_announce(FAIL) is True
    assert book.failure_to_announce(FAIL) is False
    adv = [{"kind": "update", "tag": BETA_NEW}, {"kind": "withdrawn", "tag": DEV},
           {"kind": "update", "tag": DEV_NEW}]
    assert [a["tag"] for a in book.releases_to_announce(adv)] == [BETA_NEW, DEV_NEW]
    assert book.releases_to_announce(adv) == []
    assert book.ack(FAIL) is True and book.ack(FAIL) is False
    book.save()
    again = ind.NoticeBook(str(tmp_path))                 # a new login
    assert again.failure_to_announce(FAIL) is False
    assert again.releases_to_announce(adv) == []
    assert again.acked == FAIL["time"]
    assert again.failure_to_announce(dict(FAIL, time="2026-11-01 00:00:00")) is True
    assert oct(os.stat(tmp_path / "slot-indicator.json").st_mode & 0o777) == "0o600"


def test_notice_book_survives_a_broken_file(tmp_path):
    (tmp_path / "slot-indicator.json").write_text("{broken")
    assert ind.NoticeBook(str(tmp_path)).releases == []


# ---------------------------------------------------------------------------
# Wording and wiring
# ---------------------------------------------------------------------------

USER_FACING = [
    "RQB2-bin/rq_slot_indicator.py", "RQB2-bin/rq_release_notice.py", "RQB2-bin/rq_slot_status.sh",
    "RQB2-bin/rq_health_check.py", "RQB2-bin/rq_slot_manager.sh", "RQB2-bin/rq_info.sh",
    "RQB2-system/etc/update-motd.d/20-rasqberry",
    "RQB2-system/etc/xdg/autostart/rasqberry-slot-indicator.desktop",
]


@pytest.mark.parametrize("path", USER_FACING)
def test_never_says_did_not_start(path):
    text = open(os.path.join(_ROOT, path)).read()
    assert not re.search(r"did(n't| not) start", text), path


def test_autostart_entry():
    text = open(os.path.join(_ROOT, "RQB2-system/etc/xdg/autostart/rasqberry-slot-indicator.desktop")).read()
    exec_line = re.search(r"^Exec=(\S+)", text, re.M).group(1)
    assert exec_line == "/usr/bin/rq_slot_indicator.py"
    assert os.access(os.path.join(_BIN, "rq_slot_indicator.py"), os.X_OK)
    assert "NoDisplay=true" in text and "Type=Application" in text


def test_daily_check_writes_the_login_line_and_login_shows_it():
    unit = open(os.path.join(_ROOT, "RQB2-system/etc/systemd/system/rasqberry-update-check.service")).read()
    assert "ExecStart=-/usr/bin/rq_release_notice.py --refresh --system" in unit
    hook = open(os.path.join(_ROOT, "RQB2-system/etc/profile.d/rasqberry-firstlogin.sh")).read()
    assert "head -n 1 /var/lib/rasqberry/update-notice" in hook


def test_badge_renders_when_cairo_is_there():
    pytest.importorskip("cairo")
    for state in ("ok", "checking", "pending", "failed"):
        w, h, data = ind.render_badge("B", state, dot=state == "ok")
        assert (w, h) == (64, 64) and len(data) == 64 * 64 * 4
