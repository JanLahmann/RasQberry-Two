"""
Tests for RQB2-bin/rq_after_update.sh: the user's own scripts after an A/B update.

The CONFIG partition, the slot's state folder and the DATA partition are temp
directories; runs unprivileged, with the test user standing in for root
(RQ_AU_OWNER_UID). The same script ran as root on the Pi 4 rig (Slot B).
"""

import os
import shutil
import stat
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.join(_HERE, "..", "..")
_SCRIPT = os.path.join(_REPO, "RQB2-bin", "rq_after_update.sh")
_UNIT = os.path.join(_REPO, "RQB2-system", "etc", "systemd", "system",
                     "rasqberry-after-update.service")
RELEASE = "development-2026-10-09-122452"
OLD = "beta-2026-10-04-101010"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")
needs_timeout = pytest.mark.skipif(shutil.which("timeout") is None,
                                   reason="GNU timeout required")


@pytest.fixture
def card(tmp_path):
    """An A/B card running a confirmed Slot B, with a real DATA partition."""
    config = tmp_path / "config"
    config.mkdir()
    (config / "autoboot.txt").write_text(
        "[all]\ntryboot_a_b=1\nboot_partition=3\nboot_partition_fallback=2\n\n"
        "[tryboot]\nboot_partition=2\nboot_partition_fallback=3\n")
    (config / "slot-confirmed").write_text("2026-10-09T14:47:53+02:00\nB\n")
    state = tmp_path / "state"
    state.mkdir()
    (state / "carry-over.done").write_text(f"time=2026-10-09T12:00:00+02:00\nfrom={OLD}\n")
    data = tmp_path / "data"
    hooks = data / "rasqberry" / "after-update.d"
    hooks.mkdir(parents=True)
    for d in (data, data / "rasqberry", hooks):
        os.chmod(d, 0o755)
    (tmp_path / "version").write_text(RELEASE + "\n")
    out = tmp_path / "out"
    out.mkdir()

    class Card:
        pass
    c = Card()
    c.base, c.config, c.state, c.data, c.hooks, c.out = tmp_path, config, state, data, hooks, out
    c.marker = state / "after-update.done"
    c.log = tmp_path / "log" / "after-update.log"
    c.version = tmp_path / "version"
    c.ran = out / "ran"
    return c


def _env(card, **extra):
    env = dict(os.environ,
               RQ_AU_DATA=str(card.data), RQ_AU_CONFIG_DIR=str(card.config),
               RQ_AU_STATE_DIR=str(card.state), RQ_AU_LOG=str(card.log),
               RQ_AU_VERSION_FILE=str(card.version), RQ_AU_SLOT="B",
               RQ_AU_SKIP_MOUNT_CHECK="1", RQ_AU_OWNER_UID=str(os.getuid()),
               RQ_AU_CLOCK_WAIT="0", RQ_AU_LOCK=str(card.base / "lock"),
               RQ_AU_DESKTOP_USER="learner", RQ_AU_DESKTOP_HOME="/home/learner")
    env.update(extra)
    return env


def _run(card, *args, drop=(), **extra):
    env = _env(card, **extra)
    for key in drop:
        env.pop(key, None)
    return subprocess.run(["bash", _SCRIPT, *args], capture_output=True, text=True,
                          env=env, timeout=120)


def _script(card, name, body="", mode=0o755):
    """A hook script that records its name (and env) in out/ran, then runs <body>."""
    path = card.hooks / name
    path.write_text(
        "#!/bin/bash\n"
        f'echo "{name}" >> "{card.ran}"\n'
        f'echo "{name} release=$RQ_RELEASE previous=$RQ_PREVIOUS_RELEASE '
        f'user=$RQ_DESKTOP_USER home=$RQ_DESKTOP_HOME" >> "{card.out}/env"\n'
        f'echo "hello from {name}"\n'
        + body + "\n")
    os.chmod(path, mode)
    return path


def _ran(card):
    return card.ran.read_text().split() if card.ran.exists() else []


def _marker(card):
    return dict(line.split("=", 1) for line in card.marker.read_text().splitlines() if "=" in line)


# ---------------------------------------------------------------------------
# once per release
# ---------------------------------------------------------------------------

def test_runs_in_name_order_with_the_environment(card):
    _script(card, "20-second")
    _script(card, "10-first")
    r = _run(card, "run")
    assert r.returncode == 0, r.stderr
    assert _ran(card) == ["10-first", "20-second"]
    env = (card.out / "env").read_text()
    assert f"10-first release={RELEASE} previous={OLD} user=learner home=/home/learner" in env
    m = _marker(card)
    assert m["release"] == RELEASE and m["previous"] == OLD
    assert m["state"] == "done" and m["result"] == "ran 2, failed 0, skipped 0"
    log = card.log.read_text()
    # every line of a script's output with its time and name
    assert any(line.endswith("[10-first] hello from 10-first") and line[:4].isdigit()
               for line in log.splitlines())
    assert log.index("10-first: start") < log.index("20-second: start")


