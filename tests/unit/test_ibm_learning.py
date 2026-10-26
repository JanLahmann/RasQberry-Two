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

import json
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
          "learning/courses/basics/intro.ipynb", "public/images/x.png", "scripts/build.py",
          "public/learning/images/courses/basics/fig.svg", "public/learning/images/modules/m.svg",
          "public/docs/images/tutorials/chsh-inequality/out.avif",
          "public/docs/images/guides/hello-world/o.svg", "public/docs/images/guides/other-guide/y.png"]
# the pictures the notebooks show (rig mission 2026-10-16)
_PICTURES = {"public/learning/images/courses/basics/fig.svg",
             "public/docs/images/tutorials/chsh-inequality/out.avif",
             "public/docs/images/guides/hello-world/o.svg"}
# a lesson as the website writes it: front matter, a picture by its site path
_LESSON = json.dumps({"cells": [{"cell_type": "markdown", "metadata": {}, "source": [
    "---\n", "title: Intro\n", "---\n", "\n", "# Intro\n", "\n",
    "![A figure](/learning/images/courses/basics/fig.svg)"]}],
    "metadata": {}, "nbformat": 4, "nbformat_minor": 5})
_CONTENT = {"learning/courses/basics/intro.ipynb": _LESSON}


@pytest.fixture
def old_checkout(tmp_path):
    """A checkout as RasQberry made it before #18 (cone mode)."""
    upstream = tmp_path / "upstream"
    for name in _FILES:
        f = upstream / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(_CONTENT.get(name, name))
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
        "docs/guides/hello-world.ipynb", "learning/courses/basics/intro.ipynb",
        ".rasqberry-converted"} | _PICTURES
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
def test_tidy_brings_the_pictures_to_a_download_without_them(old_checkout, tmp_path):
    # rig mission 2026-10-16: a download made with the list before (no
    # pictures) showed raw front matter and broken pictures. The next start
    # adds them, with no download, and makes the notebooks show them.
    dest = tmp_path / "before"
    dest.mkdir()
    _git(dest, "init", "-q")
    _git(dest, "remote", "add", "origin", str(tmp_path / "upstream"))
    _git(dest, "sparse-checkout", "set", "--no-cone", "/docs/tutorials/", "/docs/guides/hello-world.ipynb",
         "/learning/courses/", "/LICENSE", "/LICENSE-DOCS")
    _git(dest, "fetch", "-q", "--depth=1", "origin", "main")
    _git(dest, "checkout", "-q", "FETCH_HEAD")
    assert not (dest / "public").exists()
    _git(dest, "remote", "set-url", "origin", str(tmp_path / "gone"))      # offline
    proc = _tidy(dest)
    assert "rc=0" in proc.stdout, proc.stderr
    assert _PICTURES <= _tree(dest)
    lesson = dest / "learning" / "courses" / "basics" / "intro.ipynb"
    source = "".join(json.loads(lesson.read_text())["cells"][0]["source"])
    assert source == "# Intro\n\n![A figure](../../../public/learning/images/courses/basics/fig.svg)"
    assert (lesson.parent / "../../../public/learning/images/courses/basics/fig.svg").resolve().is_file()
    # the next start finds it done
    before = lesson.stat().st_mtime_ns
    assert "Preparing" not in _tidy(dest).stdout
    assert lesson.stat().st_mtime_ns == before


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
        "docs/guides/hello-world.ipynb", "learning/courses/basics/intro.ipynb"} | _PICTURES


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


def test_tutorials_and_courses_open_their_own_workspace():
    # one folder, two JupyterLabs: Courses opened with the tab Tutorials left
    for name, demo, nb in (("rq_ibm_tutorials.sh", "ibm-tutorials", "WELCOME-tutorials.ipynb"),
                           ("rq_ibm_courses.sh", "ibm-courses", "WELCOME-courses.ipynb")):
        text = _read(_BIN, name)
        assert f'/lab/workspaces/{demo}/tree/{nb}?token=' in text, name


# --- the pin lives in the manifests (Jan, 2026-10-24) ---------------------------

def _manifest(did):
    return json.load(open(os.path.join(_CFG, "demo-manifests", f"rq_demo_{did}.json")))


def test_the_pair_shares_one_pin_in_its_manifests():
    c, t = _manifest("ibm-courses"), _manifest("ibm-tutorials")
    assert c["install"]["source"] == t["install"]["source"]
    assert re.fullmatch(r"[0-9a-f]{40}", c["install"]["source"]["ref"])
    assert c["entrypoint"]["working_dir"] == t["entrypoint"]["working_dir"] == "ibm-quantum-learning"
    # one place: no second pin in the environment file
    assert "GIT_REF_DEMO_IBM_LEARNING=" not in _read(_CFG, "rasqberry_environment.env")


def _menu_ref(tmp_path, prelude=""):
    menu = _read(_MENU)
    body = re.search(r"^    _ibm_ref=\"\"\n.*?\(unpinned\)\"\n    fi\n", menu, re.S | re.M).group(0)
    script = f'{prelude}\nf() {{\n{body}    echo "$_ibm_ref"\n}}\nf'
    env = dict(os.environ, RQ_SHIPPED_MANIFESTS=os.path.join(_CFG, "demo-manifests"))
    return subprocess.run(["sh", "-c", script], capture_output=True, text=True, env=env).stdout.strip()


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq is required")
def test_the_download_takes_the_pin_or_the_version_chosen(tmp_path):
    pin = _manifest("ibm-courses")["install"]["source"]["ref"]
    assert _menu_ref(tmp_path) == pin                       # under dash: the manifest
    assert _menu_ref(tmp_path, 'rq_demo_ref() { echo ' + "c" * 40 + '; }') == "c" * 40


@pytest.mark.skipif(shutil.which("jq") is None or shutil.which("bash") is None,
                    reason="bash and jq are required")
def test_update_demos_lists_the_pair_once(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    log = tmp_path / "wt.log"
    wt = stubs / "whiptail"
    wt.write_text(f'#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done >> "{log}"\nexit 1\n')
    wt.chmod(0o755)
    home = tmp_path / "home"
    (home / "RasQberry-Two" / "demos" / "ibm-quantum-learning" / ".git").mkdir(parents=True)
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(f'USER_HOME="{home}"\nREPO=RasQberry-Two\nBIN_DIR="{_BIN}"\nSTD_VENV=RQB2\n')
    env = {"PATH": f"{stubs}:{os.environ['PATH']}", "HOME": str(home), "RQ_CONFIG_FILE": str(env_config)}
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_demo_update.sh")], capture_output=True,
                          text=True, env=env, timeout=120, stdin=subprocess.DEVNULL)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    items = log.read_text().splitlines()
    assert sum("IBM Quantum Tutorials" in i or "and Tutorials" in i for i in items) == 1
    assert "IBM Quantum Courses and Tutorials (notebooks): as released" in items


def test_the_tested_update_notice_names_both():
    import importlib.util
    spec = importlib.util.spec_from_file_location("rq_catalogue", os.path.join(_BIN, "rq_catalogue.py"))
    cat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cat)
    mdir = os.path.join(_CFG, "demo-manifests")
    assert cat.shared_name(_manifest("ibm-courses"), mdir) == "IBM Quantum Courses and IBM Quantum Tutorials"
    assert cat.shared_name(_manifest("grok-bloch"), mdir) == _manifest("grok-bloch")["name"]
