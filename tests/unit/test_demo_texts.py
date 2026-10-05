"""
User test 2026-10-04: the setup's last screen points to the First 15 minutes
learning path (#30).
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
