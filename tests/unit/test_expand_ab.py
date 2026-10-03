"""
Tests for RQB2-bin/rq_expand_ab.sh (B4: R-006, R-012, R-095): what an A/B card
can do, what its first start does, and the layout it gets.

Everything runs on fake facts (RQ_AB_* environment overrides); the real
repartitioning was exercised on loop devices with the beta-2026-09-30 -ab
image (see the B4 report).
"""

import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "..", "RQB2-bin", "rq_expand_ab.sh")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")

GIB = 1024 ** 3
MIB = 1024 ** 2
THRESHOLD = 58 * GIB
SHIPPED_SLOT_A = 10 * GIB          # convert-to-ab-boot-v3.sh SYSTEM_A_SIZE_MB=10240
PLACEHOLDER_B = 16 * MIB
PLACEHOLDER_DATA = 28 * MIB
P5_START_MIB = 1538                # the -ab image (partitions.txt: sector 3149824)
P5_END_MIB = P5_START_MIB + 10240

# Byte sizes of real cards (what the kernel reports for "16GB" ... "256GB")
CARDS = {
    "16GB": 15931539456,
    "32GB": 31914983424,
    "64GB": 63864569856,
    "128GB": 127865454592,
    "256GB": 255869321216,
}


def _run(*args, env=None):
    full = dict(os.environ)
    full.update(env or {})
    return subprocess.run(["bash", _SCRIPT, *args], capture_output=True, text=True, env=full)


def _facts(card, slot_a=SHIPPED_SLOT_A, slot_b=PLACEHOLDER_B, data=PLACEHOLDER_DATA,
           is_ab=True, config_dir="/nonexistent", **extra):
    env = {
        "RQ_AB_IS_AB": "1" if is_ab else "0",
        "RQ_AB_CARD_BYTES": str(card),
        "RQ_AB_SLOT_A_BYTES": str(slot_a),
        "RQ_AB_SLOT_B_BYTES": str(slot_b),
        "RQ_AB_DATA_BYTES": str(data),
        "RQ_AB_P5_START_MIB": str(P5_START_MIB),
        "RQ_AB_P5_END_MIB": str(P5_END_MIB),
        "RQ_AB_CONFIG_DIR": str(config_dir),
    }
    env.update({k: str(v) for k, v in extra.items()})
    return env


def _kv(text):
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


# ---------------------------------------------------------------------------
# Which mode a card is in
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("card,mode", [
    ("16GB", "single-pending"),
    ("32GB", "single-pending"),
    ("64GB", "dual-pending"),       # a genuine 64GB card is ~59.5 GiB: must qualify
    ("128GB", "dual-pending"),
    ("256GB", "dual-pending"),
])
def test_fresh_card_mode_by_size(card, mode):
    assert _run("mode", env=_facts(CARDS[card])).stdout.strip() == mode


def test_threshold_is_58_gib_exactly():
    assert _run("decide", "1", str(THRESHOLD), str(SHIPPED_SLOT_A), str(PLACEHOLDER_B)).stdout.strip() == "dual-pending"
    assert _run("decide", "1", str(THRESHOLD - 512), str(SHIPPED_SLOT_A), str(PLACEHOLDER_B)).stdout.strip() == "single-pending"


@pytest.mark.parametrize("slot_a,slot_b,card,mode", [
    (28 * GIB, 28 * GIB, CARDS["64GB"], "dual"),          # expanded
    (53 * GIB, 53 * GIB, CARDS["128GB"], "dual"),
    (25 * GIB, PLACEHOLDER_B, CARDS["32GB"], "single"),   # single-system mode done
    (12 * GIB, PLACEHOLDER_B, CARDS["16GB"], "single"),
    (50 * GIB, PLACEHOLDER_B, CARDS["128GB"], "single"),  # --single on a big card
])
def test_set_up_cards(slot_a, slot_b, card, mode):
    assert _run("decide", "1", str(card), str(slot_a), str(slot_b)).stdout.strip() == mode


