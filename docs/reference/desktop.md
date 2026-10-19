<!-- Generated from the code by docs/reference/reference_docs.py; do not edit. -->

# The desktop

The desktop shows a few system icons, some starter demos, and one icon per demo group. A group icon opens a window with the group's demos as icons. Icons start with a double-click (one tap in touch mode). On a small screen the starters leave the desktop first; they stay in their group windows. (Layout: `rq_desktop_session.py`, at every login.)

## On the desktop itself

- **RasQberry Setup**: The setup checklist: Wi-Fi, keyboard and time zone, password, the Pi's name, LED panel check, demo downloads, touch mode. Opens `rq_firstlogin.sh --all`. *(last icon; it goes once the setup checklist is done)*
- **RasQberry Configuration (raspi-config)**: raspi-config with the RasQberry menu (0 RasQberry): demos, setup, updates, system info. Opens `sudo raspi-config`.
- **Touch Mode**: Bigger icons, buttons and menus for a touchscreen (asks first; restarts the desktop). Opens `rq_touch_mode.sh toggle --ask`. *(only while a touchscreen is connected)*

Starters (also in their group windows):

- **Learning paths**: (beta) Short tours through the demos, for a stand, a lesson or learning to code: what to try and what to notice, step by step. Opens `rq_learning_paths.sh`.
- **IBM LED Demo**: The IBM logo in colour on the LED panel. Opens `rq_demo_run.sh led-demos ibm-logo`.
- **Grokking the Bloch Sphere**: One qubit as an arrow on a sphere: apply gates and watch the state turn (works offline, with tips on what to try). Opens `rq_demo_run.sh grok-bloch`.
- **Quantum Coin Game**: Interactive demonstration of quantum superposition and interference using a coin flip game. Opens `rq_demo_run.sh fun-with-quantum coin-game`.
- **My Quantum Programs**: Your own quantum notebooks: JupyterLab in your folder ~/My-Quantum-Programs, starting with the Hello World notebook. Opens `rq_my_programs.sh`.

## Group icons and their windows

### LED panel

Demos on the LED panel, or in its on-screen view without a panel.

- **IBM LED Demo**: The IBM logo in colour on the LED panel. Opens `rq_demo_run.sh led-demos ibm-logo`.
- **Quantum Lights Out**: Watch Grover's search solve Lights Out puzzles on the LED panel. Opens `rq_demo_run.sh quantum-lights-out`.
- **RasQ-LED Demo**: Quantum circuit demo with entanglement patterns on LEDs. Opens `rq_demo_run.sh rasq-led`.
- **Quantum Raspberry Tie**: Measured qubits on the LED panel, from a simulator or a real IBM quantum computer. Opens `rq_demo_run.sh quantum-raspberry-tie`.
- **LED-Painter**: Paint a picture on a canvas, then show it on the LED panel: Display > Display this image on the LEDs. Opens `rq_demo_run.sh led-painter`.
- **Clear All LEDs**: Turn off all LEDs on the LED panel. Opens `rq_demo_run.sh led-demos clear-leds`.

### Play

Games and puzzles you play against or with a quantum computer.

- **Quantum Fractals**: Create animated fractal art using quantum computing circuits and Julia sets. Opens `rq_demo_run.sh quantum-fractals`.
- **Quantum Paradoxes**: Interactive Jupyter notebooks exploring quantum mechanics paradoxes by Maria Violaris. Opens `rq_demo_run.sh quantum-paradoxes`.
- **Fun with Quantum**: Quantum games as Jupyter notebooks, the Fun with Quantum website (games in the browser, works offline) and the Fun with Quantum family: choose from a list. Opens `rq_demo_choose.sh fun-with-quantum`.
- **Quantum Coin Game**: Interactive demonstration of quantum superposition and interference using a coin flip game. Opens `rq_demo_run.sh fun-with-quantum coin-game`.

### Big projects

