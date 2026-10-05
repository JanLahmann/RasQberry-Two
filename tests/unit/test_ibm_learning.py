"""
User test 2026-10-04, #18: IBM Quantum Tutorials and Courses (and Quantum
Lab, which mounts the same content) opened on the raw Qiskit/documentation
repository - package.json, tox.ini, check, fix ... before the notebooks - and
their welcome text sent people to 00-Save-Credentials.ipynb instead of the
RasQberry menu's "Save my API key".

The content is now checked out without the repository's own files
(non-cone sparse checkout), and rq_ibm_learning_tidy narrows a checkout made
before, without a download.
"""

import os
import re
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_COMMON = os.path.join(_BIN, "rq_common.sh")
_MENU = os.path.join(_CFG, "RQB2_menu.sh")

needs_git = pytest.mark.skipif(shutil.which("git") is None or shutil.which("bash") is None,
                               reason="git and bash are required")


def _read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "init.defaultBranch=main",
                    *args], cwd=cwd, check=True, capture_output=True, text=True)


# A small stand-in for Qiskit/documentation: the files at its top as at the
# pinned commit, and a few of the folders
_FILES = ["package.json", "package-lock.json", "tox.ini", "check", "fix", "setup", "start",
          "README.md", "style-guide.md", "qiskit_bot.yaml", "LICENSE", "LICENSE-DOCS",
          "docs/ruff.toml", "docs/accessibility.mdx",
          "docs/tutorials/chsh-inequality.ipynb", "docs/tutorials/_toc.json",
          "docs/guides/hello-world.ipynb", "docs/guides/other-guide.ipynb",
          "learning/courses/basics/intro.ipynb", "public/images/x.png", "scripts/build.py"]


@pytest.fixture
def old_checkout(tmp_path):
    """A checkout as RasQberry made it before #18 (cone mode)."""
    upstream = tmp_path / "upstream"
    for name in _FILES:
        f = upstream / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(name)
    _git(upstream, "init", "-q")
    _git(upstream, "add", "-A")
    _git(upstream, "commit", "-qm", "docs")
    dest = tmp_path / "ibm-quantum-learning"
    dest.mkdir()
    _git(dest, "init", "-q")
    _git(dest, "remote", "add", "origin", str(upstream))
    _git(dest, "sparse-checkout", "init", "--cone")
    _git(dest, "sparse-checkout", "set", "docs/tutorials", "docs/guides/hello-world.ipynb",
         "learning/courses", "LICENSE", "LICENSE-DOCS")
    _git(dest, "fetch", "-q", "--depth=1", "origin", "main")
    _git(dest, "checkout", "-q", "FETCH_HEAD")
    # what RasQberry adds: the welcome notebooks, the credentials notebook
    (dest / "WELCOME-tutorials.ipynb").write_text("{}")
    (dest / "00-Save-Credentials.ipynb").write_text("{}")
    return dest


def _tree(d):
    out = set()
    for dirpath, dirnames, files in os.walk(d):
        dirnames[:] = [n for n in dirnames if n != ".git"]
        for name in files:
            out.add(os.path.relpath(os.path.join(dirpath, name), d))
    return out


def _tidy(d):
    return subprocess.run(["bash", "-c", f'. "{_COMMON}"; rq_ibm_learning_tidy "$1"; echo "rc=$?"', "_", str(d)],
                          capture_output=True, text=True, timeout=60)


@needs_git
def test_tidy_narrows_a_checkout_made_before(old_checkout):
    assert "package.json" in os.listdir(old_checkout)        # what the user test saw
    proc = _tidy(old_checkout)
    assert "rc=0" in proc.stdout, proc.stderr
    assert _tree(old_checkout) == {
        "LICENSE", "LICENSE-DOCS", "WELCOME-tutorials.ipynb", "00-Save-Credentials.ipynb",
        "docs/tutorials/chsh-inequality.ipynb", "docs/tutorials/_toc.json",
        "docs/guides/hello-world.ipynb", "learning/courses/basics/intro.ipynb"}
    # the checkout is still a valid one for the installer (_rq_ibm_content_ok)
    head = subprocess.run(["git", "-C", str(old_checkout), "rev-parse", "-q", "--verify", "HEAD"],
                          capture_output=True, text=True)
    assert head.returncode == 0


@needs_git
def test_tidy_keeps_a_notebook_someone_changed(old_checkout):
    nb = old_checkout / "docs" / "tutorials" / "chsh-inequality.ipynb"
    nb.write_text("my notes")
    _tidy(old_checkout)
    assert nb.read_text() == "my notes"


@needs_git
def test_tidy_does_nothing_without_the_repository_files(tmp_path):
    d = tmp_path / "ibm-quantum-learning"
    (d / "docs").mkdir(parents=True)
    proc = _tidy(d)
    assert "rc=0" in proc.stdout and _tree(d) == set()
    assert "rc=0" in _tidy(tmp_path / "missing").stdout


@needs_git
def test_a_new_download_holds_only_the_notebooks(old_checkout, tmp_path):
    # the installer's commands (clone_ibm_learning_content), with its list
    paths = re.search(r'^RQ_IBM_LEARNING_PATHS="([^"]+)"', _read(_COMMON), re.M).group(1)
    dest = tmp_path / "new"
    dest.mkdir()
    _git(dest, "init", "-q")
    _git(dest, "remote", "add", "origin", str(tmp_path / "upstream"))
    _git(dest, "sparse-checkout", "set", "--no-cone", *paths.split())
    _git(dest, "fetch", "-q", "--depth=1", "origin", "main")
    _git(dest, "checkout", "-q", "FETCH_HEAD")
    assert _tree(dest) == {
        "LICENSE", "LICENSE-DOCS", "docs/tutorials/chsh-inequality.ipynb", "docs/tutorials/_toc.json",
        "docs/guides/hello-world.ipynb", "learning/courses/basics/intro.ipynb"}


def test_installer_and_tidy_use_one_list():
    common = _read(_COMMON)
    paths = re.search(r'^RQ_IBM_LEARNING_PATHS="([^"]+)"', common, re.M).group(1)
    menu = _read(_MENU)
    assert f"git sparse-checkout set --no-cone {paths} &&" in menu
    assert "sparse-checkout init --cone" not in menu


def test_launchers_tidy_before_they_start():
    for name, var in (("rq_ibm_tutorials.sh", "DEMO_DIR"), ("rq_ibm_courses.sh", "DEMO_DIR"),
                      ("rq_quantum_lab.sh", "DOCS_DIR")):
        text = _read(_BIN, name)
        assert f'rq_ibm_learning_tidy "${var}"' in text, name
        start = "docker run" if var == "DOCS_DIR" else "jupyter-lab \\"
        assert text.index("rq_ibm_learning_tidy") < text.index(start), name


def test_welcome_and_readme_point_to_the_menu():
    menu = _read(_MENU)
    assert 'IBMQ "IBM Quantum account"' in menu and 'SAVE   "Save my API key' in menu
    welcome = _read(_BIN, "setup_ibm_tutorials.py")
    assert "00-Save-Credentials" not in welcome
    assert welcome.count("**IBM Quantum account** → **Save my API key**") == 2
    readme = _read(_CFG, "my-quantum-programs", "README.md")
    assert "**IBM Quantum account** → **Save my API key**" in readme
    assert "begin with a notebook that saves the key" not in readme