def test_same_release_does_not_run_again(card):
    _script(card, "10-once")
    _run(card, "run")
    r = _run(card, "run")
    assert r.returncode == 0
    assert "already done" in r.stdout
    assert _ran(card) == ["10-once"]


def test_new_release_runs_again(card):
    _script(card, "10-again")
    _run(card, "run")
    card.version.write_text("development-2026-10-20-090000\n")
    _run(card, "run")
    assert _ran(card) == ["10-again", "10-again"]
    env = (card.out / "env").read_text().splitlines()
    # the previous release is now the one this slot ran before
    assert env[-1].startswith(f"10-again release=development-2026-10-20-090000 previous={RELEASE}")


def test_force_runs_again(card):
    _script(card, "10-force")
    _run(card, "run")
    _run(card, "run", "--force")
    assert _ran(card) == ["10-force", "10-force"]
    assert _marker(card)["previous"] == OLD


def test_no_folder_notes_the_release(card):
    shutil.rmtree(card.hooks)
    r = _run(card, "run")
    assert r.returncode == 0
    assert _marker(card)["result"] == "no scripts"
    # scripts added later wait for the next release (or --force)
    card.hooks.mkdir()
    os.chmod(card.hooks, 0o755)
    _script(card, "10-later")
    _run(card, "run")
    assert _ran(card) == []


# ---------------------------------------------------------------------------
# failures and time limit
# ---------------------------------------------------------------------------

def test_failing_script_continues_with_the_next(card):
    _script(card, "10-fails", "exit 1")
    _script(card, "20-works")
    r = _run(card, "run")
    assert r.returncode == 0
    assert _ran(card) == ["10-fails", "20-works"]
    log = card.log.read_text()
    assert "10-fails: failed (exit code 1)" in log
    assert "20-works: done" in log
    m = _marker(card)
    assert m["state"] == "done" and m["result"] == "ran 2, failed 1, skipped 0"


@needs_timeout
def test_timeout_stops_a_script_and_continues(card):
    _script(card, "10-hangs", "sleep 60")
    _script(card, "20-after")
    r = _run(card, "run", RQ_AU_TIMEOUT="1")
    assert r.returncode == 0
    assert _ran(card) == ["10-hangs", "20-after"]
    assert "10-hangs: stopped after the time limit" in card.log.read_text()
    assert _marker(card)["result"] == "ran 2, failed 1, skipped 0"


def test_time_limit_from_the_conf_file(card):
    (card.data / "rasqberry" / "after-update.conf").write_text("TIMEOUT_MINUTES=45\n")
    _script(card, "10-x")
    _run(card, "run")
    assert "10-x: start (time limit 45 min)" in card.log.read_text()


def test_interrupted_run_is_tried_once_more(card):
    _script(card, "10-x")
    card.marker.write_text(f"release={RELEASE}\nprevious={OLD}\nstate=started\nattempts=1\n")
    _run(card, "run")
    assert _ran(card) == ["10-x"]
    assert _marker(card)["attempts"] == "2"
    # cut short twice: not again
    card.marker.write_text(f"release={RELEASE}\nprevious={OLD}\nstate=started\nattempts=2\n")
    _run(card, "run")
    assert _ran(card) == ["10-x"]
    assert _marker(card)["state"] == "done"


# ---------------------------------------------------------------------------
# what is not run
# ---------------------------------------------------------------------------

def test_unsafe_and_ignored_files_are_skipped(card):
    _script(card, "10-ok")
    _script(card, "20-world-writable", mode=0o757)
    _script(card, "30-group-writable", mode=0o775)
    _script(card, "40-not-executable", mode=0o644)
    for name in ("50-backup~", ".hidden", "60-x.dpkg-old"):
        _script(card, name)
    os.symlink(card.hooks / "10-ok", card.hooks / "70-link")
    r = _run(card, "run")
    assert r.returncode == 0
    assert _ran(card) == ["10-ok"]
    log = card.log.read_text()
    assert "20-world-writable: skipped" in log
    assert "30-group-writable: skipped" in log
    assert "40-not-executable: skipped (not executable" in log
    assert "70-link: skipped (a symbolic link" in log
    assert "50-backup~" not in log and ".hidden" not in log
    assert _marker(card)["result"] == "ran 1, failed 0, skipped 4"


@pytest.mark.parametrize("how", ["world-writable folder", "group-writable parent",
                                 "folder of another owner", "folder is a link"])
