"""
Tests for RQB2-bin/rq_slot_status.sh write (#242): the root-written
/run/rasqberry/slot-status the taskbar indicator reads, on a fake A/B card
(the stubs of test_slot_manager.py) and on a standard image; how the slot
manager and the health check use it; and the withdrawn releases in the
shell tools (update check, release picker).
"""

import importlib.util
import json
import os
import shutil
import stat
import subprocess

import pytest

from test_slot_manager import _run as _manager, _system, card  # noqa: F401 (fixture)

_HERE = os.path.dirname(os.path.abspath(__file__))
_BIN = os.path.join(_HERE, "..", "..", "RQB2-bin")
_STATUS = os.path.join(_BIN, "rq_slot_status.sh")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None or shutil.which("jq") is None,
                                reason="bash and jq are required")


def _write(card, **env):
    out = card["tmp"] / "run" / "rasqberry" / "slot-status"
    (card["tmp"] / "version").write_text("beta-2026-09-30-221656\n")
    e = dict(card["env"], RQ_SLOT_STATUS_FILE=str(out), RQ_VERSION_FILE=str(card["tmp"] / "version"),
             **env)
    proc = subprocess.run(["bash", _STATUS, "write"], capture_output=True, text=True, env=e,
                          stdin=subprocess.DEVNULL, timeout=60)
    return proc, out


def _kv(path):
    return dict(line.split("=", 1) for line in path.read_text().splitlines()
                if line and not line.startswith("#"))


def test_write_on_an_ab_card(card):
    proc, out = _write(card)
    assert proc.returncode == 0, proc.stderr
    s = _kv(out)
    assert s["layout"] == "ab" and s["current"] == "A" and s["card_mode"]
    assert s["slot_a"] == "beta-2026-09-30-221656" and s["slot_b"] == "EMPTY"
    assert s["version"] == "beta-2026-09-30-221656" and s["stream"] == "beta"
    assert s["other"] == "B" and s["other_version"] == "EMPTY"
    assert s["stream_a"] == "beta" and s["stream_b"] == ""
    assert stat.S_IMODE(os.stat(out).st_mode) == 0o644          # the desktop user reads it
    assert os.listdir(out.parent) == ["slot-status"]            # no temp file left


def test_write_names_the_other_slots_stream(card):
    _system(card["b"], "development-2026-10-04-040217")
    s = _kv(_write(card)[1])
    assert s["slot_b"] == s["other_version"] == "development-2026-10-04-040217"
    assert s["stream_b"] == "dev"


def test_write_on_a_standard_image(card):
    card["env"]["FAKE_P1_LABEL"] = "bootfs"
    proc, out = _write(card)
    assert proc.returncode == 0, proc.stderr
    s = _kv(out)
    assert s["layout"] == "single" and s["card_mode"] == "standard" and "other" not in s


def test_write_replaces_the_file_in_one_step(card):
    proc, out = _write(card)
    first = os.stat(out).st_ino
    proc, out = _write(card)
    assert proc.returncode == 0 and os.stat(out).st_ino != first   # rename, not rewrite


def test_write_fails_cleanly_without_a_summary(card, tmp_path):
    proc, out = _write(card, RQ_SLOT_MANAGER=str(tmp_path / "missing"))
    assert proc.returncode != 0 and not out.exists()


def test_slot_manager_status_uses_the_same_sentence(card):
    _system(card["b"], "beta-2026-10-15-101010")
    (card["config"] / "last-switch-failed").write_text(
        "slot=B\nreason=Qiskit check failed\ntime=2026-10-15 10:00:00\nversion=beta-2026-10-15-101010\n")
    (card["tmp"] / "version").write_text("beta-2026-09-30-221656\n")
    card["env"]["RQ_VERSION_FILE"] = str(card["tmp"] / "version")
    card["env"]["RQ_SLOT_STATUS_FILE"] = str(card["tmp"] / "no-status")
    proc = _manager(card, "status")
    assert ("The update of Slot B to beta-2026-10-15-101010 didn't work, so Slot A "
            "(beta-2026-09-30-221656) is running again.") in proc.stderr
    assert "Reason: Qiskit check failed" in proc.stderr
    assert "When: 2026-10-15 10:00:00" in proc.stderr
    assert "FAILED and was rolled back" not in proc.stderr + proc.stdout


