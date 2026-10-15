#!/usr/bin/env python3
"""
Tester missions: one per demo and one per function of RasQberry Two.

A mission names a goal, never the steps: testers use the user documentation
and the RasQberry helper, so gaps in either show up as findings. The demo
missions come from the demo manifests (shipped demos) and known-demos.json
(catalogue demos), so a new demo gets a mission without anyone writing one.

Writes, next to this script:
  tester-missions.json   the list, for the tester page and the helper bot
  testing.md             the draft tester page for rasqberry.org/testing
                         (gh-pages: content/testing.md)

Usage: python3 docs/testing/tester_missions.py [--check]
  --check   exit 1 when the written files are out of date (tests use it)
"""

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
MANIFESTS = os.path.join(ROOT, "RQB2-config", "demo-manifests")
CATALOGUE = os.path.join(ROOT, "RQB2-config", "known-demos.json")
GROUPS = os.path.join(MANIFESTS, "demo-groups.json")
OUT_JSON = os.path.join(HERE, "tester-missions.json")
OUT_PAGE = os.path.join(HERE, "testing.md")

# Postponed for this round (Jan, 2026-10-15): doQumentation, and the
# tutorials it serves on the Pi itself
POSTPONED = {"doqumentation", "qiskit-tutorials"}

# Goal sentences for the demos; a demo without one gets GENERIC_GOAL
DEMO_GOALS = {
    "composer": "Build a circuit in the IBM Quantum Composer and simulate it.",
    "entangible": "Build a circuit with the printed gate tiles and let the camera read it.",
    "fun-with-quantum": "Play the Fun with Quantum games in Jupyter.",
    "grok-bloch": "Move a qubit around the Bloch sphere and follow the gates.",
    "grok-bloch-web": "Explore the Bloch sphere in the web version.",
    "ibm-courses": "Open an IBM Quantum course and run its first code cells.",
    "ibm-tutorials": "Open an IBM Quantum tutorial and run its code cells.",
    "led-demos": "Try the LED demos: text, logos and colour effects on the LED panel.",
    "led-painter": "Paint a picture and show it on the LED panel.",
    "qoffee-maker": "Order a coffee from a quantum computer, with or without a Home Connect machine.",
    "quantum-fractals": "Watch the fractals change with the state of a qubit.",
    "quantum-lab": "Start the Quantum Lab and run a notebook.",
    "quantum-lights-out": "Watch Grover's search solve Lights Out, on the LED panel and in the console.",
    "quantum-mixer": "Mix a colour with a quantum circuit.",
    "quantum-paradoxes": "Work through one of the quantum paradox notebooks.",
    "quantum-raspberry-tie": "Show measured qubits on the LED panel, from the simulator and from a real quantum computer.",
    "rasq-led": "Show superposition and entanglement on the LED panel.",
    "racetraq": "Race a car steered by a quantum agent and train your own.",
    "sap-quantum-learning": "Take the quiz and build a circuit in SAP Quantum Learning.",
    "sap-quantum-led": "Show the SAP logo on the LED panel, coloured by three qubits.",
}
GENERIC_GOAL = "Start {name}, find out what it shows, and stop it again."

