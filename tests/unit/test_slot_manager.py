"""
Tests for RQB2-bin/rq_slot_manager.sh (A/B slots, batch B2).

- R-055: switch-to and rollback refuse a slot that holds no system (the
  placeholder, a freshly expanded slot, an interrupted update): starting it
  hangs the Pi, and a rollback into it is permanent.
- R-118: status and summary say what each slot holds.
- Ping-pong (Jan, 2026-10-04): no slot is special, PROMOTE is gone, and
  plan-update decides where an update goes and what Jan's guard says (keep at
  least one slot at beta or stable): every stream combination, older releases,
  empty targets, the last safe slot.

A fake A/B card: findmnt/lsblk/id are stubbed on PATH, each slot's root is a
temp directory reported as "already mounted", and /boot/config is a temp
directory (RQ_BOOT_COMMON_DIR).
"""

import json
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
    assert "Install an update into the other system (Slot B)" in proc.stderr
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


def test_confirm_ends_the_update_hint_of_this_slot_only(card):
    (card["config"] / "slot-confirmed").unlink()
    (card["config"] / "slot-A-updated").write_text("version=x\n")
    (card["config"] / "slot-B-updated").write_text("version=y\n")
    proc = _run(card, "confirm")
    assert proc.returncode == 0, proc.stderr
    assert not (card["config"] / "slot-A-updated").exists()     # A started well
    assert (card["config"] / "slot-B-updated").exists()


def test_status_lists_slot_contents(card):
    out = _run(card, "status").stdout
    assert "Slot A: beta-2026-09-30-221656 (beta)  <- running, start slot" in out
    assert "Slot B: empty (no system)" in out
    assert "stable" not in out and "testing" not in out
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


def test_status_on_slot_b_marks_it_running_and_start_slot(card):
    _on_slot_b(card)
    (card["config"] / "autoboot.txt").write_text(
        "[all]\ntryboot_a_b=1\nboot_partition=3\nboot_partition_fallback=2\n")
    out = _run(card, "status").stdout
    assert "Slot A: beta-2026-09-30-221656 (beta)\n" in out
    assert "Slot B: beta-2026-10-15-101010 (beta)  <- running, start slot" in out


# ---------------------------------------------------------------------------
# PROMOTE is gone (Jan, 2026-10-04): no command, no help, no log
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("command", ["promote", "update-stable"])
def test_promote_and_update_stable_are_gone(card, command):
    _on_slot_b(card)
    proc = _run(card, command, "--yes")
    assert proc.returncode == 1
    assert "Unknown command" in proc.stderr
    assert not (card["config"] / "slot-A-incomplete").exists()


def test_help_names_plan_update_and_no_promote(card):
    out = _run(card, "--help").stdout
    assert "plan-update" in out
    assert "promote" not in out.lower() and "stable" not in out.lower()


# ---------------------------------------------------------------------------
# plan-update: the target slot and Jan's guard
# ---------------------------------------------------------------------------

def _plan(card, tag, running=None, target=None, running_slot="A"):
    """plan-update <tag> on a card running <running_slot>. <running> and
    <target>: a version, "EMPTY", "INCOMPLETE" or "SYSTEM" (no version file)."""
    tmp = card["tmp"]
    roots = {}
    for slot, content in ((running_slot, running), ("B" if running_slot == "A" else "A", target)):
        root = tmp / f"plan-{slot}"
        root.mkdir()
        if content == "INCOMPLETE":
            _system(root, "beta-2026-10-15-101010")
            (card["config"] / f"slot-{slot}-incomplete").write_text("now x\n")
        elif content == "SYSTEM":
            _system(root)
        elif content not in (None, "EMPTY"):
            _system(root, content)
        roots[slot] = root
    other = "B" if running_slot == "A" else "A"
    part = {"A": "mmcblk0p5", "B": "mmcblk0p6"}
    card["env"].update({
        "FAKE_ROOT": f"/dev/{part[running_slot]}",
        "RQ_RUNNING_ROOT": str(roots[running_slot]),
        f"FAKE_MNT_{part[running_slot]}": "/",
        f"FAKE_MNT_{part[other]}": str(roots[other]),
    })
    proc = _run(card, "plan-update", tag)
    assert proc.returncode == 0, proc.stderr
    return dict(line.split("=", 1) for line in proc.stdout.splitlines())


BETA = "beta-2026-10-03-095636"
BETA_NEW = "beta-2026-10-15-101010"
DEV = "development-2026-10-04-014357"
DEV_NEW = "development-2026-10-05-010101"

# One table for both copies of the rules: this script and rq_release_notice.py
# (the taskbar indicator's warnings) - see the file's "about"
with open(os.path.join(_HERE, "data", "plan_update_cases.json")) as _f:
    PLAN_CASES = json.load(_f)["cases"]


@pytest.mark.parametrize("case", PLAN_CASES, ids=[c["why"] for c in PLAN_CASES])
def test_plan_update_shared_cases(card, case):
    plan = _plan(card, case["tag"], running=case["running"], target=case["target"])
    assert plan["target"] == "B" and plan["running"] == "A"
    assert {key: plan[key] for key in case["expect"]} == case["expect"]
    if case["expect"]["last_safe_slot"] == "yes":
        assert plan["advice"] == ("Slot B holds the only beta or stable system on this card. "
                                  "Safer: switch to Slot B first, then install into Slot A.")
    elif case["expect"]["downgrade"] != "none":
        assert "downgrade" in plan["advice"]


def test_plan_update_while_running_slot_b_targets_slot_a(card):
    # ping-pong: Slot A is no different from Slot B
    plan = _plan(card, DEV_NEW, running=DEV, target=BETA, running_slot="B")
    assert plan["target"] == "A" and plan["running"] == "B"
    assert plan["last_safe_slot"] == "yes"
    assert plan["advice"].endswith("switch to Slot A first, then install into Slot B.")


def test_plan_update_plain_advice(card):
    assert _plan(card, BETA_NEW, running=BETA, target="EMPTY")["advice"] == \
        "Slot B holds no system yet. Slot A stays as it is."


def test_plan_update_needs_a_tag(card):
    proc = _run(card, "plan-update")
    assert proc.returncode == 1 and "Usage" in proc.stderr


def test_plan_update_on_a_standard_image(card):
    card["env"]["FAKE_P1_LABEL"] = "bootfs"
    proc = _run(card, "plan-update", BETA)
    assert proc.returncode == 1
    assert "no A/B layout" in proc.stderr
