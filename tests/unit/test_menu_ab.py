"""
Tests for the A/B part of RQB2-config/RQB2_menu.sh: what the Slot Manager says
and refuses, run under dash (raspi-config's /bin/sh) with whiptail stubbed.

The model (ping-pong, Jan 2026-10-04): every update goes into the slot that is
not running, A or B alike; a good trial start makes it the start slot, the
other slot stays as the way back. There is no PROMOTE and no "stable" or
"testing" slot. Jan's guard (rq_slot_manager.sh plan-update) keeps at least
one slot at beta or stable: a downgrade asks (default: Cancel), replacing the
last beta/stable slot offers the safer switch first and needs a typed REPLACE.

- R-055: no restart or rollback into a slot without a system.
- R-051: questions are real dialogs, never a hidden prompt.
- Every dialog of these flows fits 80x24.
"""

import os
import re
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
    # Records every call. Menus answer with the next line of $WT_ANSWERS (or
    # $WT_ANSWER), an inputbox with $WT_INPUT, a yes/no with the next line of
    # $WT_YESNO_ANSWERS (else $WT_YESNO_RC / $WT_RC)
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
        *" --inputbox "*)
            printf '%s' "${WT_INPUT:-}" >&2 ;;
        *" --yesno "*)
            if [ -n "${WT_YESNO_ANSWERS:-}" ] && [ -s "$WT_YESNO_ANSWERS" ]; then
                rc=$(head -n 1 "$WT_YESNO_ANSWERS")
                sed -i.bak 1d "$WT_YESNO_ANSWERS"
                exit "$rc"
            fi
            exit "${WT_YESNO_RC:-${WT_RC:-0}}" ;;
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

# Stand-in for rq_slot_manager.sh: summary from $S, plan-update from $PLAN
SLOT_MANAGER = """\
    #!/bin/sh
    case "$1" in
        plan-update) [ -n "${PLAN_RC:-}" ] && { echo "ERROR: $PLAN" >&2; exit "$PLAN_RC"; }
                     printf '%s\\n' "$PLAN" ;;
        switch-to|rollback) echo "slot-manager $*" >> "$CALLS"; exit 1 ;;
        *) printf '%s\\n' "$S" ;;
    esac
    """

# Stand-in for rq_update_slot.sh: --preflight answers $PRE_RC (message
# $PRE_MSG); an update is recorded in $CALLS and "fails", so the menu does not
# wait for the restart
UPDATE_SLOT = """\
    #!/bin/sh
    case "$1" in
        --preflight) [ -n "${PRE_MSG:-}" ] && echo "ERROR: $PRE_MSG" >&2
                     exit "${PRE_RC:-0}" ;;
        *) echo "update $*" >> "$CALLS"; exit 1 ;;
    esac
    """

ON_A = "\n".join([
    "layout=ab", "current=A", "confirmed=yes", "default=A", "pending=",
    "slot_a=beta-2026-09-30-221656", "slot_b=EMPTY", "expanded=yes"])
ON_B = "\n".join([
    "layout=ab", "current=B", "confirmed=yes", "default=B", "pending=",
    "slot_a=beta-2026-09-30-221656", "slot_b=beta-2026-10-15-101010", "expanded=yes"])
# A dev build runs in Slot A; Slot B holds the card's only beta
ON_A_DEV = "\n".join([
    "layout=ab", "current=A", "confirmed=yes", "default=A", "pending=",
    "slot_a=development-2026-10-04-014357", "slot_b=beta-2026-10-03-095636", "expanded=yes"])

DEV_NEW = "development-2026-10-01-083408"
# Picker answers that choose DEV_NEW: Other -> dev -> the release
PICK_DEV = ["OTHER", "dev", DEV_NEW]


def _plan(target="B", target_holds="none empty", running_holds="beta beta-2026-09-30-221656",
          new="beta beta-2026-10-15-101010", downgrade="none", last_safe="no"):
    return "\n".join([
        f"target={target}", f"running={'A' if target == 'B' else 'B'}",
        f"target_holds={target_holds}", f"running_holds={running_holds}", f"new={new}",
        f"downgrade={downgrade}", f"last_safe_slot={last_safe}", "advice=x"])


def _stub(tmp_path, name, body):
    d = tmp_path / "stubs"
    d.mkdir(exist_ok=True)
    (d / name).write_text(textwrap.dedent(body))
    (d / name).chmod(0o755)


def _menu(tmp_path, snippet, **env_extra):
    _stub(tmp_path, "whiptail", WHIPTAIL)
    _stub(tmp_path, "rq_ab_releases.sh", RELEASES)
    bindir = tmp_path / "stubs"
    for name, body in (("rq_slot_manager.sh", SLOT_MANAGER), ("rq_update_slot.sh", UPDATE_SLOT)):
        if not (bindir / name).exists():
            _stub(tmp_path, name, body)
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", TERM="xterm",
               WT_LOG=str(tmp_path / "whiptail.log"), STUBS=str(bindir),
               CALLS=str(tmp_path / "calls"))
    env.update({k: v for k, v in env_extra.items() if v is not None})
    # A new session: no controlling terminal, so ab_pause's read from
    # /dev/tty fails instead of waiting for Enter
    proc = subprocess.run([DASH, "-c", f'. "{_MENU}" >/dev/null 2>&1\nBIN_DIR="$STUBS"\n{snippet}'],
                          capture_output=True, text=True, env=env, timeout=30,
                          stdin=subprocess.DEVNULL, start_new_session=True)
    log = tmp_path / "whiptail.log"
    return proc, (log.read_text() if log.exists() else "")


