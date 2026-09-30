"""
Tests for RQB2-bin/rq_pip_extras.py (issue #285).

The helper is run with the test interpreter, so "installed" means installed
in the environment running pytest. pytest itself is therefore a guaranteed
installed distribution, and a made-up name a guaranteed missing one.
"""

import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "..", "RQB2-bin", "rq_pip_extras.py")

sys.path.insert(0, os.path.join(_HERE, "..", "..", "RQB2-bin"))
import rq_pip_extras  # noqa: E402


def _run(req_text, tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text(req_text)
    out = tmp_path / "out"
    proc = subprocess.run(
        [sys.executable, _SCRIPT, str(req), str(out)],
        capture_output=True,
        text=True,
    )
    return proc, out


def test_requirement_name_parsing():
    assert rq_pip_extras.requirement_name("numpy==2.3.2") == "numpy"
    assert rq_pip_extras.requirement_name("Qiskit_Aer>=0.17 ; python_version>'3'") == "qiskit-aer"
    assert rq_pip_extras.requirement_name("pkg[extra]==1.0  # comment") == "pkg"
    assert rq_pip_extras.requirement_name("   # just a comment") is None
    assert rq_pip_extras.requirement_name("-r other.txt") is None
    assert rq_pip_extras.requirement_name("") is None


def test_installed_package_is_kept_not_downgraded(tmp_path):
    """A pin for an installed package must not land in extras.txt."""
    proc, out = _run("pytest==0.0.1\n", tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert (out / "extras.txt").read_text() == ""
    assert "keep installed: pytest==0.0.1" in proc.stdout
    constraints = (out / "constraints.txt").read_text()
    assert f"pytest=={pytest.__version__}\n" in constraints


def test_missing_package_becomes_an_extra(tmp_path):
    proc, out = _run(
        "# demo deps\npytest>=1\nrasqberry-definitely-missing-xyz==1.0\n", tmp_path
    )
    assert proc.returncode == 0, proc.stderr
    assert (out / "extras.txt").read_text() == "rasqberry-definitely-missing-xyz==1.0\n"
    assert "summary: 1 to install, 1 already present" in proc.stdout


def test_constraints_pin_every_installed_distribution(tmp_path):
    proc, out = _run("", tmp_path)
    assert proc.returncode == 0
    lines = (out / "constraints.txt").read_text().splitlines()
    assert lines, "constraints.txt should list the interpreter's packages"
    assert all("==" in line for line in lines)
    assert not any(" @ " in line or "://" in line for line in lines)


def test_unreadable_requirements_is_a_usage_error(tmp_path):
    proc = subprocess.run(
        [sys.executable, _SCRIPT, str(tmp_path / "nope.txt"), str(tmp_path / "out")],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "cannot read" in proc.stderr
