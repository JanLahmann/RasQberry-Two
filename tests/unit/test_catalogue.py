"""
User test 2026-10-04, #23: the demo catalogue (rq_demo_add_external.sh).

- A Docker demo said "installed successfully", and its first start then
  asked to download 530 MB: now it is "Registered" with the size that comes
  on the first start.
- The picker cut its descriptions at the right edge: one line each, without
  the ids in front, ending at a word.
- Removing a demo went back to the menu without a word: now it says so.

The install runs against a registry and a "repository" made here: git is a
stub that checks out the files of FAKE_REPO, docker and whiptail are stubs.
"""

import json
import os
import shutil
import stat
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_ADD = os.path.join(_BIN, "rq_demo_add_external.sh")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None or shutil.which("jq") is None,
                                reason="bash and jq are required")

_SHA = "0123456789abcdef0123456789abcdef01234567"
_IMAGE = "ghcr.io/example/dock-demo@sha256:" + "a" * 64

_WHIPTAIL = r'''#!/bin/sh
{ for a in "$@"; do printf '%s\n' "$a"; done; echo "@@"; } >> "$WT_LOG"
exit "${WT_RC:-0}"
'''

# git init / fetch do nothing; checkout copies the "repository"
_GIT = r'''#!/bin/sh
case "$1" in
  init) mkdir -p .git ;;
  checkout) cp -R "$FAKE_REPO"/. . ;;
esac
exit 0
'''


def _exe(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _manifest():
    return {
        "id": "dock-demo",
        "name": "Dock Demo",
        "category": "game",
        "description": "A racing game in a container",
        "entrypoint": {"type": "docker", "working_dir": "dock-demo", "docker_image": _IMAGE,
                       "docker_port": 8000},
        "install": {"repo_url": "https://github.com/example/dock-demo.git", "marker_file": "rqb-demo.json"},
        "needs_hw": {"leds": False, "display": "optional"},
        "desktop": {"show": False},
    }


@pytest.fixture
def cat(tmp_path):
    """A copy of RQB2-bin with its own registry, a fake home and stubs."""
    root = tmp_path / "tree"
    shutil.copytree(_BIN, root / "RQB2-bin")
    (root / "RQB2-config").mkdir(parents=True)
    os.symlink(os.path.join(_CFG, "demo-manifests"), root / "RQB2-config" / "demo-manifests")
    registry = {"demos": [{
        "id": "dock-demo", "name": "Dock Demo", "summary": "a racing game in a container",
        "provider": "the Example family", "repo_url": "https://github.com/example/dock-demo.git",
        "ref": _SHA, "manifest_path": "rqb-demo.json", "added": "2026-10-05",
        "download": {"download_mb": 530, "disk_mb": 3260}}]}
    (root / "RQB2-config" / "known-demos.json").write_text(json.dumps(registry))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "rqb-demo.json").write_text(json.dumps(_manifest()))
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _exe(stubs / "whiptail", _WHIPTAIL)
    _exe(stubs / "git", _GIT)
    _exe(stubs / "curl", "#!/bin/sh\nexit 0\n")
    _exe(stubs / "sudo", '#!/bin/sh\n[ "$1" = "-n" ] && shift\nexec "$@"\n')
    _exe(stubs / "docker", '#!/bin/sh\necho "$*" >> "$DOCKER_LOG"\n'
                           '[ "$1 $2" = "image inspect" ] && exit "${IMAGE_RC:-1}"\nexit 0\n')
    home = tmp_path / "home"
    (home / "Desktop").mkdir(parents=True)
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(f'USER_HOME="{home}"\nREPO=RasQberry-Two\nSTD_VENV=RQB2\n')
    wt_log = tmp_path / "wt.log"

    def run(args, extra=None, tty=False):
        env = {"PATH": f"{stubs}:{os.environ['PATH']}", "HOME": str(home), "USER": "rasqberry",
               "RQ_CONFIG_FILE": str(env_config), "RQ_TEST_FREE_MB": "50000",
               "FAKE_REPO": str(repo), "WT_LOG": str(wt_log), "DOCKER_LOG": str(tmp_path / "docker.log")}
        env.update(extra or {})
        script = str(root / "RQB2-bin" / "rq_demo_add_external.sh")
        if tty:
            # the dialogs at the end want a terminal, as in the menu
            import pty
            master, slave = pty.openpty()
            proc = subprocess.run(["bash", script, *args], stdin=slave, stdout=slave, stderr=slave,
                                  env=env, timeout=120)
            os.close(slave)
            os.close(master)
            return proc
        return subprocess.run(["bash", script, *args], capture_output=True, text=True, env=env,
                              timeout=120, stdin=subprocess.DEVNULL)

    def dialogs():
        if not wt_log.exists():
            return []
        calls, cur = [], []
        for line in wt_log.read_text().splitlines():
            if line == "@@":
                calls.append(cur)
                cur = []
            else:
                cur.append(line)
        return calls

    run.home = home
    run.dialogs = dialogs
    return run


def _msgbox(call):
    return call[call.index("--msgbox") + 1]


