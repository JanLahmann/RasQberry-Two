"""
Ctrl+C during a Docker download is the user's stop, not a failure (user test
2026-10-08): it said "ERROR: Could not download ...: docker pull failed" and
"The demo stopped with an error (status 1)" with the bug-report line.

Now rq_docker_pull says "Download stopped. Nothing was installed; the next
start asks again." and ends with 130, which the icon's window, the menu and
the group lists take as a stop; the Mixer (its own pull, in a subshell) and
the engine's installer path pass the 130 on instead of "Installation failed"
or the build-on-this-Pi question. Also: Quantum Mixer pulls its pinned digest
through rq_demo_docker_pull, with the commit tag as the fallback.

docker is a stub; Ctrl+C is a SIGINT the stub sends to the shell that runs
the pull (as the terminal sends it to the whole foreground group).
"""

import json
import os
import subprocess

import pytest

from test_demo_consent import box, _exe, _common  # noqa: F401
from test_docker_pin_fallback import _docker, _GONE

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_MIXER = os.path.join(_BIN, "quantum-mixer.sh")
_HOLD = os.path.join(_BIN, "rq_hold_on_error.sh")
_STOPPED = "Download stopped. Nothing was installed; the next start asks again."


def _mixer_manifest():
    with open(os.path.join(_ROOT, "RQB2-config", "demo-manifests", "rq_demo_quantum-mixer.json")) as f:
        return json.load(f)


def _ctrl_c_docker(box, how):
    """
    A docker stub whose pull is stopped with Ctrl+C. HOW: "rc1" (docker
    ends with 1, "context canceled"), "rc130", or "signal" (docker dies of
    the SIGINT itself). The shell running the pull gets the SIGINT too.
    """
    log = box.tmp / "docker.log"
    end = {"rc1": 'echo "context canceled" >&2; exit 1',
           "rc130": "exit 130",
           "signal": "trap - INT; kill -INT $$; sleep 1; exit 99"}[how]
    _exe(box.stubs / "docker", f'''#!/bin/bash
echo "$*" >> "{log}"
case "$1 $2" in
  "info "*|"ps "*) exit 0 ;;
  "image inspect"|"container inspect") exit 1 ;;
  "images -q") exit 0 ;;
esac
if [ "$1" = pull ]; then
  kill -INT $PPID
  sleep 0.3
  {end}
fi
exit 0
''')
    # the desktop user is in the docker group
    real_id = subprocess.run(["bash", "-c", "command -v id"], capture_output=True, text=True).stdout.strip()
    _exe(box.stubs / "id", f'#!/bin/sh\n[ "$1" = "-nG" ] && {{ echo "users docker"; exit 0; }}\nexec {real_id} "$@"\n')
    return log


@pytest.mark.parametrize("how", ["rc1", "rc130", "signal"])
def test_ctrl_c_during_a_download_is_a_quiet_stop(box, how):
    _ctrl_c_docker(box, how)
    proc = _common(box, 'rq_docker_pull ghcr.io/x/demo@sha256:1 "Demo X" 500 ghcr.io/x/demo:1.0; echo AFTER')
    out = proc.stdout + proc.stderr
    assert proc.returncode == 130, out
    assert _STOPPED in proc.stdout, out
    assert "AFTER" not in out
    assert "ERROR" not in out and "Could not download" not in out and "failed" not in out
    # no reason for the menu's error box, and no fallback after a stop
    assert box.err() == ""
    assert "ghcr.io/x/demo:1.0" not in (box.tmp / "docker.log").read_text()


def test_ctrl_c_in_a_terminal_ends_the_progress_line_with_stopped(box, tmp_path):
    import pty
    import threading
    _ctrl_c_docker(box, "rc1")
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
    env = dict(os.environ, PATH=f"{box.stubs}:{os.environ['PATH']}")
    proc = subprocess.run(["bash", "-c", f'. "{_BIN}/rq_common.sh"; rq_docker_pull ghcr.io/x/demo:1 "Demo X" 500'],
                          stdin=slave, stdout=slave, stderr=slave, env=env, timeout=60)
    os.close(slave)
    reader.join(5)
    os.close(master)
    text = b"".join(out).decode("utf-8", "replace")
    assert proc.returncode == 130, text
    assert "Downloading Demo X ... stopped" in text and _STOPPED in text, repr(text)
    assert "failed" not in text


