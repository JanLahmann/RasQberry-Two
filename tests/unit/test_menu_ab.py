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
            elif [ -n "${WT_ANSWERS:-}" ]; then
                exit 1    # no answers left: Back
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
        latest)  printf 'beta-2026-10-15-101010\\t%s/beta-2026-10-15-101010/r-ab.img.xz\\t2026-10-15\\t1671527604\\tabc1\\n' "$G" ;;
        list)    printf 'development-2026-10-01-083408\\t%s/development-2026-10-01-083408/d-ab.img.xz\\t2026-10-01\\t2058162296\\tdef2\\n' "$G"
                 printf 'dev-x-2026-09-30-000000\\t%s/dev-x-2026-09-30-000000/x-ab.img.xz\\t2026-09-30\\t2000000000\\tfed3\\n' "$G" ;;
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
    # the visible label, not the hidden EXPAND tag (B4, R-095)
    (ON_A.replace("expanded=yes", "expanded=no"), "Prepare the card for A/B updates"),
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
    assert "Slot B cannot be the default" in wt and "--yesno" not in wt


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
                           "beta-2026-10-15-101010/r-ab.img.xz|beta-2026-10-15-101010|1671527604|abc1\n")
    assert "latest beta, 2026-10-15, 1.7 GB (recommended)" in wt
    assert "Asking rasqberry.org" in proc.stderr


def test_picker_other_channel_defaults_to_the_own_channel(tmp_path):
    answers = tmp_path / "answers"
    answers.write_text("OTHER\ndev\ndev-x-2026-09-30-000000\n")
    proc, wt = _menu(tmp_path, 'ab_pick_image', WT_ANSWERS=str(answers))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().endswith("/x-ab.img.xz|dev-x-2026-09-30-000000|2000000000|fed3")
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


# ---------------------------------------------------------------------------
# B2 + B4: a placeholder Slot B on a small card is single-system mode (R-006)
# ---------------------------------------------------------------------------

EXPLAIN = """\
    #!/bin/sh
    # Stand-in for rq_expand_ab.sh
    case "$1" in
        mode)    echo "${FAKE_MODE:-dual}" ;;
        explain) echo "This 32 GB card is smaller than 64 GB, so it runs ONE system: (explain $2)" ;;
    esac
    """


def _stub(tmp_path, name, body):
    d = tmp_path / "stubs"
    d.mkdir(exist_ok=True)
    (d / name).write_text(textwrap.dedent(body))
    (d / name).chmod(0o755)


@pytest.mark.parametrize("mode,title,text", [
    ("single", "One system on this card", "runs ONE system: (explain --update)"),
    ("single-pending", "One system on this card", "runs ONE system: (explain --update)"),
    ("dual-pending", "Slot B is not set up", "Prepare the card for A/B updates"),
])
def test_not_set_up_follows_the_card_mode_from_the_summary(tmp_path, mode, title, text):
    _stub(tmp_path, "rq_expand_ab.sh", EXPLAIN)
    _stub(tmp_path, "rq_update_slot.sh", "#!/bin/sh\necho 'ERROR: placeholder' >&2\nexit 21\n")
    _stub(tmp_path, "rq_slot_manager.sh", "#!/bin/sh\nprintf '%s\\n' \"$S\"\n")
    summary = ON_A.replace("expanded=yes", "expanded=no") + "\ncard_mode=" + mode
    _, wt = _menu(tmp_path, 'do_ab_install_update', S=summary)
    box = wt.split("=== whiptail")[-1]
    assert title in box and text in box
    assert "too small for two systems" not in box


def test_not_set_up_falls_back_to_rq_expand_ab_without_the_key(tmp_path):
    # an older rq_slot_manager.sh without card_mode: ask rq_expand_ab.sh
    _stub(tmp_path, "rq_expand_ab.sh", EXPLAIN)
    proc, _ = _menu(tmp_path, 'ab_not_expanded_text "$S"',
                    S=ON_A.replace("expanded=yes", "expanded=no"), FAKE_MODE="single")
    assert "runs ONE system" in proc.stdout


# ---------------------------------------------------------------------------
# Feedback 2026-10-03: item 28 and the H-34 follow-ups
# ---------------------------------------------------------------------------

def _slot_manager(tmp_path, summary, answers):
    _stub(tmp_path, "rq_slot_manager.sh", "#!/bin/sh\nprintf '%s\\n' \"$S\"\n")
    _stub(tmp_path, "rq_expand_ab.sh", EXPLAIN)
    f = tmp_path / "answers"
    f.write_text(answers)
    _, wt = _menu(tmp_path, 'do_slot_manager_menu', S=summary, WT_ANSWERS=str(f))
    return [c for c in wt.split("=== whiptail") if "Slot Manager" in c]


def test_slot_manager_on_slot_a_offers_no_promote_and_no_rollback_to_b(tmp_path):
    menus = _slot_manager(tmp_path, ON_A.replace("slot_b=EMPTY", "slot_b=beta-2026-10-15-101010"), "")
    first = menus[0]
    assert "\nPROMOTE\n" not in first
    assert "Make Slot B the stable system" not in first
    assert "Go back to Slot B" not in first and "Start Slot B by default from now on" in first
    assert "beta-2026-09-30-221656 (running, starts by default)" in first


def test_slot_manager_on_slot_b_says_which_slot_starts(tmp_path):
    first = _slot_manager(tmp_path, ON_B, "")[0]
    assert "Slot B (testing): beta-2026-10-15-101010 (running, starts by default)" in first
    assert "\"testing\" only says that updates go into it" in first
    assert "Go back to Slot A for good (rollback)" in first and "PROMOTE" in first


def test_slot_manager_keeps_the_cursor_on_the_last_choice(tmp_path):
    # STATUS, then Back: the second menu opens on STATUS, not on UPDATE
    menus = _slot_manager(tmp_path, ON_A, "STATUS\n")
    assert len(menus) >= 2
    assert "--default-item\nSTATUS\n" in menus[1]


def test_install_dialog_gives_a_realistic_time(tmp_path):
    _stub(tmp_path, "rq_update_slot.sh", "#!/bin/sh\necho ok\n")
    _stub(tmp_path, "rq_slot_manager.sh", "#!/bin/sh\nprintf '%s\\n' \"$S\"\n")
    _, wt = _menu(tmp_path, 'do_ab_install_update', S=ON_A,
                  WT_ANSWER="beta-2026-10-15-101010", WT_YESNO_RC="1")
    confirm = wt.split("=== whiptail")[-1]
    assert "about 10-20 minutes" in confirm and "20-30" not in confirm
