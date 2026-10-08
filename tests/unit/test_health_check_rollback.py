"""
Tests for the automatic rollback in RQB2-bin/rq_health_check.py (B4, R-054):
when is a boot "on probation", what a failed trial boot does, and the
15-minute deadline. And when a failure happened: the trial slot's clock may
not be set yet, so the time the switch was asked for dates it.

The CONFIG partition and the device-tree properties are temp directories;
nothing reboots (reboot_now is replaced).
"""

import importlib.util
import os
import stat
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "..", "RQB2-bin", "rq_health_check.py")

AUTOBOOT_A_DEFAULT = """[all]
tryboot_a_b=1
boot_partition=2
boot_partition_fallback=3

[tryboot]
boot_partition=3
boot_partition_fallback=2
"""
AUTOBOOT_B_DEFAULT = """[all]
tryboot_a_b=1
boot_partition=3
boot_partition_fallback=2

[tryboot]
boot_partition=2
boot_partition_fallback=3
"""


@pytest.fixture
def hc(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("rq_health_check", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    config = tmp_path / "config"
    config.mkdir()
    dt = tmp_path / "dt"
    dt.mkdir()
    monkeypatch.setattr(mod, "BOOT_CONFIG_DIR", config)
    monkeypatch.setattr(mod, "DT_BOOTLOADER_DIR", dt)
    monkeypatch.setattr(mod, "WATCHDOG_MARKER", tmp_path / "wd")
    # the clock is not synchronised unless a test says so (CI hosts may be)
    monkeypatch.setattr(mod, "TIME_SYNCED", tmp_path / "timesync-synchronized")
    mod.reboots = []
    monkeypatch.setattr(mod, "reboot_now", lambda: mod.reboots.append(True))
    mod.config, mod.dt = config, dt
    return mod


def _switch_pending(config, target, autoboot=AUTOBOOT_A_DEFAULT):
    """What rq_slot_manager.sh switch-to leaves on CONFIG (running slot = default)."""
    (config / "autoboot.txt").write_text(autoboot)
    (config / "target-slot").write_text(target + "\n")
    (config / "switch-retries").write_text("0\n")


def _tryboot(dt, value):
    (dt / "tryboot").write_bytes(value.to_bytes(4, "big"))


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

def test_read_dt_u32(hc):
    _tryboot(hc.dt, 1)
    assert hc.read_dt_u32("tryboot") == 1
    (hc.dt / "partition").write_bytes(b"\x00\x00\x00\x03")
    assert hc.read_dt_u32("partition") == 3
    assert hc.read_dt_u32("missing") is None
    (hc.dt / "short").write_bytes(b"\x01")
    assert hc.read_dt_u32("short") is None


@pytest.mark.parametrize("dev,slot", [
    ("/dev/mmcblk0p5", "A"), ("/dev/mmcblk0p6", "B"), ("/dev/sda5", "A"),
    ("/dev/mmcblk0p2", None), ("", None),
])
def test_slot_from_root(hc, dev, slot):
    assert hc.slot_from_root(dev) == slot


def test_autoboot_default_partition(hc):
    assert hc.autoboot_default_partition(AUTOBOOT_A_DEFAULT) == 2
    assert hc.autoboot_default_partition(AUTOBOOT_B_DEFAULT) == 3
    assert hc.autoboot_default_partition("[tryboot]\nboot_partition=3\n") is None
    assert hc.autoboot_default_partition("") is None


# ---------------------------------------------------------------------------
# Probation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("target,slot,confirmed,tryboot,expected", [
    ("B", "B", False, 1, True),       # trial boot of the new slot
    ("B", "B", False, None, True),    # firmware without the DT property
    ("B", "B", True, 1, False),       # already confirmed
    ("B", "B", False, 0, False),      # normal boot (fallback) - never roll back
    ("B", "A", False, 0, False),      # tryboot flag lost: rq_tryboot_retry.sh's case
    (None, "A", False, 0, False),     # no switch pending (every normal boot)
    ("A", "A", False, 1, True),
])
def test_on_probation(hc, target, slot, confirmed, tryboot, expected):
    if target:
        (hc.config / "target-slot").write_text(target)
    if confirmed:
        (hc.config / "slot-confirmed").write_text("x")
    assert hc.on_probation(hc.config, slot, tryboot) is expected


