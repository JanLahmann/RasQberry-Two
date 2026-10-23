"""
rq_venv_repair.sh (batch B10, R-128, R-059): report, give root-owned files
back, and reset the RQB2 venv from the image template - keeping the old venv,
copying bin/ too (jupyter) and pointing the copied scripts at the new path.

Runs against a temporary home, a fake template and a fake environment config.
"""

import os
import shutil

import pytest

from test_learner_setup import _BIN, _fake_venv, _run, _venv, home  # noqa: F401 (fixture)

_REPAIR = os.path.join(_BIN, "rq_venv_repair.sh")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")



def test_report_counts_without_changing_anything(home):
    proc = _run(_REPAIR, [], home)
    assert "jupyter-lab:       MISSING" in proc.stdout
    assert "root-owned files:  0" in proc.stdout


def test_reset_keeps_the_old_venv_and_rewrites_paths(home, tmp_path):
    h, _ = home
    template_root = tmp_path / "template-home" / "RasQberry-Two" / "venv" / "RQB2"
    template = _fake_venv(template_root, packages=["qiskit", "numpy"])
    # the user had added a package of their own
    (_venv(h) / "lib" / "python3.13" / "site-packages" / "cowsay-6.1.dist-info").mkdir()

    proc = _run(_REPAIR, ["--reset", "--yes"], home, extra_env={"RQ_VENV_TEMPLATE": str(template)})
    venv, previous = _venv(h), _venv(h).with_name("RQB2.previous")
    assert (previous / "lib" / "python3.13" / "site-packages" / "cowsay-6.1.dist-info").is_dir()
    assert (venv / "lib" / "python3.13" / "site-packages" / "numpy-1.0.dist-info").is_dir()
    assert "cowsay" in proc.stdout
    assert (venv / "bin" / "jupyter").read_text().startswith(f"#!{venv}/bin/python3")
    assert str(template) not in (venv / "bin" / "activate").read_text()
    assert os.access(venv / "bin" / "python3", os.X_OK)
    assert (venv / "lib" / "python3.13" / "site-packages" / "00-rasqberry.pth").is_file()


def test_reset_creates_a_missing_venv(home, tmp_path):
    h, _ = home
    shutil.rmtree(_venv(h))
    template = _fake_venv(tmp_path / "t" / "RQB2", packages=["qiskit"])
    _run(_REPAIR, ["--reset"], home, extra_env={"RQ_VENV_TEMPLATE": str(template)})
    assert (_venv(h) / "bin" / "jupyter").is_file()
    assert not _venv(h).with_name("RQB2.previous").exists()


def test_reset_without_terminal_needs_yes(home, tmp_path):
    template = _fake_venv(tmp_path / "t" / "RQB2")
    proc = _run(_REPAIR, ["--reset"], home, extra_env={"RQ_VENV_TEMPLATE": str(template)}, check=False)
    assert proc.returncode != 0
    assert (_venv(home[0]) / "lib" / "python3.13" / "site-packages" / "qiskit-1.0.dist-info").is_dir()


def test_reset_with_python_313s_activate(home, tmp_path):
    # H-44 (rig, 2026-10-23): Python 3.13 writes the path indented, as
    # "export VIRTUAL_ENV=/path" next to a cygpath line. The reset ended after
    # the copy (exit 1), left the template's path in pip and jupyter-lab (no
    # interpreter for any user but the first) and listed no added packages.
    h, _ = home
    template = _fake_venv(tmp_path / "template-home" / "RasQberry-Two" / "venv" / "RQB2",
                          packages=["qiskit"])
    (template / "bin" / "activate").write_text(
        'if [ "${OSTYPE:-}" = "cygwin" ] || [ "${OSTYPE:-}" = "msys" ] ; then\n'
        f'    VIRTUAL_ENV=$(cygpath {template})\n'
        '    export VIRTUAL_ENV\n'
        'else\n'
        '    # use the path as-is\n'
        f'    export VIRTUAL_ENV={template}\n'
        'fi\n')
    (_venv(h) / "lib" / "python3.13" / "site-packages" / "cowsay-6.1.dist-info").mkdir()
    proc = _run(_REPAIR, ["--reset", "--yes"], home, extra_env={"RQ_VENV_TEMPLATE": str(template)})
    venv = _venv(h)
    assert proc.returncode == 0
    assert (venv / "bin" / "jupyter").read_text().startswith(f"#!{venv}/bin/python3")
    assert f"export VIRTUAL_ENV={venv}\n" in (venv / "bin" / "activate").read_text()
    assert "cowsay" in proc.stdout and "Fresh RasQberry Python environment ready" in proc.stdout


def test_fix_ownership_removes_what_an_interrupted_pip_run_left(home):
    # H-44: a reinstall that failed on root-owned files left ~etuptools and
    # ~kg_resources; every pip run then warned "Ignoring invalid distribution"
    site = _venv(home[0]) / "lib" / "python3.13" / "site-packages"
    for name in ("~etuptools", "~etuptools-75.5.0.dist-info", "~kg_resources"):
        (site / name).mkdir()
    proc = _run(_REPAIR, ["--fix-ownership", "--yes"], home)
    assert not list(site.glob("~*"))
    assert "Removed what an interrupted pip run left: ~etuptools" in proc.stdout
    assert (site / "qiskit-1.0.dist-info").is_dir()
