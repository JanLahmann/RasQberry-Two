"""
Tests for the automatic rollback in RQB2-bin/rq_health_check.py (B4, R-054):
when is a boot "on probation", what a failed trial boot does, and the
15-minute deadline.

The CONFIG partition and the device-tree properties are temp directories;
nothing reboots (reboot_now is replaced).
"""

import importlib.util
import os
import stat

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
    assert "Slot B did not start (tried twice); back on Slot A" in notice
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