def test_rollback_target_exists(hc):
    (hc.config / "autoboot.txt").write_text(AUTOBOOT_A_DEFAULT)
    assert hc.rollback_target_exists(hc.config, "B") is True
    assert hc.rollback_target_exists(hc.config, "A") is False


def test_fail_probation_records_clears_and_reboots(hc):
    _switch_pending(hc.config, "B")
    assert hc.fail_probation(hc.config, "B", "Qiskit check failed") == "rolled-back"
    notice = (hc.config / "last-switch-failed").read_text()
    assert "slot=B" in notice and "reason=Qiskit check failed" in notice
    # cleared, so rq_tryboot_retry.sh on Slot A does not try B again
    assert not (hc.config / "target-slot").exists()
    assert not (hc.config / "switch-retries").exists()
    assert hc.reboots == [True]


def test_a_failed_first_start_after_an_update_is_recorded_as_an_update(hc):
    # rq_update_slot.sh left slot-B-updated: "The update of Slot B ... didn't work"
    _switch_pending(hc.config, "B")
    (hc.config / "slot-B-updated").write_text("version=beta-2026-10-15-101010\ntag=x\n")
    hc.record_failed_switch(hc.config, "B", "Qiskit check failed")
    notice = (hc.config / "last-switch-failed").read_text()
    assert "update=yes\n" in notice
    assert "version=beta-2026-10-15-101010\n" in notice       # from the hint
    assert (hc.config / "slot-B-updated").exists()            # until a good start


def test_a_failed_plain_switch_is_recorded_as_a_switch(hc):
    # no hint: a switch to a slot that had started well before
    _switch_pending(hc.config, "B")
    (hc.config / "slot-A-updated").write_text("version=x\n")   # another slot's hint
    hc.record_failed_switch(hc.config, "B", "Qiskit check failed", "development-2026-10-04-040217")
    notice = (hc.config / "last-switch-failed").read_text()
    assert "update=no\n" in notice
    assert "version=development-2026-10-04-040217\n" in notice


def test_fail_probation_never_reboots_into_itself(hc):
    _switch_pending(hc.config, "B", autoboot=AUTOBOOT_B_DEFAULT)
    assert hc.fail_probation(hc.config, "B", "x") == "no-rollback-target"
    assert hc.reboots == []
    assert (hc.config / "last-switch-failed").exists()


def test_deadline_rolls_back_an_unconfirmed_trial_boot(hc, monkeypatch):
    _switch_pending(hc.config, "B")
    _tryboot(hc.dt, 1)
    monkeypatch.setattr(hc, "current_root_device", lambda: "/dev/mmcblk0p6")
    assert hc.run_deadline() == 1
    assert hc.reboots == [True]
    assert "not confirmed 15 minutes after start" in (hc.config / "last-switch-failed").read_text()


@pytest.mark.parametrize("setup", ["confirmed", "normal-boot", "no-switch", "standard-image"])
def test_deadline_does_nothing_otherwise(hc, monkeypatch, setup):
    monkeypatch.setattr(hc, "current_root_device", lambda: "/dev/mmcblk0p6")
    if setup != "standard-image":
        _switch_pending(hc.config, "B")
    if setup == "confirmed":
        (hc.config / "slot-confirmed").write_text("x")
        _tryboot(hc.dt, 1)
    elif setup == "normal-boot":
        _tryboot(hc.dt, 0)
    elif setup == "no-switch":
        (hc.config / "target-slot").unlink()
    assert hc.run_deadline() == 0
    assert hc.reboots == []


def test_failed_check_on_probation_rolls_back(hc, monkeypatch):
    _switch_pending(hc.config, "B")
    _tryboot(hc.dt, 1)
    monkeypatch.setattr(hc, "current_root_device", lambda: "/dev/mmcblk0p6")
    monkeypatch.setattr(hc, "load_environment", lambda: {})
    monkeypatch.setattr(hc, "check_venv_exists", lambda env: (False, "missing"))
    monkeypatch.setattr(hc, "report_status", lambda ok, checks: None)
    monkeypatch.setattr("sys.argv", ["rq_health_check.py"])
    with pytest.raises(SystemExit) as exc:
        hc.main()
    assert exc.value.code == 1
    assert hc.reboots == [True]
    assert "virtual environment missing" in (hc.config / "last-switch-failed").read_text()