def test_standard_image():
    assert _run("mode", env=_facts(CARDS["32GB"], is_ab=False)).stdout.strip() == "standard"


def test_status_reports_facts_and_decimal_gb(tmp_path):
    (tmp_path / "ab-layout").write_text("pending\n# comment\n")
    out = _kv(_run("status", env=_facts(CARDS["64GB"], config_dir=tmp_path)).stdout)
    assert out["mode"] == "dual-pending"
    assert out["card_gb"] == "64"           # not "59" (GiB printed as GB, R-095)
    assert out["state"] == "pending"
    assert out["optout"] == "0"
    assert out["min_dual_bytes"] == str(THRESHOLD)


# ---------------------------------------------------------------------------
# What the first start does
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode,state,optout,action", [
    ("dual-pending", "pending", "0", "dual"),
    ("single-pending", "pending", "0", "single"),
    ("dual-pending", "pending", "1", "none:opt-out"),
    ("single-pending", "pending", "1", "none:opt-out"),
    ("dual-pending", "none", "0", "none:not-pending"),     # card written before B4
    ("single-pending", "none", "0", "none:not-pending"),
    ("dual", "dual", "0", "none:not-pending"),
    ("dual", "pending", "0", "none:already-dual"),
    ("single", "pending", "0", "none:already-single"),
    ("standard", "pending", "0", "none:standard"),
    # an interrupted set-up is finished whatever sizes and opt-out say
    ("dual", "resume-dual", "1", "dual"),
    ("dual-pending", "resume-dual", "0", "dual"),
    ("single", "resume-single", "0", "single"),
])
def test_firstboot_action(mode, state, optout, action):
    assert _run("action", mode, state, optout).stdout.strip() == action


