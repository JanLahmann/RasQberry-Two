"""
Tests for fix batch B9 (classroom, Workshop & Qiskit Server, Docker demos, IBM accounts):

- every downloaded demo is pinned per release (git commit or image digest),
  and "Update demos" choices hold only while the release keeps its pin (Q8/Q32);
- rq_image_versions.py lists the newer image builds, newest first;
- doQumentation attaches to a running Workshop & Qiskit Server instead of
  restarting it (R-069, R-145) and starts headless over SSH with an ssh -L
  hint (Q19); its single-user mode "Qiskit Tutorials on this Pi" binds
  127.0.0.1 only, without the picker (items 6, 25);
- the credentials notebook saves strings, not tuples (R-064).
"""

import ast
import importlib.util
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from contextlib import redirect_stdout

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_MANIFESTS = os.path.join(_CFG, "demo-manifests")
_COMMON = os.path.join(_BIN, "rq_common.sh")

needs_bash = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required")


def _manifest(demo_id):
    with open(os.path.join(_MANIFESTS, f"rq_demo_{demo_id}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _exe(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


# --- pins (Q8/Q32) ------------------------------------------------------------

def test_every_downloaded_demo_is_pinned():
    for name in sorted(os.listdir(_MANIFESTS)):
        if not name.startswith("rq_demo_") or "schema" in name:
            continue
        m = _manifest(name[len("rq_demo_"):-len(".json")])
        inst = m.get("install", {})
        if inst.get("preinstalled"):
            continue
        if inst.get("repo_url"):
            assert re.fullmatch(r"[0-9a-f]{40}", inst.get("ref", "")), m["id"]
        if "source" in inst:
            assert re.fullmatch(r"[0-9a-f]{40}", inst["source"]["ref"]), m["id"]
        ep = m["entrypoint"]
        if ep.get("type") == "docker":
            assert re.search(r"@sha256:[0-9a-f]{64}$|:[0-9a-f]{40}$", ep["docker_image"]), m["id"]
            assert inst.get("update", {}).get("docker_tags"), m["id"]


def test_mixer_image_is_the_build_of_its_pinned_source():
    # built by the quantum-mixer repository's CI, tagged with the commit
    m = _manifest("quantum-mixer")
    assert m["entrypoint"]["docker_image"] == \
        "ghcr.io/janlahmann/quantum-mixer:" + m["install"]["source"]["ref"]


@needs_bash
def test_chosen_version_holds_only_while_the_release_keeps_its_pin(tmp_path):
    home = tmp_path / "home"
    (home / "RasQberry-Two" / "demos").mkdir(parents=True)
    pin = _manifest("doqumentation")["entrypoint"]["docker_image"]
    script = f'''
        . "{_COMMON}"
        USER_HOME="{home}"; REPO=RasQberry-Two
        echo "A $(rq_demo_image doqumentation)"
        rq_demo_set_version doqumentation:image "{pin}" "ghcr.io/x/doq@sha256:new" "new, 2026-10-02"
        echo "B $(rq_demo_image doqumentation)"
        echo "L $(rq_demo_chosen_label doqumentation:image)"
        rq_demo_set_version doqumentation:image "sha-of-an-older-release" "ghcr.io/x/doq@sha256:new" "x"
        echo "C $(rq_demo_image doqumentation)"
        rq_demo_set_version fun-with-quantum:ref "$(jq -r .install.ref "{_MANIFESTS}/rq_demo_fun-with-quantum.json")" abc "abc"
        echo "D $(rq_demo_ref fun-with-quantum)"
        echo "E $(rq_demo_ref qoffee-maker) $(rq_demo_repo qoffee-maker)"
        rq_demo_set_version fun-with-quantum:ref x ""
        echo "F $(wc -l < "$(rq_demo_versions_file)")"
    '''
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60).stdout
    lines = dict(line.split(" ", 1) for line in out.splitlines() if " " in line)
    assert lines["A"] == pin
    assert lines["B"] == "ghcr.io/x/doq@sha256:new"
    assert lines["L"] == "new, 2026-10-02"
    assert lines["C"] == pin                  # a newer release pin wins
    assert lines["D"] == "abc"
    qoffee = _manifest("qoffee-maker")["install"]["source"]
    assert lines["E"] == f"{qoffee['ref']} {qoffee['repo_url']}"
    assert lines["F"].strip() == "1"          # only the doQumentation line left


# --- rq_image_versions.py -----------------------------------------------------

def _versions_module():
    spec = importlib.util.spec_from_file_location("rq_image_versions",
                                                  os.path.join(_BIN, "rq_image_versions.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_versions(monkeypatch, facts, tags, argv):
    mod = _versions_module()

    class FakeRegistry:
        def __init__(self, repo):
            self.repo = repo

        def tags(self):
            return tags

    monkeypatch.setattr(mod, "Registry", FakeRegistry)
    monkeypatch.setattr(mod, "describe", lambda reg, ref, arch: facts.get(ref))
    monkeypatch.setattr(sys, "argv", ["rq_image_versions.py", *argv])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = mod.main()
    return rc, [line.split("\t") for line in buf.getvalue().splitlines()]


def _fact(digest, created, mb=100, note=""):
    return {"digest": digest, "created": created, "download_mb": mb, "note": note}


def test_versions_newest_first_with_latest_and_in_between(monkeypatch):
    facts = {
        "sha256:cur": _fact("sha256:cur", "2026-07-13T00:00:00Z"),
        "aaaaaaa-jupyter": _fact("sha256:a", "2026-09-01T00:00:00Z"),
        "bbbbbbb-jupyter": _fact("sha256:b", "2026-10-02T00:00:00Z", 1260, "Qiskit 2.5.2"),
        "ccccccc-jupyter": _fact("sha256:c", "2026-06-01T00:00:00Z"),   # older: not offered
        "jupyter": _fact("sha256:b", "2026-10-02T00:00:00Z", 1260, "Qiskit 2.5.2"),
    }
    rc, rows = _run_versions(monkeypatch, facts,
                             ["aaaaaaa-jupyter", "bbbbbbb-jupyter", "ccccccc-jupyter", "jupyter", "x"],
                             ["ghcr.io/janlahmann/doqumentation@sha256:cur",
                              "--tags", "^[0-9a-f]{7}-jupyter$", "--latest", "jupyter"])
    assert rc == 0
    assert [r[0].split("@")[1] for r in rows] == ["sha256:b", "sha256:a", "sha256:cur"]
    assert rows[0][1] == "jupyter (latest), bbbbbbb-jupyter"
    assert rows[0][2:] == ["2026-10-02", "1260", "Qiskit 2.5.2", "newer"]
    assert rows[-1][-1] == "current"


def test_versions_same_build_date_ordered_by_version(monkeypatch):
    # QuBins builds every tag with one timestamp
    t = "2026-09-12T10:29:18Z"
    facts = {"2.4-xl": _fact("sha256:24", t), "2.5-xl": _fact("sha256:25", t),
             "latest-xl": _fact("sha256:25", t), "1.4-xl": _fact("sha256:14", t)}
    rc, rows = _run_versions(monkeypatch, facts, ["1.4-xl", "2.4-xl", "2.5-xl"],
                             ["ghcr.io/qubins/images:2.4-xl", "--tags", r"^[0-9]+\.[0-9]+-xl$",
                              "--latest", "latest-xl"])
    assert rc == 0
    assert [(r[1], r[-1]) for r in rows] == [("latest-xl (latest), 2.5-xl", "newer"),
                                             ("2.4-xl", "current")]


def test_versions_refuses_other_registries(monkeypatch):
    rc, rows = _run_versions(monkeypatch, {}, [], ["docker.io/library/python:3", "--tags", "."])
    assert rc == 3 and rows == []


# --- doQumentation: attach, headless start (R-069, R-145, Q19) ---------------

_DOCKER = r'''#!/bin/sh
echo "$*" >> "$DOCKER_LOG"
case "$*" in
  "ps") exit 0 ;;
  "container inspect -f {{.State.Running}} doqumentation") [ -n "$RUNNING" ] && echo true; [ -n "$RUNNING" ] ;;
  "container inspect -f {{range .Config.Env}}{{println .}}{{end}} doqumentation") echo JUPYTER_TOKEN=tok123 ;;
  "container inspect -f {{.Config.Image}} doqumentation") echo "$PINNED" ;;
  "container inspect -f {{index .Config.Labels \"org.rasqberry.mode\"}} doqumentation") echo "$CONTAINER_MODE" ;;
  "container inspect doqumentation") exit 1 ;;
  "port doqumentation 80/tcp") [ "$CONTAINER_MODE" = solo ] && echo 127.0.0.1:8080 || echo 0.0.0.0:8080 ;;
  "port doqumentation 8888/tcp") echo 127.0.0.1:8896 ;;
  "image inspect"*) exit 0 ;;
  run*) echo cid ;;
  *) exit 0 ;;
esac
'''


@pytest.fixture
def doq(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _exe(stubs / "docker", _DOCKER)
    _exe(stubs / "id", '#!/bin/sh\ncase "$1" in -u) echo 1000 ;; -nG) echo "rasqberry docker" ;; *) echo 1000 ;; esac\n')
    _exe(stubs / "hostname", '#!/bin/sh\n[ "$1" = "-I" ] && echo "192.168.1.5 fe80::1" || echo rasqberry\n')
    _exe(stubs / "ss", "#!/bin/sh\nexit 0\n")
    _exe(stubs / "ip", "#!/bin/sh\necho '3: wlan0    inet 192.168.1.5/24 brd 192.168.1.255 scope global wlan0'\n"
                       "echo '4: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0'\n")
    _exe(stubs / "curl", "#!/bin/sh\nexit 0\n")
    _exe(stubs / "whiptail", "#!/bin/sh\nexit 0\n")
    home = tmp_path / "home"
    home.mkdir()
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(f'USER_HOME="{home}"\nREPO=RasQberry-Two\nBIN_DIR="{_BIN}"\nSTD_VENV=RQB2\n')
    log = tmp_path / "docker.log"

    def run(running, args=(), mode=""):
        env = {"PATH": f"{stubs}:{os.environ['PATH']}", "HOME": str(home), "USER": "rasqberry",
               "RQ_CONFIG_FILE": str(env_config), "DOCKER_LOG": str(log),
               "RUNNING": "1" if running else "", "CONTAINER_MODE": mode,
               "PINNED": _manifest("doqumentation")["entrypoint"]["docker_image"]}
        proc = subprocess.run(["bash", os.path.join(_BIN, "rq_doqumentation.sh"), *args],
                              capture_output=True, text=True, env=env, timeout=120,
                              stdin=subprocess.DEVNULL)
        return proc, (log.read_text() if log.exists() else "")
    return run


@needs_bash
def test_reopening_attaches_to_the_running_server(doq):
    proc, calls = doq(running=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "http://rasqberry.local:8080/" in proc.stdout
    assert "http://192.168.1.5:8080/" in proc.stdout and "172.17.0.1" not in proc.stdout
    assert "token=tok123" in proc.stdout
    assert "Anyone on this network can open these addresses and run code on this Pi." in proc.stdout
    assert "Restarting the server restores the" in proc.stdout
    # nothing was stopped, removed or started
    assert not re.search(r"^(stop|rm|run) ", calls, re.M), calls


@needs_bash
def test_headless_start_prints_the_addresses_and_a_tunnel(doq):
    proc, calls = doq(running=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    run = [c for c in calls.splitlines() if c.startswith("run ")]
    assert len(run) == 1
    pinned = _manifest("doqumentation")["entrypoint"]["docker_image"]
    assert run[0].endswith(pinned) and "@sha256:" in pinned
    assert "-p 127.0.0.1:8896:8888" in run[0]          # JupyterLab: teacher only
    assert "--rm" not in run[0]                         # logs survive a crash (R-109)
    assert "CORS_ORIGIN=http://localhost:8080" in run[0] and "http://192.168.1.5:8080" in run[0]
    assert "ssh -N -L 8080:127.0.0.1:8080 rasqberry@rasqberry.local" in proc.stdout
    assert "keeps running" in proc.stdout
    # the menu's way to stop it, not a Docker command (R-094)
    assert "Stop Docker demos" in proc.stdout + proc.stderr
    assert "docker stop" not in proc.stdout + proc.stderr
    # code runs only with the internet for now (R-068, doQumentation#964)
    assert "Running code needs the internet for now" in proc.stdout


@needs_bash
def test_qr_code_comes_last_and_fits_an_80x24_window(doq, tmp_path):
    # qrencode is the command (package qrencode), not just the library: a
    # version-2 code with margin 2 is 29 columns by 15 lines
    qr = "\n".join(["#" * 29] * 15)
    args = tmp_path / "qrencode.args"
    _exe(tmp_path / "stubs" / "qrencode", f'#!/bin/sh\necho "$*" > "{args}"\nprintf "%s\\n" "{qr}"\n')
    proc, _calls = doq(running=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert args.read_text().strip() == "-t ANSIUTF8 -m 2 http://192.168.1.5:8080/"
    out = proc.stdout.splitlines()
    caption = out.index("Participants can also scan this code: http://192.168.1.5:8080/")
    # last, after the notes and the browser (or ssh -L) hint: the code and the
    # lines after it fit a 24-line window
    assert caption > max(i for i, line in enumerate(out) if "ssh -N -L" in line or "Open in Lab" in line)
    assert len(out) - caption <= 20
    assert all(len(line) <= 80 for line in out[caption:])
    # a fresh start, too; not in solo mode
    proc, _calls = doq(running=False)
    assert "Participants can also scan this code" in proc.stdout
    proc, _calls = doq(running=True, args=["--solo"], mode="solo")
    assert "scan this code" not in proc.stdout


@needs_bash
def test_solo_mode_is_for_this_pi_only(doq):
    proc, calls = doq(running=False, args=["--solo"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    run = [c for c in calls.splitlines() if c.startswith("run ")]
    assert len(run) == 1
    assert "-p 127.0.0.1:8080:80" in run[0] and "-p 8080:80" not in run[0]
    assert "--label org.rasqberry.mode=solo" in run[0]
    assert "--memory 3072m" in run[0] or "--memory " in run[0]
    # localhost only: no LAN address may call the Jupyter API
    assert "192.168.1.5" not in run[0] and "rasqberry.local" not in run[0]
    assert "Qiskit Tutorials on this Pi is running: http://localhost:8080/" in proc.stdout
    assert "Participants" not in proc.stdout
    assert "needs the internet for now" in proc.stdout


@needs_bash
def test_workshop_mode_is_labelled(doq):
    proc, calls = doq(running=False)
    run = [c for c in calls.splitlines() if c.startswith("run ")][0]
    assert "--label org.rasqberry.mode=workshop" in run and "-p 8080:80" in run


@needs_bash
def test_solo_attaches_to_a_running_workshop_server(doq):
    # opened as "Qiskit Tutorials" while the group server runs: keep it, open it
    proc, calls = doq(running=True, args=["--solo"], mode="workshop")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Workshop & Qiskit Server is running." in proc.stdout
    assert not re.search(r"^(stop|rm|run) ", calls, re.M), calls


@needs_bash
def test_reopening_a_solo_server_shows_no_addresses(doq):
    proc, calls = doq(running=True, args=["--solo"], mode="solo")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Qiskit Tutorials on this Pi is running" in proc.stdout
    assert "192.168.1.5" not in proc.stdout
    assert not re.search(r"^(stop|rm|run) ", calls, re.M), calls


def test_solo_entry_runs_the_launcher_in_solo_mode():
    m = _manifest("qiskit-tutorials")
    assert m["name"] == "Qiskit Tutorials on this Pi"
    assert m["entrypoint"] == {"launcher": "rq_doqumentation.sh", "args": ["--solo"]}
    assert _manifest("doqumentation")["name"] == "Workshop & Qiskit Server"
    # next to each other in the menu
    assert abs(m["menu"]["order"] - _manifest("doqumentation")["menu"]["order"]) <= 5


# --- texts and small fixes ----------------------------------------------------

def test_credentials_notebook_saves_strings():
    nb = json.load(open(os.path.join(_CFG, "00-Save-Credentials.ipynb"), encoding="utf-8"))
    code = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") in ("token", "instance"):
            assert not isinstance(node.value, ast.Tuple), "trailing comma makes a tuple (R-064)"
    assert 'channel="ibm_quantum_platform"' in code and "delete_account" in code


def test_menu_entries():
    menu = open(os.path.join(_CFG, "RQB2_menu.sh")).read()
    assert 'UPD  "Update demos' in menu and "rq_demo_update.sh" in menu
    assert 'DSTP "Stop Docker demos' in menu and "QSTP" not in menu and "QMXS" not in menu
    assert 'SAVE   "Save my API key (checked first)"' in menu
    assert "rq_set_qiskit_ibm_token.py" in menu


def test_quantum_lab_keeps_work_and_its_port():
    lab = open(os.path.join(_BIN, "rq_quantum_lab.sh")).read()
    assert '-v "$WORK_DIR":/home/jovyan/my-work' in lab
    assert 'PORT="${QUANTUM_LAB_PORT:-8892}"' in lab
    assert "--rm" not in lab


def test_demo_loop_cleanup_runs_once():
    loop = open(os.path.join(_BIN, "rq_demo_loop.sh")).read()
    body = loop[loop.index("cleanup() {"):]
    assert body.index("trap - EXIT INT TERM") < body.index("Demo loop stopped")