def _calls(tmp_path):
    f = tmp_path / "calls"
    return f.read_text() if f.exists() else ""


def _boxes(wt):
    return [c for c in wt.split("=== whiptail") if c.strip()]


def _answers(tmp_path, name, lines):
    f = tmp_path / name
    f.write_text("".join(f"{line}\n" for line in lines))
    return str(f)


def test_menu_parses_under_dash():
    assert subprocess.run([DASH, "-n", _MENU]).returncode == 0


@pytest.mark.parametrize("summary,expected", [
    (ON_A, "Next: install an update into Slot B, the other system."),
    (ON_A.replace("slot_b=EMPTY", "slot_b=beta-2026-10-15-101010"),
     "To go back to Slot B instead, switch to it."),
    # Slot B running: the next update goes into Slot A - neither slot is special
    (ON_B, "Next: install an update into Slot A, the other system."),
    (ON_B.replace("confirmed=yes", "confirmed=no").replace("default=B", "default=A").replace("pending=", "pending=B"),
     "Slot B is on trial: the health check makes it the start slot after a good start. "
     "If the update doesn't work, the next restart returns to Slot A."),
    (ON_A.replace("confirmed=yes", "confirmed=no").replace("default=A", "default=B").replace("pending=", "pending=A"),
     "Slot A is on trial"),
    # the visible label, not the hidden EXPAND tag (B4, R-095)
    (ON_A.replace("expanded=yes", "expanded=no"), "Prepare the card for A/B updates"),
    # after a rollback was configured
    (ON_A.replace("default=A", "default=B").replace("slot_b=EMPTY", "slot_b=beta-2026-10-15-101010"),
     "The next restart starts Slot B."),
])
def test_next_step_follows_the_model(tmp_path, summary, expected):
    proc, _ = _menu(tmp_path, 'ab_next_step "$S"', S=summary)
    assert expected in proc.stdout
    assert "PROMOTE" not in proc.stdout and "stable" not in proc.stdout


def test_restart_into_an_empty_slot_is_refused(tmp_path):
    proc, wt = _menu(tmp_path, 'ab_restart_into B "$S"', S=ON_A)
    assert proc.returncode == 0
    assert "--msgbox" in wt and "--yesno" not in wt
    assert "Slot B holds: empty (no system)" in wt
    assert "black screen" in wt
    assert "Install an update into the other system (Slot B)" in wt


def test_rollback_into_an_empty_slot_is_refused(tmp_path):
    _, wt = _menu(tmp_path, 'ab_rollback "$S"', S=ON_A)
    assert "Slot B cannot be the start slot" in wt and "--yesno" not in wt


@pytest.mark.parametrize("summary,slot,other", [
    (ON_A.replace("slot_b=EMPTY", "slot_b=beta-2026-10-15-101010"), "B", "A"),
    (ON_B, "A", "B"),
])
def test_switch_dialog_says_what_happens_both_ways(tmp_path, summary, slot, other):
    _, wt = _menu(tmp_path, f'ab_restart_into {slot} "$S"', S=summary, WT_RC="1")
    box = _boxes(wt)[-1]
    assert f"Switch to Slot {slot}" in box
    assert f"If it works, the health check makes it the start slot, and Slot {other} stays as the way back" in box
    assert f"If it doesn't work, the Pi goes back to Slot {other} by itself" in box
    assert "start properly" not in box and "didn't start" not in box
    assert "slot-manager" not in _calls(tmp_path)     # cancelled


def test_rollback_asks_defaulting_to_cancel(tmp_path):
    _, wt = _menu(tmp_path, 'ab_rollback "$S"', S=ON_B, WT_RC="1")
    box = _boxes(wt)[-1]
    assert "Make Slot A the start slot" in box and "--defaultno" in box
    assert "Start Slot A: beta-2026-09-30-221656 (beta) from now on" in box
    assert "Running now: Slot B, which stays as it is." in box


def test_slot_values_and_sizes(tmp_path):
    proc, _ = _menu(tmp_path, 'ab_value "$S" slot_b; ab_describe INCOMPLETE; ab_describe beta-2026-10-15-101010; '
                              'ab_describe development-2026-10-04-014357; ab_describe 1.10.0; ab_describe my-build; '
                              'ab_gb 1671527604; ab_gb ""', S=ON_B)
    assert proc.stdout.splitlines() == [
        "beta-2026-10-15-101010", "unfinished (an update was interrupted)",
        "beta-2026-10-15-101010 (beta)", "development-2026-10-04-014357 (dev)", "1.10.0 (stable)",
        "my-build", "1.7 GB", "about 2 GB"]