def test_slot_manager_status_says_when_a_plain_switch_failed(card):
    _system(card["b"], "beta-2026-10-15-101010")
    (card["config"] / "last-switch-failed").write_text(
        "slot=B\nreason=Slot B was tried twice without success\ntime=2026-10-15 10:00:00\n"
        "update=no\n")
    (card["tmp"] / "version").write_text("beta-2026-09-30-221656\n")
    card["env"]["RQ_VERSION_FILE"] = str(card["tmp"] / "version")
    card["env"]["RQ_SLOT_STATUS_FILE"] = str(card["tmp"] / "no-status")
    proc = _manager(card, "status")
    assert ("Switching to Slot B didn't work, so Slot A (beta-2026-09-30-221656) is running "
            "again.") in proc.stderr
    assert "Reason: Slot B was tried twice without success" in proc.stderr
    assert "The update of" not in proc.stderr


def test_a_failure_dated_by_the_request_reads_the_same_everywhere(card, hc, monkeypatch):
    # rig, 2026-10-04: Slot B's clock said 11:09 at a failure at about 12:25.
    # The notice now carries the request time as time= (plus requested= and
    # clock=); "When:", the 7-day login line and the indicator's once-per-
    # failure key all go by time=, which nothing rewrites later.
    import time as _time
    requested = "2026-10-04 12:24:10"
    asked = int(_time.mktime(_time.strptime(requested, "%Y-%m-%d %H:%M:%S")))
    config = card["config"]
    _system(card["b"], "beta-2026-10-15-101010")
    (config / "target-slot").write_text("B\n")
    (config / "slot-B-updated").write_text("version=beta-2026-10-15-101010\n")
    (config / "switch-requested").write_text(f"slot=B\ntime={requested}\nepoch={asked}\n")
    monkeypatch.setattr(hc, "TIME_SYNCED", card["tmp"] / "not-synchronised")
    monkeypatch.setattr(hc, "now_epoch", lambda: asked - 75 * 60)
    hc.record_failed_switch(config, "B", "virtual environment missing", "beta-2026-10-15-101010")
    notice = (config / "last-switch-failed").read_text()
    assert f"time={requested}\n" in notice and "clock=" in notice

    (card["tmp"] / "version").write_text("beta-2026-09-30-221656\n")
    card["env"]["RQ_VERSION_FILE"] = str(card["tmp"] / "version")
    card["env"]["RQ_SLOT_STATUS_FILE"] = str(card["tmp"] / "no-status")
    proc = _manager(card, "status")
    assert ("The update of Slot B to beta-2026-10-15-101010 didn't work, so Slot A "
            "(beta-2026-09-30-221656) is running again.") in proc.stderr
    assert proc.stderr.count("When: ") == 1 and f"When: {requested}" in proc.stderr

    def login(days):
        env = dict(card["env"], RQ_HOMES_DIR=str(card["tmp"] / "home"),
                   RQ_NOW_EPOCH=str(asked + int(days * 86400)))
        return subprocess.run(["bash", _STATUS, "failure-notice", "--login"], env=env,
                              capture_output=True, text=True, timeout=30).stdout.strip()
    assert login(6.9).startswith("The update of Slot B")
    assert login(7.1) == ""

    spec = importlib.util.spec_from_file_location("rq_slot_indicator",
                                                  os.path.join(_BIN, "rq_slot_indicator.py"))
    ind = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ind)
    failure = ind.rn.read_kv(str(config / "last-switch-failed"))
    assert ind.failure_key(failure) == requested
    book = ind.NoticeBook(str(card["tmp"] / "state"))
    assert book.failure_to_announce(failure) is True and book.ack(failure) is True
    book.save()
    again = ind.NoticeBook(str(card["tmp"] / "state"))
    assert again.failure_to_announce(failure) is False and again.ack(failure) is False