def test_failed_check_outside_probation_only_reports(hc, monkeypatch):
    (hc.config / "autoboot.txt").write_text(AUTOBOOT_A_DEFAULT)
    monkeypatch.setattr(hc, "current_root_device", lambda: "/dev/mmcblk0p5")
    monkeypatch.setattr(hc, "load_environment", lambda: {})
    monkeypatch.setattr(hc, "check_venv_exists", lambda env: (False, "missing"))
    monkeypatch.setattr(hc, "report_status", lambda ok, checks: None)
    monkeypatch.setattr("sys.argv", ["rq_health_check.py"])
    with pytest.raises(SystemExit):
        hc.main()
    assert hc.reboots == []
    assert not (hc.config / "last-switch-failed").exists()


# ---------------------------------------------------------------------------
# After the retry budget: the old slot says so and stays confirmed
# ---------------------------------------------------------------------------

def _fake_slot_manager(tmp_path):
    sm = tmp_path / "rq_slot_manager.sh"
    sm.write_text("#!/bin/sh\necho \"INFO: Slot confirmed\"\nexit 0\n")
    sm.chmod(sm.stat().st_mode | stat.S_IEXEC)
    return sm


def test_exhausted_retry_leaves_a_notice_and_confirms_the_working_slot(hc, monkeypatch, tmp_path):
    _switch_pending(hc.config, "B")
    (hc.config / "switch-retries").unlink()   # rq_tryboot_retry.sh removed it
    monkeypatch.setattr(hc, "detect_ab_layout", lambda: (True, "ab"))
    monkeypatch.setattr(hc, "SLOT_MANAGER", _fake_slot_manager(tmp_path))
    monkeypatch.setattr(hc, "current_root_device", lambda: "/dev/mmcblk0p5")
    assert hc.confirm_boot_slot() is True
    notice = (hc.config / "last-switch-failed").read_text()
    assert "reason=Slot B was tried twice without success\n" in notice
    assert "update=no\n" in notice
    assert not (hc.config / "target-slot").exists()


def test_successful_switch_clears_an_old_notice(hc, monkeypatch, tmp_path):
    _switch_pending(hc.config, "B")
    (hc.config / "last-switch-failed").write_text("slot=B\nreason=old\n")
    monkeypatch.setattr(hc, "detect_ab_layout", lambda: (True, "ab"))
    monkeypatch.setattr(hc, "SLOT_MANAGER", _fake_slot_manager(tmp_path))
    monkeypatch.setattr(hc, "current_root_device", lambda: "/dev/mmcblk0p6")
    assert hc.confirm_boot_slot() is True
    assert not (hc.config / "last-switch-failed").exists()
    assert not (hc.config / "target-slot").exists()


# ---------------------------------------------------------------------------
# When it failed: the trial slot's clock may not be set yet (rig, 2026-10-04:
# no RTC, fake-hwclock gave 11:09:06 for a failure at about 12:25)
# ---------------------------------------------------------------------------

FMT = "%Y-%m-%d %H:%M:%S"
REQUESTED = "2026-10-04 12:24:10"
REQUESTED_EPOCH = int(time.mktime(time.strptime(REQUESTED, FMT)))


def _requested(config, slot="B", when=REQUESTED, epoch=True):
    """switch-requested as rq_slot_manager.sh switch-to writes it."""
    e = int(time.mktime(time.strptime(when, FMT)))
    (config / "switch-requested").write_text(
        f"slot={slot}\ntime={when}\n" + (f"epoch={e}\n" if epoch else ""))


def _clock(hc, monkeypatch, epoch, synced=False):
    monkeypatch.setattr(hc, "now_epoch", lambda: epoch)
    if synced:
        hc.TIME_SYNCED.write_text("")
    return time.strftime(FMT, time.localtime(epoch))


def _notice(hc):
    return dict(line.split("=", 1)
                for line in (hc.config / "last-switch-failed").read_text().splitlines())


def test_a_clock_behind_the_request_dates_the_failure_by_the_request(hc, monkeypatch):
    _switch_pending(hc.config, "B")
    _requested(hc.config)
    own = _clock(hc, monkeypatch, REQUESTED_EPOCH - 75 * 60)     # fake-hwclock: 11:09:10
    assert hc.fail_probation(hc.config, "B", "virtual environment missing") == "rolled-back"
    notice = _notice(hc)
    assert notice["time"] == REQUESTED
    assert notice["requested"] == REQUESTED
    assert notice["clock"] == own                                 # kept for a closer look
    assert notice["slot"] == "B" and notice["update"] == "no"
    assert not (hc.config / "switch-requested").exists()          # cleared with target-slot