Larger builds that show what quantum computing can drive.

- **Qoffee-Maker**: Quantum-controlled coffee maker using Home Connect API and Docker. Opens `rq_demo_run.sh qoffee-maker`.
- **Quantum Mixer**: Quantum beverage mixer - Qocktails, Qoffee, and Ice demos. Opens `rq_demo_run.sh quantum-mixer`.
- **Entangible**: (beta) Build quantum circuits with printed gate tiles: a camera reads them, the screen and visitors' phones show the circuit live. Needs a USB webcam or the Pi camera. Opens `rq_demo_run.sh entangible`.
- **racetraQ** *(catalogue demo: its icon comes when it is added)*: quantum reinforcement-learning racing game

### Learn & code

Write quantum programs and work through tutorials and courses.

- **My Quantum Programs**: Your own quantum notebooks: JupyterLab in your folder ~/My-Quantum-Programs, starting with the Hello World notebook. Opens `rq_my_programs.sh`.
- **IBM Quantum Composer**: Design and simulate quantum circuits in your web browser. Opens the browser at https://quantum.cloud.ibm.com/composer.
- **Grokking the Bloch Sphere**: One qubit as an arrow on a sphere: apply gates and watch the state turn (works offline, with tips on what to try). Opens `rq_demo_run.sh grok-bloch`.
- **Qiskit Tutorials on this Pi**: (beta) The IBM Quantum tutorials, guides and courses as a website just for you, with live Qiskit code on this Pi. Opens `rq_demo_run.sh qiskit-tutorials`.
- **IBM Quantum Tutorials**: Official IBM Quantum tutorials covering algorithms, optimisation, error mitigation (CC BY-SA 4.0). Opens `rq_demo_run.sh ibm-tutorials`.
- **IBM Quantum Courses**: Official IBM Quantum courses on quantum computing (CC BY-SA 4.0). Opens `rq_demo_run.sh ibm-courses`.
- **Quantum Lab (QuBins)**: Your own JupyterLab with Qiskit and the IBM Quantum course notebooks (Docker, downloaded on first start). Opens `rq_demo_run.sh quantum-lab`.

### Workshops & events

For a class or a stand: a server for many laptops, and a loop of demos.

- **Workshop & Qiskit Server**: (beta) One Pi serves the IBM Quantum tutorials, guides and courses to a group's laptops on the same network; code runs on this Pi (doQumentation). Opens `rq_demo_run.sh doqumentation`.
- **Demo Loop**: Quantum demos one after another, for a stand (LED demos and Quantum Fractals). Opens `rq_demo_loop.sh`.

### Contributed demos

Demos from other projects and partners. Add them with Manage demos > Add demo from catalogue.

- **SAP Quantum Learning** *(catalogue demo: its icon comes when it is added)*: browser quiz and circuit composer
- **SAP Quantum LED** *(catalogue demo: its icon comes when it is added)*: SAP logo on the LEDs, coloured by 3 qubits
- Demos added from the catalogue land here unless the catalogue names another group; the window offers adding one.

## Taskbar, main menu and login

- **Main menu button** (top left of the taskbar): the RasQberry icon.
- The applications menu has a **RasQberry** section with the demo launchers. Only there: **LED Test**.
- **RasQberry Desktop Session** (at login): Fit the desktop to the screen, then open the browser (BROWSER_AUTOSTART)
- **RasQberry VNC (first start)** (at login): Switch VNC on once, at the first desktop login
- **RasQberry Learner Setup** (at login): Prepare ~/My-Quantum-Programs, Thonny and Geany for your own Qiskit programs (quick and idempotent)
- **RasQberry Setup Checklist** (at login): Open the setup checklist once, at the first desktop login, after the IP address scroll on the LED panel
- **RasQberry Slot Indicator** (at login): Show the running A/B slot in the taskbar, and newer releases (with one system: only while a newer release is available)