@pytest.mark.parametrize("extra", ["", "requested=2026-10-15 09:58:30\nclock=2026-10-15 08:44:56\n"])
def test_old_and_new_notices_render_alike(card, extra):
    # "": a notice from an older health check, without requested=/clock=
    _system(card["b"], "beta-2026-10-15-101010")
    (card["config"] / "last-switch-failed").write_text(
        "slot=B\nreason=Qiskit check failed\ntime=2026-10-15 10:00:00\nupdate=no\n" + extra)
    (card["tmp"] / "version").write_text("beta-2026-09-30-221656\n")
    card["env"]["RQ_VERSION_FILE"] = str(card["tmp"] / "version")
    card["env"]["RQ_SLOT_STATUS_FILE"] = str(card["tmp"] / "no-status")
    proc = _manager(card, "status")
    assert ("Switching to Slot B didn't work, so Slot A (beta-2026-09-30-221656) is running "
            "again.") in proc.stderr
    assert "Reason: Qiskit check failed" in proc.stderr
    assert proc.stderr.count("When: ") == 1 and "When: 2026-10-15 10:00:00" in proc.stderr


@pytest.mark.parametrize("update,label,sentence", [
    ("yes", "Last update:", "The update of Slot B to beta-2026-10-15-101010 didn't work, so Slot A "
                            "(beta-2026-09-30-221656) is running again."),
    ("no", "Last switch:", "Switching to Slot B didn't work, so Slot A (beta-2026-09-30-221656) "
                           "is running again."),
])
def test_system_info_names_a_failed_update_or_switch(card, update, label, sentence):
    _system(card["b"], "beta-2026-10-15-101010")
    (card["config"] / "last-switch-failed").write_text(
        f"slot=B\nreason=x\ntime=2026-10-15 10:00:00\nupdate={update}\n"
        "version=beta-2026-10-15-101010\n")
    (card["tmp"] / "version").write_text("beta-2026-09-30-221656\n")
    env = dict(card["env"], RQ_VERSION_FILE=str(card["tmp"] / "version"),
               RQ_SLOT_STATUS_FILE=str(card["tmp"] / "no-status"),
               RQ_BUILD_JSON=str(card["tmp"] / "none.json"))
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_info.sh")], capture_output=True,
                          text=True, env=env, stdin=subprocess.DEVNULL, timeout=60)
    lines = [l for l in proc.stdout.splitlines() if l.startswith(("Last update:", "Last switch:"))]
    assert lines == [f"{label:<19}{sentence}"], proc.stdout + proc.stderr


# ---------------------------------------------------------------------------
# The login line: 7 days, or until the taskbar menu was opened (Jan, 2026-10-04)
# ---------------------------------------------------------------------------

NOW = 1_800_000_000
DAY = 86400