def test_picker_offers_the_own_channel_first_and_returns_only_the_choice(tmp_path):
    # The lab found progress lines ("Asking rasqberry.org ...") inside the
    # URL: stdout of the picker must be exactly url|tag|size
    proc, wt = _menu(tmp_path, 'ab_pick_image B', WT_ANSWER="beta-2026-10-15-101010")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ("https://github.com/JanLahmann/RasQberry-Two/releases/download/"
                           "beta-2026-10-15-101010/r-ab.img.xz|beta-2026-10-15-101010|1671527604|abc1\n")
    assert "latest beta, 2026-10-15, 1.7 GB (recommended)" in wt
    assert "Choose the release to install into Slot B:" in wt
    # tags hidden (#16): the release name is in the item text, OTHER is not shown
    menu = _boxes(wt)[0]
    assert "--notags" in menu
    assert "beta-2026-10-15-101010\nbeta-2026-10-15-101010  latest beta, 2026-10-15" in menu
    assert "Asking rasqberry.org" in proc.stderr


def test_picker_says_when_nothing_newer_is_out(tmp_path):
    # User test #2: the running beta is the latest. The picker must say so
    # plainly - never "withdrawn", never "recommended" for the same release
    vf = tmp_path / "rasqberry-version"
    vf.write_text("beta-2026-10-15-101010\n")
    _, wt = _menu(tmp_path, 'ab_pick_image B', RQ_VERSION_FILE=str(vf),
                  WT_ANSWERS=_answers(tmp_path, "menus", []))
    menu = _boxes(wt)[0]
    assert "You have the newest beta release: nothing newer is out yet." in menu
    assert "install the same release into Slot B (a second copy to go back to)" in menu
    assert "beta-2026-10-15-101010  the version you are running (a second copy)" in menu
    assert "withdrawn" not in menu and "recommended" not in menu
    assert _check_fits(wt) >= 1


def test_picker_names_slot_a_when_slot_b_runs(tmp_path):
    _, wt = _menu(tmp_path, 'ab_pick_image A', WT_ANSWER="beta-2026-10-15-101010")
    assert "Install an update into Slot A" in wt and "install into Slot A:" in wt


def test_picker_other_channel_defaults_to_the_own_channel(tmp_path):
    answers = tmp_path / "answers"
    answers.write_text("OTHER\ndev\ndev-x-2026-09-30-000000\n")
    proc, wt = _menu(tmp_path, 'ab_pick_image B', WT_ANSWERS=str(answers))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().endswith("/x-ab.img.xz|dev-x-2026-09-30-000000|2000000000|fed3")
    channel_menu = wt.split("=== whiptail")[2]
    assert "--default-item\nbeta\n" in channel_menu
    assert "Choose a release stream. This system follows: beta" in channel_menu
    assert "channel" not in wt
    # the list of releases keeps its tags: they are the release names
    release_menu = wt.split("=== whiptail")[3]
    assert "--notags" not in release_menu and "--notags" in channel_menu


# ---------------------------------------------------------------------------
# Installing an update: always into the other system, with Jan's guard
# ---------------------------------------------------------------------------

def _install(tmp_path, summary, plan, **env):
    env.setdefault("WT_ANSWER", "beta-2026-10-15-101010")
    return _menu(tmp_path, 'do_ab_install_update', S=summary, PLAN=plan, **env)


def test_install_dialog_names_both_slots(tmp_path):
    # Cancel at the confirmation: nothing is installed
    summary = ON_A.replace("slot_b=EMPTY", "slot_b=beta-2026-09-01-000000")
    proc, wt = _install(tmp_path, summary, _plan(target_holds="beta beta-2026-09-01-000000"),
                        WT_YESNO_RC="1")
    confirm = _boxes(wt)[-1]
    assert "Install an update into Slot B" in confirm
    assert "Install beta-2026-10-15-101010 into Slot B?" in confirm
    assert "Slot B now: beta-2026-09-01-000000 (beta) - will be replaced" in confirm
    assert "Slot A (running): beta-2026-09-30-221656 (beta) - not touched" in confirm
    assert "If the update doesn't work, the Pi goes back to Slot A by itself" in confirm
    assert "Checking whether Slot B can take an update" in proc.stdout
    assert _calls(tmp_path) == ""


def test_install_while_running_slot_b_goes_into_slot_a(tmp_path):
    proc, wt = _install(tmp_path, ON_B, _plan(target="A", target_holds="beta beta-2026-09-30-221656",
                                             running_holds="beta beta-2026-10-15-101010"),
                        WT_YESNO_RC="1")
    confirm = _boxes(wt)[-1]
    assert "Install beta-2026-10-15-101010 into Slot A?" in confirm
    assert "Slot A now: beta-2026-09-30-221656 (beta) - will be replaced" in confirm
    assert "Slot B (running): beta-2026-10-15-101010 (beta) - not touched" in confirm
    assert "the Pi goes back to Slot B by itself" in confirm
    assert "Checking whether Slot A can take an update" in proc.stdout