# Missions that are not one demo. Names as the user sees them (menu,
# desktop, website). needs: what the tester must have.
FUNCTIONS = [
    # Setup
    ("first-start", "Setup", "First start",
     "Install RasQberry with Raspberry Pi Imager, with your own user name, password and Wi-Fi, and reach the desktop.",
     []),
    ("setup-checklist", "Setup", "Setup Checklist",
     "Finish the Setup Checklist: every item done or skipped.", []),
    ("led-setup", "Setup", "LED panel setup",
     "Set up the LED panel: find its layout, check it, and set the brightness.", ["led-panel"]),
    ("download-all", "Setup", "Download all demos",
     "Download all demos, then start a few without internet.", ["internet"]),
    # Using the Pi
    ("desktop-groups", "Using the Pi", "Desktop folders and menu",
     "Find each demo through its desktop folder and through the RasQberry menu.", []),
    ("led-views", "Using the Pi", "LED views without a panel",
     "Watch an LED demo in the on-screen view and in the browser view.", []),
    ("demo-loop", "Using the Pi", "Demo Loop",
     "Run the Demo Loop with demos of your choice, and let it start at login.", []),
    ("learning-paths", "Using the Pi", "Learning paths",
     "Follow one learning path from start to end.", []),
    ("my-programs", "Using the Pi", "My Quantum Programs",
     "Write and run your own quantum program in My Quantum Programs.", []),
    ("touch", "Using the Pi", "Touchscreen",
     "Use the Pi by touch only: touch mode and the on-screen keyboard.", ["touchscreen"]),
    ("sound", "Using the Pi", "Sound on a Bluetooth speaker",
     "Pair a Bluetooth speaker, play a demo with sound and calibrate the sound delay.",
     ["bluetooth-speaker", "led-panel"]),
    ("help", "Using the Pi", "Help and feedback",
     "Get help for a problem from the Pi: System Info, the helper and the website.", []),
    # Demos from elsewhere
    ("catalogue", "Demos from the catalogue", "Add, update and remove a demo",
     "Add a demo from the catalogue, update it, and remove it again.", ["internet"]),
    # Updates
    ("ab-update", "Updates", "Update to a new release",
     "Install a newer release into the other system, start it, and go back to the old one.",
     ["internet", "ab-image"]),
    ("whats-new", "Updates", "Slot icon and What's new",
     "Use the slot icon in the taskbar and read What's new after an update.", ["ab-image"]),
    ("standard-update", "Updates", "Updates on the single-system image",
     "Check for a newer image on the single-system image and follow what the Pi suggests.",
     ["internet", "single-image"]),
    # Connections
    ("wifi", "Connections", "Wi-Fi",
     "Join a Wi-Fi network, and see the Pi come back after the router restarts.", []),
    ("remote", "Connections", "Remote access",
     "Reach the Pi from another computer: SSH, VNC and Raspberry Pi Connect.", ["internet"]),
    ("ibm-account", "Connections", "IBM Quantum account",
     "Save your IBM Quantum API key and run a demo on a real quantum computer.",
     ["internet", "ibm-account"]),
    ("hotspot", "Connections", "Wi-Fi hotspot",
     "Let phones and laptops join the Pi's own Wi-Fi and open its demos.", [],
     "coming"),
]

AREA_ORDER = ["Setup", "Using the Pi", "Connections", "Updates", "Demos from the catalogue"]

NEEDS_TEXT = {
    "led-panel": "LED panel",
    "touchscreen": "touchscreen",
    "bluetooth-speaker": "Bluetooth speaker",
    "internet": "internet",
    "ibm-account": "IBM Quantum account",
    "ab-image": "A/B image",
    "single-image": "single-system image",
    "display": "screen",
    "docker": "space for Docker images",
}


def demo_needs(manifest):
    """
    Hardware and accounts a demo needs, from its manifest.

    Args:
        manifest (dict): a demo manifest or catalogue entry

    Returns:
        list: needs keys (see NEEDS_TEXT)
    """
    hw = manifest.get("needs_hw") or {}
    needs = []
    if hw.get("leds") is True or manifest.get("leds") is True:
        needs.append("led-panel")
    if hw.get("display") == "required":
        needs.append("display")
    if hw.get("network") is True:
        needs.append("internet")
    if hw.get("audio"):
        needs.append("bluetooth-speaker")
    if manifest.get("needs_ibm_token") == "require":
        needs.append("ibm-account")
    return needs


def build():
    """
    The mission list.

    Returns:
        dict: {"_doc", "postponed", "missions": [...]}
    """
    groups = {g["id"]: g["title"] for g in json.load(open(GROUPS))["groups"]}
    missions = []
    shipped = []
    for path in sorted(glob.glob(os.path.join(MANIFESTS, "rq_demo_*.json"))):
        if path.endswith("rq_demo_schema.json"):
            continue
        m = json.load(open(path))
        if m["id"] in POSTPONED:
            continue
        shipped.append(m["id"])
        missions.append({
            "id": "demo-" + m["id"],
            "area": "Demos: " + groups.get(m.get("group"), "Learn & code"),
            "title": m["name"],
            "goal": DEMO_GOALS.get(m["id"], GENERIC_GOAL.format(name=m["name"])),
            "needs": demo_needs(m),
            "demo": m["id"],
        })
    for entry in json.load(open(CATALOGUE))["demos"]:
        if entry["id"] in POSTPONED or entry["id"] in shipped:
            continue
        name = entry.get("name") or entry["id"]
        missions.append({
            "id": "demo-" + entry["id"],
            "area": "Demos: " + groups.get(entry.get("group"), "Contributed demos"),
            "title": name,
            "goal": DEMO_GOALS.get(entry["id"], GENERIC_GOAL.format(name=name)),
            "needs": ["internet"] + demo_needs(entry),
            "demo": entry["id"],
            "catalogue": True,
        })
    for item in FUNCTIONS:
        mid, area, title, goal, needs = item[:5]
        mission = {"id": mid, "area": area, "title": title, "goal": goal, "needs": list(needs)}
        if len(item) > 5:
            mission["status"] = item[5]
        missions.append(mission)

    demo_areas = ["Demos: " + groups[g] for g in groups]
    order = AREA_ORDER[:1] + demo_areas + AREA_ORDER[1:]
    fn_order = [f[0] for f in FUNCTIONS]
    # areas in order; functions as listed (first start first), demos by name
    missions.sort(key=lambda m: (order.index(m["area"]) if m["area"] in order else len(order),
                                 fn_order.index(m["id"]) if m["id"] in fn_order else 0,
                                 m["title"].lower()))
    return {
        "_doc": ("Tester missions, generated by docs/testing/tester_missions.py from the demo "
                 "manifests, known-demos.json and its list of functions. A mission names a goal, "
                 "never the steps: testers use the user documentation and the RasQberry helper. "
                 "needs: what a tester must have, as keys of needs_keys, so the tester helper "
                 "can match missions to a tester's setup; status coming: not in the images yet."),
        "needs_keys": NEEDS_TEXT,
        "postponed": sorted(POSTPONED),
        "missions": missions,
    }