def _login(tmp_path, age_days, acked=None, with_time=True, login=True):
    """failure-notice [--login] for a notice <age_days> old; <acked>: the
    failure_acked of a user's indicator state (None: no state file)."""
    import time as _time
    config = tmp_path / "config"
    config.mkdir(exist_ok=True)
    stamp = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(NOW - age_days * DAY))
    notice = config / "last-switch-failed"
    notice.write_text("slot=B\nreason=x\n" + (f"time={stamp}\n" if with_time else "")
                      + "update=yes\nversion=beta-2026-10-15-101010\n")
    os.utime(notice, (NOW - age_days * DAY, NOW - age_days * DAY))
    homes = tmp_path / "home"
    if acked is not None:
        state = homes / "rasqberry" / ".local" / "state" / "rasqberry"
        state.mkdir(parents=True, exist_ok=True)
        (state / "slot-indicator.json").write_text(json.dumps(
            {"failures_noticed": [stamp], "failure_acked": stamp if acked == "this" else acked,
             "releases_noticed": []}))
    (tmp_path / "version").write_text("beta-2026-09-30-221656\n")
    status = tmp_path / "slot-status"
    status.write_text("layout=ab\ncurrent=A\nslot_a=beta-2026-09-30-221656\nslot_b=x\n")
    env = dict(os.environ, RQ_BOOT_COMMON_DIR=str(config), RQ_SLOT_STATUS_FILE=str(status),
               RQ_VERSION_FILE=str(tmp_path / "version"), RQ_HOMES_DIR=str(homes),
               RQ_NOW_EPOCH=str(NOW))
    args = ["failure-notice"] + (["--login"] if login else [])
    proc = subprocess.run(["bash", _STATUS, *args], env=env, capture_output=True, text=True,
                          timeout=30)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


SENTENCE = ("The update of Slot B to beta-2026-10-15-101010 didn't work, so Slot A "
            "(beta-2026-09-30-221656) is running again.")


@pytest.mark.parametrize("age_days,acked,shown", [
    (0, None, True),
    (6.9, None, True),
    (7.1, None, False),                 # at most 7 days
    (30, None, False),
    (1, "this", False),                 # the taskbar menu was opened with this failure
    (1, "2026-01-01 00:00:00", True),   # ... with an earlier failure: still shown
    (8, "this", False),
])
def test_login_line_for_7_days_or_until_the_menu_was_opened(tmp_path, age_days, acked, shown):
    assert _login(tmp_path, age_days, acked) == (SENTENCE if shown else "")


def test_login_line_without_a_time_goes_by_the_file_date(tmp_path):
    assert _login(tmp_path, 1, with_time=False) == SENTENCE
    (tmp_path / "old").mkdir()
    assert _login(tmp_path / "old", 9, with_time=False) == ""


@pytest.mark.parametrize("age_days,acked", [(30, None), (1, "this")])
def test_system_info_and_slot_manager_keep_the_sentence(tmp_path, age_days, acked):
    assert _login(tmp_path, age_days, acked, login=False) == SENTENCE


def test_motd_uses_the_login_rule():
    text = open(os.path.join(_HERE, "..", "..", "RQB2-system", "etc", "update-motd.d",
                             "20-rasqberry")).read()
    assert "rq_slot_status.sh failure-notice --login" in text
    for path in ("rq_info.sh", "rq_slot_manager.sh"):
        assert "failure-notice --login" not in open(os.path.join(_BIN, path)).read(), path


def test_the_indicator_keeps_the_failure_time_as_acked(tmp_path):
    # the key failure-notice --login compares with
    spec = importlib.util.spec_from_file_location("rq_slot_indicator",
                                                  os.path.join(_BIN, "rq_slot_indicator.py"))
    ind = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ind)
    book = ind.NoticeBook(str(tmp_path))
    assert book.ack({"slot": "B", "time": "2026-10-15 10:00:00", "reason": "x"}) is True
    book.save()
    data = json.loads((tmp_path / "slot-indicator.json").read_text())
    assert data["failure_acked"] == "2026-10-15 10:00:00"


# ---------------------------------------------------------------------------
# The health check writes it at every start, and never fails because of it
# ---------------------------------------------------------------------------

