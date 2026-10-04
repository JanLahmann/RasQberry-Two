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
    assert "was tried twice without success; " in text
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
