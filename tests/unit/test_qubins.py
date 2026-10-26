"""
QuBins (beta): one demo that lets you choose the QuBins image (Qiskit version,
xl or small) and the notebooks to put into the lab.

  * rq_qubins.py images: the monthly snapshots from the registry (a fixture
    of ghcr.io's answers, no network), the tested image first and marked,
    downloaded and in-use marks, offline: the cached list or the tested image;
  * rq_qubins.py last/remember: the choices kept for "Start with last settings";
  * rq_qubins.py mounts: my-work writable, the chosen content read-only at
    the same paths, only the chosen part of the shared IBM checkout;
  * rq_qubins.sh end to end with stub tools: choose, download, run; the next
    start with the last settings; the engine does not download the tested
    image before the choice;
  * the manifest: valid, beta, pinned like Qiskit Live, icon and menu entry.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time

import pytest

from test_demo_consent import box, _exe  # noqa: F401

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_MANIFESTS = os.path.join(_CFG, "demo-manifests")
_HELPER = os.path.join(_BIN, "rq_qubins.py")
_LAUNCHER = os.path.join(_BIN, "rq_qubins.sh")
_ENGINE = os.path.join(_BIN, "rq_demo_run.sh")
_FIXTURE = os.path.join(_HERE, "data", "qubins_registry.json")

_PIN = "ghcr.io/qubins/images@sha256:dd8f4f727fe450c9a13c8eb1404e5c471274f28f91be8bdf1fac14436ff33a48"
_PIN_TAG = "2.5-xl-20261008"


def _load():
    spec = importlib.util.spec_from_file_location("rq_qubins", _HELPER)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, _BIN)
    spec.loader.exec_module(mod)
    return mod


qb = _load()


def _manifest(demo_id):
    with open(os.path.join(_MANIFESTS, f"rq_demo_{demo_id}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _fixture_ref(tag):
    with open(_FIXTURE, encoding="utf-8") as fh:
        return "ghcr.io/qubins/images@" + json.load(fh)["manifests"][tag]["digest"]


def _images(*args, registry=_FIXTURE):
    env = dict(os.environ, RQ_QUBINS_REGISTRY_FILE=registry)
    proc = subprocess.run([sys.executable, _HELPER, "images", "--pin", _PIN, "--pin-tag", _PIN_TAG,
                           "--pin-mb", "890", *args], capture_output=True, text=True, env=env,
                          timeout=60)
    rows = [line.split("\t") for line in proc.stdout.splitlines()]
    return proc, rows


# --- the image list -----------------------------------------------------------

def test_only_the_newest_snapshot_per_version_and_variant():
    tags = ["2.6-xl", "2.6-xl-20261020", "2.6-small-20261020", "2.6-xxl-20261020",
            "2.5-xl-20260908", "2.5-xl-20261008", "2.5-small-20261008",
            "2.4-xl-20261008", "2.3-xl-20261008", "2.2-xl-20261008",
            "2.1-xl-rise-20261008", "2.6-xl-arm64", "latest-xl", "1.4-xl"]
    got = qb.snapshot_candidates(tags, minors=4)
    # newest Qiskit first, xl before small; no moving tag, xxl, rise or 2.2
    assert got == ["2.6-xl-20261020", "2.6-small-20261020", "2.5-xl-20261008",
                   "2.5-small-20261008", "2.4-xl-20261008", "2.3-xl-20261008"]
    assert qb.snapshot_candidates(tags, minors=1) == ["2.6-xl-20261020", "2.6-small-20261020"]
    assert qb.parse_tag("2.6-xl") is None and qb.parse_tag("2.1-xl-rise-20261008")[2] == "xl-rise"


def test_the_list_from_the_registry_fixture():
    proc, rows = _images("--local", _PIN.split("@")[1])
    assert proc.returncode == 0, proc.stderr
    # REF TAG QISKIT VARIANT DATE MB MARKS
    assert all(len(r) == 7 for r in rows)
    assert rows[0] == [_PIN, _PIN_TAG, "2.5.2", "xl", "2026-10-08", "887", "tested,downloaded"]
    assert [r[1] for r in rows[1:]] == ["2.6-xl-20261020", "2.6-small-20261020", "2.5-small-20261008",
                                        "2.4-xl-20261008", "2.4-small-20261008", "2.3-xl-20261008",
                                        "2.3-small-20261008"]
    six = rows[1]
    assert six[0] == _fixture_ref("2.6-xl-20261020")     # the index digest, as pins are
    assert six[2:] == ["2.6.0", "xl", "2026-10-20", "1007", "-"]
    # an older snapshot of the same version is not offered
    assert "2.5-xl-20260908" not in [r[1] for r in rows]


def test_in_use_is_marked_and_kept_when_the_registry_lacks_it():
    gone = "ghcr.io/qubins/images@sha256:" + "e" * 64
    _, rows = _images("--in-use", _fixture_ref("2.6-small-20261020"))
    assert [r[6] for r in rows if r[1] == "2.6-small-20261020"] == ["in-use"]
    _, rows = _images("--in-use", gone, "--in-use-label", "2.2-xl-20260801")
    assert [r for r in rows if r[0] == gone] == [[gone, "2.2-xl-20260801", "2.2", "xl", "2026-08-01", "0", "in-use"]]


def test_offline_the_tested_image_only(tmp_path):
    proc, rows = _images(registry=str(tmp_path / "no-such-registry.json"))
    assert proc.returncode == 2
    assert rows == [[_PIN, _PIN_TAG, "2.5", "xl", "2026-10-08", "890", "tested"]]


def test_the_cache_saves_the_network_and_serves_offline(tmp_path):
    cache = tmp_path / "cache.json"
    proc, rows = _images("--cache", str(cache))
    assert proc.returncode == 0 and len(rows) == 8 and cache.exists()
    # fresh: no registry needed
    proc, again = _images("--cache", str(cache), registry=str(tmp_path / "none.json"))
    assert proc.returncode == 0 and again == rows
    # old and offline: still the cached list, with exit status 2
    data = json.loads(cache.read_text())
    data["time"] = time.time() - 7 * 24 * 3600
    cache.write_text(json.dumps(data))
    proc, old = _images("--cache", str(cache), registry=str(tmp_path / "none.json"))
    assert proc.returncode == 2 and old == rows


# --- the last choices ---------------------------------------------------------

def test_choices_are_remembered(tmp_path):
    state = tmp_path / "state" / "qubins.json"
    run = lambda *a: subprocess.run([sys.executable, _HELPER, *a], capture_output=True,  # noqa: E731
                                    text=True, timeout=30)
    assert run("last", "--state", str(state)).returncode == 1
    ref = _fixture_ref("2.6-xl-20261020")
    proc = run("remember", "--state", str(state), "--image", ref, "--label", "2.6-xl-20261020",
               "--content", "ibm-courses,bogus,ibm-tutorials")
    assert proc.returncode == 0, proc.stderr
    out = run("last", "--state", str(state))
    assert out.returncode == 0
    # known content only, in a fixed order
    assert out.stdout == f"{ref}\t2.6-xl-20261020\tibm-tutorials,ibm-courses\n"
    # nothing extra: an empty content field
    run("remember", "--state", str(state), "--image", ref, "--label", "x", "--content", "")
    assert run("last", "--state", str(state)).stdout == f"{ref}\tx\t\n"
    # a fallback tag that was downloaded instead of a pruned snapshot
    assert run("remember", "--state", str(state), "--image", "ghcr.io/qubins/images:2.6-xl").returncode == 0
    assert run("last", "--state", str(state)).stdout.startswith("ghcr.io/qubins/images:2.6-xl\t")
    # only QuBins images; a broken file counts as none
    assert run("remember", "--state", str(state), "--image", "ghcr.io/other/x@sha256:1").returncode == 2
    state.write_text("{broken")
    assert run("last", "--state", str(state)).returncode == 1


# --- the mounts ---------------------------------------------------------------

def _demos(tmp_path):
    demos = tmp_path / "demos"
    ibm = demos / "ibm-quantum-learning"
    for d in ("docs/tutorials", "docs/guides", "learning/courses", "public/docs/images",
              "public/learning/images/courses"):
        (ibm / d).mkdir(parents=True)
    for f in ("WELCOME-tutorials.ipynb", "WELCOME-courses.ipynb", "LICENSE-DOCS"):
        (ibm / f).write_text("{}")
    (demos / "quantum-paradoxes").mkdir()
    return demos


def _pairs(args):
    assert args[::2] == ["-v"] * (len(args) // 2)
    return args[1::2]


def test_mounts_courses_only(tmp_path):
    demos = _demos(tmp_path)
    welcome = tmp_path / "WELCOME.ipynb"
    welcome.write_text("{}")
    args, notes = qb.mount_args(["ibm-courses"], str(demos), "/w", str(welcome), str(tmp_path / "none"))
    ibm = f"{demos}/ibm-quantum-learning"
    assert _pairs(args) == [
        "/w:/home/jovyan/my-work",                                  # writable
        f"{welcome}:/home/jovyan/WELCOME.ipynb:ro",
        f"{ibm}/WELCOME-courses.ipynb:/home/jovyan/ibm-quantum-learning/WELCOME-courses.ipynb:ro",
        f"{ibm}/learning/courses:/home/jovyan/ibm-quantum-learning/learning/courses:ro",
        f"{ibm}/public/learning/images/courses:/home/jovyan/ibm-quantum-learning/public/learning/images/courses:ro",
        f"{ibm}/LICENSE-DOCS:/home/jovyan/ibm-quantum-learning/LICENSE-DOCS:ro",
    ]
    assert notes == []


def test_mounts_nothing_extra_and_missing_content(tmp_path):
    demos = _demos(tmp_path)
    args, notes = qb.mount_args("", str(demos), "/w")
    assert _pairs(args) == ["/w:/home/jovyan/my-work"]
    args, notes = qb.mount_args("fun-with-quantum,quantum-paradoxes,ibm-tutorials", str(demos), "/w")
    vols = _pairs(args)
    assert f"{demos}/quantum-paradoxes:/home/jovyan/quantum-paradoxes:ro" in vols
    assert f"{demos}/ibm-quantum-learning/docs/tutorials:/home/jovyan/ibm-quantum-learning/docs/tutorials:ro" in vols
    assert not any("learning/courses" in v for v in vols)
    assert all(v.endswith(":ro") for v in vols[1:])
    assert vols.count(f"{demos}/ibm-quantum-learning/LICENSE-DOCS:/home/jovyan/ibm-quantum-learning/LICENSE-DOCS:ro") == 1
    assert notes == ["fun-with-quantum is not on this Pi: left out"]


def test_mounts_with_copies(tmp_path):
    demos = _demos(tmp_path)
    copies = tmp_path / "copies"
    hook = tmp_path / "hide-work.sh"
    hook.write_text("rmdir /home/jovyan/work 2>/dev/null || true\n")
    qb.prepare("quantum-paradoxes", str(demos), str(copies))
    args, _ = qb.mount_args(["quantum-paradoxes", "ibm-courses"], str(demos), "/w", copies=str(copies),
                            hook=str(hook))
    vols = _pairs(args)
    assert f"{hook}:/usr/local/bin/before-notebook.d/90-rasqberry-hide-work.sh:ro" in vols
    assert f"{copies}/quantum-paradoxes:/home/jovyan/quantum-paradoxes" in vols
    assert f"{demos}/quantum-paradoxes:/home/jovyan/originals/quantum-paradoxes:ro" in vols
    # no copy of the courses (not prepared): the originals, read-only, as before
    assert (f"{demos}/ibm-quantum-learning/learning/courses:"
            "/home/jovyan/ibm-quantum-learning/learning/courses:ro") in vols


# --- the user's copies: prepare / reset ----------------------------------------

def _original(tmp_path):
    demos = _demos(tmp_path)
    nb = demos / "ibm-quantum-learning" / "learning" / "courses" / "basics" / "lesson.ipynb"
    nb.parent.mkdir(parents=True)
    nb.write_text('{"original": 1}')
    pic = nb.parent / "figure.png"
    pic.write_bytes(b"\x89PNG" + b"0" * 4000)
    (demos / "ibm-quantum-learning" / "00-Save-Credentials.ipynb").write_text("{}")
    git = demos / "ibm-quantum-learning" / ".git"
    git.mkdir()
    (git / "HEAD").write_text("not a real repository\n")
    (demos / "ibm-quantum-learning" / ".rasqberry-converted").write_text("1")
    par = demos / "quantum-paradoxes"
    (par / "WELCOME.ipynb").write_text('{"p": 1}')
    (par / ".git").mkdir()
    return demos, nb, pic


def test_prepare_copies_text_links_the_rest_and_keeps_changes(tmp_path):
    demos, nb, pic = _original(tmp_path)
    copies = tmp_path / "work" / "qubins"
    assert qb.prepare("ibm-courses", str(demos), str(copies)) == []
    mine = copies / "ibm-quantum-learning" / "learning" / "courses" / "basics" / "lesson.ipynb"
    assert mine.read_text() == '{"original": 1}'
    assert os.stat(mine).st_ino != os.stat(nb).st_ino               # a real copy: editable
    assert os.stat(mine.parent / "figure.png").st_ino == os.stat(pic).st_ino   # no space
    assert (copies / "ibm-quantum-learning" / "WELCOME-courses.ipynb").exists()
    assert (copies / "ibm-quantum-learning" / "00-Save-Credentials.ipynb").exists()
    # only the chosen part, no repository files
    assert not (copies / "ibm-quantum-learning" / "docs").exists()
    assert not (copies / "ibm-quantum-learning" / ".git").exists()
    assert qb.copied(str(copies)) == ["ibm-courses"]
    # the user's change survives the next start
    mine.write_text('{"mine": 1}')
    assert qb.prepare("ibm-courses", str(demos), str(copies)) == []
    assert mine.read_text() == '{"mine": 1}' and nb.read_text() == '{"original": 1}'
    # a folder the user deleted comes back
    shutil.rmtree(copies / "ibm-quantum-learning" / "learning" / "courses")
    qb.prepare("ibm-courses", str(demos), str(copies))
    assert mine.read_text() == '{"original": 1}'


def test_a_newer_original_is_named_once_and_the_copy_kept(tmp_path):
    demos, nb, _ = _original(tmp_path)
    copies = tmp_path / "work" / "qubins"
    qb.prepare("ibm-courses,quantum-paradoxes", str(demos), str(copies))
    mine = copies / "ibm-quantum-learning" / "learning" / "courses" / "basics" / "lesson.ipynb"
    mine.write_text('{"mine": 1}')
    # Update demos moves the checkout (here: the converter's mark changes)
    nb.write_text('{"original": 2}')
    (demos / "ibm-quantum-learning" / ".rasqberry-converted").write_text("2")
    notes = qb.prepare("ibm-courses,quantum-paradoxes", str(demos), str(copies))
    assert len(notes) == 1 and notes[0].startswith("IBM Quantum Courses: a newer original is in originals/")
    assert "Reset" in notes[0]
    assert mine.read_text() == '{"mine": 1}'
    assert qb.prepare("ibm-courses", str(demos), str(copies)) == []      # said once
    # Reset gives the new one, and the note is not repeated
    assert qb.reset("ibm-courses", str(demos), str(copies)) == ["IBM Quantum Courses"]
    assert mine.read_text() == '{"original": 2}'
    assert qb.prepare("ibm-courses", str(demos), str(copies)) == []


def test_reset_only_the_chosen_content_never_my_work(tmp_path):
    demos, nb, _ = _original(tmp_path)
    work = tmp_path / "work"
    copies = work / "qubins"
    my_work = work / "quantum-lab"
    my_work.mkdir(parents=True)
    (my_work / "mine.ipynb").write_text("{}")
    qb.prepare("ibm-courses,quantum-paradoxes", str(demos), str(copies))
    lesson = copies / "ibm-quantum-learning" / "learning" / "courses" / "basics" / "lesson.ipynb"
    extra = lesson.parent / "my-notes.ipynb"
    lesson.write_text("changed")
    extra.write_text("new")
    par = copies / "quantum-paradoxes" / "WELCOME.ipynb"
    par.write_text("changed")
    cred = copies / "ibm-quantum-learning" / "00-Save-Credentials.ipynb"
    cred.write_text("my key cell")
    assert qb.reset("ibm-courses", str(demos), str(copies)) == ["IBM Quantum Courses"]
    # nothing of the changes in that content is kept
    assert lesson.read_text() == '{"original": 1}' and not extra.exists()
    # the rest is untouched
    assert par.read_text() == "changed"
    assert cred.read_text() == "my key cell"
    assert (my_work / "mine.ipynb").exists()
    assert nb.read_text() == '{"original": 1}'


def test_prepare_reset_and_copies_from_the_command_line(tmp_path):
    demos, _, _ = _original(tmp_path)
    copies = tmp_path / "copies"
    run = lambda *a: subprocess.run([sys.executable, _HELPER, *a], capture_output=True,  # noqa: E731
                                    text=True, timeout=30)
    assert run("copies", "--copies", str(copies)).stdout == "\n"
    proc = run("prepare", "--content", "quantum-paradoxes,fun-with-quantum", "--demos", str(demos),
               "--copies", str(copies))
    assert proc.returncode == 0 and proc.stdout == "", proc.stderr
    assert run("copies", "--copies", str(copies)).stdout == "quantum-paradoxes\n"
    proc = run("reset", "--content", "quantum-paradoxes", "--demos", str(demos), "--copies", str(copies))
    assert proc.stdout == "Quantum Paradoxes\n"


def test_reset_from_the_start_dialog(box):
    env = _rig(box, ["2", '"quantum-paradoxes"'])
    assert box([_LAUNCHER], extra=env).returncode == 0
    mine = box.home / "RasQberry-Two" / "work" / "qubins" / "quantum-paradoxes" / "WELCOME.ipynb"
    mine.write_text("changed")
    # RESET, choose Quantum Paradoxes, confirm; back in the first dialog: LAST
    (box.tmp / "answers").write_text('RESET\n"quantum-paradoxes"\nLAST\n')
    (box.tmp / "wt_n").write_text("0")
    (box.tmp / "wt.log").write_text("")
    proc = box([_LAUNCHER], extra=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert mine.read_text() == "{}"
    texts = ["\n".join(c) for c in box.dialogs()]
    assert any("--yesno" in t and "All your changes in these notebooks are lost" in t for t in texts)
    assert any("--msgbox" in t and "Back to the original: Quantum Paradoxes" in t for t in texts)


# --- the launcher, end to end with stubs ---------------------------------------

_DOCKER = r'''#!/bin/sh
echo "$*" >> "$DOCKER_LOG"
case "$1 $2" in
  "info "*|"ps "*) exit 0 ;;
  "image inspect") grep -qxF "$3" "$PULLED"; exit $? ;;
  "images --digests") sed 's/.*@//' "$PULLED"; exit 0 ;;
  "container inspect")
    [ "$3" = "-f" ] && { echo true; exit 0; }
    exit 1 ;;
esac
case "$1" in
  pull) echo "$3" >> "$PULLED"; exit 0 ;;
  run) echo cid; exit 0 ;;
esac
exit 0
'''

# Answers the menus and checklists one by one (WT_ANSWERS); CANCEL = Esc
_WHIPTAIL = r'''#!/bin/sh
{ for a in "$@"; do printf '%s\n' "$a"; done; echo "@@"; } >> "$WT_LOG"
case " $* " in
  *" --menu "*|*" --checklist "*)
    n=$(cat "$WT_N" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$WT_N"
    a=$(sed -n "${n}p" "$WT_ANSWERS")
    [ "$a" = CANCEL ] && exit 1
    printf '%s' "$a" >&2 ;;
esac
exit 0
'''


def _rig(box, answers):
    pulled = box.tmp / "pulled"
    pulled.touch()
    _exe(box.stubs / "docker", _DOCKER)
    _exe(box.stubs / "whiptail", _WHIPTAIL)
    _exe(box.stubs / "id", '#!/bin/sh\ncase "$1" in -u) echo 1000 ;; *) echo "rasqberry docker" ;; esac\n')
    for tool in ("ss", "ping"):
        _exe(box.stubs / tool, "#!/bin/sh\nexit 0\n")
    (box.tmp / "answers").write_text("\n".join(answers) + "\n")
    (box.tmp / "wt_n").write_text("0")
    demos = box.home / "RasQberry-Two" / "demos"
    ibm = demos / "ibm-quantum-learning"
    for d in ("docs/tutorials", "learning/courses", "public/learning/images/courses"):
        (ibm / d).mkdir(parents=True, exist_ok=True)
    for f in ("WELCOME-tutorials.ipynb", "WELCOME-courses.ipynb"):
        (ibm / f).write_text("{}")
    (demos / "quantum-paradoxes").mkdir(exist_ok=True)
    (demos / "quantum-paradoxes" / "WELCOME.ipynb").write_text("{}")
    return {"DOCKER_LOG": str(box.tmp / "docker.log"), "PULLED": str(pulled),
            "WT_ANSWERS": str(box.tmp / "answers"), "WT_N": str(box.tmp / "wt_n"),
            "RQ_QUBINS_REGISTRY_FILE": _FIXTURE, "RQ_TEST_ROOT_GB": "64", "RQ_UMAMI": "0",
            "RQ_LAB_OVERRIDES": str(box.tmp / "no-overrides")}


def _docker_calls(box):
    log = box.tmp / "docker.log"
    return log.read_text().splitlines() if log.exists() else []


def test_choose_download_and_start_then_start_with_last_settings(box):
    six = _fixture_ref("2.6-xl-20261020")
    env = _rig(box, ["2", '"ibm-courses" "quantum-paradoxes"'])
    proc = box([_LAUNCHER], extra=env)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    menus = [c for c in box.dialogs() if "--menu" in c or "--checklist" in c]
    image_menu, content = menus
    # the tested image first and marked; the in-use one preselected
    assert image_menu[image_menu.index("--default-item") + 1] == "1"
    start = image_menu.index("--menu") + 5
    items = dict(zip(image_menu[start::2], image_menu[start + 1::2]))
    first = items["1"]
    assert "2.5.2" in first and "xl" in first and "[tested]" in first and "~887 MB" in first
    assert items["2"].startswith("2.6.0  xl") and len(items) == 8
    assert "IBM Quantum Courses (on this Pi)" in content and "Fun with Quantum (download ~30 MB)" in content
    # first start: the courses preselected, as in Qiskit Live
    states = dict(zip(content[content.index("--checklist") + 5::3], content[content.index("--checklist") + 7::3]))
    assert states == {"ibm-tutorials": "OFF", "ibm-courses": "ON", "quantum-paradoxes": "OFF",
                      "fun-with-quantum": "OFF"}
    calls = _docker_calls(box)
    assert f"pull -q {six}" in calls
    (run,) = [c for c in calls if c.startswith("run ")]
    home = box.home / "RasQberry-Two"
    assert f"-v {home}/work/quantum-lab:/home/jovyan/my-work " in run
    # the user's copies, writable; the originals read-only next to them
    copies = f"{home}/work/qubins"
    assert f"-v {copies}/ibm-quantum-learning/learning/courses:/home/jovyan/ibm-quantum-learning/learning/courses " in run
    assert (f"{home}/demos/ibm-quantum-learning/learning/courses:"
            "/home/jovyan/originals/ibm-quantum-learning/learning/courses:ro") in run
    assert f"-v {copies}/quantum-paradoxes:/home/jovyan/quantum-paradoxes " in run
    assert f"{home}/demos/quantum-paradoxes:/home/jovyan/originals/quantum-paradoxes:ro" in run
    # pictures stay the originals, read-only, where the notebooks look for them
    assert (f"{home}/demos/ibm-quantum-learning/public/learning/images/courses:"
            "/home/jovyan/ibm-quantum-learning/public/learning/images/courses:ro") in run
    assert (home / "work/qubins/quantum-paradoxes/WELCOME.ipynb").exists()
    assert "docs/tutorials" not in run
    # the image's own empty work folder is removed by a start hook
    assert f"{_CFG}/qubins/hide-work.sh:/usr/local/bin/before-notebook.d/90-rasqberry-hide-work.sh:ro" in run
    assert f"{_CFG}/qubins/WELCOME.ipynb:/home/jovyan/WELCOME.ipynb:ro" in run
    assert "-p 127.0.0.1:8894:8888" in run and "--label org.rasqberry.demo=qubins" in run
    assert run.endswith(six)
    assert "lab/tree/WELCOME.ipynb?token=rasqberry" in proc.stdout
    # kept: the choices, and the image as the version in use
    state = json.loads((box.home / ".local/state/rasqberry/qubins.json").read_text())
    assert state["image"] == six and state["content"] == ["ibm-courses", "quantum-paradoxes"]
    versions = (home / "demos" / ".demo-versions").read_text()
    assert versions.startswith(f"qubins:image\t{_PIN}\t{six}\t2.6-xl-20261020")

    # second start: "Start with last settings", no list, no download
    (box.tmp / "answers").write_text("LAST\n")
    (box.tmp / "wt_n").write_text("0")
    (box.tmp / "docker.log").write_text("")
    (box.tmp / "wt.log").write_text("")
    proc = box([_LAUNCHER], extra=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    (menu,) = box.dialogs()
    assert "LAST" in menu and "Reset notebooks to the original" in menu
    assert "Start with last settings: 2.6-xl-20261020, IBM Quantum Courses, Quantum Paradoxes" in menu
    calls = _docker_calls(box)
    assert not [c for c in calls if c.startswith("pull")]
    (run2,) = [c for c in calls if c.startswith("run ")]
    assert run2 == run


def test_the_tested_image_with_nothing_extra(box):
    env = _rig(box, ["1", ""])
    proc = box([_LAUNCHER], extra=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    calls = _docker_calls(box)
    assert f"pull -q {_PIN}" in calls
    (run,) = [c for c in calls if c.startswith("run ")]
    assert "ibm-quantum-learning" not in run and "quantum-paradoxes" not in run
    assert run.endswith(_PIN)
    # the tested image is the release version: nothing recorded as newer
    versions = box.home / "RasQberry-Two" / "demos" / ".demo-versions"
    assert not versions.exists() or "qubins:image" not in versions.read_text()


def test_the_engine_does_not_download_before_the_choice(box):
    env = _rig(box, ["CANCEL"])
    proc = box([_ENGINE, "qubins"], extra=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "rq_qubins.sh" in proc.stdout + proc.stderr
    assert not [c for c in _docker_calls(box) if c.startswith("pull")]
    # Manage demos > Download: the tested image
    proc = box([_ENGINE, "qubins", "--install-only"], extra=dict(env, RQ_DEMO_CONSENT="yes"))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"pull -q {_PIN}" in _docker_calls(box)
    assert box([_ENGINE, "qubins", "--is-installed"], extra=env).returncode == 0


# --- the manifest and its places ------------------------------------------------

def test_manifest_is_valid_beta_and_pinned_like_qiskit_live():
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_demo_validate.sh"),
                           os.path.join(_MANIFESTS, "rq_demo_qubins.json")],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    m, lab = _manifest("qubins"), _manifest("quantum-lab")
    assert m["maturity"] == "beta"
    ep = m["entrypoint"]
    assert ep["type"] == "docker" and ep["launcher"] == "rq_qubins.sh" and ep["docker_image_choice"] is True
    # the tested default is a monthly snapshot pinned by digest, as Qiskit Live's
    assert ep["docker_image"] == lab["entrypoint"]["docker_image"]
    assert qb.parse_tag(ep["docker_image_tag"]) is not None
    assert ep["docker_image_fallback"] == "ghcr.io/qubins/images:" + ep["docker_image_tag"].rsplit("-", 1)[0]
    assert m["install"]["download_all"] is False
    import re
    tags = re.compile(m["install"]["update"]["docker_tags"])
    assert tags.search("2.6-xl-20261020") and tags.search("2.6-small") and not tags.search("2.6-xxl")
    schema = _manifest("schema")
    assert "docker_image_choice" in schema["properties"]["entrypoint"]["properties"]


def test_icon_menu_and_lists():
    text = open(os.path.join(_CFG, "desktop-bookmarks", "qubins.desktop")).read()
    assert "Exec=/usr/bin/rq_hold_on_error.sh /usr/bin/rq_demo_run.sh qubins\n" in text
    assert os.path.exists(os.path.join(_ROOT, "desktop-icons", "quantum-lab.svg"))
    sys.path.insert(0, _BIN)
    import rq_desktop_session as ds  # noqa: E402
    assert "qubins" in ds.ICON_ORDER
    stage = open(os.path.join(_ROOT, "stage-RQB2", "06-desktop-integration", "00-run-chroot.sh")).read()
    assert stage.count("|qubins|") == 2
    assert "qubins)" in open(os.path.join(_BIN, "rq_docker_demos.sh")).read()
    m = _manifest("qubins")
    assert m["menu"]["show"] and m["desktop"]["show"]


@pytest.mark.parametrize("name", ["rq_qubins.sh"])
def test_launcher_follows_the_standards(name):
    src = open(os.path.join(_BIN, name)).read()
    assert src.startswith("#!/bin/bash\nset -euo pipefail\n")
    assert '. "${SCRIPT_DIR}/rq_common.sh"' in src and "load_rqb2_env" in src
    # other QuBins images (Qiskit Live's too) are not removed after a download
    assert "rq_docker_drop_old" not in src
    assert "mapfile" not in src and "readarray" not in src     # bash 3 in the tests