def page(data):
    """
    The draft tester page (Markdown, as the website's other pages).

    Args:
        data (dict): from build()

    Returns:
        str: the page
    """
    lines = [
        "# Testing RasQberry Two",
        "",
        "Thank you for helping us test RasQberry Two! About ten testers try every demo and",
        "every function on their own Pis, so we find what breaks and what is hard to follow.",
        "",
        "## How it works",
        "",
        "- **Talk to the tester helper** (bottom right on this page). Tell it your Pi model, your",
        "  hardware (LED panel, touchscreen, Bluetooth speaker) and which demos you like, and it",
        "  suggests missions that fit. Choose your own tester name or ID, so it can keep track of",
        "  your missions. The tester passphrase unlocks it: <!-- TODO: shared passphrase -->.",
        "- **Do the mission on your own.** A mission is a goal, not a recipe. Find your way with",
        "  the [documentation](/) and the normal RasQberry helper on the Pi's start page, as any",
        "  user would. The tester helper does not help with the mission itself; it points you",
        "  there. Where the documentation or the helper leaves you stuck, that is a finding too.",
        "- **Report back to the tester helper:** what worked, what didn't, confusing words, slow",
        "  steps, ideas. It writes it down for us, and we follow up on GitHub.",
        "",
        "## What is recorded",
        "",
        "<!-- TODO (Jan): check the wording once the tester helper is set up. -->",
        "The tester helper keeps your conversation, with your tester name or ID, your Pi model,",
        "hardware and RasQberry version, for 90 days. It stores no IP address and no cookies.",
        "Use any tester name you like; it does not need to be your real name.",
        "",
        "## Missions",
    ]
    current = None
    for m in data["missions"]:
        if m["area"] != current:
            current = m["area"]
            lines += ["", f"### {current}", ""]
        needs = ", ".join(NEEDS_TEXT.get(n, n) for n in m["needs"])
        extra = []
        if needs:
            extra.append(f"needs: {needs}")
        if m.get("status") == "coming":
            extra.append("coming soon")
        tail = f" *({'; '.join(extra)})*" if extra else ""
        lines.append(f"- **{m['title']}**: {m['goal']}{tail}")
    lines += ["", "Postponed to a later round: the Workshop & Qiskit Server and the Qiskit",
              "Tutorials on this Pi (doQumentation).", ""]
    return "\n".join(lines)


def main():
    """Write (or with --check, compare) the mission list and the page."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="fail when the files are out of date")
    args = parser.parse_args()
    data = build()
    outputs = {OUT_JSON: json.dumps(data, indent=2, ensure_ascii=False) + "\n", OUT_PAGE: page(data)}
    stale = []
    for path, text in outputs.items():
        old = open(path).read() if os.path.exists(path) else None
        if old != text:
            stale.append(os.path.basename(path))
            if not args.check:
                with open(path, "w") as f:
                    f.write(text)
    if args.check and stale:
        print(f"Out of date: {', '.join(stale)}. Run: python3 docs/testing/tester_missions.py",
              file=sys.stderr)
        return 1
    if not args.check:
        print(f"{len(data['missions'])} missions" + (f"; wrote {', '.join(stale)}" if stale else "; up to date"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
