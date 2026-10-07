"""
Learning paths (issue #309): RQB2-config/demo-manifests/learning-paths.json is
read by the Pi (rq_learning_paths.sh, from the RasQberry menu and the desktop
icon) and by the website (generate-demo-list.js on gh-pages). These tests keep
the file honest - every step names a demo, variant, tool or page that exists -
and walk the chooser with a stub whiptail.
"""

import json
import os
import pty
import re
import shutil
import subprocess
import textwrap
import threading

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_MANIFESTS = os.path.join(_CFG, "demo-manifests")
_PATHS = os.path.join(_MANIFESTS, "learning-paths.json")
_SCRIPT = os.path.join(_BIN, "rq_learning_paths.sh")
_MENU = os.path.join(_CFG, "RQB2_menu.sh")
_BOOKMARK = os.path.join(_CFG, "desktop-bookmarks", "learning-paths.desktop")

_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")

needs_bash = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required")


def _paths():
    with open(_PATHS, encoding="utf-8") as fh:
        return json.load(fh)["paths"]


def _manifests():
    out = {}
    for name in os.listdir(_MANIFESTS):
        if name.startswith("rq_demo_") and name.endswith(".json") and "schema" not in name:
            with open(os.path.join(_MANIFESTS, name), encoding="utf-8") as fh:
                m = json.load(fh)
            out[m["id"]] = m
    return out


def _steps():
    for p in _paths():
        for i, s in enumerate(p["steps"]):
            yield p, i, s


# --- the file -------------------------------------------------------------------

def test_paths_have_every_field_and_unique_ids():
    paths = _paths()
    assert paths, "no learning paths"
    ids = [p["id"] for p in paths]
    assert len(ids) == len(set(ids)), ids
    for p in paths:
        assert _ID.match(p["id"]), p["id"]
        for key in ("title", "audience", "goal"):
            assert isinstance(p.get(key), str) and p[key].strip(), (p["id"], key)
        assert isinstance(p.get("minutes"), int) and 5 <= p["minutes"] <= 180, p["id"]
        assert p.get("maturity") == "beta", p["id"]
        assert 2 <= len(p.get("steps", [])) <= 6, p["id"]


def test_every_step_starts_something_that_exists():
    manifests = _manifests()
    for p, i, s in _steps():
        where = f"{p['id']} step {i + 1}"
        kinds = [k for k in ("demo", "command", "url") if k in s]
        assert len(kinds) == 1, f"{where}: exactly one of demo, command, url"
        if "demo" in s:
            assert s["demo"] in manifests, f"{where}: no manifest for {s['demo']}"
            if "variant" in s:
                variants = [v["id"] for v in manifests[s["demo"]].get("variants", [])]
                assert s["variant"] in variants, f"{where}: {s['demo']} has no variant {s['variant']}"
        else:
            assert "variant" not in s, where
            assert s.get("name"), f"{where}: a {kinds[0]} step needs a name"
        if "command" in s:
            assert re.fullmatch(r"rq_[a-z0-9_]+\.sh", s["command"]), where
            tool = os.path.join(_BIN, s["command"])
            assert os.path.isfile(tool) and os.access(tool, os.X_OK), f"{where}: {tool}"
        if "url" in s:
            assert s["url"].startswith("https://"), where


def test_hints_are_short_plain_ascii():
    # whiptail shows them (docs/STYLE.md: plain ASCII), the website too
    for p, i, s in _steps():
        for key in ("try", "notice"):
            text = s.get(key, "")
            assert text.strip(), f"{p['id']} step {i + 1}: {key} missing"
            assert text.isascii(), f"{p['id']} step {i + 1}: {key} is not ASCII"
            assert len(text) <= 100, f"{p['id']} step {i + 1}: {key} too long"
    for p in _paths():
        assert p["goal"].isascii() and len(p["goal"]) <= 100, p["id"]


_RUNGS = ["Play", "Understand", "Code", "Real hardware", "Certify", "Build & share"]


def test_every_path_says_where_to_go_next():
    ids = [p["id"] for p in _paths()]
    for p in _paths():
        assert 2 <= len(p.get("next", [])) <= 3, p["id"]
        for e in p["next"]:
            assert ("path" in e) != ("url" in e), f"{p['id']}: path or url: {e}"
            if "path" in e:
                assert e["path"] in ids and e["path"] != p["id"], f"{p['id']}: {e['path']}"
            else:
                assert e["url"].startswith("https://") and e.get("name"), f"{p['id']}: {e}"
            why = e.get("why", "")
            assert why.strip() and why.isascii() and len(why) <= 100, f"{p['id']}: {why}"


