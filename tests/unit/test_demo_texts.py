"""
User test 2026-10-04: texts outside the demos that must say what the demos
really are - Quantum Lights Out is a self-running Grover solver, not a game to
play (#13); the setup's last screen points to the First 15 minutes learning
path (#30).
"""

import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_MANIFESTS = os.path.join(_CFG, "demo-manifests")
_BOOKMARKS = os.path.join(_CFG, "desktop-bookmarks")


def _read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def _manifest(demo_id):
    return json.loads(_read(_MANIFESTS, f"rq_demo_{demo_id}.json"))


def _desktop(name):
    entry = {}
    for line in _read(_BOOKMARKS, name).splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            entry.setdefault(key, value)
    return entry


# --- #13: Quantum Lights Out -------------------------------------------------------

def test_lights_out_is_nowhere_called_a_game_to_play():
    for top in (_BIN, _CFG):
        for dirpath, _, files in os.walk(top):
            if "demo-patches" in dirpath:
                continue   # the demo itself
            for name in files:
                if name.endswith((".sh", ".py", ".json", ".desktop", ".md")):
                    text = _read(dirpath, name)
                    assert "puzzle game" not in text, os.path.join(dirpath, name)


def test_lights_out_says_grover_solves_it():
    m = _manifest("quantum-lights-out")
    assert "Grover" in m["description"] and m["category"] != "game", m["description"]
    assert "game" not in m["keywords"] and "game" not in m["install"]["download"]["what"]
    comment = _desktop("quantum-lights-out.desktop")["Comment"]
    assert "Grover" in comment and "game" not in comment.lower()
    menu = _read(_CFG, "RQB2_menu.sh")
    qlo = menu[menu.index("do_select_qlo_option() {"):]
    qlo = qlo[:qlo.index("\n}\n")]
    assert '"Options"' not in qlo and "Grover's search solves Lights Out puzzles" in qlo


# --- #30: where to start after the setup -------------------------------------------

def test_setup_done_recommends_the_first_path():
    # the setup's last screen named Quantum Lights Out ("a puzzle game") and
    # Fractals; the website starts with the First 15 minutes path
    text = _read(_BIN, "rq_firstlogin.sh")
    done = text[text.index('"Done.'):]
    done = done[:done.index("$REOPEN")]
    first = json.loads(_read(_MANIFESTS, "learning-paths.json"))["paths"][0]["title"]
    assert f'\\"{first}\\"' in done and "Learning paths icon" in done
    assert "Lights Out" not in done and "Fractals" not in done
    # 15 lines high, 74 wide: the text fits without scrolling
    body = re.sub(r'\\"', '"', done[1:]).rstrip() + "\n\n" + \
        "Open this list again: the RasQberry Setup icon, or sudo raspi-config -> 0 RasQberry -> Setup Checklist."
    lines = sum(max(1, -(-len(line) // 70)) for line in body.split("\n"))
    assert lines <= 15 - 7, body