def test_a_docker_demo_is_registered_with_what_its_first_start_downloads(cat):
    proc = cat(["dock-demo"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (cat.home / ".local/config/demo-manifests/rq_demo_dock-demo.json").is_file()
    last = cat.dialogs()[-1]
    assert _arg(last, "--title") == "Demo added"
    text = _msgbox(last)
    assert text.startswith("Registered: Dock Demo. On its first start it downloads its Docker image, "
                           "about 530 MB."), text
    assert "Start it from the Quantum Demos menu." in text
    assert "installed successfully" not in proc.stdout + proc.stderr + text


def test_a_demo_whose_image_is_here_is_installed(cat):
    proc = cat(["dock-demo"], extra={"IMAGE_RC": "0"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _msgbox(cat.dialogs()[-1]).startswith("Dock Demo is installed.")


def _arg(call, option):
    return call[call.index(option) + 1] if option in call else None


def test_picker_lines_fit_without_ids(cat):
    proc = cat([], extra={"WT_RC": "1"})          # Back
    assert proc.returncode == 0, proc.stdout + proc.stderr
    menu = [c for c in cat.dialogs() if "--menu" in c][0]
    assert "--notags" in menu
    items = menu[menu.index("--") + 1:]
    assert items[0] == "dock-demo" and items[1] == "Dock Demo - a racing game in a container"


def test_the_shipped_catalogue_fits_one_line_each():
    registry = json.load(open(os.path.join(_CFG, "known-demos.json"), encoding="utf-8"))["demos"]
    for d in registry:
        name = d["name"] + (" (beta)" if d.get("maturity") == "beta" else "")
        label = f"{name} - {d['summary']}"
        assert len(label) <= 66, label           # 78 wide, no tags: nothing is cut


@pytest.mark.parametrize("text,expected", [
    ("short", "short"),
    ("x" * 66, "x" * 66),
    ("traQmania (beta) - quantum reinforcement-learning racing game in a container",
     "traQmania (beta) - quantum reinforcement-learning racing game..."),
])
def test_long_lines_end_at_a_word(text, expected):
    script = (f'eval "$(sed -n \'/^fit_line() {{/,/^}}/p\' "{_ADD}")"; fit_line "$1"')
    out = subprocess.run(["bash", "-c", script, "_", text], capture_output=True, text=True).stdout
    assert out == expected and len(out) <= 66


def test_removal_says_it_is_done(cat):
    proc = cat(["dock-demo"], extra={"IMAGE_RC": "0"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    proc = cat(["--remove", "dock-demo"], extra={"IMAGE_RC": "1"}, tty=True)
    assert proc.returncode == 0
    last = cat.dialogs()[-1]
    assert _arg(last, "--title") == "Demo removed"
    assert _msgbox(last).startswith("Dock Demo was removed. Free space now: 50.0 GB.")
    assert not (cat.home / ".local/config/demo-manifests/rq_demo_dock-demo.json").exists()


def test_removal_without_a_terminal_asks_and_says_nothing(cat):
    cat(["dock-demo"], extra={"IMAGE_RC": "0"})
    n = len(cat.dialogs())
    proc = cat(["--remove", "dock-demo"], extra={"IMAGE_RC": "1"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert len(cat.dialogs()) == n


# --- one progress line instead of Docker's list of layers -------------------------

_COMMON = os.path.join(_BIN, "rq_common.sh")


def _pull(tmp_path, tty, rc=0):
    stubs = tmp_path / "pull-stubs"
    stubs.mkdir()
    net = tmp_path / "net" / "eth0" / "statistics"
    net.mkdir(parents=True)
    (net / "rx_bytes").write_text("1000000000\n")
    log = tmp_path / "pull.log"
    # a pull that takes a moment and receives 120 MB; layer lines on stdout
    # as Docker prints them without -q
    _exe(stubs / "docker", f'#!/bin/sh\necho "$*" >> "{log}"\n'
                           'case " $* " in *" -q "*) ;; *) echo "abc123: Pulling fs layer" ;; esac\n'
                           f'echo 1120000000 > "{net}/rx_bytes"; sleep 3\n'
                           f'[ {rc} -eq 0 ] || echo "Error response from daemon: manifest unknown" >&2\n'
                           f'exit {rc}\n')
    env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", RQ_NET_DIR=str(tmp_path / "net"))
    script = f'. "{_COMMON}"; rq_docker_pull ghcr.io/x/demo@sha256:1 "Demo X" 530; echo "rc=$?"'
    if not tty:
        proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env, timeout=60)
        return proc.stdout + proc.stderr, log.read_text()
    import pty
    import threading
    master, slave = pty.openpty()
    out = []

    def read():
        while True:
            try:
                data = os.read(master, 4096)
            except OSError:
                return
            if not data:
                return
            out.append(data)
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    subprocess.run(["bash", "-c", script], stdin=slave, stdout=slave, stderr=slave, env=env, timeout=60)
    os.close(slave)
    reader.join(5)
    os.close(master)
    return b"".join(out).decode("utf-8", "replace"), log.read_text()


def test_pull_in_a_terminal_shows_one_line_with_the_megabytes(tmp_path):
    out, calls = _pull(tmp_path, tty=True)
    assert "pull -q ghcr.io/x/demo@sha256:1" in calls
    assert "Pulling fs layer" not in out
    assert "Downloading Demo X ... 120 of about 530 MB," in out, repr(out)
    assert "Downloading Demo X ... done (" in out and "rc=0" in out


def test_pull_without_a_terminal_is_quiet(tmp_path):
    out, calls = _pull(tmp_path, tty=False)
    assert "pull -q" in calls and "Pulling fs layer" not in out and "rc=0" in out


def test_a_failed_pull_still_says_why(tmp_path):
    out, _calls = _pull(tmp_path, tty=False, rc=1)
    assert "The registry does not offer ghcr.io/x/demo@sha256:1" in out and "manifest unknown" in out