def test_where_to_go_next_ladder():
    with open(_PATHS, encoding="utf-8") as fh:
        ladder = json.load(fh)["ladder"]
    assert [r["rung"] for r in ladder] == _RUNGS
    for r in ladder:
        assert r["text"].isascii() and r["text"].strip(), r["rung"]
        # one menu line: "N Rung: text"
        assert len(r["rung"]) + len(r["text"]) + 4 <= 70, r["rung"]
        assert 1 <= len(r["links"]) <= 4, r["rung"]
        for link in r["links"]:
            assert link.get("name") and link["url"].startswith("https://"), link
            note = link.get("note", "")
            assert note.isascii() and len(note) <= 140, link
            # a sentence that names it: the website and the Pi show it alone
            assert not note or link["name"].split()[-1] in note, link
    # CertiQ is a community project: say so where it is offered (Jan)
    certiq = [lk for r in ladder for lk in r["links"] if lk["name"] == "CertiQ"]
    assert certiq and "not affiliated with or endorsed by IBM" in certiq[0]["note"]
    for p in _paths():
        for e in p["next"]:
            if e.get("name") == "CertiQ":
                assert "unofficial" in e["why"], e


def _lines(text, width):
    return sum(len(textwrap.wrap(line, width) or [""]) for line in text.split("\n"))


def test_step_screens_fit_80x24():
    # the prompt (goal on the first step, the step, try, notice) + 3 items +
    # whiptail's frame; rq_learning_paths.sh shrinks the list beyond that
    for p, i, s in _steps():
        name = s.get("name") or _manifests()[s["demo"]]["name"]
        prompt = (p["goal"] + "\n\n" if i == 0 else "") + \
            f"Step {i + 1} of {len(p['steps'])}: {name}\n\nTry: {s['try']}\nNotice: {s['notice']}"
        assert _lines(prompt, 74) + 3 + 7 <= 24, f"{p['id']} step {i + 1}"


def test_keep_going_and_ladder_screens_fit_80x24():
    titles = {p["id"]: p["title"] for p in _paths()}
    for p in _paths():
        prompt = f'Keep going after "{p["title"]}":'
        for e in p["next"]:
            prompt += f"\n\n{e.get('name') or titles[e['path']]}: {e['why']}"
        # + More ideas, + the feedback form
        assert _lines(prompt, 74) + len(p["next"]) + 2 + 7 <= 24, p["id"]
    with open(_PATHS, encoding="utf-8") as fh:
        ladder = json.load(fh)["ladder"]
    assert 2 + len(ladder) + 7 <= 24
    for r in ladder:
        prompt = f"{r['rung']}: {r['text']}"
        for link in r["links"]:
            if link.get("note"):
                prompt += f"\n\n{link['note']}"
        assert _lines(prompt, 74) + len(r["links"]) + 7 <= 24, r["rung"]


# --- what the steps say matches what the demos do (user test 2026-10-04) ---------

def test_first_program_avoids_the_chsh_tutorial():
    # #1: Tutorials -> Get started holds only CHSH, which fails in Simulator
    # Mode (upstream doQumentation); Hello World runs. Go back to Get started
    # once doQumentation is fixed.
    steps = [s for _, _, s in _steps() if s.get("demo") == "qiskit-tutorials"]
    assert steps
    for s in steps:
        assert "Hello World" in s["try"] and "Get started" not in s["try"], s


def test_rasq_led_step_matches_the_demo():
    # #11: RasQ-LED asks nothing ("Choose 1, then 2"); it runs every block size
    # by itself
    src = open(os.path.join(_BIN, "RasQ-LED.py"), encoding="utf-8").read()
    main = src[src.index("def main():"):]
    assert "\n    demo_loop(" in main and "\n    interactive_mode()" not in main
    steps = [s for _, _, s in _steps() if s.get("demo") == "rasq-led"]
    assert steps
    for s in steps:
        assert "choose" not in s["try"].lower() and "watch" in s["try"].lower(), s


def test_no_step_promises_what_the_later_steps_do_not_show():
    # #30: "Later steps show qubits on them" (the LEDs) - none of them did
    for p, i, s in _steps():
        assert "later step" not in s["notice"].lower(), f"{p['id']} step {i + 1}"


# --- where it is offered ----------------------------------------------------------

