"""
Tests for the A/B part of RQB2-config/RQB2_menu.sh (batch B2): what the
Slot Manager says and refuses, run under dash (raspi-config's /bin/sh) with
whiptail stubbed. The model (Jan, 2026-10-02): Slot A stable, Slot B testing,
updates into Slot B, PROMOTE copies a tested Slot B to Slot A.

- R-055: no restart or rollback into a slot without a system.
- R-050: UPDATE while running Slot B offers PROMOTE or going back to Slot A.
- R-051: PROMOTE asks in a real dialog (default: Cancel).
"""

import os
import shutil
import subprocess
import textwrap

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MENU = os.path.join(_HERE, "..", "..", "RQB2-config", "RQB2_menu.sh")

DASH = shutil.which("dash")
pytestmark = pytest.mark.skipif(DASH is None, reason="dash (raspi-config's /bin/sh) required")

WHIPTAIL = """\
    #!/bin/sh
    # Records every call; answers menus with the next line of $WT_ANSWERS
    # (or $WT_ANSWER), exits with $WT_RC
    {
        echo "=== whiptail"
        for a in "$@"; do printf '%s\\n' "$a"; done
    } >> "$WT_LOG"
    case " $* " in
        *" --menu "*)
            if [ -n "${WT_ANSWERS:-}" ] && [ -s "$WT_ANSWERS" ]; then
                head -n 1 "$WT_ANSWERS" >&2
                sed -i.bak 1d "$WT_ANSWERS"
            elif [ -n "${WT_ANSWER:-}" ]; then
                printf '%s' "$WT_ANSWER" >&2
            fi ;;
    esac
    case " $* " in
        *" --yesno "*) exit "${WT_YESNO_RC:-${WT_RC:-0}}" ;;
    esac
    exit "${WT_RC:-0}"
    """

# Stand-in for rq_ab_releases.sh ($BIN_DIR is pointed at it)
RELEASES = """\
    #!/bin/sh
    G=https://github.com/JanLahmann/RasQberry-Two/releases/download
    case "$1" in
        channel) echo beta ;;
        latest)  printf 'beta-2026-10-15-101010\\t%s/beta-2026-10-15-101010/r-ab.img.xz\\t2026-10-15\\t1671527604\\n' "$G" ;;
        list)    printf 'development-2026-10-01-083408\\t%s/development-2026-10-01-083408/d-ab.img.xz\\t2026-10-01\\t2058162296\\n' "$G"
                 printf 'dev-x-2026-09-30-000000\\t%s/dev-x-2026-09-30-000000/x-ab.img.xz\\t2026-09-30\\t2000000000\\n' "$G" ;;
    esac
    """

ON_A = "\n".join([
    "layout=ab", "current=A", "confirmed=yes", "default=A", "pending=",
    "slot_a=beta-2026-09-30-221656", "slot_b=EMPTY", "expanded=yes"])
ON_B = "\n".join([
    "layout=ab", "current=B", "confirmed=yes", "default=B", "pending=",
    "slot_a=beta-2026-09-30-221656", "slot_b=beta-2026-10-15-101010", "expanded=yes"])


def _menu(tmp_path, snippet, **env_extra):
    bindir = tmp_path / "stubs"
    bindir.mkdir(exist_ok=True)
    (bindir / "whiptail").write_text(textwrap.dedent(WHIPTAIL))
    (bindir / "whiptail").chmod(0o755)
    (bindir / "rq_ab_releases.sh").write_text(textwrap.dedent(RELEASES))
    (bindir / "rq_ab_releases.sh").chmod(0o755)
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", TERM="xterm",
               WT_LOG=str(tmp_path / "whiptail.log"), STUBS=str(bindir), **env_extra)
    proc = subprocess.run([DASH, "-c", f'. "{_MENU}" >/dev/null 2>&1\nBIN_DIR="$STUBS"\n{snippet}'],
                          capture_output=True, text=True, env=env, timeout=30,
                          stdin=subprocess.DEVNULL)
    log = tmp_path / "whiptail.log"
    return proc, (log.read_text() if log.exists() else "")


def test_menu_parses_under_dash():
    assert subprocess.run([DASH, "-n", _MENU]).returncode == 0


@pytest.mark.parametrize("summary,expected", [
    (ON_A, "Next: install an update into Slot B."),
    (ON_A.replace("slot_b=EMPTY", "slot_b=beta-2026-10-15-101010"), "restart into Slot B to use it"),
    (ON_B, "If this version works well, PROMOTE copies it to Slot A"),
    (ON_B.replace("confirmed=yes", "confirmed=no"), "on trial"),
    (ON_A.replace("expanded=yes", "expanded=no"), "EXPAND it first"),
    # right after PROMOTE, before the restart
    (ON_B.replace("default=B", "default=A").replace("slot_a=beta-2026-09-30-221656", "slot_a=beta-2026-10-15-101010"),
     "PROMOTE is done: restart to start from Slot A"),
    # after a rollback was configured
    (ON_A.replace("default=A", "default=B").replace("slot_b=EMPTY", "slot_b=beta-2026-10-15-101010"),
     "The next restart starts Slot B."),
])
def test_next_step_follows_the_model(tmp_path, summary, expected):
    proc, _ = _menu(tmp_path, 'ab_next_step "$S"', S=summary)
    assert expected in proc.stdout