@pytest.fixture
def hc(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("rq_health_check", os.path.join(_BIN, "rq_health_check.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_health_check_writes_the_slot_status(hc, tmp_path, monkeypatch):
    marker = tmp_path / "called"
    fake = tmp_path / "rq_slot_status.sh"
    fake.write_text(f"#!/bin/bash\necho \"$1\" > {marker}\n")
    fake.chmod(0o755)
    monkeypatch.setattr(hc, "SLOT_STATUS", fake)
    hc.write_slot_status()
    assert marker.read_text().strip() == "write"
    fake.write_text("#!/bin/bash\nexit 3\n")
    hc.write_slot_status()                                   # a failure is only logged
    monkeypatch.setattr(hc, "SLOT_STATUS", tmp_path / "missing")
    hc.write_slot_status()


def test_health_check_reasons_name_the_slots():
    text = open(os.path.join(_BIN, "rq_health_check.py")).read()
    assert "was tried twice without success" in text
    assert "is running again" not in text          # the sentence says that, not the reason
    assert "the desktop did not come up within" in text


# ---------------------------------------------------------------------------
# Withdrawn releases in the shell tools (RQB-release-controls.json)
# ---------------------------------------------------------------------------

def test_update_check_does_not_offer_a_withdrawn_release(tmp_path):
    from test_update_check import RELEASES, _SCRIPT
    (tmp_path / "version").write_text("beta-2025-12-30-211449\n")
    (tmp_path / "releases.json").write_text(json.dumps(RELEASES))
    (tmp_path / "controls.json").write_text(json.dumps(
        {"beta-2026-10-01-120000": {"withdrawn": True, "reason": "breaks the LED panel"}}))
    env = dict(os.environ, RQ_VERSION_FILE=str(tmp_path / "version"),
               RQ_RELEASES_FILE=str(tmp_path / "releases.json"),
               RQ_RELEASE_CONTROLS_FILE=str(tmp_path / "controls.json"),
               RQ_UPDATE_STATE=str(tmp_path / "state"))
    proc = subprocess.run(["bash", _SCRIPT, "--refresh"], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "beta-2026-10-01-120000 was withdrawn: breaks the LED panel" in proc.stdout
    assert not (tmp_path / "state").exists()


def test_release_picker_skips_withdrawn_releases(tmp_path, monkeypatch):
    import test_ab_releases as t
    controls = tmp_path / "controls.json"
    controls.write_text(json.dumps({"releases": {
        "beta-2026-09-30-221656": {"withdrawn": True, "reason": "slot switch fails on the Pi 4"}}}))
    monkeypatch.setenv("RQ_RELEASE_CONTROLS_FILE", str(controls))
    latest = t._run(tmp_path, "beta-2025-12-30-211449", "latest")
    listed = t._run(tmp_path, "beta-2025-12-30-211449", "list", "beta")
    assert latest.returncode == 2
    assert "was withdrawn: slot switch fails on the Pi 4" in latest.stderr
    tags = [row.split("\t")[0] for row in listed.stdout.splitlines()]
    assert "beta-2026-09-30-221656" not in tags and "beta-2025-12-30-211449" in tags


def test_no_controls_file_means_nothing_is_withdrawn(tmp_path, monkeypatch):
    import test_ab_releases as t
    monkeypatch.setenv("RQ_RELEASE_CONTROLS_FILE", str(tmp_path / "missing.json"))
    latest = t._run(tmp_path, "beta-2025-12-30-211449", "latest")
    assert latest.returncode == 0, latest.stderr


def test_no_controls_file_with_jq_16_means_nothing_is_withdrawn(tmp_path, monkeypatch):
    # Raspberry Pi OS ships jq 1.6, which exits 0 on EMPTY input even with -e:
    # with no controls file (404) the beta said "The latest beta release ...
    # was withdrawn: ." (night user test, 2026-10-04). Emulate that jq here.
    import shutil
    import test_ab_releases as t
    real_jq = shutil.which("jq")
    assert real_jq
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "jq"
    fake.write_text(f"""#!/bin/bash
input=$(cat)
[ -n "$input" ] || exit 0          # jq 1.6: no input, no output, success
printf '%s' "$input" | exec {real_jq} "$@"
""")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setenv("RQ_RELEASE_CONTROLS_FILE", str(tmp_path / "missing.json"))
    latest = t._run(tmp_path, "beta-2025-12-30-211449", "latest")
    assert latest.returncode == 0, latest.stderr
    assert "withdrawn" not in latest.stderr
