"""
Tests for rq_download_all.sh ("Download all demos", R-031, Jan's Q27) and
rq_demo_remove.sh ("Remove a demo", R-047/R-160), plus the shipped files that
go with them: manifest sizes, desktop icons that keep their window open on
failure (R-029), the first-login step (R-087) and rq_info.sh --report (R-121).

The demo engine is replaced by a stub (RQ_DEMO_ENGINE) that "installs" by
creating the demo's marker file; whiptail is a stub that answers from WT_RC.
"""

import json
import os
import re
import shutil
import stat
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_DL = os.path.join(_BIN, "rq_download_all.sh")
_REMOVE = os.path.join(_BIN, "rq_demo_remove.sh")
_ENV_CONFIG = os.path.join(_CFG, "rasqberry_env-config.sh")
_ENV = os.path.join(_CFG, "rasqberry_environment.env")
_MANIFESTS = os.path.join(_CFG, "demo-manifests")

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required")

# whiptail stub: logs every call; a --yesno answers from WT_RC_<n> for the
# n-th yes/no question (default 0 = yes)
_WHIPTAIL = r'''#!/bin/sh
{ for a in "$@"; do printf '%s\n' "$a"; done; echo "@@"; } >> "$WT_LOG"
case " $* " in *" --yesno "*)
  n=$(cat "$WT_LOG.n" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$WT_LOG.n"
  eval "rc=\${WT_RC_$n:-0}"; exit "$rc" ;;
esac
exit 0
'''

# engine stub: --is-installed looks at a marker; --install-only creates it
_ENGINE = r'''#!/bin/sh
id="$1"
case "$2" in
  --is-installed) [ -e "$FAKE_DONE/$id" ]; exit ;;
  --install-only)
    echo "$id" >> "$FAKE_DONE/calls"
    case " $FAIL_IDS " in *" $id "*) echo "ERROR: could not download $id"; exit 1 ;; esac
    touch "$FAKE_DONE/$id"
    wd=$(jq -r '.entrypoint.working_dir // empty' "$MANIFESTS/rq_demo_$id.json")
    mk=$(jq -r '.install.marker_file // empty' "$MANIFESTS/rq_demo_$id.json")
    if [ -n "$wd" ] && [ -n "$mk" ]; then mkdir -p "$DEMOS/$wd"; touch "$DEMOS/$wd/$mk"; fi
    exit 0 ;;
esac
exit 2
'''