def test_a_clock_after_the_request_dates_the_failure_itself(hc, monkeypatch):
    # the normal case: NTP was quicker than the failure (or the 15-minute deadline)
    _switch_pending(hc.config, "B")
    _requested(hc.config)
    own = _clock(hc, monkeypatch, REQUESTED_EPOCH + 95)
    hc.record_failed_switch(hc.config, "B", "x")
    notice = _notice(hc)
    assert notice["time"] == own
    assert notice["requested"] == REQUESTED
    assert "clock" not in notice


def test_a_synchronised_clock_is_trusted_over_the_request(hc, monkeypatch):
    # the asking slot's clock was ahead (set by hand): a synchronised clock wins
    _switch_pending(hc.config, "B")
    _requested(hc.config)
    own = _clock(hc, monkeypatch, REQUESTED_EPOCH - 3600, synced=True)
    hc.record_failed_switch(hc.config, "B", "x")
    assert _notice(hc)["time"] == own
    assert "clock" not in _notice(hc)


@pytest.mark.parametrize("setup", ["none", "other-slot"])
def test_without_a_request_for_this_slot_the_clock_is_used(hc, monkeypatch, setup):
    # none: the switch was asked for by an older system that does not record it
    _switch_pending(hc.config, "B")
    if setup == "other-slot":
        _requested(hc.config, slot="A")
    own = _clock(hc, monkeypatch, REQUESTED_EPOCH - 75 * 60)
    hc.record_failed_switch(hc.config, "B", "x")
    notice = _notice(hc)
    assert notice["time"] == own
    assert "requested" not in notice and "clock" not in notice


def test_a_request_without_epoch_goes_by_its_time(hc, monkeypatch):
    _switch_pending(hc.config, "B")
    _requested(hc.config, epoch=False)
    _clock(hc, monkeypatch, REQUESTED_EPOCH - 600)
    hc.record_failed_switch(hc.config, "B", "x")
    assert _notice(hc)["time"] == REQUESTED


def test_the_working_slot_dates_an_exhausted_retry_by_the_request_too(hc, monkeypatch, tmp_path):
    # Slot A records "tried twice" at its own early boot: fake-hwclock again
    _switch_pending(hc.config, "B")
    _requested(hc.config)
    _clock(hc, monkeypatch, REQUESTED_EPOCH - 20)
    monkeypatch.setattr(hc, "detect_ab_layout", lambda: (True, "ab"))
    monkeypatch.setattr(hc, "SLOT_MANAGER", _fake_slot_manager(tmp_path))
    monkeypatch.setattr(hc, "current_root_device", lambda: "/dev/mmcblk0p5")
    assert hc.confirm_boot_slot() is True
    assert _notice(hc)["time"] == REQUESTED
    assert not (hc.config / "switch-requested").exists()


def test_a_good_switch_clears_the_request(hc, monkeypatch, tmp_path):
    _switch_pending(hc.config, "B")
    _requested(hc.config)
    monkeypatch.setattr(hc, "detect_ab_layout", lambda: (True, "ab"))
    monkeypatch.setattr(hc, "SLOT_MANAGER", _fake_slot_manager(tmp_path))
    monkeypatch.setattr(hc, "current_root_device", lambda: "/dev/mmcblk0p6")
    assert hc.confirm_boot_slot() is True
    assert not (hc.config / "switch-requested").exists()
    assert not (hc.config / "last-switch-failed").exists()


def test_user_home_follows_uid_1000_not_the_name():
    """#319: a renamed desktop user (e.g. jan) must not fail the venv check."""
    import importlib.util, pwd as _pwd, types
    from pathlib import Path as _P
    src = _P(__file__).resolve().parents[2] / "RQB2-bin" / "rq_health_check.py"
    text = src.read_text()
    assert "~rasqberry" not in text
    spec = importlib.util.spec_from_file_location("rq_health_check_home", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fake = types.SimpleNamespace(pw_dir="/home/jan")
    orig = mod.pwd.getpwuid
    mod.pwd.getpwuid = lambda uid: fake if uid == 1000 else orig(uid)
    try:
        assert mod.desktop_user_home() == "/home/jan"
    finally:
        mod.pwd.getpwuid = orig
