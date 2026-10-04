# Quantum Computing Demos Overview

RasQberry Two has 17 demos: visualisations, games, notebooks and LED demos that
make quantum concepts visible. The [Demo List](/03-quantum-computing-demos/01-demo-list/)
has the details for each one, generated from the same manifests the image
installs from. Not sure where to start? The
[Learning paths](/03-quantum-computing-demos/02-learning-paths/) put demos in a
good order for a stand, a lesson or your first program.

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
| Fun with Quantum | Game notebooks (Quantum Coin Game, GHZ game, Hardy's paradox, magic square, 3-SAT), the games in the browser and the Fun with Quantum family | display |
| Quantum Paradoxes | Notebooks on quantum paradoxes and phenomena | display |
| IBM Quantum Tutorials | Official IBM Quantum tutorials as local notebooks | display |
| IBM Quantum Courses | Official IBM Quantum courses as local notebooks | display |
| Quantum Lab (QuBins) | Local JupyterLab with the IBM Quantum Learning notebooks | display, network |
| Workshop & Qiskit Server <span className="beta-tag">beta</span> | One Pi serves the IBM Quantum tutorials and courses, with runnable Qiskit code, to a group's laptops (built on doQumentation) | network |
| Qiskit Tutorials on this Pi <span className="beta-tag">beta</span> | The same tutorials and courses, just for you on this Pi | display |
| Quantum Mixer | Interactive circuit builder and simulator | display |
| IBM Quantum Composer | IBM's online circuit composer | display, network, IBM Quantum account |

Only the LED demos, RasQ-LED and Quantum Fractals are on the card from the
start. The others download on their first start, which needs a network
connection; Docker demos (Qoffee-Maker, Quantum Mixer, Quantum Lab,
Workshop & Qiskit Server) take 2–4 GB each and need a card of 32 GB or more.
Demos tagged beta are new:
[tell us how they work](https://github.com/JanLahmann/RasQberry-Two/issues/new?template=demo-feedback.yml).

## Running demos

1. **Desktop icons:** double-click the demo icon.
2. **Desktop menu:** **Applications** → **RasQberry** → [Demo Name].
3. **RasQberry menu:** `sudo raspi-config` → **0 RasQberry** → **Quantum Demos**.
4. **Command line:** `rq_demo_run.sh <demo-id>`, e.g. `rq_demo_run.sh quantum-fractals`.
   The ids are on the [Demo List](/03-quantum-computing-demos/01-demo-list/).

Most demos need a display: a monitor, or [VNC](/02-software/02-system-options/).

To stop a demo, press Enter or Ctrl+C in its window, or close the window. The
Workshop & Qiskit Server keeps running until you stop it.

## No LED panel?

LED demos open an on-screen view of the panel when no panel is connected. To
watch the panel in a browser on any device in the network, switch on the web
view in `sudo raspi-config` → **0 RasQberry** → **Quantum Demos** → **LEDs**
→ **Output Targets**, then open `http://rasqberry.local:8098`.

## IBM Quantum accounts

Every demo runs on the built-in simulator, without an account. An IBM Quantum
account is only needed to run circuits on real IBM hardware, and to use the
online Composer. Once saved, the account is kept in `~/.qiskit` and every demo
uses it.

## More in the Quantum Demos menu

- **Download all demos (one-time setup):** installs every demo now instead of on
  first use, before taking the Pi somewhere without a network.
- **Learning paths (beta):** short tours through the demos
  ([on the website](/03-quantum-computing-demos/02-learning-paths/)).
- **Add demo from catalogue:** installs reviewed third-party demos, each pinned to a
  fixed commit (for example traQmania and the SAP demos). From a terminal:
  `rq_demo_add_external.sh --list`, `rq_demo_add_external.sh <id>`,
  `rq_demo_add_external.sh --remove <id>`.
- **Continuous Demo Loop (Conference):** runs demos one after another, for a booth.
- **Update demos:** moves a demo to a newer upstream version, or back.
- **Stop an LED demo still running, clear LEDs:** frees the LED panel when a demo
  is still holding it; the next LED demo cannot start until then.
- **Stop Docker demos:** stops the Workshop & Qiskit Server, Quantum Lab,
  Qoffee-Maker or Quantum Mixer.

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