def _exe(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def box(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _exe(stubs / "whiptail", _WHIPTAIL)
    _exe(stubs / "curl", "#!/bin/sh\nexit 0\n")
    _exe(stubs / "sudo", '#!/bin/sh\n[ "$1" = "-n" ] && shift\nexec "$@"\n')
    _exe(stubs / "engine", _ENGINE)
    home = tmp_path / "home"
    (home / "RasQberry-Two" / "demos").mkdir(parents=True)
    done = tmp_path / "done"
    done.mkdir()
    env_file = tmp_path / "rasqberry_environment.env"
    env_file.write_text(open(_ENV).read())
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(open(_ENV_CONFIG).read()
                          .replace("/usr/config/rasqberry_environment.env", str(env_file))
                          .replace('USER_HOME="$(eval echo ~${SUDO_USER})"', f'USER_HOME="{home}"'))
    tty = tmp_path / "tty"
    tty.write_text("")

    def run(script, args, extra=None):
        env = {
            "PATH": f"{stubs}:{os.environ['PATH']}",
            "HOME": str(home),
            "USER": "rasqberry",
            "RQ_CONFIG_FILE": str(env_config),
            "RQ_ENV_FILE": str(env_file),
            "RQ_TEST_TTY": str(tty),
            "RQ_TEST_FREE_MB": "50000",
            "RQ_DEMO_ENGINE": str(stubs / "engine"),
            "FAKE_DONE": str(done),
            "MANIFESTS": _MANIFESTS,
            "DEMOS": str(home / "RasQberry-Two" / "demos"),
            "WT_LOG": str(tmp_path / "wt.log"),
        }
        env.update(extra or {})
        return subprocess.run(["bash", script, *args], capture_output=True, text=True, env=env,
                              timeout=180, start_new_session=True)

    def dialogs():
        log = tmp_path / "wt.log"
        if not log.exists():
            return []
        calls, cur = [], []
        for line in log.read_text().splitlines():
            if line == "@@":
                calls.append(cur)
                cur = []
            else:
                cur.append(line)
        return calls

    def installs():
        f = done / "calls"
        return f.read_text().split() if f.exists() else []

    run.home = home
    run.env_file = env_file
    run.stubs = stubs
    run.dialogs = dialogs
    run.installs = installs
    run.done = done
    return run


def _text(call, kind="--yesno"):
    return call[call.index(kind) + 1]


_GIT_DEMOS = {"fun-with-quantum", "grok-bloch", "ibm-tutorials", "ibm-courses", "led-painter",
              "quantum-lights-out", "quantum-paradoxes", "quantum-raspberry-tie"}
_DOCKER_DEMOS = {"doqumentation", "qoffee-maker", "quantum-lab", "quantum-mixer"}


def test_the_list_comes_from_the_manifests(box):
    proc = box(_DL, ["--list"])
    assert proc.returncode == 0, proc.stderr
    ids = {line.split("\t")[0] for line in proc.stdout.splitlines()}
    assert _GIT_DEMOS <= ids, ids                    # no docker here: Docker demos not listed
    assert not ({"composer", "grok-bloch-web", "led-demos"} & ids)


def test_one_question_then_the_docker_opt_in_with_total_size(box):
    _exe(box.stubs / "docker", '#!/bin/sh\ncase "$1" in info) exit 0 ;; image) exit 1 ;; esac\nexit 1\n')
    proc = box(_DL, [], extra={"WT_RC_2": "1"})     # yes to the demos, no to Docker
    assert proc.returncode == 0, proc.stdout + proc.stderr
    calls = [c for c in box.dialogs() if "--yesno" in c]
    assert len(calls) == 2
    first, docker = _text(calls[0]), _text(calls[1])
    assert "Not on this Pi yet (8)" in first and "Quantum Lights Out" in first
    assert "Free:      50.0 GB" in first and "start without the internet" in first
    assert "Docker demos" in docker and "Workshop & Qiskit Server" in docker and "Quantum Mixer" in docker
    # the Mixer is a prebuilt download now (Jan, Q27c): no build cache peak
    assert "while installing" not in docker and "Space:" in docker
    assert "--defaultno" in calls[1]
    assert set(box.installs()) == _GIT_DEMOS
    # IBM tutorials and courses share one download: counted once
    assert "about 174 MB" in first, first   # 30+6+80+2+1+31+24
    summary = _text(box.dialogs()[-1], "--msgbox")
    assert "Downloaded: 8 of 8." in summary
    assert "Docker demos download on their first start" in summary


def test_docker_demos_when_chosen(box):
    _exe(box.stubs / "docker", '#!/bin/sh\ncase "$1" in info) exit 0 ;; image) exit 1 ;; esac\nexit 1\n')
    proc = box(_DL, ["--yes", "--docker"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert set(box.installs()) == _GIT_DEMOS | _DOCKER_DEMOS


def test_not_enough_space_for_the_choice_is_refused(box):
    proc = box(_DL, ["--yes"], extra={"RQ_TEST_FREE_MB": "900"})
    assert proc.returncode == 1
    assert "Not enough free space" in proc.stdout and "Remove a demo" in proc.stdout
    assert box.installs() == []


def test_failures_are_named_and_the_rest_installed(box):
    proc = box(_DL, ["--yes"], extra={"FAIL_IDS": "grok-bloch"})
    assert proc.returncode == 1
    assert "Downloaded: 7 of 8." in proc.stdout
    assert "Grokking the Bloch Sphere: could not download grok-bloch" in proc.stdout
    assert "download-all.log" in proc.stdout


def test_offline_stops_before_asking(box):
    _exe(box.stubs / "curl", "#!/bin/sh\nexit 7\n")
    proc = box(_DL, ["--yes"])
    assert proc.returncode == 1 and "No internet connection" in proc.stdout
    assert box.installs() == []


def test_pending_follows_the_demos_not_the_flags(box):
    # R-087: Lights Out and Raspberry Tie were never flagged, so the setup
    # step stayed pending after everything was downloaded
    assert box(_DL, ["--pending"]).returncode == 0
    box(_DL, ["--yes"])
    assert box(_DL, ["--pending"]).returncode == 1


def test_first_login_step_uses_it():
    text = open(os.path.join(_BIN, "rq_firstlogin.sh")).read()
    assert 'rq_download_all.sh" --pending' in text
    assert "_INSTALLED=false" not in text


# --- manifests, icons --------------------------------------------------------

def _manifest(demo_id):
    with open(os.path.join(_MANIFESTS, f"rq_demo_{demo_id}.json")) as fh:
        return json.load(fh)


@pytest.mark.parametrize("demo_id", sorted(_GIT_DEMOS | _DOCKER_DEMOS))
def test_every_download_states_its_size(demo_id):
    d = _manifest(demo_id)["install"]["download"]
    assert d["download_mb"] > 0 and d["what"] and d["time"]


def test_lights_out_and_raspberry_tie_have_flags():
    assert _manifest("quantum-lights-out")["install"]["installed_flag"] == "QUANTUM_LIGHTS_OUT_INSTALLED"
    assert _manifest("quantum-raspberry-tie")["install"]["installed_flag"] == "QUANTUM_RASPBERRY_TIE_INSTALLED"


def test_icons_in_a_terminal_keep_their_window_on_failure():
    d = os.path.join(_CFG, "desktop-bookmarks")
    for name in sorted(os.listdir(d)):
        text = open(os.path.join(d, name)).read()
        if "\nTerminal=true" not in text:
            continue
        exec_line = [line for line in text.splitlines() if line.startswith("Exec=")][0]
        # -t "Title": the window's title instead of the command line (R-135)
        assert re.match(r'Exec=/usr/bin/rq_hold_on_error\.sh (-t "[^"]+" )?/usr/bin/', exec_line), \
            (name, exec_line)


@pytest.mark.parametrize("icon,demo", [("doqumentation", "doqumentation"),
                                       ("qoffee-maker", "qoffee-maker"),
                                       ("quantum-mixer", "quantum-mixer")])
def test_docker_icons_go_through_the_engine(icon, demo):
    # so their first start asks, like every other demo (Q27)
    text = open(os.path.join(_CFG, "desktop-bookmarks", f"{icon}.desktop")).read()
    assert f"Exec=/usr/bin/rq_hold_on_error.sh /usr/bin/rq_demo_run.sh {demo}\n" in text


# --- Remove a demo -----------------------------------------------------------

def test_remove_lists_and_removes_a_checkout(box):
    d = box.home / "RasQberry-Two" / "demos" / "quantum-paradoxes"
    d.mkdir()
    (d / "WELCOME.ipynb").write_text("x" * 2_000_000)
    with open(box.env_file, "a") as fh:
        fh.write("QUANTUM_PARADOXES_INSTALLED=true\n")
    proc = box(_REMOVE, ["--list"])
    assert proc.returncode == 0, proc.stderr
    assert "quantum-paradoxes\t2\tQuantum Paradoxes" in proc.stdout
    proc = box(_REMOVE, ["quantum-paradoxes", "--yes"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not d.exists()
    flags = [line for line in box.env_file.read_text().splitlines()
             if line.startswith("QUANTUM_PARADOXES_INSTALLED=")]
    assert flags[-1] == "QUANTUM_PARADOXES_INSTALLED=false"


def test_ibm_tutorials_and_courses_are_one_entry(box):
    d = box.home / "RasQberry-Two" / "demos" / "ibm-quantum-learning"
    d.mkdir()
    (d / "x").write_text("x")
    proc = box(_REMOVE, ["--list"])
    lines = [line for line in proc.stdout.splitlines() if "IBM" in line]
    assert len(lines) == 1, proc.stdout
    assert "IBM Quantum Courses" in lines[0] and "IBM Quantum Tutorials" in lines[0]


def test_remove_takes_the_docker_image(box, tmp_path):
    log = tmp_path / "docker.log"
    _exe(box.stubs / "docker", f'#!/bin/sh\necho "$*" >> "{log}"\n'
         'case "$1 $2" in "info "*) exit 0 ;; "image inspect") case " $* " in *" -f "*) echo 3910000000 ;; esac; exit 0 ;; esac\nexit 0\n')
    proc = box(_REMOVE, ["--list"])
    assert "quantum-lab\t3910\tQuantum Lab (QuBins)" in proc.stdout, proc.stdout + proc.stderr
    proc = box(_REMOVE, ["quantum-lab", "--yes"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    # the pinned image (by digest, Jan Q8)
    assert "rmi ghcr.io/qubins/images@sha256:" in log.read_text()


# --- R-121 ------------------------------------------------------------------

def test_report_is_saved_in_the_home(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), RQ_BUILD_JSON=str(tmp_path / "none.json"))
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_info.sh"), "--report"],
                          capture_output=True, text=True, env=env, timeout=120)
    assert proc.returncode == 0, proc.stderr
    files = [p for p in os.listdir(tmp_path) if p.startswith("rasqberry-report-")]
    assert len(files) == 1 and "Saved:" in proc.stdout
    text = open(tmp_path / files[0]).read()
    assert "===== System =====" in text and "===== Disk =====" in text
