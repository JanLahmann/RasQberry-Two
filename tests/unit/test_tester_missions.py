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
    # the rest as the Pi's folders (mission sweep 2026-10-16)
    for mid in ("demo-led-demos", "demo-led-painter", "demo-quantum-lights-out",
                "demo-quantum-raspberry-tie", "demo-rasq-led"):
        assert m[mid]["group"] == "led", mid
    for mid in ("demo-entangible", "demo-racetraq", "demo-qoffee-maker", "demo-quantum-mixer"):
        assert m[mid]["group"] == "big", mid
    for mid in ("demo-quantum-paradoxes", "demo-quantum-fractals"):
        assert m[mid]["group"] == "fwq", mid
    for mid in ("demo-grok-bloch", "demo-grok-bloch-web", "demo-qiskit-tutorials"):
        assert m[mid]["group"] == "learn", mid
    assert m["hotspot"]["group"] == "advanced" and m["hotspot"]["status"] == "coming"


def test_group_titles_are_the_pis_folders():
    folders = {g["title"] for g in json.load(open(os.path.join(
        _ROOT, "RQB2-config", "demo-manifests", "demo-groups.json")))["groups"]}
    titles = {g["id"]: g["title"] for g in _missions()["groups"]}
    for gid in ("led", "big", "fwq", "learn"):
        assert titles[gid] in folders, gid
    # "other" spans two folders, so it must not sound like one of them
    assert titles["other"] not in folders


def test_needs_match_what_the_pi_asks_for():
    m = _by_id()
    # Docker demos: the Pi stops them on a 16 GB card and tags them "32 GB" in the menu
    for mid in ("demo-qoffee-maker", "demo-quantum-mixer", "demo-quantum-lab",
                "demo-qiskit-tutorials", "demo-racetraq"):
        assert "big-card" in m[mid]["needs"], mid
    for mid in ("demo-grok-bloch", "demo-quantum-fractals", "demo-entangible"):
        assert "big-card" not in m[mid]["needs"], mid
    # catalogue demos: from their rqb-demo.json at the pinned commit
    assert "display" in m["demo-racetraq"]["needs"]
    assert "display" in m["demo-sap-quantum-learning"]["needs"]
    # most IBM tutorials, Hello world too, run on IBM hardware
    assert {"internet", "ibm-account"} <= set(m["demo-ibm-tutorials"]["needs"])
    # not in beta-2026-10-10: Entangible and the sound delay
    assert "dev-image" in m["demo-entangible"]["needs"] and "dev-image" in m["sound"]["needs"]
    assert "internet" in m["whats-new"]["needs"]
    for mission in _missions()["missions"]:
        assert len(mission["needs"]) == len(set(mission["needs"])), mission["id"]


def test_only_a_demo_that_requires_sound_needs_a_speaker():
    """"none" is the schema's default (review D7), "optional" works without."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("tester_missions", _GEN)
    tm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tm)
    for audio, needs in (("none", []), ("optional", []), ("required", ["bluetooth-speaker"])):
        assert tm.demo_needs({"needs_hw": {"audio": audio}}) == needs, audio
    assert tm.demo_needs({"needs_hw": {}}) == []


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
