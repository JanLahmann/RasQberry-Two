# Quantum Computing Demos in RasQberry Two

Start a demo from its desktop icon, from `sudo raspi-config` → **0 RasQberry** →
**Quantum Demos**, or from a terminal with `rq_demo_run.sh <id>`. Demos marked
"network on first start" download the first time you run them. An optional IBM
account is only needed to run on real IBM hardware.

> This page is generated from the [demo manifests](https://github.com/JanLahmann/RasQberry-Two/tree/development/RQB2-config/demo-manifests)
> — the same files the image installs from, so it cannot fall out of step with
> what ships. To change an entry, edit its manifest; edits made here are
> overwritten.

## See quantum states

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **[Grokking the Bloch Sphere](/03-quantum-computing-demos/bloch-sphere/)** | Interactive Bloch sphere visualization for understanding qubit states | display, network on first start | `grok-bloch` |
| **Grokking the Bloch Sphere (Web)** | Interactive 3D visualization and exploration of the Bloch sphere for quantum computing education (online version) | display, network | `grok-bloch-web` |
| **[Quantum Fractals](/03-quantum-computing-demos/fractals/)** | Generate and explore quantum-inspired fractal patterns in the browser | display | `quantum-fractals` |
| **[Quantum Raspberry Tie](/03-quantum-computing-demos/raspberry-tie/)** | Visualize quantum circuit execution on LED matrix with Sense HAT emulator | LED panel or on-screen view, display, network on first start, IBM account optional | `quantum-raspberry-tie` |
| **RasQ-LED Demo** | Visualize quantum circuit execution results on the LED matrix | LED panel or on-screen view, IBM account optional | `rasq-led` |
| **Quantum-Mixer** | Interactive quantum circuit builder and simulator (Docker container) | display, network on first start | `quantum-mixer` |
| **[Qoffee-Maker](/03-quantum-computing-demos/qoffee-maker/)** | Quantum-controlled coffee maker using Home Connect API (Docker container) | display, network | `qoffee-maker` |

## Play

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **[Quantum Lights Out](/03-quantum-computing-demos/quantum-lights-out/)** | A quantum version of the classic Lights Out puzzle game using quantum circuits | LED panel or on-screen view, network on first start | `quantum-lights-out` |

## Notebooks to work through

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **Fun with Quantum** | Collection of Jupyter notebooks exploring quantum computing through interactive games and experiments: the Quantum Coin Game, GHZ-Game, GHZ on Real Devices, Hardy's Paradox, the Mermin-Peres Magic Square Game, and 3-SAT | display, network on first start, IBM account optional | `fun-with-quantum` |
| **Quantum Paradoxes** | Interactive Jupyter notebooks exploring quantum paradoxes and phenomena | display, network on first start, IBM account optional | `quantum-paradoxes` |
| **IBM Quantum Tutorials** | Official IBM Quantum tutorials from Qiskit documentation (CC BY-SA 4.0) | display, network on first start, IBM account optional | `ibm-tutorials` |
| **IBM Quantum Courses** | Official IBM Quantum learning courses from Qiskit documentation (CC BY-SA 4.0) | display, network on first start, IBM account optional | `ibm-courses` |

## Learn and teach

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **IBM Quantum Composer** | Design and simulate quantum circuits in your web browser | display, network, IBM account optional | `composer` |
| **Quantum Lab (QuBins)** | Local JupyterLab quantum environment (QuBins signed community image) preloaded with the IBM Quantum Learning course notebooks (Docker container) | display, network | `quantum-lab` |
| **doQumentation (Workshop Server)** | Local IBM Quantum tutorials, guides and courses website with live in-browser code execution against a local Qiskit Jupyter server - the basis for a RasQberry Workshop Server. Pulls the doQumentation jupyter-local image on first run (Docker container, part of the Fun with Quantum family) | display, network, IBM account optional | `doqumentation` |

## LED panel

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **LED Demos** | Collection of LED matrix display demos and animations | LED panel or on-screen view | `led-demos` |

## Tools

| Demo | What it is | Needs | Start it with |
|---|---|---|---|
| **LED-Painter** | Paint and draw on the LED matrix using a graphical interface | LED panel or on-screen view, display, network on first start | `led-painter` |

---

*Generated from the demo manifests in [`RQB2-config/demo-manifests`](https://github.com/JanLahmann/RasQberry-Two/tree/development/RQB2-config/demo-manifests) — the same files the image installs from.*
