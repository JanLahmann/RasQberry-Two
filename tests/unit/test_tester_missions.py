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


def _by_id():
    return {m["id"]: m for m in _missions()["missions"]}


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
    # only doQumentation waits for a later round (Jan, 2026-10-15)
    assert postponed == {"doqumentation"}
    assert "demo-qiskit-tutorials" in _by_id()


def test_fun_with_quantum_has_one_mission_per_part():
    manifest = json.load(open(os.path.join(_ROOT, "RQB2-config", "demo-manifests",
                                           "rq_demo_fun-with-quantum.json")))
    parts = [m for m in _missions()["missions"] if m.get("demo") == "fun-with-quantum"]
    assert [m["part"] for m in parts] == [v["id"] for v in manifest["variants"]]
    assert all(m["group"] == "fwq" for m in parts)


def test_everything_is_beta_but_three():
    # no mission was tested by people yet, except these three (Jan, 2026-10-15)
    not_beta = {mid for mid, m in _by_id().items() if m.get("maturity") != "beta"}
    assert not_beta == {"demo-grok-bloch-web", "demo-composer", "demo-ibm-courses"}
    page = open(os.path.join(_DIR, "testing.md")).read()
    assert page.count("Early beta, not yet tested by people") == len(_by_id()) - 3


def test_every_mission_has_a_group_and_no_group_is_empty():
    data = _missions()
    groups = [g["id"] for g in data["groups"]]
    assert groups == ["core", "user", "advanced", "led", "big", "fwq", "learn", "other"]
    used = [m["group"] for m in data["missions"]]
    assert set(used) <= set(groups)
    for g in groups:
        assert g in used, f"group {g} is empty"
    # missions come group by group, in the groups' order
    assert used == sorted(used, key=groups.index)


def test_demo_groups_follow_the_rules():
    m = _by_id()
    # outside services (IBM, SAP) - also an LED demo of SAP's
    for mid in ("demo-composer", "demo-ibm-courses", "demo-ibm-tutorials", "demo-quantum-lab",
                "demo-sap-quantum-learning", "demo-sap-quantum-led"):
        assert m[mid]["group"] == "other", mid
    for mid in ("demo-led-demos", "demo-led-painter", "demo-quantum-lights-out",
                "demo-quantum-raspberry-tie", "demo-rasq-led"):
        assert m[mid]["group"] == "led", mid
    for mid in ("demo-entangible", "demo-racetraq", "demo-qoffee-maker", "demo-quantum-mixer"):
        assert m[mid]["group"] == "big", mid
    for mid in ("demo-quantum-paradoxes", "demo-quantum-fractals", "demo-grok-bloch",
                "demo-grok-bloch-web", "demo-qiskit-tutorials"):
        assert m[mid]["group"] == "learn", mid
    assert m["hotspot"]["group"] == "advanced" and m["hotspot"]["status"] == "coming"


def test_missions_name_goals_not_steps():
    for m in _missions()["missions"]:
        goal = m["goal"]
        assert goal.endswith(".") and goal.count(". ") == 0, m["id"]
        assert len(goal) <= 120, m["id"]
        assert not re.search(r"(^|\s)(\d+[.)]|step \d|first,|then click|click on|>\s)", goal, re.I), m["id"]


def test_missions_are_unique_and_complete():
    data = _missions()
    ids = [m["id"] for m in data["missions"]]
    assert len(ids) == len(set(ids))
    for m in data["missions"]:
        assert m["title"] and m["group"] and isinstance(m["needs"], list), m["id"]
        assert set(m["needs"]) <= set(data["needs_keys"]), m["id"]
    for fn in ("first-start", "setup-checklist", "led-setup", "ab-update", "standard-update",
               "wifi", "sound", "catalogue", "desktop-groups", "touch", "remote", "whats-new",
               "ibm-account", "learning-paths", "my-programs", "help", "hotspot"):
        assert fn in ids, fn
