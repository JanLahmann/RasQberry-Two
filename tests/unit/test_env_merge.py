"""
Tests for RQB2-bin/rq_env_merge.py (issue #290): a branch update must keep
device state in rasqberry_environment.env while picking up new defaults.
"""

import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, "..", "..")
_SCRIPT = os.path.join(_ROOT, "RQB2-bin", "rq_env_merge.py")

sys.path.insert(0, os.path.join(_ROOT, "RQB2-bin"))
import rq_env_merge  # noqa: E402


def _merge(new, current):
    merged, added, kept, carried = rq_env_merge.merge(new.splitlines(), current.splitlines())
    return "\n".join(merged), added, kept, carried


def test_device_values_survive_and_new_keys_arrive():
    new = "# LED\nLED_LAYOUT=single-24x8\nLED_BRIGHTNESS=0.2\nNEW_FEATURE=on\n"
    cur = "# LED\nLED_LAYOUT=quad-4x12\nLED_BRIGHTNESS=0.2\n"
    text, added, kept, carried = _merge(new, cur)
    assert "LED_LAYOUT=quad-4x12" in text
    assert "LED_LAYOUT=single-24x8" not in text
    assert "NEW_FEATURE=on" in text
    assert added == ["NEW_FEATURE"]
    assert kept == ["LED_LAYOUT"]
    assert carried == []


def test_layout_and_comments_come_from_the_new_defaults():
    new = "# new comment\nA=1\n\n# section B\nB=2\n"
    cur = "# old comment\nB=20\nA=10\n"
    text, *_ = _merge(new, cur)
    assert text.splitlines() == ["# new comment", "A=10", "", "# section B", "B=20"]


def test_device_only_keys_are_carried_over():
    new = "A=1\n"
    cur = "A=1\nRQ_FIRSTLOGIN_DONE=true\nQOFFEE_MAKER_INSTALLED=true\n"
    text, added, kept, carried = _merge(new, cur)
    assert carried == ["RQ_FIRSTLOGIN_DONE", "QOFFEE_MAKER_INSTALLED"]
    assert text.rstrip().endswith("RQ_FIRSTLOGIN_DONE=true\nQOFFEE_MAKER_INSTALLED=true")
    assert "Kept by rq_update_from_branch.sh" in text


def test_last_assignment_on_the_device_wins():
    # update_env_var may append instead of editing in place; the shell uses the last one
    text, *_ = _merge("A=1\n", "A=2\nA=3\n")
    assert text.strip() == "A=3"


def test_export_prefix_and_quoted_values():
    text, *_ = _merge('export A="x y"\n', 'A="kept value"\n')
    assert text.strip() == 'A="kept value"'


def test_merge_is_idempotent():
    new = "A=1\nB=2\n"
    once, *_ = _merge(new, "A=9\nC=3\n")
    twice, added, kept, carried = _merge(new, once)
    assert twice == once
    assert added == []


def test_cli_writes_output_and_summary(tmp_path):
    (tmp_path / "new.env").write_text("A=1\nB=2\n")
    (tmp_path / "cur.env").write_text("A=5\nX=7\n")
    out = tmp_path / "out.env"
    proc = subprocess.run(
        [sys.executable, _SCRIPT, str(tmp_path / "new.env"), str(tmp_path / "cur.env"), str(out)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "1 new setting(s), 1 device value(s) kept, 1 device-only" in proc.stdout
    body = out.read_text()
    assert "A=5" in body and "B=2" in body and "X=7" in body


def test_real_env_file_merges_onto_itself_unchanged():
    path = os.path.join(_ROOT, "RQB2-config", "rasqberry_environment.env")
    lines = open(path, encoding="utf-8").read().splitlines()
    merged, added, kept, carried = rq_env_merge.merge(lines, lines)
    assert (added, kept, carried) == ([], [], [])
    assert merged == lines


def test_retired_raspi_config_globals_are_dropped():
    # R-001: INTERACTIVE/ASK_TO_REBOOT/CONFIG are raspi-config's own variables;
    # carried over, they switch raspi-config to non-interactive mode.
    new = "A=1\n"
    cur = ("A=1\nINTERACTIVE=true\nASK_TO_REBOOT=0\nCONFIG=/boot/config.txt\n"
           "MARKER_QRT=QuantumRaspberryTie.v7_1.py\nRQ_FIRSTLOGIN_DONE=true\n")
    text, added, kept, carried = _merge(new, cur)
    assert carried == ["RQ_FIRSTLOGIN_DONE"]
    for key in ("INTERACTIVE", "ASK_TO_REBOOT", "CONFIG", "MARKER_QRT"):
        assert key + "=" not in text


def test_shipped_defaults_do_not_set_raspi_config_globals():
    env = os.path.join(_ROOT, "RQB2-config", "rasqberry_environment.env")
    keys = rq_env_merge.assignments(open(env, encoding="utf-8").read().splitlines())
    for key in rq_env_merge.RETIRED_KEYS:
        assert key not in keys, f"{key} must not be in the shipped env file (R-001)"
