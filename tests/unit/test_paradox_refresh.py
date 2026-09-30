"""
Tests for the --refresh mode of RQB2-bin/setup_quantum_paradoxes.py (issue #181):
existing installs are re-patched when the setup script changes, with the user's
previous notebooks kept in a backup folder.
"""

import importlib.util
import json
import os
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SETUP = os.path.join(_HERE, "..", "..", "RQB2-bin", "setup_quantum_paradoxes.py")


def _load():
    spec = importlib.util.spec_from_file_location("setup_quantum_paradoxes", _SETUP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _notebook(code):
    return {"cells": [{"cell_type": "code", "metadata": {}, "source": [code],
                       "outputs": [], "execution_count": None}],
            "metadata": {}, "nbformat": 4, "nbformat_minor": 4}


@pytest.fixture
def checkout(tmp_path):
    """A git checkout with one upstream-style notebook per paradox."""
    mod = _load()
    for name in mod.PARADOXES:
        (tmp_path / name).write_text(json.dumps(_notebook("qc.cnot(0, 1)\n")))
    git = ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(git[:3] + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "upstream"], check=True)
    return mod, tmp_path


def _code(path):
    cells = json.loads(path.read_text())["cells"]
    return "".join("".join(c["source"]) for c in cells if c["cell_type"] == "code")


def test_setup_writes_stamp(checkout):
    mod, repo = checkout
    mod.setup_quantum_paradoxes(repo)
    assert (repo / mod.STAMP_FILE).read_text().strip() == mod.setup_fingerprint()
    assert (repo / "WELCOME.ipynb").exists()


def test_refresh_is_a_no_op_when_current(checkout):
    mod, repo = checkout
    mod.setup_quantum_paradoxes(repo)
    mod.refresh_quantum_paradoxes(repo)
    assert not list(repo.glob("backup-*"))


def test_refresh_repatches_old_install(checkout):
    """No stamp (install from before #181): back up, restore upstream, re-patch."""
    mod, repo = checkout
    name = next(iter(mod.PARADOXES))
    # An old install: patched by an older script, then run by the user
    (repo / name).write_text(json.dumps(_notebook("qc.cx(0, 1)\nOLD PATCH\n")))

    mod.refresh_quantum_paradoxes(repo)

    backups = list(repo.glob("backup-*"))
    assert len(backups) == 1
    assert "OLD PATCH" in _code(backups[0] / name)
    code = _code(repo / name)
    assert "OLD PATCH" not in code
    assert "qc.cx(0, 1)" in code  # re-patched from the upstream qc.cnot
    assert (repo / mod.STAMP_FILE).read_text().strip() == mod.setup_fingerprint()


def test_refresh_after_script_change(checkout):
    mod, repo = checkout
    mod.setup_quantum_paradoxes(repo)
    (repo / mod.STAMP_FILE).write_text("older-version\n")
    mod.refresh_quantum_paradoxes(repo)
    assert len(list(repo.glob("backup-*"))) == 1
    assert (repo / mod.STAMP_FILE).read_text().strip() == mod.setup_fingerprint()
