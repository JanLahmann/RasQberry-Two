# Quantum Computing Demos Overview

The RasQberry image ships 17 demos: visualizations, games, notebooks and LED
demos that make quantum concepts visible. The [Demo List](/03-quantum-computing-demos/01-demo-list/)
has the full details for each one, generated from the same manifests the image
installs from.

## The demos at a glance

| Demo | What it shows | Needs |
|------|---------------|-------|
| [Grokking the Bloch Sphere](/03-quantum-computing-demos/bloch-sphere/) | Single-qubit states and gates on the Bloch sphere (local and web version) | display |
| [Quantum Fractals](/03-quantum-computing-demos/fractals/) | Julia-set animations driven by a one-qubit circuit | display |
| [Qoffee-Maker](/03-quantum-computing-demos/qoffee-maker/) | Measurement and probabilities: a circuit picks your drink | display, network |
| [Quantum Lights Out](/03-quantum-computing-demos/quantum-lights-out/) | Grover's search solving the Lights Out puzzle | LED panel |
| [Quantum Raspberry Tie](/03-quantum-computing-demos/raspberry-tie/) | Measured qubits on the LEDs, from a simulator or real IBM hardware | LED panel, display |
| RasQ-LED | Circuit results visualized on the LED matrix | LED panel |
| [LED Demos](/03-quantum-computing-demos/led-display/) | LED tests, text, logos and colour effects | LED panel |
| LED-Painter | Paint on the LED matrix from a graphical interface | LED panel, display |
| Fun with Quantum | Game notebooks: Quantum Coin Game, GHZ game, Hardy's paradox, magic square, 3-SAT | display |
| Quantum Paradoxes | Notebooks on quantum paradoxes and phenomena | display |
| IBM Quantum Tutorials | Official IBM Quantum tutorials as local notebooks | display |
| IBM Quantum Courses | Official IBM Quantum courses as local notebooks | display |
| Quantum Lab (QuBins) | Local JupyterLab with the IBM Quantum Learning notebooks | display, network |
| doQumentation (Workshop Server) | Local IBM Quantum docs site with runnable code | display, network |
| Quantum-Mixer | Interactive circuit builder and simulator | display |
| IBM Quantum Composer | IBM's online circuit composer | display, network |

Several demos are downloaded the first time you start them, so that first start
needs a network connection.

## Running demos

1. **Desktop icons:** double-click the demo icon.
2. **Desktop menu:** **Applications** → **RasQberry** → [Demo Name].
3. **RasQberry menu:** `sudo raspi-config` → **0 RasQberry** → **Quantum Demos**.
4. **Command line:** `rq_demo_run.sh <demo-id>`, e.g. `rq_demo_run.sh quantum-fractals`.
   The ids are on the [Demo List](/03-quantum-computing-demos/01-demo-list/). A demo
   that is not installed yet is installed on first use.

Every demo needs a RasQberry image on a Pi 5 (recommended) or Pi 4. Most need a
display — a monitor, or VNC.

## More in the Quantum Demos menu

- **Download all demos (one-time setup):** installs every demo now instead of on
  first use — useful before taking the Pi somewhere without a network.
- **Add demo from catalog:** installs reviewed third-party demos, each pinned to a
  fixed commit (for example traQmania and the SAP demos). From a terminal:
  `rq_demo_add_external.sh --list`, `rq_demo_add_external.sh <id>`,
  `rq_demo_add_external.sh --remove <id>`.
- **Continuous Demo Loop (Conference):** runs demos one after another, for a booth.
- **Stop last running demo and clear LEDs:** frees the LED panel when a demo is
  still holding it; the next LED demo cannot start until then.

## Learning resources

- [IBM Quantum Learning](https://learning.quantum.ibm.com/)
- [Qiskit Documentation](https://quantum.cloud.ibm.com/docs/)
- [IBM Quantum Composer](https://quantum.ibm.com/composer)
- [Fun with Quantum](http://fun-with-quantum.org)
