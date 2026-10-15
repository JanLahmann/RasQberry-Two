"""
Tester missions (docs/testing): one per demo and one per function, goals
only - testers find the way with the documentation and the helper.
"""

import glob
import json
import os
import re
import subprocess

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DIR = os.path.join(_ROOT, "docs", "testing")
_GEN = os.path.join(_DIR, "tester_missions.py")


def _missions():
    return json.load(open(os.path.join(_DIR, "tester-missions.json")))


def test_files_are_up_to_date():
    proc = subprocess.run(["python3", _GEN, "--check"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_every_demo_has_a_mission():
    data = _missions()
    postponed = set(data["postponed"])
    covered = {m["demo"] for m in data["missions"] if "demo" in m}
    shipped = set()
    for path in glob.glob(os.path.join(_ROOT, "RQB2-config", "demo-manifests", "rq_demo_*.json")):
        if not path.endswith("rq_demo_schema.json"):
            shipped.add(json.load(open(path))["id"])
    catalogue = {d["id"] for d in json.load(open(os.path.join(_ROOT, "RQB2-config", "known-demos.json")))["demos"]}
    missing = sorted((shipped | catalogue) - postponed - covered)
    assert not missing, f"demos without a mission: {missing}"
    # doQumentation waits for a later round (Jan, 2026-10-15)
    assert {"doqumentation", "qiskit-tutorials"} <= postponed


def test_fun_with_quantum_has_one_mission_per_part():
    manifest = json.load(open(os.path.join(_ROOT, "RQB2-config", "demo-manifests",
                                           "rq_demo_fun-with-quantum.json")))
    parts = {m["part"] for m in _missions()["missions"] if m.get("demo") == "fun-with-quantum"}
    assert parts == {v["id"] for v in manifest["variants"]}
    assert "coin-game" in parts


def test_beta_demos_are_marked():
    data = _missions()
    beta = {m["id"] for m in data["missions"] if m.get("maturity") == "beta"}
    # from the manifests (and their variants), known-demos.json and learning-paths.json
    for mid in ("demo-entangible", "demo-racetraq", "demo-fun-with-quantum-website",
                "demo-fun-with-quantum-family", "learning-paths"):
        assert mid in beta, mid
    assert "demo-fun-with-quantum-coin-game" not in beta
    page = open(os.path.join(_DIR, "testing.md")).read()
    assert page.count("Early beta, not yet tested by people") == len(beta)


def test_missions_name_goals_not_steps():
    for m in _missions()["missions"]:
        goal = m["goal"]
        assert goal.endswith(".") and goal.count(". ") == 0, m["id"]
        assert len(goal) <= 120, m["id"]
        assert not re.search(r"(^|\s)(\d+[.)]|step \d|first,|then click|click on|>\s)", goal, re.I), m["id"]


def test_missions_are_unique_and_complete():
    missions = _missions()["missions"]
    ids = [m["id"] for m in missions]
    assert len(ids) == len(set(ids))
    for m in missions:
        assert m["title"] and m["area"] and isinstance(m["needs"], list), m["id"]
    for fn in ("first-start", "setup-checklist", "led-setup", "ab-update", "standard-update",
               "wifi", "sound", "catalogue", "desktop-groups", "touch", "remote", "whats-new",
               "ibm-account", "learning-paths", "my-programs", "help", "hotspot"):
        assert fn in ids, fn
