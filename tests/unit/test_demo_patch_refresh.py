"""
A changed RasQberry patch reaches a demo that is installed already
(rq_demo_run.sh refresh_demo_patch), pre-beta review 2026-10-16:

- B5: a patch that creates a file (Grok Bloch's rasqberry-help.js) could
  never be refreshed: "git checkout HEAD -- <new file>" failed, so every
  start said "Could not update the RasQberry changes".
- B4: the refresh ran git as root inside the user's checkout, and git honours
  the checkout's own .git/config (core.fsmonitor, hooks): a command in it ran
  as root. Now git runs as the checkout's user, without fsmonitor and hooks,
  and the patch note replaces a symlink instead of writing through it.

The checkouts are real git repositories made here.
"""

import os
import re
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_RUN = os.path.join(_ROOT, "RQB2-bin", "rq_demo_run.sh")

pytestmark = pytest.mark.skipif(shutil.which("git") is None or shutil.which("sha256sum") is None,
                                reason="git and sha256sum are required")

_FUNCS = ("apply_demo_patch", "_rq_patch_refresh", "refresh_demo_patch")


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                            GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t"))


def _patch(repo, edit, help_text):
    """A patch against the pinned commit: index.html changed, rasqberry-help.js created."""
    (repo / "index.html").write_text(edit)
    (repo / "rasqberry-help.js").write_text(help_text)
    _git(repo, "add", "-N", "rasqberry-help.js")
    diff = subprocess.run(["git", "-C", str(repo), "diff"], capture_output=True, text=True, check=True).stdout
    _git(repo, "reset", "-q")
    _git(repo, "checkout", "-q", "--", "index.html")
    (repo / "rasqberry-help.js").unlink()
    return diff


@pytest.fixture
def demo(tmp_path):
    """Grok-Bloch-like: a pinned checkout with the old patch applied, and a new patch."""
    if os.geteuid() == 0:
        # as root the refresh hands over to the desktop user (checked below and on the rig)
        pytest.skip("runs the refresh as the user it is")
    home = tmp_path / "home"
    repo = home / "RasQberry-Two" / "demos" / "grok-bloch"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / "index.html").write_text("<html>\n<body>\nupstream\n</body>\n</html>\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "pin")
    patches = tmp_path / "patches"
    patches.mkdir()
    (patches / "old.patch").write_text(_patch(repo, "<html>\n<body>\nupstream\nold help\n</body>\n</html>\n", "old\n"))
    (patches / "new.patch").write_text(_patch(repo, "<html>\n<body>\nupstream\nnew help\n</body>\n</html>\n", "new\n"))
    (patches / "broken.patch").write_text((patches / "new.patch").read_text().replace("upstream", "elsewhere"))

    def run(patch_name, setup=""):
        script = (f'eval "$(sed -n ' + " ".join(f"-e '/^{f}() {{/,/^}}/p'" for f in _FUNCS) + f' "{_RUN}")"\n'
                  'info() { echo "INFO: $*"; }; warn() { echo "WARN: $*"; }; debug() { :; }\n'
                  'get_user_name() { id -un; }\n'
                  'get_field() { case "$1" in .install.patch_file) echo "$PATCH_NAME" ;; '
                  '.entrypoint.working_dir) echo grok-bloch ;; esac; }\n'
                  f'{setup}\nrefresh_demo_patch\n')
        env = dict(os.environ, USER_HOME=str(home), REPO="RasQberry-Two", PATCHES_DIR=str(patches),
                   PATCH_NAME=patch_name, DEMO_TITLE="Grok Bloch")
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env, cwd=str(tmp_path))

    # installed under the old patch
    subprocess.run(["git", "-C", str(repo), "apply", str(patches / "old.patch")], check=True)
    (repo / ".git" / "rq-patch.sha256").write_text(
        subprocess.run(["sha256sum"], stdin=open(patches / "old.patch"), capture_output=True,
                       text=True).stdout.split()[0] + "\n")
    run.repo, run.patches, run.tmp = repo, patches, tmp_path
    return run


def _sha(path):
    return subprocess.run(["sha256sum"], stdin=open(path), capture_output=True, text=True).stdout.split()[0]


def test_a_patch_that_creates_a_file_is_refreshed(demo):
    out = demo("new.patch")
    assert "INFO: Updated the RasQberry changes to Grok Bloch" in out.stdout, out.stdout + out.stderr
    assert "new help" in (demo.repo / "index.html").read_text()
    assert "old help" not in (demo.repo / "index.html").read_text()
    assert (demo.repo / "rasqberry-help.js").read_text() == "new\n"
    assert (demo.repo / ".git" / "rq-patch.sha256").read_text().strip() == _sha(demo.patches / "new.patch")
    # and once only
    assert demo("new.patch").stdout == ""


def test_a_patch_that_does_not_apply_leaves_the_demo_as_it_was(demo):
    before = {f: (demo.repo / f).read_text() for f in ("index.html", "rasqberry-help.js")}
    out = demo("broken.patch")
    assert "WARN: Could not update the RasQberry changes to Grok Bloch: it runs as before." in out.stdout
    assert {f: (demo.repo / f).read_text() for f in before} == before
    assert (demo.repo / ".git" / "rq-patch.sha256").read_text().strip() == _sha(demo.patches / "old.patch")


def test_the_checkouts_own_git_config_runs_nothing(demo):
    # what a program with write access to the checkout could plant
    flag = demo.tmp / "PWNED"
    with open(demo.repo / ".git" / "config", "a") as f:
        f.write(f"[core]\n\tfsmonitor = touch {flag}\n")
    hooks = demo.repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    for hook in ("post-checkout", "post-index-change", "pre-applypatch"):
        (hooks / hook).write_text(f"#!/bin/sh\ntouch {flag}\n")
        (hooks / hook).chmod(0o755)
    out = demo("new.patch")
    assert "Updated the RasQberry changes" in out.stdout, out.stdout + out.stderr
    assert not flag.exists()


def test_the_patch_note_is_not_written_through_a_symlink(demo):
    target = demo.tmp / "elsewhere"
    target.write_text("keep\n")
    note = demo.repo / ".git" / "rq-patch.sha256"
    note.unlink()
    note.symlink_to(target)
    out = demo("new.patch")
    assert "Updated the RasQberry changes" in out.stdout, out.stdout + out.stderr
    assert target.read_text() == "keep\n"
    assert not note.is_symlink() and note.read_text().strip() == _sha(demo.patches / "new.patch")


def test_root_hands_the_refresh_to_the_user():
    text = open(_RUN).read()
    fn = text[text.index("refresh_demo_patch() {"):text.index("# Install demo from manifest")]
    # as root: chown -R (does not follow symlinks), then git only as the user
    assert 'chown -R "$owner:$owner" "$dir"' in fn
    assert 'sudo -u "$owner" -H -- bash -c "$(declare -f apply_demo_patch _rq_patch_refresh)"' in fn
    git = re.compile(r"(?<![./\w-])git ")
    assert not git.search(fn)
    for f in ("apply_demo_patch() {", "_rq_patch_refresh() {"):
        body = text[text.index(f):text.index("\n}\n", text.index(f))]
        calls = [ln for ln in body.splitlines() if git.search(ln) and not ln.strip().startswith("#")]
        assert calls and all("core.fsmonitor=false" in ln for ln in calls), calls
        assert "checkout HEAD" not in body or '"${git[@]}" checkout HEAD' in body