def test_install_runs_the_update_into_the_target_slot(tmp_path):
    _install(tmp_path, ON_A, _plan(), WT_YESNO_RC="0")
    assert _calls(tmp_path).strip() == (
        "update https://github.com/JanLahmann/RasQberry-Two/releases/download/beta-2026-10-15-101010/"
        "r-ab.img.xz beta-2026-10-15-101010 --slot B --sha256 abc1")


@pytest.mark.parametrize("plan", [
    _plan(),                                                         # empty target
    _plan(target_holds="dev development-2026-10-01-083408", new=f"dev {DEV_NEW}",
          running_holds="dev development-2026-10-04-014357"),        # dev over dev
])
def test_no_warning_for_an_empty_target_or_dev_over_dev(tmp_path, plan):
    _, wt = _install(tmp_path, ON_A, plan, WT_YESNO_RC="1")
    yesnos = [b for b in _boxes(wt) if "--yesno" in b]
    assert len(yesnos) == 1 and "Install an update into Slot B" in yesnos[0]
    assert "downgrade" not in wt and "last beta or stable" not in wt


@pytest.mark.parametrize("downgrade,holds,picks,text", [
    ("stream", "beta beta-2026-10-03-095636", PICK_DEV,
     "Slot B holds beta-2026-10-03-095636 (beta).\\ndevelopment-2026-10-01-083408 (dev) comes from a "
     "less tested release stream, so installing it is a downgrade."),
    ("older", "beta beta-2026-10-20-000000", ["beta-2026-10-15-101010"],
     "Slot B holds beta-2026-10-20-000000 (beta).\\nbeta-2026-10-15-101010 is older, "
     "so installing it is a downgrade."),
])
def test_a_downgrade_warns_defaulting_to_cancel(tmp_path, downgrade, holds, picks, text):
    plan = _plan(target_holds=holds, downgrade=downgrade)
    _, wt = _install(tmp_path, ON_A, plan, WT_ANSWER=None, WT_ANSWERS=_answers(tmp_path, "menus", picks),
                     WT_YESNO_ANSWERS=_answers(tmp_path, "yn", ["1"]))
    box = [b for b in _boxes(wt) if "--yesno" in b][0]
    assert "This is a downgrade" in box and "--defaultno" in box
    assert text in box
    assert "Install it anyway?" in box
    # cancelled: no confirmation, no update
    assert len([b for b in _boxes(wt) if "--yesno" in b]) == 1
    assert _calls(tmp_path) == ""


def test_an_accepted_downgrade_passes_allow_downgrade(tmp_path):
    plan = _plan(target_holds="beta beta-2026-10-03-095636", new=f"dev {DEV_NEW}", downgrade="stream")
    _install(tmp_path, ON_A, plan, WT_ANSWER=None, WT_ANSWERS=_answers(tmp_path, "menus", PICK_DEV),
             WT_YESNO_ANSWERS=_answers(tmp_path, "yn", ["0", "0"]))
    assert _calls(tmp_path).rstrip().endswith(f"{DEV_NEW} --slot B --sha256 def2 --allow-downgrade")


LAST_SAFE_PLAN = _plan(target_holds="beta beta-2026-10-03-095636",
                       running_holds="dev development-2026-10-04-014357",
                       new=f"dev {DEV_NEW}", downgrade="stream", last_safe="yes")


def test_the_last_safe_slot_offers_the_safer_switch_first(tmp_path):
    # downgrade accepted, then SWITCH: the switch dialog (cancelled), no update
    _, wt = _install(tmp_path, ON_A_DEV, LAST_SAFE_PLAN, WT_ANSWER=None,
                     WT_ANSWERS=_answers(tmp_path, "menus", PICK_DEV + ["SWITCH"]),
                     WT_YESNO_ANSWERS=_answers(tmp_path, "yn", ["0", "1"]))
    menu = [b for b in _boxes(wt) if "last beta or stable" in b][0]
    assert "Slot B holds your last beta or stable system" in menu
    assert "Slot B: beta-2026-10-03-095636 (beta)" in menu
    assert "Slot A (running): development-2026-10-04-014357 (dev)" in menu
    assert f"Installing {DEV_NEW} into Slot B replaces the only beta or stable system on this card" in menu
    assert "Safer: switch to Slot B first. After the restart, install the update into Slot A." in menu
    items = menu.split("--menu", 1)[1]
    assert items.index("SWITCH\nSwitch to Slot B now, then install into Slot A") < items.index(
        "REPLACE\nReplace Slot B anyway")
    assert "Switch to Slot B" in _boxes(wt)[-1] and "--yesno" in _boxes(wt)[-1]
    assert "update " not in _calls(tmp_path)