def test_restart_into_an_empty_slot_is_refused(tmp_path):
    proc, wt = _menu(tmp_path, 'ab_restart_into B "$S"', S=ON_A)
    assert proc.returncode == 0
    assert "--msgbox" in wt and "--yesno" not in wt
    assert "Slot B holds: empty (no system)" in wt
    assert "black screen" in wt
    assert "Install an update into Slot B" in wt


def test_rollback_into_an_empty_slot_is_refused(tmp_path):
    _, wt = _menu(tmp_path, 'ab_rollback "$S"', S=ON_A)
    assert "Rollback not possible" in wt and "--yesno" not in wt


def test_promote_on_slot_a_explains_instead_of_failing(tmp_path):
    _, wt = _menu(tmp_path, 'do_ab_promote "$S"', S=ON_A)
    assert "only while the Pi is running Slot B" in wt
    assert "Install a system into Slot B first" in wt


def test_promote_asks_in_a_visible_dialog_defaulting_to_cancel(tmp_path):
    proc, wt = _menu(tmp_path, 'do_ab_promote "$S"; echo rc=$?', S=ON_B, WT_RC="1")
    assert "--yesno" in wt and "--defaultno" in wt
    assert "Promote" in wt and "Copy the running system to Slot A?" in wt
    assert "beta-2026-10-15-101010" in wt and "will be replaced" in wt
    assert "rc=0" in proc.stdout        # cancelled: nothing else ran


def test_update_from_slot_b_offers_promote_or_slot_a(tmp_path):
    _, wt = _menu(tmp_path, 'ab_offer_free_slot_b "$S"', S=ON_B, WT_RC="1")
    assert "You are running Slot B right now" in wt
    assert "PROMOTE" in wt and "SLOT_A" in wt


def test_offer_without_a_system_in_slot_a_offers_promote_only(tmp_path):
    _, wt = _menu(tmp_path, 'ab_offer_free_slot_b "$S"',
                  S=ON_B.replace("slot_a=beta-2026-09-30-221656", "slot_a=EMPTY"), WT_RC="1")
    assert "PROMOTE" in wt and "SLOT_A" not in wt


def test_slot_values_and_sizes(tmp_path):
    proc, _ = _menu(tmp_path, 'ab_value "$S" slot_b; ab_describe INCOMPLETE; ab_gb 1671527604; ab_gb ""',
                    S=ON_B)
    assert proc.stdout.splitlines() == [
        "beta-2026-10-15-101010", "unfinished (an update or copy was interrupted)", "1.7 GB", "about 2 GB"]


def test_picker_offers_the_own_channel_first_and_returns_only_the_choice(tmp_path):
    # The lab found progress lines ("Asking rasqberry.org ...") inside the
    # URL: stdout of the picker must be exactly url|tag|size
    proc, wt = _menu(tmp_path, 'ab_pick_image', WT_ANSWER="beta-2026-10-15-101010")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ("https://github.com/JanLahmann/RasQberry-Two/releases/download/"
                           "beta-2026-10-15-101010/r-ab.img.xz|beta-2026-10-15-101010|1671527604\n")
    assert "latest beta, 2026-10-15, 1.7 GB (recommended)" in wt
    assert "Asking rasqberry.org" in proc.stderr


def test_picker_other_channel_defaults_to_the_own_channel(tmp_path):
    answers = tmp_path / "answers"
    answers.write_text("OTHER\ndev\ndev-x-2026-09-30-000000\n")
    proc, wt = _menu(tmp_path, 'ab_pick_image', WT_ANSWERS=str(answers))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().endswith("/x-ab.img.xz|dev-x-2026-09-30-000000|2000000000")
    channel_menu = wt.split("=== whiptail")[2]
    assert "--default-item\nbeta\n" in channel_menu
    assert "This system follows: beta" in channel_menu


def test_install_dialog_names_both_slots(tmp_path):
    # Cancel at the confirmation: nothing is installed
    preflight = tmp_path / "stubs"
    preflight.mkdir()
    (preflight / "rq_update_slot.sh").write_text("#!/bin/sh\necho ok\n")
    (preflight / "rq_update_slot.sh").chmod(0o755)
    (preflight / "rq_slot_manager.sh").write_text("#!/bin/sh\nprintf '%s\\n' \"$S\"\n")
    (preflight / "rq_slot_manager.sh").chmod(0o755)
    _, wt = _menu(tmp_path, 'do_ab_install_update', S=ON_A.replace("slot_b=EMPTY", "slot_b=beta-2026-09-01-000000"),
                  WT_ANSWER="beta-2026-10-15-101010", WT_YESNO_RC="1")
    confirm = wt.split("=== whiptail")[-1]
    assert "Install beta-2026-10-15-101010 into Slot B (testing)?" in confirm
    assert "beta-2026-09-01-000000 - will be replaced" in confirm
    assert "beta-2026-09-30-221656 - not touched" in confirm