def test_unsafe_folder_runs_nothing(card, how):
    _script(card, "10-x")
    extra = {}
    if how == "world-writable folder":
        os.chmod(card.hooks, 0o777)
    elif how == "group-writable parent":
        os.chmod(card.data / "rasqberry", 0o775)
    elif how == "folder of another owner":
        # the folders are the test user's; expect another owner (root)
        extra["RQ_AU_OWNER_UID"] = str(os.getuid() + 4242)
    else:
        real = card.base / "elsewhere"
        card.hooks.rename(real)
        os.symlink(real, card.hooks)
    r = _run(card, "run", **extra)
    assert r.returncode == 0
    assert _ran(card) == []
    assert "no after-update script runs" in r.stderr
    # still due: runs at the next start once the folder is safe
    assert not card.marker.exists()


def test_no_data_partition_runs_nothing(card):
    _script(card, "10-x")
    r = _run(card, "run", drop=("RQ_AU_SKIP_MOUNT_CHECK",))
    assert r.returncode == 0
    assert "not a prepared data partition" in r.stdout
    assert _ran(card) == [] and not card.marker.exists()


def test_standard_image_runs_nothing(card):
    _script(card, "10-x")
    (card.config / "autoboot.txt").unlink()
    r = _run(card, "run")
    assert r.returncode == 0
    assert "not an A/B card" in r.stdout
    assert _ran(card) == [] and not card.marker.exists()


@pytest.mark.parametrize("state", ["no slot-confirmed", "trial start pending",
                                   "other slot is the default"])
def test_unconfirmed_slot_runs_nothing(card, state):
    _script(card, "10-x")
    if state == "no slot-confirmed":
        (card.config / "slot-confirmed").unlink()
    elif state == "trial start pending":
        (card.config / "slot-confirmed").unlink()
        (card.config / "target-slot").write_text("B\n")
    else:
        (card.config / "autoboot.txt").write_text("[all]\nboot_partition=2\n\n[tryboot]\nboot_partition=3\n")
    r = _run(card, "run")
    assert r.returncode == 0
    assert "not confirmed yet" in r.stdout
    assert _ran(card) == [] and not card.marker.exists()
    # --force does not bypass it either
    _run(card, "run", "--force")
    assert _ran(card) == []


def test_runs_once_the_slot_is_confirmed(card):
    _script(card, "10-x")
    (card.config / "slot-confirmed").unlink()
    (card.config / "target-slot").write_text("B\n")
    _run(card, "run")
    assert _ran(card) == []
    # the health check confirms: slot-confirmed, target-slot removed
    (card.config / "target-slot").unlink()
    (card.config / "slot-confirmed").write_text("2026-10-09T15:00:00+02:00\nB\n")
    _run(card, "run")
    assert _ran(card) == ["10-x"]


def test_other_slot_keeps_its_own_marker(card):
    """Going back to a slot that already ran its scripts runs nothing."""
    _script(card, "10-x")
    card.marker.write_text(f"release={RELEASE}\nprevious={OLD}\nstate=done\nattempts=1\n")
    _run(card, "run")
    assert _ran(card) == []


# ---------------------------------------------------------------------------
# status, unit, installation
# ---------------------------------------------------------------------------

def test_status_shows_the_last_run(card):
    _script(card, "10-x", "exit 3")
    _run(card, "run")
    r = _run(card, "status")
    assert r.returncode == 0
    assert "10-x" in r.stdout
    assert f"release={RELEASE}" in r.stdout
    assert "10-x: failed (exit code 3)" in r.stdout


def test_run_needs_root(card):
    if os.getuid() == 0:
        pytest.skip("runs as root")
    r = _run(card, "run", drop=("RQ_AU_OWNER_UID",))
    assert r.returncode != 0
    assert "run as root" in r.stderr


def test_unit_runs_after_the_health_check_on_ab_cards_only():
    unit = open(_UNIT).read()
    assert "After=rasqberry-health-check.service network-online.target" in unit
    assert "Wants=network-online.target" in unit
    assert "ConditionPathExists=/boot/config/autoboot.txt" in unit
    assert "ExecStart=/usr/bin/rq_after_update.sh run" in unit
    # a long script must not hold up the start-up (multi-user.target)
    assert "Type=exec" in unit
    assert "WantedBy=multi-user.target" in unit


def test_unit_is_enabled_and_checked_at_build():
    enabled = open(os.path.join(_REPO, "RQB2-system", "enabled-units.txt")).read().split()
    assert "rasqberry-after-update.service" in enabled
    check = open(os.path.join(_REPO, "stage-RQB2", "08-ab-boot-support", "00-run-chroot.sh")).read()
    assert "rq_after_update.sh" in check and "rasqberry-after-update.service" in check
    assert os.stat(_SCRIPT).st_mode & stat.S_IXUSR
