"""
Tests for RQB2-bin/rq_slot_manager.sh (A/B slots, batch B2).

- R-055: switch-to and rollback refuse a slot that holds no system (the
  placeholder, a freshly expanded slot, an interrupted update): starting it
  hangs the Pi, and a rollback into it is permanent.
- R-118: status and summary say what each slot holds.
- R-051: promote never waits on an invisible prompt.

A fake A/B card: findmnt/lsblk/id are stubbed on PATH, each slot's root is a
temp directory reported as "already mounted", and /boot/config is a temp
directory (RQ_BOOT_COMMON_DIR).
"""

import os
import shutil
import subprocess
import textwrap

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "..", "RQB2-bin", "rq_slot_manager.sh")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")

GB = 1024 ** 3

STUBS = {
    # findmnt / -o source -n            -> the running root partition
    # findmnt -rn -o TARGET --source X  -> where X is mounted (FAKE_MNT_<name>)
    "findmnt": """\
        #!/bin/bash
        src=""
        prev=""
        for a in "$@"; do
            [ "$prev" = "--source" ] && src="$a"
            prev="$a"
        done
        if [ -n "$src" ]; then
            var="FAKE_MNT_$(basename "$src")"
            [ -n "${!var:-}" ] || exit 1
            echo "${!var}"
            exit 0
        fi
        case "$1" in
            /) echo "$FAKE_ROOT" ;;
            *) exit 1 ;;
        esac
        """,
    # lsblk -no pkname P | -no label /dev/mmcblk0p1 | -lnpo NAME,LABEL DEV | -bno SIZE P
    "lsblk": """\
        #!/bin/bash
        last="${@: -1}"
        case "$*" in
            *pkname*) echo mmcblk0 ;;
            *NAME,LABEL*)
                echo "/dev/mmcblk0p1 CONFIG"
                echo "/dev/mmcblk0p2 BOOT-A"
                echo "/dev/mmcblk0p3 boot-b"
                echo "/dev/mmcblk0p5 SYSTEM-A"
                echo "/dev/mmcblk0p6 SYSTEM-B"
                echo "/dev/mmcblk0p7 data" ;;
            *SIZE*)
                var="FAKE_SIZE_$(basename "$last")"
                echo "${!var:-0}" ;;
            *label*|*LABEL*)
                [ "$last" = "/dev/mmcblk0p1" ] && echo "${FAKE_P1_LABEL:-CONFIG}" ;;
        esac
        exit 0
        """,
    "id": """\
        #!/bin/bash
        echo 0
        """,
    "mount": """\
        #!/bin/bash
        echo "mount $*" >> "$FAKE_CALLS"
        exit 32
        """,
    "umount": """\
        #!/bin/bash
        echo "umount $*" >> "$FAKE_CALLS"
        exit 0
        """,
    "reboot": """\
        #!/bin/bash
        echo "reboot $*" >> "$FAKE_CALLS"
        """,
}


def _system(root, version=None):
    """A slot root that holds a system (init binary, optional version file)."""
    (root / "usr/lib/systemd").mkdir(parents=True)
    (root / "usr/lib/systemd/systemd").write_text("")
    if version:
        (root / "etc").mkdir()
        (root / "etc/rasqberry-version").write_text(version + "\n")
    return root


