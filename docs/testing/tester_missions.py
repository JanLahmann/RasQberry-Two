#!/usr/bin/env python3
"""
Tester missions: one per demo and one per function of RasQberry Two.

A mission names a goal, never the steps: testers use the user documentation
and the RasQberry helper, so gaps in either show up as findings. The demo
missions come from the demo manifests (shipped demos) and known-demos.json
(catalogue demos), so a new demo gets a mission - and a group - without
anyone writing one.

Writes, next to this script:
  tester-missions.json   the list, for the tester page and the tester helper
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
OUT_JSON = os.path.join(HERE, "tester-missions.json")
OUT_PAGE = os.path.join(HERE, "testing.md")

# Postponed for this round (Jan, 2026-10-15)
POSTPONED = {"doqumentation"}

# The groups, in the page's order (Jan, 2026-10-15). The demo groups are
# named as the Pi's folders they match (mission sweep 2026-10-16), except
# "other", which the Pi spreads over Learn & code and Contributed demos.
GROUPS = [
    ("core", "Core RasQberry"),
    ("user", "RasQberry user"),
    ("advanced", "RasQberry advanced configuration"),
    ("led", "LED panel"),
    ("big", "Big projects"),
    ("fwq", "Play"),
    ("learn", "Learn & code"),
    ("other", "IBM and partner demos"),
]

# Group rules for demos, in this order:
#   other: a service from outside (IBM, SAP) - not "written by someone else".
#          Catalogue entries name it in "provider"; the shipped manifests
#          have no such field, so their outside services are listed here.
#   else:  the Pi's folder (the manifest's or catalogue entry's "group", see
#          demo-groups.json): LED panel, Play (Fun with Quantum, paradoxes,
#          fractals), Big projects, Learn & code; a catalogue entry without
#          one goes to Contributed demos, as on the Pi
OUTSIDE_SERVICES = {"composer", "ibm-courses", "ibm-tutorials", "quantum-lab"}
OWN_PROVIDERS = {"the Fun with Quantum family"}
FOLDER_GROUPS = {"led-panel": "led", "play": "fwq", "projects": "big", "learn": "learn",
                 "contributed": "other"}

# Beta for every mission, whatever the manifests say: no mission has been
# tested by people yet, except these three (Jan, 2026-10-15)
NOT_BETA = {"demo-grok-bloch-web", "demo-composer", "demo-ibm-courses"}
BETA_NOTE = "Early beta, not yet tested by people: expect rough edges."

# Goal sentences for the demos; a demo without one gets GENERIC_GOAL
DEMO_GOALS = {
    "composer": "Build a circuit in the IBM Quantum Composer and simulate it.",
    "entangible": "Build a circuit with the printed gate tiles and let the camera read it.",
    "grok-bloch": "Move a qubit around the Bloch sphere and follow the gates.",
    "grok-bloch-web": "Open the online version from the Pi and move a qubit around the Bloch sphere.",
    "ibm-courses": "Open an IBM Quantum course and run its first code cells.",
    "ibm-tutorials": "Open an IBM Quantum tutorial and run its code cells.",
    "led-demos": "Try the LED demos: text, logos and colour effects on the LED panel.",
    "led-painter": "Paint a picture and show it on the LED panel.",
    "qiskit-tutorials": "Open a tutorial in doQumentation (IBM Quantum Learning on this Pi) and run its code.",
    "qoffee-maker": "Order a coffee from a quantum computer, with or without a Home Connect machine.",
    "quantum-fractals": "Watch the fractals change with the state of a qubit.",
    "quantum-lab": "Start the Qiskit Live and run a notebook.",
    "qubins": "Choose a Qiskit version and the notebooks, start QuBins and run a notebook.",
    "quantum-lights-out": "Watch Grover's search solve Lights Out, on the LED panel and in the console.",
    "quantum-mixer": "Mix a cocktail, an ice cream or a coffee with a quantum circuit.",
    "quantum-paradoxes": "Work through one of the quantum paradox notebooks.",
    "quantum-raspberry-tie": ("Show measured qubits on the LED panel, from the simulator or, with an IBM Quantum "
                              "account, a real quantum computer."),
    "rasq-led": "Show superposition and entanglement on the LED panel.",
    "racetraq": "Race a car steered by a quantum agent and train your own.",
    "sap-quantum-learning": "Take the quiz and build a circuit in SAP Quantum Learning.",
    "sap-quantum-led": "Show the SAP logo on the LED panel, coloured by three qubits.",
}
GENERIC_GOAL = "Start {name}, find out what it shows, and stop it again."

# Titles where the manifest's name is not what the tester finds: the Pi
# shows the online Bloch sphere only as "Online version" in the Grokking
# submenu (its own manifest is hidden)
DEMO_TITLES = {
    "grok-bloch-web": "Grokking the Bloch Sphere: online version",
}

# Demos with one mission per part: the variants of their manifest, named as
# the menu and the variant chooser show them (Fun with Quantum: Jan,
# 2026-10-15). The desktop entry "Quantum Coin Game" opens the coin-game part.
SPLIT_DEMOS = {"fun-with-quantum"}
PART_GOALS = {
    "fun-with-quantum": {
        "readme": "Open the Fun with Quantum start page and pick a game from it.",
        "coin-game": "Play the Quantum Coin Game, first classically, then with the quantum H move.",
        "ghz-game": "Play the GHZ Game and see how quantum players win.",
        "hardys-paradox": "Work through Hardy's Paradox.",
        "mermin-peres": "Play the Mermin–Peres Magic Square.",
        "3-sat": "Solve a 3-SAT problem with Grover's algorithm.",
        "chsh-game": "Play the CHSH Game.",
        "prisoners-dilemma": "Play the Quantum Prisoner's Dilemma.",
        "ghz-real-devices": "Run the GHZ experiment on a real quantum computer.",
        "website": "Play the games in the browser on the Fun with Quantum website, also offline.",
        "family": "Explore the other projects of the Fun with Quantum family.",
    },
}
PART_NEEDS = {"fun-with-quantum": {"ghz-real-devices": ["internet", "ibm-account"],
                                   "family": ["internet"]}}
# Part titles where the variant's name does not fit a title ("Start here:
# what the games are about": the notebook is a list of the games)
PART_TITLES = {"fun-with-quantum": {"readme": "Fun with Quantum: start here"}}

# Missions that are not one demo, in their group's order. Names as the user
# sees them (menu, desktop, website). needs: what the tester must have.
FUNCTIONS = [
    # core
    ("first-start", "core", "First start",
     "Install RasQberry with Raspberry Pi Imager, with your own user name, password and Wi-Fi, and reach the desktop.",
     []),
    ("setup-checklist", "core", "Setup Checklist",
     "Go through the Setup Checklist until its icon leaves the desktop: do each step, or skip it.", []),
    ("desktop-groups", "core", "Desktop folders and menu",
     "Find each demo through its desktop folder and through the RasQberry menu.", []),
    ("wifi", "core", "Wi-Fi",
     "Join a Wi-Fi network, and see the Pi come back after the router restarts.", []),
    ("ab-update", "core", "Update to a new release",
     "Install a release into the other system (a newer one, or the same again), start it, and go back.",
     ["internet", "ab-image"]),
    ("whats-new", "core", "Slot icon and What's new",
     "Use the slot icon in the taskbar and read What's new after an update.",
     ["internet", "ab-image"]),
    ("help", "core", "Help and feedback",
     "Get help for a problem from the Pi: System Info, the helper and the website.", []),
    # user
    ("download-all", "user", "Download all demos",
     "Download all demos, then start a few without internet.", ["internet"]),
    ("demo-loop", "user", "Demo Loop",
     "Run the Demo Loop with demos of your choice, and let it start at login.", []),
    ("learning-paths", "user", "Learning paths",
     "Follow one learning path from start to end.", []),
    ("my-programs", "user", "My Quantum Programs",
     "Write and run your own quantum program in My Quantum Programs.", []),
    ("ibm-account", "user", "IBM Quantum account",
     "Save your IBM Quantum API key and run a demo on a real quantum computer.",
     ["internet", "ibm-account"]),
    ("catalogue", "user", "Add and remove a demo",
     "Add a demo from the catalogue, start it, and remove it again.", ["internet"]),
    ("led-views", "user", "LED views without a panel",
     "Watch an LED demo in the on-screen view and in the browser view.", []),
    ("touch", "user", "Touchscreen",
     "Use the Pi by touch only: touch mode and the on-screen keyboard.", ["touchscreen"]),
    # advanced
    ("led-setup", "advanced", "LED panel setup",
     "Set up the LED panel: find its layout, check it, and set the brightness.", ["led-panel"]),
    ("sound", "advanced", "Sound on a Bluetooth speaker",
     "Pair a Bluetooth speaker and calibrate the sound delay until tick and LED flash come together.",
     ["bluetooth-speaker", "led-panel", "dev-image"]),
    ("remote", "advanced", "Remote access",
     "Reach the Pi from another computer: SSH, VNC and Raspberry Pi Connect.", ["internet"]),
    ("hotspot", "advanced", "Wi-Fi hotspot",
     "Let phones and laptops join the Pi's own Wi-Fi and open its demos.", [],
     "coming"),
    ("standard-update", "advanced", "Updates on the single-system image",
     "Check for a newer image on the single-system image and follow what the Pi suggests.",
     ["internet", "single-image"]),
]

NEEDS_TEXT = {
    "led-panel": "LED panel",
    "touchscreen": "touchscreen",
    "bluetooth-speaker": "Bluetooth speaker",
    "internet": "internet",
    "ibm-account": "IBM Quantum account",
    "ab-image": "A/B image on a 64 GB card or larger",
    "single-image": "single-system image",
    "display": "screen",
    "camera": "camera (USB webcam or Pi camera)",
    "big-card": "SD card of 32 GB or more",
    "dev-image": "development image",
}

# Needs the manifests have no field for (yet). Catalogue demos: known-demos.json
# has no needs, so they come from the demo's rqb-demo.json at the pinned commit.
EXTRA_NEEDS = {
    "entangible": ["camera", "dev-image"],  # tiles read by a camera; not in beta-2026-10-10
    "racetraq": ["display", "big-card"],    # rqb-demo.json: display required, a Docker demo
    "sap-quantum-learning": ["display"],    # rqb-demo.json: display required (web page)
    # most tutorials, Hello world too, run on IBM hardware through the saved account
    "ibm-tutorials": ["internet", "ibm-account"],
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
    # "none" (the schema's default) and "optional" need no speaker
    if hw.get("audio") == "required":
        needs.append("bluetooth-speaker")
    if manifest.get("needs_ibm_token") == "required":
        needs.append("ibm-account")
    # a Docker demo: the Pi stops it on a 16 GB card (rq_stop_if_card_too_small),
    # the menu tags it "32 GB" (rq_demo_generate_menu.sh demo_needs)
    entry = manifest.get("entrypoint") or {}
    if entry.get("type") == "docker" or (manifest.get("install") or {}).get("docker_image_of"):
        needs.append("big-card")
    for need in EXTRA_NEEDS.get(manifest.get("id", ""), []):
        if need not in needs:
            needs.append(need)
    return needs


def demo_group(demo_id, manifest, catalogue=False):
    """
    The group of a demo, by the rules above.

    Args:
        demo_id (str): the demo's id
        manifest (dict): its manifest or catalogue entry
        catalogue (bool): a known-demos.json entry (no group: Contributed demos)

    Returns:
        str: a group id
    """
    provider = manifest.get("provider")
    if demo_id in OUTSIDE_SERVICES or (provider and provider not in OWN_PROVIDERS):
        return "other"
    folder = manifest.get("group") or ("contributed" if catalogue else "learn")
    return FOLDER_GROUPS.get(folder, "learn")


def build():
    """
    The mission list.

    Returns:
        dict: {"_doc", "groups", "needs_keys", "postponed", "missions": [...]}
    """
    missions = []
    shipped = []
    for path in sorted(glob.glob(os.path.join(MANIFESTS, "rq_demo_*.json"))):
        if path.endswith("rq_demo_schema.json"):
            continue
        m = json.load(open(path))
        if m["id"] in POSTPONED:
            continue
        shipped.append(m["id"])
        group = demo_group(m["id"], m)
        if m["id"] in SPLIT_DEMOS:
            for v in m.get("variants", []):
                extra = [n for n in PART_NEEDS.get(m["id"], {}).get(v["id"], []) if n not in demo_needs(m)]
                missions.append({
                    "id": f"demo-{m['id']}-{v['id']}",
                    "group": group,
                    # "Fun with Quantum: GHZ Game", as the chooser shows it under its demo
                    "title": PART_TITLES.get(m["id"], {}).get(v["id"]) or (
                        v["name"] if v["name"].startswith(m["name"]) else f"{m['name']}: {v['name']}"),
                    "goal": PART_GOALS.get(m["id"], {}).get(v["id"], GENERIC_GOAL.format(name=v["name"])),
                    "needs": demo_needs(m) + extra,
                    "demo": m["id"],
                    "part": v["id"],
                })
            continue
        missions.append({
            "id": "demo-" + m["id"],
            "group": group,
            "title": DEMO_TITLES.get(m["id"], m["name"]),
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
            "group": demo_group(entry["id"], entry, catalogue=True),
            "title": name,
            "goal": DEMO_GOALS.get(entry["id"], GENERIC_GOAL.format(name=name)),
            "needs": ["internet"] + [n for n in demo_needs(entry) if n != "internet"],
            "demo": entry["id"],
            "catalogue": True,
        })
    for item in FUNCTIONS:
        mid, group, title, goal, needs = item[:5]
        mission = {"id": mid, "group": group, "title": title, "goal": goal, "needs": list(needs)}
        if len(item) > 5:
            mission["status"] = item[5]
        missions.append(mission)

    for m in missions:
        if m["id"] not in NOT_BETA:
            m["maturity"] = "beta"

    order = [g for g, _ in GROUPS]
    # groups in order; functions as listed (first start first), parts of a
    # demo as its manifest lists them (Start here first), then the other
    # demos by name (in Play: Fun with Quantum first, as in the Pi's menu)
    listed = [f[0] for f in FUNCTIONS] + [m["id"] for m in missions if "part" in m]
    missions.sort(key=lambda m: (order.index(m["group"]),
                                 listed.index(m["id"]) if m["id"] in listed else len(listed),
                                 m["title"].lower()))
    return {
        "_doc": ("Tester missions, generated by docs/testing/tester_missions.py from the demo "
                 "manifests, known-demos.json and its list of functions. A mission names a goal, "
                 "never the steps: testers use the user documentation and the RasQberry helper. "
                 "group: one of groups; needs: what a tester must have, as keys of needs_keys, so "
                 "the tester helper can match missions to a tester's setup; maturity beta: early "
                 "beta, not yet tested by people; part: one part of a demo (a variant of its "
                 "manifest); status coming: not in the images yet."),
        "groups": [{"id": g, "title": t} for g, t in GROUPS],
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
        "Testing runs by invitation. Would you like to help? Write to",
        "[info@rasqberry.org](mailto:info@rasqberry.org) and tell us which Pi and hardware you have.",
        "",
        "## Before you start: the right version",
        "",
        "Test the **latest beta** or the **latest development image**, nothing older:",
        "",
        "- **Latest beta:** in Raspberry Pi Imager, **RasQberry Two Beta**.",
        "- **Latest development image:** in Imager, **RasQberry developer builds** →",
        "  **RasQberry Two Dev A/B (development …)** with the newest date (**RasQberry Two Dev",
        "  (development …)** is its single-system image). Other entries in that folder are",
        "  experiments; leave them out.",
        "",
        "The A/B image is best: on a card of 64 GB or more it updates over the air, so you stay",
        "on the newest version. Missions that need the development image test what is not in",
        "the beta yet.",
        "**System Info** in the RasQberry menu shows your version; tell Ket which one you use.",
        "",
        "## How it works",
        "",
        "- **Talk to Ket, our AI tester helper** (bottom right on this page). Tell Ket your Pi model, your",
        "  hardware (LED panel, touchscreen, Bluetooth speaker) and which demos you like, and it",
        "  suggests missions that fit. Sign in with a tester name or ID you choose freely (any",
        "  name, it need not be your real one), so it can keep track of your missions. The tester",
        "  passphrase you got from us unlocks it.",
        "- **Do the mission on your own.** A mission is a goal, not a recipe. Find your way with",
        "  the [documentation](/) and Ket on the Pi's start page (the normal RasQberry helper), as any",
        "  user would. On an image built before 16 October 2026, open",
        "  [rasqberry.org/?from=pi&assistant=1](https://rasqberry.org/?from=pi&assistant=1) once in",
        "  the Pi's browser: Ket then stays for that tab. In tester mode, Ket does not help with the",
        "  mission itself; it points you there. Where the documentation or Ket leaves you stuck,",
        "  that is a finding too.",
        "- **Report back to Ket:** what worked, what didn't, confusing words, slow",
        "  steps, ideas. It writes it down for us, and we follow up on GitHub.",
        "",
        "Nearly everything is still an early beta that no person has tested yet: expect rough",
        "edges. That is why we need you.",
        "",
        "Most demos download on their first start: have internet then, or run **Download all",
        "demos** first.",
        "",
        '<div id="privacy"></div>',
        "",
        "## What is recorded",
        "",
        "Your messages are answered by Claude (Anthropic).",
        "What we keep, and for how long: your tester name or ID (chosen by you, please no e-mail",
        "address), your hardware and preferences, your conversations with Ket, the",
        "findings you save, and which missions you started or finished. We keep them for 90 days,",
        "then delete them. The tester passphrase is checked but never stored. We use this only to",
        "find and fix problems in RasQberry; findings may become public GitHub issues, without",
        "your name or ID. No IP address, no cookies.",
        "",
        "## Missions",
    ]
    titles = dict(GROUPS)
    current = None
    for m in data["missions"]:
        if m["group"] != current:
            current = m["group"]
            lines += ["", f"### {titles[current]}", ""]
        extra = []
        needs = ", ".join(NEEDS_TEXT.get(n, n) for n in m["needs"])
        if needs:
            extra.append(f"needs: {needs}")
        if m.get("status") == "coming":
            extra.append("coming soon")
        tail = f" *({'; '.join(extra)})*" if extra else ""
        beta = f" {BETA_NOTE}" if m.get("maturity") == "beta" else ""
        lines.append(f"- **{m['title']}**: {m['goal']}{beta}{tail}")
    lines += [""]
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