def test_replacing_the_last_safe_slot_needs_a_typed_replace(tmp_path):
    _, wt = _install(tmp_path, ON_A_DEV, LAST_SAFE_PLAN, WT_ANSWER=None,
                     WT_ANSWERS=_answers(tmp_path, "menus", PICK_DEV + ["REPLACE"]),
                     WT_YESNO_ANSWERS=_answers(tmp_path, "yn", ["0", "0"]), WT_INPUT="REPLACE")
    box = [b for b in _boxes(wt) if "--inputbox" in b][0]
    assert "Type REPLACE to overwrite it:" in box
    assert _calls(tmp_path).rstrip().endswith("--allow-downgrade --force-replace-safe-slot")


@pytest.mark.parametrize("typed", ["replace", "yes", ""])
def test_anything_but_replace_changes_nothing(tmp_path, typed):
    _, wt = _install(tmp_path, ON_A_DEV, LAST_SAFE_PLAN, WT_ANSWER=None,
                     WT_ANSWERS=_answers(tmp_path, "menus", PICK_DEV + ["REPLACE"]),
                     WT_YESNO_ANSWERS=_answers(tmp_path, "yn", ["0", "0"]), WT_INPUT=typed)
    assert "Nothing was changed" in _boxes(wt)[-1]
    assert "Slot B still holds beta-2026-10-03-095636 (beta)." in _boxes(wt)[-1]
    assert _calls(tmp_path) == ""


# A renamed user (#319): a release that only knows rasqberry needs a typed
# RASQBERRY (rq_update_slot.sh then gets --force-old-release)
OLD_RELEASE_PLAN = _plan() + "\nuser=jan\nuser_names=no"


def test_an_old_release_for_a_renamed_user_needs_a_typed_rasqberry(tmp_path):
    _, wt = _install(tmp_path, ON_A, OLD_RELEASE_PLAN, WT_INPUT="RASQBERRY")
    box = [b for b in _boxes(wt) if "--inputbox" in b][0]
    assert "This release does not know your user name" in box
    assert "only knows the user rasqberry" in box
    assert "not as jan" in box and "/home/jan" in box and "Raspberry Pi Connect" in box
    assert "Type RASQBERRY to install it anyway:" in box
    assert _calls(tmp_path).rstrip().endswith("--force-old-release")
    assert _check_fits(wt) >= 1


@pytest.mark.parametrize("typed", ["rasqberry", "yes", ""])
def test_anything_but_rasqberry_installs_nothing(tmp_path, typed):
    _, wt = _install(tmp_path, ON_A, OLD_RELEASE_PLAN, WT_INPUT=typed)
    assert "Nothing was changed" in _boxes(wt)[-1]
    assert _calls(tmp_path) == ""


def test_an_unchecked_release_says_so(tmp_path):
    _, wt = _install(tmp_path, ON_A, _plan() + "\nuser=jan\nuser_names=unknown", WT_INPUT="")
    box = [b for b in _boxes(wt) if "--inputbox" in b][0]
    assert "Could not check whether beta-2026-10-15-101010 knows user names" in box


@pytest.mark.parametrize("extra", ["\nuser=jan\nuser_names=yes", "\nuser=rasqberry\nuser_names=n/a", ""])
def test_no_user_name_question_otherwise(tmp_path, extra):
    _, wt = _install(tmp_path, ON_A, _plan() + extra, WT_YESNO_RC="1")
    assert "This release does not know your user name" not in wt


def test_the_plan_gets_the_download_url():
    text = open(_MENU).read()
    assert 'rq_slot_manager.sh plan-update "$tag" "$url"' in text


def test_a_slot_on_trial_explains_instead_of_installing(tmp_path):
    msg = "Slot A, the system you are running, is still on trial: try again in a few minutes."
    _, wt = _install(tmp_path, ON_A, _plan(), PRE_RC="28", PRE_MSG=msg)
    box = _boxes(wt)[-1]
    assert "Cannot install an update now" in box and "still on trial" in box
    assert "ERROR" not in box


def test_a_plan_that_fails_stops_before_any_question(tmp_path):
    _, wt = _install(tmp_path, ON_A, "Cannot check what Slot B holds", PLAN_RC="1")
    box = _boxes(wt)[-1]
    assert "Could not check what the update would replace" in box
    assert "--yesno" not in wt and _calls(tmp_path) == ""


def test_install_dialog_gives_a_realistic_time(tmp_path):
    _, wt = _install(tmp_path, ON_A, _plan(), WT_YESNO_RC="1")
    confirm = _boxes(wt)[-1]
    assert "about 10-20 minutes" in confirm and "20-30" not in confirm


def test_check_for_update_offers_the_other_system(tmp_path):
    _stub(tmp_path, "rq_update_check.sh", "#!/bin/sh\necho 'beta-2026-10-15-101010 is out.'\nexit 10\n")
    _, wt = _menu(tmp_path, 'do_check_for_update', S=ON_B, WT_RC="1")
    box = _boxes(wt)[-1]
    assert "Install it into Slot A, the other system, now?" in box
    assert "Slot B, the system you are running, stays as it is" in box


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