def test_a_callers_ctrl_c_trap_comes_back_after_the_pull(box):
    _docker(box, "")
    proc = _common(box, "trap 'echo CALLER' INT; rq_docker_pull ghcr.io/x/demo:1 X; trap -p INT")
    assert "echo CALLER" in proc.stdout, proc.stdout + proc.stderr
    proc = _common(box, "rq_docker_pull ghcr.io/x/demo:1 X; echo \"[$(trap -p INT)]\"")
    assert "[]" in proc.stdout, proc.stdout + proc.stderr


def test_a_real_failure_still_says_why(box):
    _docker(box, "Error response from daemon: Get \"https://ghcr.io/v2/\": dial tcp: lookup ghcr.io: no such host")
    proc = _common(box, 'rq_docker_pull ghcr.io/x/demo@sha256:1 "Demo X"')
    assert proc.returncode == 1 and "Could not download Demo X" in proc.stderr
    assert _STOPPED not in proc.stdout


def test_the_icon_window_closes_quietly_after_the_stop(box):
    _ctrl_c_docker(box, "rc1")
    script = os.path.join(box.tmp, "pull.sh")
    _exe(box.tmp / "pull.sh", f'#!/bin/bash\n. "{_BIN}/rq_common.sh"\nrq_docker_pull ghcr.io/x/demo:1 "Demo X"\n')
    proc = box([_HOLD, script])
    assert proc.returncode == 130, proc.stdout + proc.stderr
    assert "stopped with an error" not in proc.stdout and "rq_info.sh --report" not in proc.stdout


# --- Quantum Mixer ------------------------------------------------------------

def _run_mixer(box, extra=None):
    env = {"RQ_AUTO_INSTALL": "1", "RQ_DEMO_CONSENT": "yes", "QUANTUM_MIXER_PORT": "8085"}
    env.update(extra or {})
    return box([_MIXER], extra=env)


def test_ctrl_c_during_the_mixer_download_is_a_stop_not_a_build(box):
    log = _ctrl_c_docker(box, "rc1")
    proc = _run_mixer(box)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 130, out
    assert _STOPPED in proc.stdout, out
    assert "not available on ghcr.io" not in out and "Build" not in out
    assert box.err() == "" and box.dialogs() == []
    calls = log.read_text()
    assert "build" not in calls and "run -d" not in calls
    assert "QUANTUM_MIXER_INSTALLED=true" not in box.env_file.read_text()


def _mixer_docker(box, pull_error):
    log = _docker(box, pull_error)
    real_id = subprocess.run(["bash", "-c", "command -v id"], capture_output=True, text=True).stdout.strip()
    _exe(box.stubs / "id", f'#!/bin/sh\n[ "$1" = "-nG" ] && {{ echo "users docker"; exit 0; }}\nexec {real_id} "$@"\n')
    return log


def test_the_mixer_downloads_its_pinned_digest(box):
    ep = _mixer_manifest()["entrypoint"]
    log = _mixer_docker(box, "")
    proc = _run_mixer(box)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    calls = log.read_text()
    assert f"pull -q {ep['docker_image']}" in calls
    assert ep["docker_image_fallback"] not in calls
    run = [c for c in calls.splitlines() if c.startswith("run ")]
    assert run and run[0].endswith(ep["docker_image"]), run


def test_the_mixer_takes_the_commit_tag_when_the_digest_is_gone(box):
    ep = _mixer_manifest()["entrypoint"]
    log = _mixer_docker(box, _GONE)
    proc = _run_mixer(box)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    calls = log.read_text()
    assert f"pull -q {ep['docker_image_fallback']}" in calls
    run = [c for c in calls.splitlines() if c.startswith("run ")]
    assert run and run[0].endswith(ep["docker_image_fallback"]), run
    assert "build" not in calls


# --- the engine's installer path and "Update demos" -------------------------------

def test_the_engine_passes_a_stopped_install_on():
    with open(os.path.join(_BIN, "rq_demo_run.sh")) as f:
        engine = f.read()
    part = engine[engine.index('install_demo_raspiconfig "$installer" || irc=$?'):]
    part = part[:part.index("return 0")]
    assert "129|130|143) exit \"$irc\"" in part
    with open(os.path.join(_BIN, "rq_common.sh")) as f:
        common = f.read()
    fn = common[common.index("install_demo_raspiconfig() {"):]
    fn = fn[:fn.index("\n}\n")]
    assert '129|130|143) return "$rc"' in fn


def test_update_demos_says_a_stopped_download_changed_nothing():
    with open(os.path.join(_BIN, "rq_demo_update.sh")) as f:
        text = f.read()
    assert 'Download stopped. $name keeps the version in use.' in text
