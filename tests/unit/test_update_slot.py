"""
Tests for RQB2-bin/rq_update_slot.sh (A/B slot update, batch B2).

- R-002: decompressing on a terminal must leave the image byte-exact. The old
  `xz -dcvT0 img.xz > raw 2>&1 | tee -a log` sent xz's progress (stderr) into
  the image, so every update started from the menu or a terminal failed its
  checksum. The tests run the real function under a pseudo-terminal, like the
  menu does, and compare sha256.
- The checksum fields: an -ab image is checked against the ab_* fields.
- --preflight refusals and their exit codes (R-050, R-052).

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


def _preflight(tmp_path, root, size, avail_kb, slot="B"):
    env = _env(tmp_path,
               PATH=f"{_stubs(tmp_path)}:{os.environ['PATH']}",
               RQ_UPDATE_DIR=str(tmp_path / "dl"),
               FAKE_ROOT=root, FAKE_BOOTFW="/dev/mmcblk0p2",
               FAKE_PART_SIZE=str(size), FAKE_AVAIL_KB=str(avail_kb))
    return subprocess.run(
        _source(f'preflight_checks {slot} /dev/mmcblk0p6 /dev/mmcblk0p3'),
        capture_output=True, text=True, env=env)


GB = 1024 ** 3


def test_preflight_passes_on_slot_a_with_an_expanded_slot_b(tmp_path):
    proc = _preflight(tmp_path, "/dev/mmcblk0p5", 26 * GB, 40 * 1024 * 1024)
    assert proc.returncode == 0, proc.stderr


def test_preflight_running_on_slot_b_explains_promote_or_slot_a(tmp_path):
    proc = _preflight(tmp_path, "/dev/mmcblk0p6", 26 * GB, 40 * 1024 * 1024)
    assert proc.returncode == 20
    assert "running now" in proc.stderr
    assert "PROMOTE" in proc.stderr and "Slot A" in proc.stderr


def test_preflight_placeholder_slot_says_expand(tmp_path):
    proc = _preflight(tmp_path, "/dev/mmcblk0p5", 16 * 1024 * 1024, 40 * 1024 * 1024)
    assert proc.returncode == 21
    assert "EXPAND" in proc.stderr and "Software & Image Updates" in proc.stderr


def test_preflight_too_little_space_says_what_to_do(tmp_path):
    proc = _preflight(tmp_path, "/dev/mmcblk0p5", 26 * GB, 5 * 1024 * 1024)
    assert proc.returncode == 22
    assert "15GB needed" in proc.stderr and "Delete" in proc.stderr


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