@pytest.mark.parametrize("mode,title,text", [
    ("single", "One system on this card", "runs ONE system: (explain --update)"),
    ("single-pending", "One system on this card", "runs ONE system: (explain --update)"),
    ("dual-pending", "Slot B is not set up", "Prepare the card for A/B updates"),
])
def test_not_set_up_follows_the_card_mode_from_the_summary(tmp_path, mode, title, text):
    _stub(tmp_path, "rq_expand_ab.sh", EXPLAIN)
    summary = ON_A.replace("expanded=yes", "expanded=no") + "\ncard_mode=" + mode
    _, wt = _menu(tmp_path, 'do_ab_install_update', S=summary, PRE_RC="21", PRE_MSG="placeholder")
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
# The Slot Manager
# ---------------------------------------------------------------------------

def _slot_manager(tmp_path, summary, answers):
    _stub(tmp_path, "rq_expand_ab.sh", EXPLAIN)
    f = tmp_path / "answers"
    f.write_text(answers)
    _, wt = _menu(tmp_path, 'do_slot_manager_menu', S=summary, WT_ANSWERS=str(f))
    return [c for c in wt.split("=== whiptail") if "Slot Manager" in c]


def test_slot_manager_on_slot_a(tmp_path):
    first = _slot_manager(tmp_path, ON_A.replace("slot_b=EMPTY", "slot_b=development-2026-10-04-014357"), "")[0]
    assert "Slot A: beta-2026-09-30-221656 (beta) - running, start slot" in first
    assert "Slot B: development-2026-10-04-014357 (dev)\\n" in first
    assert "UPDATE\nInstall an update into the other system (Slot B)\n" in first
    assert "TRYBOOT_B\nSwitch to Slot B (restart and try it)\n" in first
    assert "ROLLBACK\nMake Slot B the start slot (rollback, no trial)\n" in first
    # Slot A is confirmed and the start slot: nothing to confirm (user test #16)
    assert "CONFIRM" not in first
    assert "PROMOTE" not in first and "(stable)" not in first and "testing" not in first


def test_slot_manager_on_slot_b_is_the_mirror_image(tmp_path):
    first = _slot_manager(tmp_path, ON_B, "")[0]
    assert "Slot B: beta-2026-10-15-101010 (beta) - running, start slot" in first
    assert "Slot A: beta-2026-09-30-221656 (beta)\\n" in first
    assert "UPDATE\nInstall an update into the other system (Slot A)\n" in first
    assert "TRYBOOT_A\nSwitch to Slot A (restart and try it)\n" in first
    assert "ROLLBACK\nMake Slot A the start slot (rollback, no trial)\n" in first
    assert "CONFIRM" not in first
    assert "PROMOTE" not in first and "(stable)" not in first and "testing" not in first


def test_slot_manager_hides_the_tags(tmp_path):
    # UPDATE / TRYBOOT_B / STATUS are internal ids (user test #16)
    for first in (_slot_manager(tmp_path, ON_A, "")[0], _slot_manager(tmp_path, ON_B, "")[0]):
        assert "--notags" in first.split("--menu", 1)[0]


@pytest.mark.parametrize("content", ["EMPTY", "INCOMPLETE", "UNKNOWN", ""])
def test_slot_manager_offers_no_switch_into_a_slot_without_a_system(tmp_path, content):
    # The user test saw "Switch to Slot B" and "rollback" with Slot B empty
    # (#16): the menu offers only what rq_slot_manager.sh would not refuse
    first = _slot_manager(tmp_path, ON_A.replace("slot_b=EMPTY", f"slot_b={content}"), "")[0]
    items = first.split("--menu", 1)[1]
    assert "UPDATE\nInstall an update into the other system (Slot B)\n" in items
    assert "STATUS\nShow slot details\n" in items
    assert "TRYBOOT" not in items and "ROLLBACK" not in items and "Switch to" not in items
    assert "CONFIRM" not in items       # confirmed, start slot: nothing to confirm


def test_slot_manager_offers_confirm_while_not_confirmed(tmp_path):
    first = _slot_manager(tmp_path, ON_A.replace("confirmed=yes", "confirmed=no"), "")[0]
    assert "CONFIRM\nKeep Slot A as the start slot\n" in first
    assert "TRYBOOT" not in first and "ROLLBACK" not in first


def test_slot_manager_on_trial_names_the_start_slot_right(tmp_path):
    # Slot B on trial: Slot A is still the start slot
    trial = ON_B.replace("confirmed=yes", "confirmed=no").replace("default=B", "default=A") \
        .replace("pending=", "pending=B")
    first = _slot_manager(tmp_path, trial, "")[0]
    assert "Slot A: beta-2026-09-30-221656 (beta) - start slot" in first
    assert "Slot B: beta-2026-10-15-101010 (beta) - running\\n" in first
    assert "CONFIRM\nMake Slot B the start slot now (confirm)\n" in first
    assert "ROLLBACK\nGo back to Slot A (rollback)\n" in first


def test_slot_manager_keeps_the_cursor_on_the_last_choice(tmp_path):
    # STATUS, then Back: the second menu opens on STATUS, not on UPDATE
    menus = _slot_manager(tmp_path, ON_A, "STATUS\n")
    assert len(menus) >= 2
    assert "--default-item\nSTATUS\n" in menus[1]


