"""
Tests for RQB2-bin/rq_update_slot.sh (A/B slot update, batch B2).

- R-002: decompressing on a terminal must leave the image byte-exact. The old
  `xz -dcvT0 img.xz > raw 2>&1 | tee -a log` sent xz's progress (stderr) into
  the image, so every update started from the menu or a terminal failed its
  checksum. The tests run the real function under a pseudo-terminal, like the
  menu does, and compare sha256.
- The checksum fields: an -ab image is checked against the ab_* fields.
- --preflight refusals and their exit codes (R-050, R-052).
- Ping-pong (Jan, 2026-10-04): the target is the slot that is not running, A
  or B alike; a slot on trial is not left without its way back (28); Jan's
  guard refuses an unconfirmed downgrade (26) or an overwrite of the last beta
  or stable slot (27) without a terminal, and asks in one.

The script is sourced (it only runs main when executed), and commands that
need a real A/B card (findmnt, blockdev, df) are stubbed on PATH.
"""

import hashlib
import os
import pty
import select
import shutil
import subprocess
import textwrap

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "..", "RQB2-bin", "rq_update_slot.sh")

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("xz") is None,
    reason="bash and xz are required",
)


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _image(tmp_path, size=3_000_000):
    """A random 'image' and its .xz, as the release ships it."""
    raw = tmp_path / "orig.img"
    raw.write_bytes(os.urandom(size // 2) + bytes(size - size // 2))
    subprocess.run(["xz", "-k", "-T0", str(raw)], check=True)
    return raw, tmp_path / "orig.img.xz"


def _run_on_pty(cmd, env, timeout=60):
    """Run cmd with stdin/stdout/stderr on a pseudo-terminal (as in the menu);
    returns (exit code, everything the terminal showed)."""
    master, slave = pty.openpty()
    proc = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
    os.close(slave)
    shown = b""
    while True:
        ready, _, _ = select.select([master], [], [], timeout)
        if not ready:
            proc.kill()
            raise AssertionError("timed out; terminal so far: %r" % shown)
        try:
            chunk = os.read(master, 4096)
        except OSError:  # EIO on Linux once the child closed the terminal
            break
        if not chunk:
            break
        shown += chunk
    os.close(master)
    return proc.wait(timeout=timeout), shown.decode(errors="replace")


def _env(tmp_path, **extra):
    env = dict(os.environ, RQ_UPDATE_LOG=str(tmp_path / "update.log"), **extra)
    return env


def _source(snippet):
    return ["bash", "-c", f'. "{_SCRIPT}"\n' + textwrap.dedent(snippet)]


def test_decompress_on_a_terminal_keeps_the_image_byte_exact(tmp_path):
    raw, xz = _image(tmp_path)
    out = tmp_path / "image.img"
    rc, shown = _run_on_pty(
        _source(f'decompress_image "{xz}" "{out}"'), _env(tmp_path))
    assert rc == 0, shown
    assert out.stat().st_size == raw.stat().st_size
    assert _sha(out) == _sha(raw)
    # xz -v reported to the terminal, not into the file
    assert "orig.img.xz" in shown


def test_the_old_pipeline_corrupted_the_image(tmp_path):
    """The shipped line, for reference: on a terminal it appends xz's summary
    to the image (H-18: +44 bytes on the Pi 5) - what the test above guards."""
    raw, xz = _image(tmp_path)
    out = tmp_path / "image.img"
    log = tmp_path / "update.log"
    rc, _ = _run_on_pty(
        ["bash", "-c", f'xz -dcvT0 "{xz}" > "{out}" 2>&1 | tee -a "{log}"'], _env(tmp_path))
    assert rc == 0
    assert out.stat().st_size > raw.stat().st_size
    assert _sha(out) != _sha(raw)


def test_decompress_without_a_terminal_logs_quietly(tmp_path):
    raw, xz = _image(tmp_path)
    out = tmp_path / "image.img"
    proc = subprocess.run(_source(f'decompress_image "{xz}" "{out}"'),
                          capture_output=True, text=True, env=_env(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert _sha(out) == _sha(raw)
    assert proc.stdout == "" and proc.stderr == ""


def test_corrupt_download_fails_instead_of_writing_garbage(tmp_path):
    _, xz = _image(tmp_path)
    data = bytearray(xz.read_bytes())
    data[len(data) // 2] ^= 0xFF
    xz.write_bytes(bytes(data))
    proc = subprocess.run(_source(f'decompress_image "{xz}" "{tmp_path / "image.img"}"'),
                          capture_output=True, text=True, env=_env(tmp_path))
    assert proc.returncode != 0


@pytest.mark.parametrize("url,kind,field", [
    ("https://x/rasqberry-beta-2026-09-30-ab.img.xz", "image", "ab_image_sha256"),
    ("https://x/rasqberry-beta-2026-09-30-ab.img.xz", "extract", "ab_extract_sha256"),
    ("https://x/rasqberry-beta-2026-09-30.img.xz", "image", "image_sha256"),
    ("https://x/rasqberry-beta-2026-09-30.img.xz", "extract", "extract_sha256"),
])
def test_an_ab_image_is_checked_against_the_ab_checksums(tmp_path, url, kind, field):
    # The dev stream's image_sha256 is the STANDARD image's: using it for an
    # -ab download aborted the update as "corrupted or tampered"
    proc = subprocess.run(_source(f'sha_field_for "{url}" {kind}'),
                          capture_output=True, text=True, env=_env(tmp_path))
    assert proc.stdout.strip() == field


# --- preflight ---------------------------------------------------------------

STUBS = {
    "findmnt": """\
        #!/bin/bash
        # findmnt / -o source -n   |  findmnt /boot/firmware -o source -n
        # findmnt -rn -o TARGET --source DEV  -> $FAKE_MOUNTED_AT (if set)
        case "$*" in
            *--source*) [ -n "${FAKE_MOUNTED_AT:-}" ] || exit 1; echo "$FAKE_MOUNTED_AT"; exit 0 ;;
        esac
        case "$1" in
            /) echo "$FAKE_ROOT" ;;
            /boot/firmware) echo "$FAKE_BOOTFW" ;;
            *) exit 1 ;;
        esac
        """,
    "umount": """\
        #!/bin/bash
        exit 32
        """,
    "blockdev": """\
        #!/bin/bash
        echo "${FAKE_PART_SIZE:-0}"
        """,
    "df": """\
        #!/bin/bash
        echo "Avail"
        echo "${FAKE_AVAIL_KB:-0}"
        """,
}


def _stubs(tmp_path):
    bindir = tmp_path / "stubs"
    bindir.mkdir()
    for name, body in STUBS.items():
        path = bindir / name
        path.write_text(textwrap.dedent(body))
        path.chmod(0o755)
    return bindir


PARTS = {"A": ("/dev/mmcblk0p5", "/dev/mmcblk0p2"), "B": ("/dev/mmcblk0p6", "/dev/mmcblk0p3")}


def _preflight(tmp_path, root, size, avail_kb, slot="B", config=None):
    bootfw = PARTS["A" if root.endswith("5") else "B"][1]
    env = _env(tmp_path,
               PATH=f"{_stubs(tmp_path)}:{os.environ['PATH']}",
               RQ_UPDATE_DIR=str(tmp_path / "dl"),
               RQ_BOOT_COMMON_DIR=str(config or tmp_path / "no-config"),
               FAKE_ROOT=root, FAKE_BOOTFW=bootfw,
               FAKE_PART_SIZE=str(size), FAKE_AVAIL_KB=str(avail_kb))
    system, boot = PARTS[slot]
    return subprocess.run(
        _source(f'preflight_checks {slot} {system} {boot}'),
        capture_output=True, text=True, env=env)


GB = 1024 ** 3


def test_preflight_passes_on_slot_a_with_an_expanded_slot_b(tmp_path):
    proc = _preflight(tmp_path, "/dev/mmcblk0p5", 26 * GB, 40 * 1024 * 1024)
    assert proc.returncode == 0, proc.stderr


def test_preflight_passes_on_slot_b_for_slot_a(tmp_path):
    # ping-pong: running Slot B, the update goes into Slot A
    proc = _preflight(tmp_path, "/dev/mmcblk0p6", 26 * GB, 40 * 1024 * 1024, slot="A")
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("root,slot,other", [("/dev/mmcblk0p6", "B", "A"), ("/dev/mmcblk0p5", "A", "B")])
def test_preflight_refuses_the_running_slot_and_names_the_other(tmp_path, root, slot, other):
    proc = _preflight(tmp_path, root, 26 * GB, 40 * 1024 * 1024, slot=slot)
    assert proc.returncode == 20
    assert "running now" in proc.stderr
    assert f"Updates go into the other system, Slot {other}" in proc.stderr
    assert "PROMOTE" not in proc.stderr and "stable" not in proc.stderr


def test_preflight_placeholder_slot_says_expand(tmp_path):
    proc = _preflight(tmp_path, "/dev/mmcblk0p5", 16 * 1024 * 1024, 40 * 1024 * 1024)
    assert proc.returncode == 21
    # the visible menu label (B4, R-095); a small card gets rq_expand_ab.sh's
    # single-system explanation instead (tests/unit/test_expand_ab.py)
    assert "Prepare the card for A/B updates" in proc.stderr and "Software & Image Updates" in proc.stderr


def test_preflight_too_little_space_says_what_to_do(tmp_path):
    proc = _preflight(tmp_path, "/dev/mmcblk0p5", 26 * GB, 5 * 1024 * 1024)
    assert proc.returncode == 22
    assert "15 GB needed" in proc.stderr and "Delete" in proc.stderr


def test_refusals_are_logged(tmp_path):
    _preflight(tmp_path, "/dev/mmcblk0p6", 26 * GB, 40 * 1024 * 1024)
    assert "REFUSED (20)" in (tmp_path / "update.log").read_text()


# --- unmounting the target (R-146) ------------------------------------------

def _unmount(tmp_path, **extra):
    env = _env(tmp_path, PATH=f"{_stubs(tmp_path)}:{os.environ['PATH']}", **extra)
    return subprocess.run(_source('unmount_target /dev/mmcblk0p6; echo "went on"'),
                          capture_output=True, text=True, env=env)


def test_a_target_that_is_not_mounted_is_fine(tmp_path):
    # Under set -euo pipefail an empty findmnt must not end the update - the
    # normal case once the slots are no longer automounted
    proc = _unmount(tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "went on" in proc.stdout


def test_a_target_that_stays_mounted_stops_the_update(tmp_path):
    proc = _unmount(tmp_path, FAKE_MOUNTED_AT="/media/rasqberry/SYSTEM-B")
    assert proc.returncode == 1
    assert "cannot be unmounted" in proc.stderr
    assert "went on" not in proc.stdout


# --- H-34 / item 24: checksums for every release, quiet logs ------------------

def test_github_digest_is_used_when_the_manifest_has_none(tmp_path):
    # older releases are no stream head: GitHub's asset digest verifies them
    api = tmp_path / "api" / "repos" / "JanLahmann" / "RasQberry-Two" / "releases" / "tags"
    api.mkdir(parents=True)
    (api / "beta-2026-09-30-221656").write_text(
        '{"assets": [{"name": "x-ab.img.xz", "digest": "sha256:' + "ab" * 32 + '"}]}')
    env = _env(tmp_path, RQ_GITHUB_API=f"file://{tmp_path}/api",
               RQB_RELEASES_URL=f"file://{tmp_path}/missing.json")
    proc = subprocess.run(_source(
        'SHA256_SUM=""; resolve_image_sha256 '
        'https://github.com/JanLahmann/RasQberry-Two/releases/download/beta-2026-09-30-221656/x-ab.img.xz '
        'beta-2026-09-30-221656'), capture_output=True, text=True, env=env)
    assert proc.stdout.strip() == "ab" * 32, proc.stderr


def test_an_image_without_any_checksum_is_refused_before_the_download():
    text = open(_SCRIPT).read()
    main = text[text.index("main() {"):]
    assert main.index('refuse "$RC_UNVERIFIED"') < main.index("download_image ")
    assert "--allow-unverified" in text


def test_preflight_without_root_says_sudo_without_a_log_error(tmp_path):
    env = dict(os.environ, RQ_UPDATE_LOG="/var/log/rasqberry-update-slot-test-no-write.log")
    if os.geteuid() == 0:
        pytest.skip("runs as root")
    proc = subprocess.run(["bash", _SCRIPT, "--preflight"], capture_output=True, text=True, env=env)
    assert proc.returncode == 1
    assert "Permission denied" not in proc.stderr and "sudo" in proc.stderr


# --- ping-pong: the target, a slot on trial (exit 28) --------------------------

LSBLK = """\
    #!/bin/bash
    case "$*" in
        *pkname*) echo mmcblk0 ;;
        *NAME,LABEL*)
            echo "/dev/mmcblk0p1 CONFIG"
            echo "/dev/mmcblk0p2 BOOT-A"
            echo "/dev/mmcblk0p3 boot-b"
            echo "/dev/mmcblk0p5 SYSTEM-A"
            echo "/dev/mmcblk0p6 SYSTEM-B"
            echo "/dev/mmcblk0p7 data" ;;
    esac
    exit 0
    """


@pytest.mark.parametrize("root,target", [("/dev/mmcblk0p5", "B"), ("/dev/mmcblk0p6", "A")])
def test_the_default_target_is_the_slot_that_is_not_running(tmp_path, root, target):
    bindir = _stubs(tmp_path)
    (bindir / "lsblk").write_text(textwrap.dedent(LSBLK))
    (bindir / "lsblk").chmod(0o755)
    env = _env(tmp_path, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_ROOT=root)
    proc = subprocess.run(_source('parse_arguments; echo "$TARGET_SLOT"'),
                          capture_output=True, text=True, env=env)
    assert proc.stdout.strip() == target, proc.stderr


def _config(tmp_path, default, pending=None, confirmed=True):
    config = tmp_path / "config"
    config.mkdir()
    other = 3 if default == 2 else 2
    (config / "autoboot.txt").write_text(
        f"[all]\ntryboot_a_b=1\nboot_partition={default}\nboot_partition_fallback={other}\n\n"
        f"[tryboot]\nboot_partition={other}\nboot_partition_fallback={default}\n")
    if pending:
        (config / "target-slot").write_text(pending + "\n")
    if confirmed:
        (config / "slot-confirmed").write_text("now\n")
    return config


def test_a_slot_on_trial_keeps_its_way_back(tmp_path):
    # Running Slot B on trial ([all] still starts A): Slot A is not overwritten
    config = _config(tmp_path, default=2, pending="B", confirmed=False)
    proc = _preflight(tmp_path, "/dev/mmcblk0p6", 26 * GB, 40 * 1024 * 1024, slot="A", config=config)
    assert proc.returncode == 28
    assert "still on trial" in proc.stderr and "Slot A is the way back" in proc.stderr


def test_a_pending_rollback_says_restart_first(tmp_path):
    # rollback chose Slot B; the Pi still runs Slot A
    config = _config(tmp_path, default=3, confirmed=False)
    proc = _preflight(tmp_path, "/dev/mmcblk0p5", 26 * GB, 40 * 1024 * 1024, slot="B", config=config)
    assert proc.returncode == 28
    assert "The next restart starts Slot B" in proc.stderr and "Restart first" in proc.stderr


@pytest.mark.parametrize("root,slot,default", [("/dev/mmcblk0p5", "B", 2), ("/dev/mmcblk0p6", "A", 3)])
def test_a_confirmed_start_slot_can_be_updated(tmp_path, root, slot, default):
    config = _config(tmp_path, default=default, pending="A" if slot == "B" else "B")
    proc = _preflight(tmp_path, root, 26 * GB, 40 * 1024 * 1024, slot=slot, config=config)
    assert proc.returncode == 0, proc.stderr


def test_an_unconfirmed_start_slot_without_a_trial_can_be_updated(tmp_path):
    # e.g. a health check that failed on a normal start: updating must stay possible
    config = _config(tmp_path, default=2, confirmed=False)
    proc = _preflight(tmp_path, "/dev/mmcblk0p5", 26 * GB, 40 * 1024 * 1024, slot="B", config=config)
    assert proc.returncode == 0, proc.stderr


# --- Jan's guard: exit codes 26 and 27 ------------------------------------------

def _plan_stub(tmp_path, downgrade="none", last_safe="no", target="B",
               target_holds="beta beta-2026-10-03-095636", new="dev development-2026-10-05-010101"):
    stub = tmp_path / "planner"
    stub.write_text("#!/bin/sh\n"
                    "[ \"$1\" = plan-update ] || exit 9\n"
                    f"echo target={target}\necho running={'A' if target == 'B' else 'B'}\n"
                    f"echo 'target_holds={target_holds}'\n"
                    "echo 'running_holds=dev development-2026-10-04-014357'\n"
                    f"echo 'new={new}'\necho downgrade={downgrade}\n"
                    f"echo last_safe_slot={last_safe}\necho advice=x\n")
    stub.chmod(0o755)
    return stub


def _guard(tmp_path, flags="", pty_input=None, **plan):
    env = _env(tmp_path, RQ_SLOT_PLANNER=str(_plan_stub(tmp_path, **plan)))
    snippet = f'TARGET_SLOT=B; parse_arguments {flags}; enforce_update_guard development-2026-10-05-010101; echo GUARD-PASSED'
    if pty_input is None:
        proc = subprocess.run(_source(snippet), capture_output=True, text=True, env=env,
                              stdin=subprocess.DEVNULL)
        return proc.returncode, proc.stdout + proc.stderr
    return _run_on_pty_with_input(_source(snippet), env, pty_input)


def _run_on_pty_with_input(cmd, env, text, timeout=30):
    master, slave = pty.openpty()
    proc = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
    os.close(slave)
    shown, sent = b"", False
    while True:
        ready, _, _ = select.select([master], [], [], timeout)
        if not ready:
            proc.kill()
            raise AssertionError("timed out; terminal so far: %r" % shown)
        try:
            chunk = os.read(master, 4096)
        except OSError:
            break
        if not chunk:
            break
        shown += chunk
        if not sent and (b"[y/N]" in shown or b"anyway: " in shown):
            os.write(master, text.encode() + b"\n")
            sent = True
    os.close(master)
    return proc.wait(timeout=timeout), shown.decode(errors="replace")


def test_no_warning_passes(tmp_path):
    rc, out = _guard(tmp_path)
    assert rc == 0 and "GUARD-PASSED" in out


@pytest.mark.parametrize("downgrade,text", [
    ("stream", "comes from a less tested release channel, so installing it is a downgrade"),
    ("older", "is older, so installing it is a downgrade"),
])
def test_a_downgrade_without_a_terminal_is_refused_with_26(tmp_path, downgrade, text):
    rc, out = _guard(tmp_path, downgrade=downgrade)
    assert rc == 26
    assert text in out and "--allow-downgrade" in out and "Nothing was changed" in out
    assert "GUARD-PASSED" not in out
    assert "REFUSED (26)" in (tmp_path / "update.log").read_text()


def test_allow_downgrade_lets_it_through(tmp_path):
    rc, out = _guard(tmp_path, flags="--allow-downgrade", downgrade="stream")
    assert rc == 0 and "GUARD-PASSED" in out


def test_the_last_safe_slot_without_a_terminal_is_refused_with_27(tmp_path):
    rc, out = _guard(tmp_path, last_safe="yes")
    assert rc == 27
    assert "the only beta or stable system on this card" in out
    assert "Safer: switch to Slot B first" in out and "switch-to B --reboot" in out
    assert "--force-replace-safe-slot" in out and "GUARD-PASSED" not in out


def test_force_replace_safe_slot_lets_it_through(tmp_path):
    rc, out = _guard(tmp_path, flags="--force-replace-safe-slot", last_safe="yes")
    assert rc == 0 and "GUARD-PASSED" in out


def test_both_warnings_need_both_options(tmp_path):
    rc, _ = _guard(tmp_path, flags="--allow-downgrade", downgrade="stream", last_safe="yes")
    assert rc == 27
    rc, out = _guard(tmp_path, flags="--allow-downgrade --force-replace-safe-slot",
                     downgrade="stream", last_safe="yes")
    assert rc == 0 and "GUARD-PASSED" in out


@pytest.mark.parametrize("answer,rc", [("y", 0), ("n", 26), ("", 26)])
def test_a_downgrade_in_a_terminal_asks_default_no(tmp_path, answer, rc):
    code, shown = _guard(tmp_path, pty_input=answer, downgrade="older")
    assert "Install it anyway? [y/N]" in shown
    assert code == rc


@pytest.mark.parametrize("answer,rc", [("REPLACE", 0), ("replace", 27), ("yes", 27)])
def test_the_last_safe_slot_in_a_terminal_needs_a_typed_replace(tmp_path, answer, rc):
    code, shown = _guard(tmp_path, pty_input=answer, last_safe="yes")
    assert "Type REPLACE to overwrite Slot B anyway:" in shown
    assert code == rc


def test_a_plan_for_another_slot_stops_the_update(tmp_path):
    rc, out = _guard(tmp_path, target="A")
    assert rc == 1 and "Nothing was changed" in out


def test_a_finished_update_leaves_the_updated_hint(tmp_path):
    # slot-<X>-updated tells the health check that a failed first start of
    # this slot was an update, not a plain switch (Jan, 2026-10-04)
    config = tmp_path / "config"
    config.mkdir()
    (config / "slot-B-updated").write_text("version=old\n")
    proc = subprocess.run(_source('''
        mark_slot_incomplete B beta-2026-10-15-101010
        [ -e "$RQ_BOOT_COMMON_DIR/slot-B-updated" ] && echo STALE
        mark_slot_updated B beta-2026-10-15-101010 beta-2026-10-15-101010
        clear_slot_incomplete B
    '''), env=_env(tmp_path, RQ_BOOT_COMMON_DIR=str(config)), capture_output=True, text=True,
        timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert "STALE" not in proc.stdout                    # a new write starts afresh
    hint = (config / "slot-B-updated").read_text()
    assert "version=beta-2026-10-15-101010\n" in hint and "tag=beta-2026-10-15-101010\n" in hint
    assert not (config / "slot-B-incomplete").exists()


def test_the_hint_is_written_when_the_slot_is_complete():
    text = open(_SCRIPT).read()
    body = text[text.index("write_image_to_slot() {"):text.index("cleanup_download() {")]
    assert body.index("mark_slot_incomplete ") < body.index("mark_slot_updated ")
    assert body.index("mark_slot_updated ") < body.index('clear_slot_incomplete "$target_slot"')


def test_the_guard_runs_before_the_download():
    text = open(_SCRIPT).read()
    main = text[text.index("main() {"):]
    assert main.index('preflight_checks "$TARGET_SLOT"') < main.index("enforce_update_guard ")
    assert main.index("enforce_update_guard ") < main.index("resolve_image_sha256 ")
    assert main.index("enforce_update_guard ") < main.index("download_image ")


def test_slot_a_is_not_special_any_more():
    text = open(_SCRIPT).read()
    for gone in ("UPDATE STABLE", "--confirm", "STABLE_SLOT", "PROMOTE", "promote"):
        assert gone not in text, gone


def test_exit_codes_are_documented_in_the_header():
    text = open(_SCRIPT).read()
    header = text[:text.index("SCRIPT_DIR=")]
    for code in range(20, 29):
        assert f"#   {code} " in header, code


def test_fstab_of_the_new_slot_names_config_and_data_by_the_shared_helper():
    # "/dev/<disk>p1" was wrong for a card on USB (sda1)
    text = open(_SCRIPT).read()
    assert "ab_partition_by_number 1" in text and "ab_partition_by_number 7" in text
    assert "${root_dev}p1" not in text and "${root_dev}p7" not in text
