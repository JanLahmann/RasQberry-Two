"""
Tests for RQB2-system/ and rq_install_system_files.sh (issue #294): one tree of
system files, installed the same way by the image build and by the branch
updater.
"""

import glob
import os
import re
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_TREE = os.path.join(_ROOT, "RQB2-system")
_INSTALLER = os.path.join(_ROOT, "RQB2-bin", "rq_install_system_files.sh")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


def _install(root, mode):
    env = dict(os.environ, RQ_SYS_USER="rasqberry", RQ_SYS_REPO="RasQberry-Two", RQ_SYS_VENV="RQB2")
    proc = subprocess.run(["bash", _INSTALLER, _TREE, mode, "--root", str(root)],
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _enabled_units():
    units = []
    for line in open(os.path.join(_TREE, "enabled-units.txt")):
        line = line.split("#", 1)[0].strip()
        if line:
            units.append(line)
    return units


def test_every_enabled_unit_is_in_the_tree():
    for unit in _enabled_units():
        assert os.path.isfile(os.path.join(_TREE, "etc/systemd/system", unit)), unit


def test_build_installs_everything_with_modes_and_placeholders(tmp_path):
    out = _install(tmp_path, "--build")
    for src in glob.glob(os.path.join(_TREE, "**", "*"), recursive=True):
        rel = os.path.relpath(src, _TREE)
        if os.path.isdir(src) or rel == "enabled-units.txt":
            continue
        dest = tmp_path / rel
        assert dest.is_file(), rel
        assert bool(dest.stat().st_mode & 0o111) == os.access(src, os.X_OK), rel
        assert "@USER@" not in dest.read_text(errors="ignore"), rel
    renderer = (tmp_path / "etc/systemd/system/rasqberry-led-renderer.service").read_text()
    assert "/home/rasqberry/RasQberry-Two/venv/RQB2/bin/python3" in renderer
    for unit in _enabled_units():
        assert f"Enabled: {unit}" in out


def test_update_enables_only_new_units(tmp_path):
    _install(tmp_path, "--build")
    assert "No new units to enable" in _install(tmp_path, "--update")
    (tmp_path / "etc/systemd/system/rasqberry-update-check.timer").unlink()
    out = _install(tmp_path, "--update")
    assert "Enabled: rasqberry-update-check.timer" in out
    assert out.count("Enabled:") == 1


def test_disabled_on_purpose_units_are_not_enabled():
    units = _enabled_units()
    assert "rasqberry-led-renderer.service" not in units
    assert "rasqberry-update-poller.timer" not in units


def test_no_stage_script_writes_system_files_inline():
    # Regression guard for #294: these files belong in RQB2-system/, where the
    # branch updater can refresh them.
    bad = []
    for script in glob.glob(os.path.join(_ROOT, "stage-RQB2", "*", "0*-run*.sh")):
        for n, line in enumerate(open(script), 1):
            if re.match(r"\s*(cat\s*>|install\b.*|cp\b.*)\s*\"?(\$\{ROOTFS_DIR\})?/(usr/local/(bin|lib)|etc/systemd/system|etc/xdg/autostart|etc/profile\.d)/", line):
                bad.append(f"{os.path.relpath(script, _ROOT)}:{n}: {line.strip()}")
    assert not bad, "install these from RQB2-system/ instead:\n" + "\n".join(bad)


def test_firstboot_tasks_are_in_the_tree():
    # rasqberry-firstboot.sh runs every task in /usr/local/lib/rasqberry-firstboot.d;
    # a .gitignore 'lib/' rule once dropped this file from the repository.
    task = os.path.join(_TREE, "usr/local/lib/rasqberry-firstboot.d/01-expand-filesystem.sh")
    assert os.path.isfile(task) and os.access(task, os.X_OK)
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", task], cwd=_ROOT,
                             capture_output=True, text=True)
    assert tracked.returncode == 0, "01-expand-filesystem.sh is not tracked by git"
