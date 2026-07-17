# Qoffee Maker

Build a quantum circuit, measure it, and get the drink the measurement chose.
Each beverage is a bit pattern — 000, 001, 010 … — so ordering a cappuccino means
constructing a circuit whose measurement lands on the right one. Quantum
mechanics being what it is, you can shift the odds but never quite give an order.

![Qoffee Maker](https://qoffee-maker.org/Bilder/Event%20Image.jpeg)

**Needs:** a display · a network connection · **Start it with:** `rq_demo_run.sh qoffee-maker`

## Run it

Double-click the **Qoffee Maker** icon on the desktop. It starts the Qoffee
container, opens the notebook, and switches straight into the app view — you do
not have to run any cells yourself.

It is also under **Applications → RasQberry → Qoffee Maker**, or in
`sudo raspi-config` → **0 RasQberry** → **Quantum Computing Demos**.

The first launch pulls the Qoffee container image, so give it a few minutes and a
decent connection. After that it starts quickly.

## What you'll see

![Qoffee Maker Demo Interface](/demo-screenshots/qoffee-maker-interface.png)

Drag gates onto the qubits to build a circuit. The interface shows the
probability of each of the eight outcomes, and which drink each one pours. Choose
a backend to compare an ideal simulation against one with realistic noise — the
noisy run is the honest one, and it is a good way to feel what error means in
practice before anyone mentions error correction.

![Beverage Overview](https://qoffee-maker.org/Bilder/übersicht.png)

Start by aiming for an outcome you can hit reliably (000, or 111), then try for a
specific drink in the middle. That is where it gets interesting: superposition
means your circuit sets *probabilities*, so you may need a few attempts — which is
the point of the demo.

With a real Home Connect coffee machine attached, the winning measurement actually
brews it. Without one, everything works except the coffee.

## Credits and documentation

By **Max Simon** and **Jan-R. Lahmann**, from the "serious games for quantum
computing" family. Full details, the hardware setup and the event kit are on the
project's own site:

- **[qoffee-maker.org](https://qoffee-maker.org)** — the project and its documentation
- [Fun with Quantum](http://fun-with-quantum.org) — more quantum games, also on this image
- [IBM Quantum Learning: measurement](https://learning.quantum.ibm.com/course/basics-of-quantum-information/single-systems#measurement)

*See the [Demo List](01-demo-list) for everything else on the image.*