def test_quantum_demos_menu_offers_the_paths_near_the_top():
    menu = open(_MENU, encoding="utf-8").read()
    start = menu.index('"RasQberry: Quantum Demos" "Select a demo or option"')
    items = menu[start:menu.index('"$@"', start)]
    assert 'PATHS "Learning paths (beta)' in items
    assert items.index("PATHS") < items.index("LED ")
    assert 'run_engine_demo "$BIN_DIR/rq_learning_paths.sh" --menu' in menu
    assert "PATHS) do_learning_paths" in menu


def test_desktop_icon_opens_the_chooser():
    entry = {}
    for line in open(_BOOKMARK, encoding="utf-8"):
        if "=" in line:
            key, value = line.rstrip("\n").split("=", 1)
            entry.setdefault(key, value)
    assert entry["Name"] == "Learning paths"
    assert entry["Comment"].startswith("(beta) ")
    assert entry["Exec"] == '/usr/bin/rq_hold_on_error.sh -t "Learning paths" /usr/bin/rq_learning_paths.sh'
    assert entry["Terminal"] == "true" and "RasQberry" in entry["Categories"]
    stage = open(os.path.join(_ROOT, "stage-RQB2", "06-desktop-integration", "00-run-chroot.sh")).read()
    assert stage.count("|learning-paths)") == 2
    import sys
    sys.path.insert(0, _BIN)
    import rq_desktop_session as ds  # noqa: E402
    assert "learning-paths" in ds.ICON_ORDER


# --- the chooser -----------------------------------------------------------------

