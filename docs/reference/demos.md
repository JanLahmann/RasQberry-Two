<!-- Generated from the code by docs/reference/reference_docs.py; do not edit. -->

# Demos

Every demo starts from its group in the RasQberry menu (**Quantum Demos > <group>**), from its icon in the group's desktop window, or in a terminal with `rq_demo_run.sh <id>` (variants: `rq_demo_run.sh <id> <variant>`). *(beta)*: new or less tested.

## LED panel

### LED Demos

Tests, text, logos and colour effects on the LED panel.

- id `led-demos`; menu: Quantum Demos > LED panel (its entries stand there directly); needs the LED panel (or its on-screen view), works without a screen.
  - variant `ibm-logo`: IBM Logo
  - variant `text-display`: Text Display
  - variant `logo-display`: Logo Display
  - variant `led-test`: LED Test
  - variant `clear-leds`: Clear LEDs

### LED-Painter

Paint and draw on the LED panel from a graphical interface.

- id `led-painter`; menu: Quantum Demos > LED panel > LED-Painter; desktop: LED panel window; needs the LED panel (or its on-screen view), a screen; download about 2 MB on first start.

### Quantum Lights Out

Watch Grover's search solve Lights Out puzzles on the LED panel, one after another.

- id `quantum-lights-out`; menu: Quantum Demos > LED panel > Quantum Lights Out; desktop: LED panel window; needs the LED panel (or its on-screen view); download about 1 MB on first start.
  - variant `gui`: LED panel
  - variant `console`: Console

### Quantum Raspberry Tie

Measured qubits on the LED panel, from a simulator or a real IBM quantum computer.

- id `quantum-raspberry-tie`; menu: Quantum Demos > LED panel > Quantum Raspberry Tie; desktop: LED panel window; needs the LED panel (or its on-screen view), a screen, an IBM Quantum account for real quantum computers (optional); download about 24 MB on first start.
  - variant `simulator`: Local simulator (no account needed)
  - variant `noise`: Local simulator with a noise model
  - variant `real`: Real IBM Quantum computer (IBM Quantum account)

### RasQ-LED Demo

Circuits with superposition and entanglement, measured and shown on the LED panel.

- id `rasq-led`; menu: Quantum Demos > LED panel > RasQ-LED Demo; desktop: LED panel window; needs the LED panel (or its on-screen view), works without a screen.

## Play

### Fun with Quantum

Quantum games as Jupyter notebooks (Quantum Coin Game, GHZ game, Hardy's paradox, Mermin–Peres magic square, 3-SAT with Grover, CHSH game, quantum prisoner's dilemma, GHZ on real devices), the Fun with Quantum website with browser versions of the games (works offline), and the Fun with Quantum family of projects.

- id `fun-with-quantum`; menu: Quantum Demos > Play > Fun with Quantum; desktop: Play window; needs an IBM Quantum account for real quantum computers (optional); download about 30 MB on first start.
  - variant `readme`: Start here: what the games are about *(beta)*
  - variant `coin-game`: Quantum Coin Game *(beta)*
  - variant `ghz-game`: GHZ Game *(beta)*
  - variant `hardys-paradox`: Hardy's Paradox *(beta)*
  - variant `mermin-peres`: Mermin–Peres Magic Square *(beta)*
  - variant `3-sat`: 3-SAT with Grover's Algorithm *(beta)*
  - variant `chsh-game`: The CHSH Game *(beta)*
  - variant `prisoners-dilemma`: The Quantum Prisoner's Dilemma *(beta)*
  - variant `ghz-real-devices`: GHZ on Real Quantum Devices *(beta)*
  - variant `website`: Fun with Quantum website: games in the browser *(beta)*
  - variant `family`: Fun with Quantum family: related projects *(beta)*

### Quantum Fractals

Julia-set fractals that change with the state of one qubit, in the browser.

- id `quantum-fractals`; menu: Quantum Demos > Play > Quantum Fractals; desktop: Play window; needs a screen.

### Quantum Paradoxes

Interactive Jupyter notebooks exploring quantum paradoxes and phenomena.

- id `quantum-paradoxes`; menu: Quantum Demos > Play > Quantum Paradoxes; desktop: Play window; needs an IBM Quantum account for real quantum computers (optional); download about 31 MB on first start.

## Big projects

### Qoffee-Maker

Quantum-controlled coffee maker using Home Connect API (Docker container).

- id `qoffee-maker`; menu: Quantum Demos > Big projects > Qoffee-Maker; desktop: Big projects window; needs internet, a screen, a 32 GB card (Docker); download about 770 MB on first start.

### Quantum Mixer

Mix a cocktail, an ice cream or a coffee with a quantum circuit (Docker container).