PLAIN_STATUS = "\n".join([
    "Running now: Slot A, beta-2026-09-30-221656 (beta)",
    "Other slot:  Slot B, beta-2026-10-15-101010 (beta)",
    "",
    "Slot A is confirmed: it started well and is the start slot.",
    "Next restart: Slot A again.",
    "",
    "An update goes into Slot B and replaces what it holds. Slot A stays as it is, to go back to.",
    "",
    "The update of Slot B to beta-2026-10-15-101010 didn't work, so Slot A is running again.",
    "Reason: the health check found no desktop after 10 minutes",
    "",
    "Technical details: sudo rq_slot_manager.sh status"])


def test_slot_details_are_plain_and_fit_without_scrolling(tmp_path):
    # User test #16: STATUS printed partitions and "autoboot.txt: EXISTS",
    # and its scrolling box lost the right border over SSH
    _stub(tmp_path, "rq_expand_ab.sh", EXPLAIN)
    _stub(tmp_path, "rq_slot_manager.sh", """\
        #!/bin/sh
        case "$1" in
            status) echo "status $*" >> "$CALLS"; printf '%s\\n' "$PLAIN" ;;
            *) printf '%s\\n' "$S" ;;
        esac
        """)
    _, wt = _menu(tmp_path, 'do_slot_manager_menu', S=ON_B, PLAIN=PLAIN_STATUS,
                  WT_ANSWERS=_answers(tmp_path, "menus", ["STATUS"]))
    assert "--plain" in _calls(tmp_path)
    box = [b for b in _boxes(wt) if "--msgbox" in b][0]
    assert "Slot details" in box and "Next restart: Slot A again." in box
    assert "--scrolltext" not in box
    assert _check_fits(box) == 1


def test_software_updates_menu_names_no_promote(tmp_path):
    _stub(tmp_path, "rq_expand_ab.sh", EXPLAIN)
    _, wt = _menu(tmp_path, 'do_ab_boot_menu', WT_ANSWERS=_answers(tmp_path, "menus", []))
    assert "Slot Manager (install updates, switch systems)" in wt
    assert "promote" not in wt.lower()


# ---------------------------------------------------------------------------
# 80x24: every dialog of these flows fits without cutting text off
# ---------------------------------------------------------------------------

def _rows_needed(text, width):
    rows = 0
    for line in text.replace("\\n", "\n").split("\n"):
        rows += max(1, len(textwrap.wrap(line, width - 4, break_on_hyphens=False)))
    return rows


def _check_fits(wt):
    checked = 0
    for box in _boxes(wt):
        args = box.strip("\n").split("\n")
        for kind, extra in (("--menu", None), ("--yesno", 7), ("--msgbox", 7), ("--inputbox", 7)):
            if kind not in args:
                continue
            i = args.index(kind)
            text = args[i + 1]
            # the text may hold real newlines (rq_* output): rejoin up to the numbers
            j = i + 2
            while not re.fullmatch(r"\d+", args[j]):
                text += "\n" + args[j]
                j += 1
            height, width = int(args[j]), int(args[j + 1])
            assert height <= 24 and width <= 80, (kind, height, width)
            if kind == "--menu":
                items = (len(args) - (j + 3)) // 2
                need = _rows_needed(text, width) + items + 7
            else:
                need = _rows_needed(text, width) + extra
            assert need <= 24 or "--scrolltext" in args, (kind, need, text)
            checked += 1
    return checked


@pytest.mark.parametrize("flow", ["switch", "downgrade-replace", "slot-manager-a", "slot-manager-b",
                                  "rollback", "on-trial"])
def test_dialogs_fit_80x24(tmp_path, flow):
    if flow == "switch":
        _, wt = _install(tmp_path, ON_A_DEV, LAST_SAFE_PLAN, WT_ANSWER=None,
                         WT_ANSWERS=_answers(tmp_path, "menus", PICK_DEV + ["SWITCH"]),
                         WT_YESNO_ANSWERS=_answers(tmp_path, "yn", ["0", "1"]))
    elif flow == "downgrade-replace":
        _, wt = _install(tmp_path, ON_A_DEV, LAST_SAFE_PLAN, WT_ANSWER=None,
                         WT_ANSWERS=_answers(tmp_path, "menus", PICK_DEV + ["REPLACE"]),
                         WT_YESNO_ANSWERS=_answers(tmp_path, "yn", ["0", "1"]), WT_INPUT="REPLACE")
    elif flow == "slot-manager-a":
        _stub(tmp_path, "rq_expand_ab.sh", EXPLAIN)
        _, wt = _menu(tmp_path, 'do_slot_manager_menu',
                      S=ON_A_DEV.replace("confirmed=yes", "confirmed=no").replace("pending=", "pending=A")
                      .replace("default=A", "default=B"),
                      WT_ANSWERS=_answers(tmp_path, "menus", []))
    elif flow == "slot-manager-b":
        _stub(tmp_path, "rq_expand_ab.sh", EXPLAIN)
        _, wt = _menu(tmp_path, 'do_slot_manager_menu', S=ON_B, WT_ANSWERS=_answers(tmp_path, "menus", []))
    elif flow == "rollback":
        _, wt = _menu(tmp_path, 'ab_rollback "$S"', S=ON_A_DEV, WT_RC="1")
    else:
        _, wt = _install(tmp_path, ON_A, _plan(), PRE_RC="28",
                         PRE_MSG="Slot A, the system you are running, is still on trial: the health check "
                                 "makes it the start slot a few minutes after a good start. Until then Slot B "
                                 "is the way back, so it is not overwritten. Try again in a few minutes.")
    assert _check_fits(wt) >= 1


