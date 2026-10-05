"""
Tests for rq_docker_demos.sh, the menu's "Stop Docker demos" (#2 of the
2026-10-05 user test):

- it finds the running demo containers by label and by their known names,
  also when the last known name (quantum-mixer) is not running: that ended
  the entry silently with status 1 (set -e with pipefail);
- it always says what it did: "No Docker demo is running.", "Stopped: ...",
  "Nothing was stopped." or which container is still stopping.
"""

import os
import shutil
import stat
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_BIN = os.path.abspath(os.path.join(_HERE, "..", "..", "RQB2-bin"))

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required")

# Containers are files in $STATE: NAME (running), NAME.label (carries the
# org.rasqberry.demo label), NAME.stuck (does not go away)
_DOCKER = r'''#!/bin/sh
echo "$*" >> "$DOCKER_LOG"
case "$1" in
  ps) for f in "$STATE"/*.label; do [ -e "$f" ] && basename "$f" .label; done; exit 0 ;;
  container)
    if [ "$3" = -f ]; then [ -e "$STATE/$5" ] && echo true; exit 0; fi
    [ -e "$STATE/$3" ]; exit $? ;;
  stop) n="$2" ;;
  rm) n="$3" ;;
  *) exit 0 ;;
esac
[ -e "$STATE/$n.stuck" ] || rm -f "$STATE/$n" "$STATE/$n.label"
exit 0
'''

# whiptail: logs each call; a checklist answers $WT_CHOICE (on stderr, as
# whiptail does) with status $WT_RC
_WHIPTAIL = r'''#!/bin/sh
printf '%s\n' "$*" >> "$WT_LOG"
case "$*" in
  *--checklist*) printf '%s' "$WT_CHOICE" >&2; exit "${WT_RC:-0}" ;;
esac
exit 0
'''


def _exe(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def stop(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    _exe(stubs / "docker", _DOCKER)
    _exe(stubs / "whiptail", _WHIPTAIL)
    _exe(stubs / "id", '#!/bin/sh\n[ "$1" = "-u" ] && echo 0 || echo root\n')   # the menu runs as root
    _exe(stubs / "sleep", "#!/bin/sh\nexit 0\n")
    wt_log = tmp_path / "whiptail.log"
    docker_log = tmp_path / "docker.log"

    def run(args, running=(), labelled=(), stuck=(), choice="", wt_rc=0):
        for name in running:
            (state / name).write_text("")
        for name in labelled:
            (state / (name + ".label")).write_text("")
        for name in stuck:
            (state / (name + ".stuck")).write_text("")
        env = {"PATH": f"{stubs}:{os.environ['PATH']}", "HOME": str(tmp_path), "STATE": str(state),
               "DOCKER_LOG": str(docker_log), "WT_LOG": str(wt_log), "WT_CHOICE": choice,
               "WT_RC": str(wt_rc)}
        proc = subprocess.run(["bash", os.path.join(_BIN, "rq_docker_demos.sh"), *args],
                              capture_output=True, text=True, env=env, timeout=60,
                              stdin=subprocess.DEVNULL)
        calls = wt_log.read_text() if wt_log.exists() else ""
        return proc, calls, (docker_log.read_text() if docker_log.exists() else "")
    return run


def _msgbox(calls):
    boxes = [line for line in calls.splitlines() if "--msgbox" in line]
    assert len(boxes) == 1, calls
    return boxes[0]


def test_list_finds_the_workshop_server_without_the_mixer(stop):
    # the reported case: only the Workshop server runs (no quantum-mixer)
    proc, _, _ = stop(["--list"], running=["doqumentation"], labelled=["doqumentation"])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.split() == ["doqumentation"]


def test_list_finds_containers_by_name_and_by_label(stop):
    proc, _, _ = stop(["--list"], running=["quantum-lab", "traqmania"], labelled=["traqmania"])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.split() == ["quantum-lab", "traqmania"]


def test_stop_menu_says_when_nothing_runs(stop):
    proc, calls, _ = stop(["--stop-menu"])
    assert proc.returncode == 0, proc.stderr
    assert "No Docker demo is running." in _msgbox(calls)
    assert "--checklist" not in calls


def test_stop_menu_stops_the_chosen_ones_and_says_so(stop):
    names = ["doqumentation", "quantum-lab", "quantum-mixer"]
    proc, calls, docker = stop(["--stop-menu"], running=names, labelled=names,
                               choice='"doqumentation" "quantum-lab" "quantum-mixer"')
    assert proc.returncode == 0, proc.stderr
    checklist = [line for line in calls.splitlines() if "--checklist" in line][0]
    for label in ("Workshop & Qiskit Server", "Quantum Lab (QuBins)", "Quantum Mixer"):
        assert label in checklist
    for name in names:
        assert f"stop {name}" in docker
    assert ("Stopped: Workshop & Qiskit Server / Qiskit Tutorials, Quantum Lab (QuBins), "
            "Quantum Mixer.") in _msgbox(calls)


def test_stop_menu_with_nothing_ticked_says_so(stop):
    proc, calls, docker = stop(["--stop-menu"], running=["doqumentation"], choice="")
    assert proc.returncode == 0, proc.stderr
    assert "Nothing was stopped." in _msgbox(calls)
    assert "stop doqumentation" not in docker


def test_stop_menu_names_a_container_that_does_not_go(stop):
    proc, calls, _ = stop(["--stop-menu"], running=["doqumentation", "qoffee"], stuck=["qoffee"],
                          choice='"doqumentation" "qoffee"')
    assert proc.returncode == 0, proc.stderr
    box = _msgbox(calls)
    assert "Stopped: Workshop & Qiskit Server / Qiskit Tutorials." in box
    assert "Still stopping: Qoffee-Maker. Try again in a minute." in box


def test_stop_menu_cancel_stops_nothing(stop):
    proc, calls, docker = stop(["--stop-menu"], running=["doqumentation"], wt_rc=1)
    assert proc.returncode == 0, proc.stderr
    assert "stop doqumentation" not in docker
    assert "--msgbox" not in calls
