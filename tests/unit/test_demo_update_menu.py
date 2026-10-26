"""
Update demos (rq_demo_update.sh), user test 2026-10-26: no technical tags,
no full SHAs or digests glued to the date, nothing cut off at 80 columns,
and a first entry that checks all demos at once.
"""

import os
import shutil
import subprocess

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_SCRIPT = os.path.join(_BIN, "rq_demo_update.sh")

needs_tools = pytest.mark.skipif(shutil.which("bash") is None or shutil.which("jq") is None,
                                 reason="bash and jq are required")


def _helpers(code):
    """Run CODE with the script's menu-text helpers (between the markers)."""
    text = open(_SCRIPT).read()
    start = text.index("# --- menu texts")
    end = text.index("# --- end of menu texts ---")
    names = text[text.index("join_names() {"):text.index("# The other shipped demos")]
    script = text[start:end] + names + "\n" + code
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True).stdout


def test_short_id_prefers_a_named_tag_then_seven_characters():
    digest = "ghcr.io/x/y@sha256:" + "ab12cd34" * 8
    assert _helpers(f'short_id "jupyter (latest), 2.5-xl-20261008" "{digest}"').strip() == "2.5-xl-20261008"
    assert _helpers(f'short_id "4c3021af{"0" * 32}" "{digest}"').strip() == "4c3021a"
    assert _helpers(f'short_id "-" "{digest}"').strip() == "ab12cd3"


def test_a_version_line_is_short_and_spaced():
    line = _helpers('version_item 2026-10-23 4c3021a 1890 "release, tested" "Qiskit 2.5.2, commit 1234567"')
    assert line.startswith("2026-10-23  4c3021a  ~1890 MB  release, tested  Qiskit")
    assert len(line.rstrip("\n")) <= 68
    assert _helpers("fit " + "x" * 80).strip().endswith("...")


def test_the_ibm_pair_is_named_without_repeating_words():
    assert _helpers('join_names "IBM Quantum Courses" "IBM Quantum Tutorials"').strip() == \
        "IBM Quantum Courses and Tutorials"
    assert _helpers('join_names "Quantum Coin Game" "GHZ Game"').strip() == "Quantum Coin Game and GHZ Game"


def test_the_pickers_hide_their_tags_and_say_what_choosing_does():
    text = open(_SCRIPT).read()
    assert text.count('whiptail --title') == text.count('--notags --menu') == 4
    assert "The one you choose is downloaded and used from the next start." in text
    assert "The one you choose is installed now" in text
    assert 'CHECK "Check all for newer versions"' in text


@needs_tools
def test_the_menu_starts_with_check_all_and_fits_80_columns(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    log = tmp_path / "wt.log"
    wt = stubs / "whiptail"
    wt.write_text(f'#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done >> "{log}"\nexit 1\n')
    wt.chmod(0o755)
    home = tmp_path / "home"
    for wd in ("ibm-quantum-learning", "grok-bloch", "fun-with-quantum"):
        (home / "RasQberry-Two" / "demos" / wd / ".git").mkdir(parents=True)
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(f'USER_HOME="{home}"\nREPO=RasQberry-Two\nBIN_DIR="{_BIN}"\nSTD_VENV=RQB2\n')
    env = {"PATH": f"{stubs}:{os.environ['PATH']}", "HOME": str(home), "RQ_CONFIG_FILE": str(env_config)}
    proc = subprocess.run(["bash", _SCRIPT], capture_output=True, text=True, env=env, timeout=120,
                          stdin=subprocess.DEVNULL)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    args = log.read_text().splitlines()
    menu = args[args.index("--menu") + 5:]
    tags, items = menu[0::2], menu[1::2]
    assert tags[0] == "CHECK" and items[0] == "Check all for newer versions"
    assert all(t.isdigit() for t in tags[1:]), tags
    assert "IBM Quantum Courses and Tutorials (notebooks): as released" in items
    assert all(len(i) <= 68 for i in items), items


def _newer_text(stubs, key):
    text = open(_SCRIPT).read()
    fn = text[text.index("newer_text() {"):]
    fn = fn[:fn.index("\n}\n") + 3]
    return subprocess.run(["bash", "-c", stubs + "\n" + fn + f'\nnewer_text {key} mf || echo NONE'],
                          capture_output=True, text=True).stdout.strip()


def test_check_all_names_only_what_is_newer():
    base = ('current_pin() { echo cur; }; rq_demo_repo() { echo url; }; '
            'image_versions() { printf "new\\t-\\t2026-10-23\\t1890\\t-\\tnewer\\ncur\\t-\\t2026-10-01\\t1800\\t-\\tcurrent\\n"; }; ')
    assert _newer_text(base + "tested_pin() { :; }", "lab:image") == "newer version from 2026-10-23"
    assert _newer_text(base + "tested_pin() { echo new; }", "lab:image") == \
        "newer version from 2026-10-23, tested update"
    same = ('current_pin() { echo cur; }; rq_demo_repo() { echo url; }; tested_pin() { :; }; '
            'image_versions() { printf "cur\\t-\\t2026-10-01\\t1800\\t-\\tcurrent\\n"; }; '
            'git() { printf "cur\\tHEAD\\n"; }')
    assert _newer_text(same, "lab:image") == "NONE"
    assert _newer_text(same, "games:ref") == "NONE"
    assert _newer_text(same.replace('printf "cur\\tHEAD', 'printf "head\\tHEAD'), "games:ref") == \
        "newer version on GitHub"