# ---------------------------------------------------------------------------
# "What's new" in the update offer (user test 2026-10-08 F1)
# ---------------------------------------------------------------------------

NOTICE = """\
    #!/bin/sh
    # Stand-in for rq_release_notice.py --whats-new: records its arguments
    echo "notice $*" >> "$CALLS"
    [ "$1" = --whats-new ] || exit 0
    echo "What's new in $2:"
    echo "- Now on Raspberry Pi OS Trixie (Debian 13), with Python 3.13 and the"
    echo "  current Qiskit"
    echo "- A/B image: the SD card stays in the Pi. New releases install over the"
    echo "  air and keep your settings, Wi-Fi, LED setup and Raspberry Pi…"
    echo "- Raspberry Pi Imager: your password, Wi-Fi, SSH key, keyboard and"
    echo "  Raspberry Pi Connect are applied (the user name stays rasqberry)"
    """
CHECK_OUT = """\
    #!/bin/sh
    echo 'This image:     beta-2026-09-30-221656'
    echo 'Latest beta:    beta-2026-10-15-101010'
    echo 'A newer image is available.'
    exit 10
    """


def _height(box):
    """A dialog's height: the line before its width (the last two arguments)."""
    args = box.strip().splitlines()
    return int(args[-2])


def test_check_for_update_shows_whats_new_and_fits_80x24(tmp_path):
    _stub(tmp_path, "rq_update_check.sh", CHECK_OUT)
    _stub(tmp_path, "rq_release_notice.py", NOTICE)
    _, wt = _menu(tmp_path, 'do_check_for_update', S=ON_A, WT_RC="1")
    box = _boxes(wt)[-1]
    assert "What's new in beta-2026-10-15-101010:" in box
    assert "- Now on Raspberry Pi OS Trixie" in box
    assert "Install it into Slot B, the other system, now?" in box
    assert _height(box) <= 24
    call = [c for c in _calls(tmp_path).splitlines() if "--whats-new" in c][0]
    assert "--whats-new beta-2026-10-15-101010" in call
    assert "--mark-seen" in call and "--refresh" in call
    width = int(call.split("--width ")[1].split()[0])
    lines = int(call.split("--lines ")[1].split()[0])
    assert width <= 72 and 2 <= lines <= 7


def test_whats_new_is_not_shown_twice_on_the_way_to_the_install(tmp_path):
    # Install now -> the picker: the same release's "What's new" only once
    _stub(tmp_path, "rq_update_check.sh", CHECK_OUT)
    _stub(tmp_path, "rq_release_notice.py", NOTICE)
    _, wt = _menu(tmp_path, 'do_check_for_update', S=ON_A, PLAN=_plan(),
                  WT_YESNO_ANSWERS=_answers(tmp_path, "yesno", ["0", "1"]),
                  WT_ANSWER="beta-2026-10-15-101010")
    assert wt.count("What's new in beta-2026-10-15-101010:") == 1


def test_picker_shows_whats_new_from_the_slot_manager(tmp_path):
    _stub(tmp_path, "rq_release_notice.py", NOTICE)
    _, wt = _menu(tmp_path, 'ab_pick_image B', WT_ANSWER="beta-2026-10-15-101010")
    menu = _boxes(wt)[0]
    assert "What's new in beta-2026-10-15-101010:" in menu
    assert "Choose the release to install into Slot B:" in menu
    args = menu.strip().splitlines()
    text = [i for i, a in enumerate(args) if a.endswith("Choose the release to install into Slot B:")]
    assert int(args[text[0] + 1]) <= 24


def test_no_whats_new_without_a_summary_or_for_the_running_release(tmp_path):
    _stub(tmp_path, "rq_release_notice.py", "#!/bin/sh\nexit 0\n")
    _stub(tmp_path, "rq_update_check.sh", CHECK_OUT)
    _, wt = _menu(tmp_path, 'do_check_for_update', S=ON_A, WT_RC="1")
    assert "What's new" not in wt
    vf = tmp_path / "rasqberry-version"
    vf.write_text("beta-2026-10-15-101010\n")
    _stub(tmp_path, "rq_release_notice.py", NOTICE)
    _, wt = _menu(tmp_path, 'ab_pick_image B', RQ_VERSION_FILE=str(vf),
                  WT_ANSWERS=_answers(tmp_path, "menus", []))
    assert "What's new" not in wt
