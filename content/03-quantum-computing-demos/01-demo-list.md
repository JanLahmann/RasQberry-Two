# Quantum Computing Demos in RasQberry

Every demo below ships with the RasQberry image. Start one from the desktop icon,
from `sudo raspi-config` → **0 RasQberry** → **Quantum Computing Demos**, or from
a terminal with `rq_demo_run.sh <id>`. Demos install themselves the first time
you run them.

> This page is generated from the [demo manifests](https://github.com/JanLahmann/RasQberry-Two/tree/development/RQB2-config/demo-manifests)
> — the same files the image installs from, so it cannot fall out of step with
> what ships. To change an entry, edit its manifest; edits made here are
> overwritten.

## See quantum states

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **[Grokking the Bloch Sphere](/03-quantum-computing-demos/bloch-sphere/)** | Interactive Bloch sphere visualization for understanding qubit states | display | `grok-bloch` |
| **Grokking the Bloch Sphere (Web)** | Interactive 3D visualization and exploration of the Bloch sphere for quantum computing education (online version) | display, network | `grok-bloch-web` |
| **[Quantum Fractals](/03-quantum-computing-demos/fractals/)** | Julia-set fractals that change with the state of one qubit, in the browser | display | `quantum-fractals` |
| **[Quantum Raspberry Tie](/03-quantum-computing-demos/raspberry-tie/)** | Measured qubits on the LED panel, from a simulator or a real IBM quantum computer | LED panel, display, IBM Quantum token | `quantum-raspberry-tie` |
| **RasQ-LED Demo** | Circuits with superposition and entanglement, measured and shown on the LED panel | LED panel | `rasq-led` |
| **Quantum-Mixer** | Interactive quantum circuit builder and simulator (Docker container) | display | `quantum-mixer` |
| **[Qoffee-Maker](/03-quantum-computing-demos/qoffee-maker/)** | Quantum-controlled coffee maker using Home Connect API (Docker container) | display, network | `qoffee-maker` |

## Play

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **[Quantum Lights Out](/03-quantum-computing-demos/quantum-lights-out/)** | Lights Out puzzle on the LED panel, solved by Grover's search | LED panel | `quantum-lights-out` |

## Notebooks to work through

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **Fun with Quantum** | Quantum games as Jupyter notebooks (Quantum Coin Game, GHZ game, Hardy's paradox, Mermin-Peres magic square, 3-SAT with Grover), the Fun with Quantum website with browser versions of the games (works offline), and the Fun with Quantum family of projects | IBM Quantum token | `fun-with-quantum` |
| **Quantum Paradoxes** | Interactive Jupyter notebooks exploring quantum paradoxes and phenomena | IBM Quantum token | `quantum-paradoxes` |
| **IBM Quantum Tutorials** | Official IBM Quantum tutorials from Qiskit documentation (CC BY-SA 4.0) | IBM Quantum token | `ibm-tutorials` |
| **IBM Quantum Courses** | Official IBM Quantum learning courses from Qiskit documentation (CC BY-SA 4.0) | IBM Quantum token | `ibm-courses` |

## Learn and teach

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **IBM Quantum Composer** | Design and simulate quantum circuits in your web browser | display, network, IBM Quantum token | `composer` |
| **Quantum Lab (QuBins)** | Local JupyterLab quantum environment (QuBins signed community image) preloaded with the IBM Quantum Learning course notebooks (Docker container) | network | `quantum-lab` |
| **doQumentation (Workshop Server)** | Local IBM Quantum tutorials, guides and courses website with live in-browser code execution against a local Qiskit Jupyter server - the basis for a RasQberry Workshop Server. Pulls the doQumentation jupyter-local image on first run (Docker container, part of the Fun with Quantum family) | network, IBM Quantum token | `doqumentation` |

## LED panel

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **LED Demos** | Collection of LED matrix display demos and animations | LED panel | `led-demos` |

## Tools

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **LED-Painter** | Paint and draw on the LED matrix using a graphical interface | LED panel, display | `led-painter` |

---

*Generated from the demo manifests in [`RQB2-config/demo-manifests`](https://github.com/JanLahmann/RasQberry-Two/tree/development/RQB2-config/demo-manifests) — the same files the image installs from.*
