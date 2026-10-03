# Quantum Computing Demos Overview

RasQberry Two has 17 demos: visualisations, games, notebooks and LED demos that
make quantum concepts visible. The [Demo List](/03-quantum-computing-demos/01-demo-list/)
has the details for each one, generated from the same manifests the image
installs from.

## The demos at a glance

| Demo | What it shows | Needs |
|------|---------------|-------|
| [Grokking the Bloch Sphere](/03-quantum-computing-demos/bloch-sphere/) | Single-qubit states and gates on the Bloch sphere (local and web version) | display |
| [Quantum Fractals](/03-quantum-computing-demos/fractals/) | Julia-set animations driven by a one-qubit circuit | display |
| [Qoffee-Maker](/03-quantum-computing-demos/qoffee-maker/) | Measurement and probabilities: a circuit picks your drink | display, network |
| [Quantum Lights Out](/03-quantum-computing-demos/quantum-lights-out/) | Grover's search solving the Lights Out puzzle | LED panel or on-screen view |
| [Quantum Raspberry Tie](/03-quantum-computing-demos/raspberry-tie/) | Measured qubits on the LEDs, from a simulator or real IBM hardware | LED panel or on-screen view, display |
| RasQ-LED | Superposition and entanglement shown on the LED panel | LED panel or on-screen view |
| [LED Demos](/03-quantum-computing-demos/led-display/) | LED tests, text, logos and colour effects | LED panel or on-screen view |
| LED-Painter | Paint on the LED panel from a graphical interface | LED panel or on-screen view, display |
| Fun with Quantum | Game notebooks: Quantum Coin Game, GHZ game, Hardy's paradox, magic square, 3-SAT | display |
| Quantum Paradoxes | Notebooks on quantum paradoxes and phenomena | display |
| IBM Quantum Tutorials | Official IBM Quantum tutorials as local notebooks | display |
| IBM Quantum Courses | Official IBM Quantum courses as local notebooks | display |
| Quantum Lab (QuBins) | Local JupyterLab with the IBM Quantum Learning notebooks | display, network |
| Workshop & Qiskit Server | IBM Quantum tutorials and courses with runnable code, for one Pi or a whole group (based on doQumentation) | display, network |
| Quantum-Mixer | Interactive circuit builder and simulator | display |
| IBM Quantum Composer | IBM's online circuit composer | display, network, IBM account |

Only the LED demos, RasQ-LED and Quantum Fractals are on the card from the
start. The others download on their first start, which needs a network
connection; Docker demos (Qoffee-Maker, Quantum-Mixer, Quantum Lab,
Workshop & Qiskit Server) take 2–4 GB each and need a card of 32 GB or more.

## Running demos

1. **Desktop icons:** double-click the demo icon.
2. **Desktop menu:** **Applications** → **RasQberry** → [Demo Name].
3. **RasQberry menu:** `sudo raspi-config` → **0 RasQberry** → **Quantum Demos**.
4. **Command line:** `rq_demo_run.sh <demo-id>`, e.g. `rq_demo_run.sh quantum-fractals`.
   The ids are on the [Demo List](/03-quantum-computing-demos/01-demo-list/).

Most demos need a display: a monitor, or [VNC](/02-software/02-system-options/).

## No LED panel?

LED demos open an on-screen view of the panel when no panel is connected. To
watch the panel in a browser on any device in the network, switch on the web
view in `sudo raspi-config` → **0 RasQberry** → **Quantum Demos** → **Test LEDs**
→ **Output Targets**, then open `http://rasqberry.local:8098`.

## IBM Quantum accounts

Every demo runs on the built-in simulator, without an account. An IBM Quantum
account is only needed to run circuits on real IBM hardware, and to use the
online Composer. Once saved, the account is kept in `~/.qiskit` and every demo
uses it.

## More in the Quantum Demos menu

- **Download all demos (one-time setup):** installs every demo now instead of on
  first use, before taking the Pi somewhere without a network.
- **Add demo from catalog:** installs reviewed third-party demos, each pinned to a
  fixed commit (for example traQmania and the SAP demos). From a terminal:
  `rq_demo_add_external.sh --list`, `rq_demo_add_external.sh <id>`,
  `rq_demo_add_external.sh --remove <id>`.
- **Continuous Demo Loop (Conference):** runs demos one after another, for a booth.
- **Stop last running demo and clear LEDs:** frees the LED panel when a demo is
  still holding it; the next LED demo cannot start until then.

## At a booth or in class

- Run **Download all demos** while you still have a network.
- The screen does not blank. To change that: `sudo raspi-config` →
  **2 Display Options** → **Screen Blanking**.
- **Browser at login** in **0 RasQberry** stops the browser opening rasqberry.org
  at every start.
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
