# Quantum Computing Demos Overview

RasQberry Two has about 20 demos: visualisations, games, notebooks and LED demos that
make quantum concepts visible. The [Demo List](/03-quantum-computing-demos/01-demo-list/)
has the details for each one, generated from the same manifests the image
installs from. Not sure where to start? The
[Learning paths](/03-quantum-computing-demos/02-learning-paths/) put demos in a
good order for a stand, a lesson or your first program.

## The demos at a glance

The demos come in six groups. Each is an icon on the desktop and a submenu of
**Quantum Demos** in the RasQberry menu.

| Group | What is in it |
|-------|---------------|
| **LED panel** | IBM LED Demo, RasQ-LED, [Quantum Lights Out](/03-quantum-computing-demos/quantum-lights-out/), [Quantum Raspberry Tie](/03-quantum-computing-demos/raspberry-tie/), LED-Painter, [text and logos](/03-quantum-computing-demos/led-display/) |
| **Play** | Fun with Quantum (eight games, from the Quantum Coin Game to GHZ on real devices, its website and family), Quantum Paradoxes, [Quantum Fractals](/03-quantum-computing-demos/fractals/) |
| **Big projects** | [Qoffee-Maker](/03-quantum-computing-demos/qoffee-maker/), Quantum Mixer, [Entangible](#2-entangible), [racetraQ](https://racetraq.org) |
| **Learn & code** | My Quantum Programs, [Grokking the Bloch Sphere](/03-quantum-computing-demos/bloch-sphere/), Qiskit Tutorials on this Pi, Quantum Lab (QuBins), IBM Quantum Tutorials and Courses, IBM Quantum Composer |
| **Workshops & events** | Workshop & Qiskit Server, Demo Loop |
| **Contributed demos** | Demos from partners, added from the catalogue: SAP Quantum LED, SAP Quantum Learning |

A few starters sit loose on the desktop too: Learning paths, IBM LED Demo,
Grokking the Bloch Sphere, Quantum Coin Game and My Quantum Programs.

Only the LED demos, RasQ-LED and Quantum Fractals are on the card from the
start. The others download on their first start, which needs a network
connection; Docker demos (Qoffee-Maker, Quantum Mixer, Quantum Lab, Qiskit
Tutorials on this Pi, Workshop & Qiskit Server) take 2–4 GB each and need a card
of 32 GB or more.
Demos tagged beta are new and some things may not work yet. On the Pi they say
"(beta)" on their icon and when they start:
[tell us how they work](https://github.com/JanLahmann/RasQberry-Two/issues/new?template=demo-feedback.yml).

## Running demos

1. **Desktop:** double-click a starter, or a group's folder and then the demo.
   Fun with Quantum then shows a list of its games.
2. **Desktop menu:** **Applications** → **RasQberry** → [Demo Name].
3. **RasQberry menu:** double-click **RasQberry Configuration** on the desktop (or
   run `sudo raspi-config`) → **0 RasQberry** → **Quantum Demos** → the group.
4. **Command line:** `rq_demo_run.sh <demo-id>`, e.g. `rq_demo_run.sh quantum-fractals`.
   The ids are on the [Demo List](/03-quantum-computing-demos/01-demo-list/).

Most demos need a display: a monitor, or [VNC](/02-software/02-system-options/).

To stop a demo, press Enter or Ctrl+C in its window, or close the window. The
Workshop & Qiskit Server keeps running until you stop it.

## No LED panel?

LED demos also show the panel in an on-screen view, so they work without one. To
watch the panel in a browser on any device in the network, switch on the web
view in `sudo raspi-config` → **0 RasQberry** → **Quantum Demos** → **LED panel**
→ **LED setup & tests** → **Output Targets**, then open `http://rasqberry.local:8098`.

## IBM Quantum accounts

The demos run on the built-in simulator, without an account. A free IBM Quantum
account ([quantum.cloud.ibm.com](https://quantum.cloud.ibm.com)) is needed for
real IBM hardware: the demos' real-hardware options, and most IBM Quantum
Tutorials, Hello world included, which are written for it. Save its API key
once: **0 RasQberry** → **IBM Quantum account** → **Save my API key**; it is kept
in `~/.qiskit`. The Fun with Quantum notebooks ask for the key in their
real-hardware cell. The online Composer simulates up to four qubits without
signing in.

## Entangible

Entangible (**Big projects**) reads printed gate tiles with a camera, a USB
webcam or the Pi camera: print the
[tiles and board (A4)](https://github.com/JanLahmann/entangible/releases/latest/download/entangible-print-kit-A4.pdf)
and point the camera down at the board. Without a camera it runs, but reads no
tiles. Phones on the same network join with the address its window shows; they
warn about the certificate once (tap **Advanced**, then **Proceed**).

## More in the Quantum Demos menu

- **Learning paths (beta):** short tours through the demos
  ([on the website](/03-quantum-computing-demos/02-learning-paths/)).
- **Stop a running LED demo:** frees the LED panel when a demo is still holding
  it; the next LED demo cannot start until then.
- **Manage demos:**
  - **Download all demos (one-time setup):** installs every demo now (the Docker
    demos if you say yes) instead of on first use, before taking the Pi
    somewhere without a network.
  - **Add demo from catalogue:** installs reviewed third-party demos, each pinned
    to a fixed commit (for example racetraQ and the SAP demos). Partner demos
    go to Contributed demos, racetraQ to Big projects. From a terminal: `rq_demo_add_external.sh --list`,
    `rq_demo_add_external.sh <id>`, `rq_demo_add_external.sh --remove <id>`.
  - **Update demos:** moves a demo that comes with the image to a newer upstream
    version, or back. A catalogue demo updates when the catalogue has a newer
    version: the RasQberry badge in the taskbar offers it, or run
    `rq_demo_add_external.sh --update <id>`.
  - **Remove a demo:** frees space; it downloads again when started (a catalogue
    demo is uninstalled: add it again from the catalogue).
  - **Stop Docker demos:** stops the Workshop & Qiskit Server, Quantum Lab,
    Qoffee-Maker or Quantum Mixer.
- **Workshops & events** → **Demo Loop:** LED demos and Quantum Fractals one after
  another, for a booth: **Choose the demos**, **Start the demo loop** (Enter skips
  a demo, x stops the loop), **Start the Demo Loop at login**.

## At a booth or in class

- Run **Download all demos** while you still have a network.
- The screen does not blank. To change that: `sudo raspi-config` →
  **2 Display Options** → **Screen Blanking**.
- **0 RasQberry** → **Desktop Settings** → **Browser at login** stops the browser
  opening rasqberry.org at every start.
- On a large monitor, Quantum Lights Out, Grokking the Bloch Sphere, Quantum
  Fractals, the LED demos and the Quantum Coin Game draw visitors in
  ([more](/workshops/#2-for-a-stand)).
- Change the default password on a shared network, or keep it for a booth
  ([how](/02-software/02-system-options/)).

## Learning resources

- [IBM Quantum Learning](https://quantum.cloud.ibm.com/learning)
- [Qiskit Documentation](https://quantum.cloud.ibm.com/docs/)
- [IBM Quantum Composer](https://quantum.cloud.ibm.com/composer)
- [Fun with Quantum](https://fun-with-quantum.org)