@pytest.fixture
def card(tmp_path):
    bindir = tmp_path / "stubs"
    bindir.mkdir()
    for name, body in STUBS.items():
        (bindir / name).write_text(textwrap.dedent(body))
        (bindir / name).chmod(0o755)
    config = tmp_path / "config"
    config.mkdir()
    (config / "autoboot.txt").write_text(
        "[all]\ntryboot_a_b=1\nboot_partition=2\nboot_partition_fallback=3\n\n"
        "[tryboot]\nboot_partition=3\nboot_partition_fallback=2\n")
    (config / "slot-confirmed").write_text("now\nA\n")
    slot_a = _system(tmp_path / "slot-a", "beta-2026-09-30-221656")
    slot_b = tmp_path / "slot-b"          # expanded but empty: mkfs + nothing
    slot_b.mkdir()
    env = dict(
        os.environ,
        PATH=f"{bindir}:{os.environ['PATH']}",
        RQ_BOOT_COMMON_DIR=str(config),
        RQ_RUNNING_ROOT=str(slot_a),
        RQ_PROMOTE_LOG=str(tmp_path / "promote.log"),
        FAKE_CALLS=str(tmp_path / "calls"),
        FAKE_ROOT="/dev/mmcblk0p5",
        FAKE_MNT_mmcblk0p5="/",
        FAKE_MNT_mmcblk0p6=str(slot_b),
        FAKE_SIZE_mmcblk0p6=str(26 * GB),
    )
    return {"env": env, "config": config, "a": slot_a, "b": slot_b, "tmp": tmp_path}


def _run(card, *args, **kw):
    return subprocess.run(["bash", _SCRIPT, *args], capture_output=True, text=True,
                          env=card["env"], stdin=subprocess.DEVNULL, timeout=30, **kw)


def _summary(card):
    proc = _run(card, "summary")
    assert proc.returncode == 0, proc.stderr
    return dict(line.split("=", 1) for line in proc.stdout.splitlines())


def test_summary_reports_both_slots(card):
    s = _summary(card)
    assert s["layout"] == "ab"
    assert s["current"] == "A"
    assert s["confirmed"] == "yes"
    assert s["default"] == "A"
    assert s["slot_a"] == "beta-2026-09-30-221656"
    assert s["slot_b"] == "EMPTY"
    assert s["expanded"] == "yes"


def test_summary_says_single_system_mode(card):
    # B4: a placeholder Slot B on a small card is single-system mode; the menu
    # explains that instead of "not set up" (card_mode from rq_expand_ab.sh)
    card["env"].update(RQ_AB_IS_AB="1", RQ_AB_CARD_BYTES=str(32_000_000_000),
                       RQ_AB_SLOT_A_BYTES=str(25 * GB), RQ_AB_SLOT_B_BYTES=str(16 * 1024 * 1024),
                       RQ_AB_DATA_BYTES=str(3 * GB), FAKE_SIZE_mmcblk0p6=str(16 * 1024 * 1024))
    s = _summary(card)
    assert s["card_mode"] == "single"
    assert s["expanded"] == "no"


def test_summary_on_a_standard_image(card):
    card["env"]["FAKE_P1_LABEL"] = "bootfs"
    assert _run(card, "summary").stdout.strip() == "layout=single"


def test_placeholder_slot_is_not_expanded(card):
    card["env"]["FAKE_SIZE_mmcblk0p6"] = str(16 * 1024 * 1024)
    assert _summary(card)["expanded"] == "no"


@pytest.mark.parametrize("command", [["switch-to", "B"], ["rollback"]])
def test_an_empty_slot_is_refused(card, command):
    before = (card["config"] / "autoboot.txt").read_text()
    proc = _run(card, *command)
    assert proc.returncode == 25
    assert "holds no system" in proc.stderr
    assert "Install an update into Slot B" in proc.stderr
    assert (card["config"] / "autoboot.txt").read_text() == before
    assert not (card["config"] / "target-slot").exists()


def test_an_interrupted_update_is_refused(card):
    _system(card["b"], "beta-2026-10-15-101010")
    (card["config"] / "slot-B-incomplete").write_text("2026-10-15 beta-2026-10-15-101010\n")
    assert _summary(card)["slot_b"] == "INCOMPLETE"
    proc = _run(card, "switch-to", "B")
    assert proc.returncode == 25
    assert "unfinished update" in proc.stderr