- id `quantum-mixer`; menu: Quantum Demos > Big projects > Quantum Mixer; desktop: Big projects window; needs a screen, a 32 GB card (Docker); download about 900 MB on first start.

## Learn & code

### Grokking the Bloch Sphere

Interactive Bloch sphere visualisation for understanding qubit states.

- id `grok-bloch`; menu: Quantum Demos > Learn & code > Grokking the Bloch Sphere; desktop: Learn & code window; download about 6 MB on first start.
  - variant `local`: On this Pi (works offline, with tips)
  - variant `web`: Online version (javafxpert.github.io)

### Grokking the Bloch Sphere (Web)

Interactive 3D visualization and exploration of the Bloch sphere for quantum computing education (online version).

- id `grok-bloch-web`; needs internet, a screen.

### IBM Quantum Composer

Design and simulate quantum circuits in your web browser.

- id `composer`; menu: Quantum Demos > Learn & code > IBM Quantum Composer; desktop: Learn & code window; needs internet, a screen, an IBM Quantum account for real quantum computers (optional).

### IBM Quantum Courses

Official IBM Quantum learning courses from Qiskit documentation (CC BY-SA 4.0).

- id `ibm-courses`; menu: Quantum Demos > Learn & code > IBM Quantum Courses; desktop: Learn & code window; needs an IBM Quantum account for real quantum computers (optional); download about 80 MB on first start.

### IBM Quantum Tutorials

Official IBM Quantum tutorials from Qiskit documentation (CC BY-SA 4.0).

- id `ibm-tutorials`; menu: Quantum Demos > Learn & code > IBM Quantum Tutorials; desktop: Learn & code window; needs an IBM Quantum account for real quantum computers (optional); download about 80 MB on first start.

### Qiskit Live (QuBins)

Local JupyterLab quantum environment (QuBins signed community image) preloaded with the IBM Quantum Learning course notebooks (Docker container).

- id `quantum-lab`; menu: Quantum Demos > Learn & code > Qiskit Live (QuBins); desktop: Learn & code window; needs internet, a 32 GB card (Docker); download about 890 MB on first start.

## Contributed demos

### SAP Quantum Learning

Browser quiz and circuit composer.

- id `sap-quantum-learning`; from the catalogue: add it with Quantum Demos > Manage demos > Add demo from catalogue (or `rq_demo_add_external.sh sap-quantum-learning`); provided by SAP; download about 2 MB.

### SAP Quantum LED

Sap logo on the leds, coloured by 3 qubits.

- id `sap-quantum-led`; from the catalogue: add it with Quantum Demos > Manage demos > Add demo from catalogue (or `rq_demo_add_external.sh sap-quantum-led`); provided by SAP; drives the LED panel; download about 1 MB.

## Beta: try & tell us

### doQumentation (IBM Quantum Learning on this Pi) *(beta)*

The IBM Quantum tutorials, guides and courses as a website just for you, with live Qiskit code on this Pi. The Workshop & Qiskit Server for one person, without the network.

- id `qiskit-tutorials`; menu: Quantum Demos > Beta: try & tell us > doQumentation (IBM Quantum Learning on this Pi); desktop: Beta: try & tell us window; needs an IBM Quantum account for real quantum computers (optional), a 32 GB card (Docker).

### Entangible *(beta)*

Build quantum circuits with printed gate tiles on a printed board: a camera reads them and the screen shows the circuit live; phones join over the network. Needs a USB webcam or the Pi camera.

- id `entangible`; menu: Quantum Demos > Beta: try & tell us > Entangible; desktop: Beta: try & tell us window; needs a camera; download about 100 MB on first start.

### QuBins *(beta)*

JupyterLab with the Qiskit version you choose (QuBins Docker images), and the notebooks you choose: IBM Quantum Tutorials and Courses, Quantum Paradoxes, Fun with Quantum, or only your own work.

- id `qubins`; menu: Quantum Demos > Beta: try & tell us > QuBins; desktop: Beta: try & tell us window; needs internet, a 32 GB card (Docker); download about 890 MB on first start.

### Workshop & Qiskit Server *(beta)*

One Pi serves the IBM Quantum tutorials, guides and courses to a group's laptops on the same network; code runs on this Pi. Built on doQumentation (Docker image, downloaded on first start).

- id `doqumentation`; menu: Quantum Demos > Beta: try & tell us > Workshop & Qiskit Server; desktop: Beta: try & tell us window; needs internet, an IBM Quantum account for real quantum computers (optional), a 32 GB card (Docker); download about 1300 MB on first start.

### racetraQ *(beta)*

Quantum reinforcement-learning racing game.

- id `racetraq`; from the catalogue: add it with Quantum Demos > Manage demos > Add demo from catalogue (or `rq_demo_add_external.sh racetraq`); provided by the Fun with Quantum family; download about 600 MB.