@needs_bash
def test_list_prints_every_path_and_step():
    env = dict(os.environ, RQ_CONFIG_FILE="/nonexistent")
    proc = subprocess.run(["bash", _SCRIPT, "--list"], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    for p in _paths():
        assert f"{p['title']} (beta)" in proc.stdout
    assert "Quantum Coin Game" in proc.stdout and "Grokking the Bloch Sphere" in proc.stdout
    assert "template=demo-feedback.yml&demo=learning-paths" in proc.stdout


# whiptail stub: logs argv as one JSON line per call, answers from a queue
# file (one reply per call; ESC = the Esc key)
_WHIPTAIL = r'''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["WT_LOG"], "a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\n")
with open(os.environ["WT_QUEUE"]) as fh:
    queue = fh.read().splitlines()
reply = queue.pop(0) if queue else ""
with open(os.environ["WT_QUEUE"], "w") as fh:
    fh.write("\n".join(queue) + "\n")
if reply in ("", "ESC"):
    sys.exit(255)
sys.stderr.write(reply)
'''


def _walk(tmp_path, replies, args=(), demo_rc=0, tty_out=False, desktop=False):
    """Run the chooser on a pty with a stub whiptail and stub demos.

    With tty_out, its output goes to the pty too (as in a terminal window)
    and is returned as a fourth value; a stub demo sets its own window title.
    With desktop, there is a screen and a stub browser.
    """
    bin_dir = tmp_path / "RQB2-bin"
    bin_dir.mkdir()
    shutil.copy(_SCRIPT, bin_dir)
    shutil.copy(os.path.join(_BIN, "rq_common.sh"), bin_dir)
    log = tmp_path / "started.log"
    for tool in ("rq_demo_run.sh", "rq_my_programs.sh"):
        (bin_dir / tool).write_text(f'#!/bin/sh\nprintf \'\\033]0;LED Demos\\007\'\n'
                                    f'echo "{tool} $*" >> "{log}"\nexit {demo_rc}\n')
        (bin_dir / tool).chmod(0o755)
    (tmp_path / "RQB2-config").mkdir()
    os.symlink(_MANIFESTS, tmp_path / "RQB2-config" / "demo-manifests")
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    (stubs / "whiptail").write_text(_WHIPTAIL)
    (stubs / "whiptail").chmod(0o755)
    queue = tmp_path / "queue"
    queue.write_text("\n".join(replies) + "\n")
    wt_log = tmp_path / "whiptail.log"
    env = {"PATH": f"{stubs}:{os.environ['PATH']}", "HOME": str(tmp_path),
           "RQ_CONFIG_FILE": "/nonexistent", "WT_LOG": str(wt_log), "WT_QUEUE": str(queue)}
    if desktop:
        (stubs / "chromium-browser").write_text(f'#!/bin/sh\necho "browser $*" >> "{log}"\n')
        (stubs / "chromium-browser").chmod(0o755)
        env["DISPLAY"] = ":0"
    master, slave = pty.openpty()
    os.write(master, b"\n" * 20)    # Enter for every "Press Enter" pause
    out = []
    if tty_out:
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
        proc = subprocess.run(["bash", str(bin_dir / "rq_learning_paths.sh"), *args],
                              stdin=slave, stdout=slave, stderr=slave, env=env, timeout=60)
        os.close(slave)
        reader.join(5)
    else:
        proc = subprocess.run(["bash", str(bin_dir / "rq_learning_paths.sh"), *args],
                              stdin=slave, capture_output=True, text=True, env=env, timeout=60)
        os.close(slave)
    os.close(master)
    calls = [json.loads(line) for line in wt_log.read_text().splitlines()] if wt_log.exists() else []
    started = log.read_text().splitlines() if log.exists() else []
    if tty_out:
        return proc, calls, started, b"".join(out).decode("utf-8", "replace")
    return proc, calls, started


def _arg(call, option):
    return call[call.index(option) + 1] if option in call else None


@needs_bash
def test_walk_a_path_start_next_back_finish(tmp_path):
    replies = ["0", "start", "next", "back", "next", "next", "next",   # path 1
               "ESC",                                                   # Keep going: Done
               "3", "start", "next", "next", "start", "ESC",            # path 4, URL step
               "ESC"]
    proc, calls, started = _walk(tmp_path, replies)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert started == ["rq_demo_run.sh led-demos ibm-logo", "rq_my_programs.sh "]
    for call in calls:   # every box fits 80x24
        menu = call.index("--menu")
        assert int(call[menu + 2]) <= 24 and int(call[menu + 3]) <= 80, call
    paths = _paths()
    # the list: one entry per path, then feedback; Close on the desktop
    assert _arg(calls[0], "--cancel-button") == "Close"
    assert "First 15 minutes: visitors at a stand, 15 min" in calls[0]
    assert "feedback" in calls[0] and "ladder" in calls[0]
    # step 1: the goal, the step, the hints; no Back yet
    step1 = calls[1][calls[1].index("--menu") + 1]
    assert paths[0]["goal"] in step1 and "Step 1 of 3: IBM LED Demo" in step1
    assert "Try: " + paths[0]["steps"][0]["try"] in step1
    assert "back" not in calls[1] and _arg(calls[1], "--cancel-button") == "Done"
    # after the demo: Next is preselected
    assert _arg(calls[2], "--default-item") == "next"
    step2 = calls[3]
    assert "Step 2 of 3: Grokking the Bloch Sphere" in step2[step2.index("--menu") + 1]
    assert "Back to step 1: IBM LED Demo" in step2 and "Next step: Quantum Coin Game" in step2
    assert "Step 1 of 3" in calls[4][calls[4].index("--menu") + 1]
    assert "Finish this path" in calls[6]
    assert 'That was the last step of "First 15 minutes"' in proc.stdout
    assert "&demo=learning-paths/first-15-minutes" in proc.stdout
    # the URL step: no screen here, so the address is shown
    assert _arg(calls[7], "--title") == "RasQberry: Keep Going"
    assert "Open IBM Quantum Learning" in calls[12]
    assert "https://quantum.cloud.ibm.com/learning" in proc.stdout


@needs_bash
def test_from_the_menu_the_list_has_a_back_button(tmp_path):
    proc, calls, _ = _walk(tmp_path, ["ESC"], ["--menu"])
    assert proc.returncode == 0, proc.stderr
    assert _arg(calls[0], "--cancel-button") == "Back"


@needs_bash
def test_feedback_entry_prints_the_form_link(tmp_path):
    proc, _, _ = _walk(tmp_path, ["feedback", "ESC"])
    assert proc.returncode == 0, proc.stderr
    assert "Learning paths are new" in proc.stdout
    assert "issues/new?template=demo-feedback.yml&demo=learning-paths" in proc.stdout


@needs_bash
def test_after_a_failed_start_the_step_offers_start_again(tmp_path):
    proc, calls, started = _walk(tmp_path, ["1", "start", "ESC", "ESC"], demo_rc=1)
    assert proc.returncode == 0, proc.stderr
    assert started == ["rq_demo_run.sh grok-bloch local"]
    assert "It stopped with an error" in proc.stderr + proc.stdout
    assert _arg(calls[2], "--default-item") == "start"



@needs_bash
def test_finish_keep_going_and_where_to_go_next(tmp_path):
    replies = ["2", "next", "next", "next",      # Entanglement to the end
               "n0",                             # Keep going: open the CHSH tutorial
               "more", "r4", "k0", "ESC", "ESC",  # Where to go next: Certify, CertiQ
               "n2",                             # Keep going: the next path
               "ESC", "ESC"]                     # Done, Close
    proc, calls, _ = _walk(tmp_path, replies)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    for call in calls:
        menu = call.index("--menu")
        assert int(call[menu + 2]) <= 24 and int(call[menu + 3]) <= 80, call
    keep = calls[4]
    assert _arg(keep, "--title") == "RasQberry: Keep Going" and _arg(keep, "--cancel-button") == "Done"
    prompt = keep[keep.index("--menu") + 1]
    for e in _paths()[2]["next"]:
        assert e["why"] in prompt
    assert "Open CHSH inequality tutorial" in keep and "Next path: Your first program" in keep
    assert "More ideas: where to go next" in keep
    # a page: no screen here, so the address is printed
    assert "https://doqumentation.org/tutorials/chsh-inequality" in proc.stdout
    ladder = calls[6]
    assert _arg(ladder, "--title") == "RasQberry: Where to Go Next"
    assert "5 Certify: Prepare for the Qiskit v2.x Developer certification" in ladder
    certify = calls[7]
    assert "not affiliated with or endorsed by IBM" in certify[certify.index("--menu") + 1]
    assert "Open CertiQ" in certify and "https://certiq.dev" in proc.stdout
    # the next path starts at its first step
    step = calls[11]
    assert _arg(step, "--title") == "RasQberry: Your first program (beta)"
    assert "Step 1 of 3: My Quantum Programs" in step[step.index("--menu") + 1]


@needs_bash
def test_where_to_go_next_from_the_list(tmp_path):
    proc, calls, _ = _walk(tmp_path, ["ladder", "r0", "k1", "ESC", "ESC", "ESC"])
    assert proc.returncode == 0, proc.stderr
    assert _arg(calls[1], "--title") == "RasQberry: Where to Go Next"
    assert _arg(calls[2], "--title") == "RasQberry: Play"
    assert "https://qamposer.org" in proc.stdout
    assert _arg(calls[4], "--title") == "RasQberry: Where to Go Next"



@needs_bash
def test_keep_going_opens_the_feedback_form(tmp_path):
    # #30: the feedback address was plain text only; now it opens (on the
    # desktop) or is shown alone (over SSH, as here)
    replies = ["0", "next", "next", "next", "feedback", "ESC", "ESC"]
    proc, calls, _ = _walk(tmp_path, replies)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    keep = calls[4]
    assert _arg(keep, "--title") == "RasQberry: Keep Going"
    assert "Tell us how it went (needs a free GitHub account)" in keep   # #11: no surprise
    assert ("Open this address: https://github.com/JanLahmann/RasQberry-Two/issues/new"
            "?template=demo-feedback.yml&demo=learning-paths/first-15-minutes") in proc.stdout


@needs_bash
def test_the_list_opens_the_feedback_form(tmp_path):
    proc, _, _ = _walk(tmp_path, ["feedback", "ESC"])
    assert proc.returncode == 0, proc.stderr
    assert "Open this address: https://github.com/" in proc.stdout


@needs_bash
def test_the_window_title_comes_back_after_a_demo(tmp_path):
    # #30: the window kept the title of the last demo ("LED Demos")
    proc, _, started, out = _walk(tmp_path, ["0", "start", "ESC", "ESC"], tty_out=True)
    assert proc.returncode == 0, out
    assert started == ["rq_demo_run.sh led-demos ibm-logo"]
    ours, theirs = "\033]0;Learning paths\007", "\033]0;LED Demos\007"
    assert theirs in out and out.rindex(ours) > out.rindex(theirs), repr(out)


@needs_bash
def test_a_page_on_the_desktop_says_where_this_window_is(tmp_path):
    # Chromium opens maximised over the learning path's window (#15)
    hint = "The browser covers this window: to get back here, click it in the taskbar."
    proc, _, started = _walk(tmp_path, ["feedback", "ESC"], desktop=True)
    assert proc.returncode == 0, proc.stderr
    assert any(line.startswith("browser ") and "demo=learning-paths" in line for line in started), started
    assert hint in proc.stdout
    # the third step of "Your first program" is a page
    (tmp_path / "step").mkdir()
    proc, _, started = _walk(tmp_path / "step", ["3", "next", "next", "start", "ESC", "ESC"], desktop=True)
    assert proc.returncode == 0, proc.stderr
    assert any("quantum.cloud.ibm.com/learning" in line for line in started), started
    assert hint in proc.stdout
    # over SSH no browser opens, and nothing is said about one
    (tmp_path / "ssh").mkdir()
    proc, _, _ = _walk(tmp_path / "ssh", ["feedback", "ESC"])
    assert "Open this address:" in proc.stdout and hint not in proc.stdout