@pytest.mark.parametrize("marker", ["no-auto-expand", "no-auto-expand.txt"])
def test_optout_marker_names(tmp_path, marker):
    (tmp_path / "ab-layout").write_text("pending\n")
    (tmp_path / marker).write_text("")
    proc = _run("firstboot", "--dry-run", env=_facts(CARDS["64GB"], config_dir=tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "-> none:opt-out" in proc.stdout


def test_firstboot_dry_run_small_card(tmp_path):
    (tmp_path / "ab-layout").write_text("pending\n")
    proc = _run("firstboot", "--dry-run", env=_facts(CARDS["32GB"], config_dir=tmp_path))
    assert "mode=single-pending state=pending optout=0 -> single" in proc.stdout


def test_firstboot_on_old_card_does_nothing(tmp_path):
    # no ab-layout file: a card written from an image before B4
    proc = _run("firstboot", "--dry-run", env=_facts(CARDS["64GB"], config_dir=tmp_path))
    assert "-> none:not-pending" in proc.stdout


def test_firstboot_records_already_set_up_card(tmp_path):
    (tmp_path / "ab-layout").write_text("pending\n")
    proc = _run("firstboot", env=_facts(CARDS["64GB"], slot_a=28 * GIB, slot_b=28 * GIB,
                                         config_dir=tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "ab-layout").read_text().splitlines()[0] == "dual"


# ---------------------------------------------------------------------------
# The layout
# ---------------------------------------------------------------------------

def _plan(how, card):
    a_end, b_start, b_end, data_start, data_mib, system_mib = map(
        int, _run("layout", how, str(card), str(P5_START_MIB)).stdout.split())
    return a_end, b_start, b_end, data_start, data_mib, system_mib


@pytest.mark.parametrize("card,slot_gib,data_gib", [
    # measured after the menu expansion on the rig (docs/ab-boot.md, lsblk)
    (127865454592, 52.9, 11.8),
    (255869321216, 106.6, 23.7),
])
def test_dual_plan_matches_the_hardware_verified_split(card, slot_gib, data_gib):
    a_end, b_start, b_end, data_start, data_mib, system_mib = _plan("dual", card)
    assert round(system_mib / 1024, 1) == slot_gib
    assert round((b_end - b_start) / 1024, 1) == slot_gib
    assert abs(data_mib / 1024 - data_gib) < 0.15


@pytest.mark.parametrize("card", list(CARDS.values()))
@pytest.mark.parametrize("how", ["dual", "single"])
def test_plan_fits_the_card_without_overlap(how, card):
    if how == "dual" and card < THRESHOLD:
        return
    card_mib = card // MIB
    a_end, b_start, b_end, data_start, data_mib, system_mib = _plan(how, card)
    assert P5_END_MIB <= a_end < b_start < b_end < data_start < card_mib
    assert b_start - a_end >= 2 and data_start - b_end >= 2      # room for the EBRs
    assert data_start + data_mib == card_mib
    # DATA stays 10% of the space after the boot partitions (Jan, Q5); in
    # dual mode the EBR gaps and p5's 2 MiB offset come off its end
    assert 0 <= (card_mib - 1536) * 10 // 100 - data_mib <= 8


@pytest.mark.parametrize("card", [CARDS["16GB"], CARDS["32GB"]])
def test_single_plan_uses_the_card(card):
    card_mib = card // MIB
    a_end, b_start, b_end, data_start, data_mib, system_mib = _plan("single", card)
    assert b_end - b_start == 16                       # Slot B stays a placeholder
    # everything but DATA, the placeholder and two EBR gaps goes to Slot A
    assert card_mib - a_end == data_mib + 16 + 4
    assert system_mib > 10240                          # grows past the shipped 10 GiB


def test_plan_refuses_two_systems_on_a_small_card():
    proc = _run("plan", "--dual", env=_facts(CARDS["32GB"]))
    assert proc.returncode != 0
    assert "too small for two systems" in proc.stderr


def test_plan_refuses_to_shrink_slot_a():
    # a card barely larger than the image: single mode would have to shrink p5
    proc = _run("plan", "--single", env=_facts(12 * GIB))
    assert proc.returncode != 0
    assert "shrink" in proc.stderr


def test_plan_text_is_for_people():
    out = _run("plan", "--text", env=_facts(CARDS["64GB"])).stdout
    assert "Card: 64 GB" in out
    assert "28.0 GB" in out and "6.2 GB" in out
    assert "empty until you install an update" in out    # not "fully configured" (R-095)


def test_apply_needs_root_and_yes():
    proc = _run("apply", "--dual", env=_facts(CARDS["64GB"]))
    assert proc.returncode != 0


# ---------------------------------------------------------------------------
# Words (R-006, R-095)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("card,slot_a,expect", [
    (CARDS["32GB"], SHIPPED_SLOT_A, "Use the whole card"),
    (CARDS["32GB"], 25 * GIB, "runs ONE system"),
    (CARDS["64GB"], SHIPPED_SLOT_A, "Prepare the card for A/B updates"),
])
def test_explain_never_dead_ends(card, slot_a, expect):
    out = _run("explain", env=_facts(card, slot_a=slot_a)).stdout
    assert expect in out
    assert "AB_BOOT" not in out and "EXPAND" not in out
    assert "0 RasQberry" in out or "Imager" in out


def test_single_mode_says_how_to_update_and_to_copy_files():
    out = _run("explain", env=_facts(CARDS["32GB"], slot_a=25 * GIB)).stdout
    assert "32 GB card is smaller than 64 GB" in out
    assert "write the new image" in out
    assert "copy your files" in out


def test_explain_mentions_the_optout(tmp_path):
    (tmp_path / "no-auto-expand").write_text("")
    out = _run("explain", env=_facts(CARDS["64GB"], config_dir=tmp_path)).stdout
    assert "no-auto-expand" in out


def test_explain_for_update_is_empty_on_a_dual_card():
    out = _run("explain", "--update", env=_facts(CARDS["64GB"], slot_a=28 * GIB, slot_b=28 * GIB))
    assert out.returncode == 0
    assert out.stdout.strip() == ""
