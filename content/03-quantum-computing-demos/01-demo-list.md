# Quantum Computing Demos in RasQberry Two

The demos come in five groups: a folder on the desktop and a submenu of
`sudo raspi-config` → **0 RasQberry** → **Quantum Demos** each. A terminal
starts them with `rq_demo_run.sh <id>`. Demos marked "network on first start"
download the first time you run them. An IBM Quantum account is only needed to
run on real IBM hardware. Demos tagged beta are new:
[tell us how they work](https://github.com/JanLahmann/RasQberry-Two/issues/new?template=demo-feedback.yml).

New here? Start with the [First 15 minutes](/03-quantum-computing-demos/02-learning-paths/#2-first-15-minutes) learning path.

> This page is generated from the [demo manifests](https://github.com/JanLahmann/RasQberry-Two/tree/development/RQB2-config/demo-manifests)
> — the same files the image installs from, so it cannot fall out of step with
> what ships. To change an entry, edit its manifest; edits made here are
> overwritten.

## LED panel

Demos on the LED panel, or in its on-screen view without a panel.

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **[LED Demos](/03-quantum-computing-demos/led-display/)** | Tests, text, logos and colour effects on the LED panel | LED panel or on-screen view | `led-demos` |
| **RasQ-LED Demo** | Circuits with superposition and entanglement, measured and shown on the LED panel | LED panel or on-screen view | `rasq-led` |
| **[Quantum Lights Out](/03-quantum-computing-demos/quantum-lights-out/)** | Watch Grover's search solve Lights Out puzzles on the LED panel, one after another | LED panel or on-screen view, network on first start | `quantum-lights-out` |
| **[Quantum Raspberry Tie](/03-quantum-computing-demos/raspberry-tie/)** | Measured qubits on the LED panel, from a simulator or a real IBM quantum computer | LED panel or on-screen view, display, network on first start, IBM Quantum account optional | `quantum-raspberry-tie` |
| **LED-Painter** | Paint and draw on the LED panel from a graphical interface | LED panel or on-screen view, display, network on first start | `led-painter` |

## Play

Games and puzzles you play against or with a quantum computer.

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **Fun with Quantum** | Quantum games as Jupyter notebooks (Quantum Coin Game, GHZ game, Hardy's paradox, Mermin-Peres magic square, 3-SAT with Grover), the Fun with Quantum website with browser versions of the games (works offline), and the Fun with Quantum family of projects | network on first start, IBM Quantum account optional | `fun-with-quantum` |
| **Quantum Paradoxes** | Interactive Jupyter notebooks exploring quantum paradoxes and phenomena | network on first start, IBM Quantum account optional | `quantum-paradoxes` |
| **[Quantum Fractals](/03-quantum-computing-demos/fractals/)** | Julia-set fractals that change with the state of one qubit, in the browser | display | `quantum-fractals` |

## Big projects

Larger builds that show what quantum computing can drive.

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **[Qoffee-Maker](/03-quantum-computing-demos/qoffee-maker/)** | Quantum-controlled coffee maker using Home Connect API (Docker container) | display, network | `qoffee-maker` |
| **Quantum Mixer** | Interactive quantum circuit builder and simulator (Docker container) | display, network on first start | `quantum-mixer` |
| **traQmania** <span className="beta-tag">beta</span> | Quantum reinforcement-learning racing game (provided by the Fun with Quantum family) | add it first: **Manage demos** → **Add demo from catalogue** (530 MB) | `traqmania` |

## Learn & code

Write quantum programs and work through tutorials and courses.

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **[Grokking the Bloch Sphere](/03-quantum-computing-demos/bloch-sphere/)** | Interactive Bloch sphere visualisation for understanding qubit states | network on first start | `grok-bloch` |
| **Qiskit Tutorials on this Pi** <span className="beta-tag">beta</span> | The IBM Quantum tutorials, guides and courses as a website just for you, with live Qiskit code on this Pi. The Workshop & Qiskit Server for one person, without the network | IBM Quantum account optional | `qiskit-tutorials` |
| **Quantum Lab (QuBins)** | Local JupyterLab quantum environment (QuBins signed community image) preloaded with the IBM Quantum Learning course notebooks (Docker container) | network | `quantum-lab` |
| **IBM Quantum Tutorials** | Official IBM Quantum tutorials from Qiskit documentation (CC BY-SA 4.0) | network on first start, IBM Quantum account optional | `ibm-tutorials` |
| **IBM Quantum Courses** | Official IBM Quantum learning courses from Qiskit documentation (CC BY-SA 4.0) | network on first start, IBM Quantum account optional | `ibm-courses` |
| **IBM Quantum Composer** | Design and simulate quantum circuits in your web browser | display, network, IBM Quantum account optional | `composer` |

## Workshops & events

For a class or a stand: a server for many laptops, and a loop of demos.

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **Workshop & Qiskit Server** <span className="beta-tag">beta</span> | One Pi serves the IBM Quantum tutorials, guides and courses to a group's laptops on the same network; code runs on this Pi. Built on doQumentation (Docker image, downloaded on first start) | network, IBM Quantum account optional | `doqumentation` |

## Contributed demos

Demos from other projects and partners. Add them with Manage demos > Add demo from catalogue.

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **SAP Quantum Learning** | Browser quiz and circuit composer (provided by SAP) | add it first: **Manage demos** → **Add demo from catalogue** (2 MB) | `sap-quantum-learning` |
| **SAP Quantum LED** | SAP logo on the LEDs, coloured by 3 qubits (provided by SAP) | add it first: **Manage demos** → **Add demo from catalogue** (1 MB) | `sap-quantum-led` |

---

*Generated from the demo manifests in [`RQB2-config/demo-manifests`](https://github.com/JanLahmann/RasQberry-Two/tree/development/RQB2-config/demo-manifests) — the same files the image installs from.*
