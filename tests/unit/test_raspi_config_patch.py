"""
Tests for RQB2-bin/rq_patch_raspiconfig.sh (R-117): the "0 RasQberry" entry is
patched into raspi-config completely or not at all.

The raspi-config used here is rebuilt from the "before" side of
raspi-config.diff (its context lines) with filler in between, so the test needs
no network and no Raspberry Pi. A "trixie-like" variant changes the line hunk 1
anchors on, as trixie's raspi-config does (INTERACTIVE="${INTERACTIVE:-True}").
"""

import os
import re
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_DIFF = os.path.join(_ROOT, "RQB2-config", "raspi-config.diff")
_PATCHER = os.path.join(_ROOT, "RQB2-bin", "rq_patch_raspiconfig.sh")

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("patch") is None,
    reason="bash and patch are required")

_MARKERS = ('RQB2_menu="/usr/config/RQB2_menu.sh"', '"0 RasQberry"', "do_rasqberry_menu")


def _original_hunks():
    """[(start_line, [lines])]: the "before" text of each hunk of the context
    diff. The diff only adds lines, so its "***" parts are empty and the
    original is the "---" part without the "+ " lines."""
    hunks, cur = [], None
    for line in open(_DIFF).read().splitlines():
        m = re.match(r"^\*\*\* (\d+),(\d+) \*\*\*\*$", line)
        if m:
            cur = (int(m.group(1)), [])
            hunks.append(cur)
            continue
        if cur is None or re.match(r"^--- \d+,\d+ ----$", line):
            continue
        if line.startswith("  "):
            cur[1].append(line[2:])
        elif line == " " or line == "":
            cur[1].append("")
    return hunks


def _fake_raspi_config(path, trixie=False):
    out = []
    for start, lines in _original_hunks():
        while len(out) < start - 1:
            out.append(f"# filler {len(out) + 1}")
        out.extend(lines)
    text = "\n".join(out) + "\n"
    if trixie:
        text = text.replace("INTERACTIVE=True\n", 'INTERACTIVE="${INTERACTIVE:-True}"\n')
    path.write_text(text)
    return text


def _patch(target):
    env = dict(os.environ, RQ_RASPI_CONFIG=str(target), RQ_RASPI_CONFIG_DIFF=_DIFF)
    return subprocess.run(["bash", _PATCHER], capture_output=True, text=True, env=env)


def _markers(text):
    return [m for m in _MARKERS if m in text]


def test_clean_file_gets_all_three_changes(tmp_path):
    target = tmp_path / "raspi-config"
    _fake_raspi_config(target)
    proc = _patch(target)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _markers(target.read_text()) == list(_MARKERS)
    # second run: nothing to do
    before = target.read_text()
    assert _patch(target).returncode == 0
    assert target.read_text() == before


def test_file_the_diff_does_not_fit_is_left_untouched(tmp_path):
    target = tmp_path / "raspi-config"
    original = _fake_raspi_config(target, trixie=True)
    proc = _patch(target)
    assert proc.returncode != 0, "a half-fitting patch must not be reported as success"
    assert target.read_text() == original, "nothing may be applied when one hunk fails"
    assert "does not fit" in proc.stderr


def test_half_patched_file_is_repaired_from_its_backup(tmp_path):
    target = tmp_path / "raspi-config"
    clean = _fake_raspi_config(target)
    shutil.copy(target, str(target) + ".orig")
    # what the old patcher left on a raspi-config hunk 1 did not fit
    target.write_text(clean.replace('"1 System Options"', '"0 RasQberry" "Configure RasQberry-Two" \\\n"1 System Options"', 1)
                      + "        0\\ *) do_rasqberry_menu ;;\n")
    proc = _patch(target)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _markers(target.read_text()) == list(_MARKERS)