def test_a_slot_with_a_system_can_be_tried(card):
    _system(card["b"], "beta-2026-10-15-101010")
    proc = _run(card, "switch-to", "B")
    assert proc.returncode == 0, proc.stderr
    autoboot = (card["config"] / "autoboot.txt").read_text()
    assert "[tryboot]\nboot_partition=3" in autoboot
    assert (card["config"] / "target-slot").read_text().strip() == "B"
    assert not (card["config"] / "slot-confirmed").exists()


def test_force_skips_the_check(card):
    proc = _run(card, "switch-to", "B", "--force")
    assert proc.returncode == 0, proc.stderr
    assert "--force" in proc.stderr


def test_rollback_into_a_system_is_permanent(card):
    _system(card["b"], "beta-2026-10-15-101010")
    proc = _run(card, "rollback")
    assert proc.returncode == 0, proc.stderr
    assert "[all]\ntryboot_a_b=1\nboot_partition=3" in (card["config"] / "autoboot.txt").read_text()


def test_a_slot_without_version_file_still_counts_as_a_system(card):
    _system(card["b"])
    assert _summary(card)["slot_b"] == "SYSTEM"
    assert _run(card, "switch-to", "B").returncode == 0


def test_status_lists_slot_contents(card):
    out = _run(card, "status").stdout
    assert "Slot A (stable): beta-2026-09-30-221656  <- running" in out
    assert "Slot B (testing): empty (no system)" in out
    assert "Slot Status: CONFIRMED" in out          # the rig tests grep this


def test_status_unconfirmed_during_a_trial_says_where_the_next_start_goes(card):
    # Running B on trial: a normal start still boots A
    _system(card["b"], "beta-2026-10-15-101010")
    card["env"]["FAKE_ROOT"] = "/dev/mmcblk0p6"
    card["env"]["RQ_RUNNING_ROOT"] = str(card["b"])
    card["env"]["FAKE_MNT_mmcblk0p5"] = str(card["a"])
    (card["config"] / "slot-confirmed").unlink()
    assert "returns to Slot A unless this slot is confirmed" in _run(card, "status").stderr


def test_status_unconfirmed_default_slot_does_not_threaten_a_rollback(card):
    (card["config"] / "slot-confirmed").unlink()
    err = _run(card, "status").stderr
    assert "UNCONFIRMED (stays the default" in err
    assert "will rollback" not in err


def _on_slot_b(card):
    _system(card["b"], "beta-2026-10-15-101010")
    card["env"]["FAKE_ROOT"] = "/dev/mmcblk0p6"
    card["env"]["RQ_RUNNING_ROOT"] = str(card["b"])
    card["env"]["FAKE_MNT_mmcblk0p5"] = str(card["a"])
    card["env"]["FAKE_MNT_mmcblk0p6"] = "/"
    (card["config"] / "slot-confirmed").write_text("now\nB\n")


def test_promote_without_a_terminal_never_waits_on_a_hidden_prompt(card):
    _on_slot_b(card)
    proc = _run(card, "promote")      # stdin is /dev/null, output captured
    assert proc.returncode == 1
    assert "pass --yes" in proc.stderr
    assert not (card["config"] / "slot-A-incomplete").exists()


def test_promote_only_from_slot_b(card):
    proc = _run(card, "promote", "--yes")
    assert proc.returncode == 1
    assert "only while Slot B is the running system" in proc.stderr


def test_promote_needs_a_confirmed_slot_b(card):
    _on_slot_b(card)
    (card["config"] / "slot-confirmed").unlink()
    proc = _run(card, "promote", "--yes")
    assert proc.returncode == 1
    assert "not confirmed yet" in proc.stderr


def test_failed_promote_leaves_slot_a_usable(card):
    # Slot A is busy (still mounted after umount): nothing may be written
    _on_slot_b(card)
    proc = _run(card, "promote", "--yes")
    assert proc.returncode == 1
    assert "cannot be unmounted" in proc.stderr
    assert not (card["config"] / "slot-A-incomplete").exists()
    assert _summary(card)["slot_a"] == "beta-2026-09-30-221656"
