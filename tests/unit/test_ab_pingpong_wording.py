"""
Ping-pong A/B updates (Jan, 2026-10-04): the words of the old model are gone.

- PROMOTE (copying Slot B to Slot A) does not exist any more: no command, menu
  entry, help text, log or doc mentions it.
- No slot has a role name. "stable" stays as the name of a release stream
  ("beta or stable", "Stable releases", "1.10.0 (stable)"), but never labels
  a slot: not "Slot A (stable)", "Slot B (testing)", "the stable system", ...
"""

import os
import re

import pytest

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
_DIRS = ["RQB2-bin", "RQB2-config", "RQB2-system", "docs"]
# ab-boot-validation.md is the dated test log of the old model: history
_HISTORY = {os.path.join("docs", "ab-boot-validation.md")}


def _files():
    for d in _DIRS:
        for base, _, names in os.walk(os.path.join(_ROOT, d)):
            for name in names:
                path = os.path.join(base, name)
                rel = os.path.relpath(path, _ROOT)
                if rel in _HISTORY or name.endswith((".png", ".jpg", ".svg", ".ico", ".pyc")):
                    continue
                try:
                    with open(path, encoding="utf-8") as f:
                        yield rel, f.read()
                except UnicodeDecodeError:
                    continue


def _hits(pattern):
    rx = re.compile(pattern, re.IGNORECASE)
    return [f"{rel}:{n}: {line.strip()}"
            for rel, text in _files()
            for n, line in enumerate(text.splitlines(), 1)
            if rx.search(line)]


def test_promote_is_gone():
    assert _hits(r"\bpromot") == []


def test_no_typed_update_stable_confirmation():
    assert _hits(r"UPDATE STABLE|update-stable|STABLE_SLOT") == []


@pytest.mark.parametrize("pattern", [
    r"slot [ab] \((stable|testing)",       # "Slot A (stable)", "Slot B (testing, running)"
    r"slot [ab] = (stable|testing)",
    r"\b(stable|testing) slot\b",          # "the stable slot", "testing slot"
    r"slot [ab] is (the )?(stable|for testing|testing)",
    r"\bthe stable (system|one|fallback|baseline)",
    r"\bstable fallback\b",
    r"\"testing\" only says",
    r"slot_label",
])
def test_no_slot_is_called_stable_or_testing(pattern):
    assert _hits(pattern) == []


def test_stable_as_a_stream_is_still_there():
    # the guard and the release picker need the word
    assert _hits(r"beta or stable")
    assert _hits(r"Stable releases")
