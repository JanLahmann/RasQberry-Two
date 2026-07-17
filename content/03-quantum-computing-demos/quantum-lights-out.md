# Quantum Lights Out

The [Lights Out puzzle](https://en.wikipedia.org/wiki/Lights_Out_(game)) — press a
tile, it toggles itself and its neighbours, and you have to turn every light off —
solved by **Grover's search** running on a quantum simulator, with each step of
the solution played out on the LED panel.

![Quantum Lights Out Animation](https://github.com/user-attachments/assets/23778cc3-99d3-4872-9463-fcd3b8f09b4f)

**Needs:** the LED panel · **Start it with:** `rq_demo_run.sh quantum-lights-out`

## Run it

Double-click the **Quantum Lights Out** icon on the desktop; the puzzle and its
solution appear on the LED panel.

It is also under **Applications → RasQberry → Quantum Lights Out**, or in
`sudo raspi-config` → **0 RasQberry** → **Quantum Computing Demos**. There is a
console variant in the menu that plays in the terminal instead.

## What you'll see

A 3×3 grid of lit tiles appears in the middle of the panel. After a short pause
while the circuit runs, each press of the solution is shown in turn, until the
grid goes dark.

## How it works

Lights Out is a **search** problem: of all the combinations of presses, which one
turns everything off? That is what Grover's algorithm is for.

The circuit holds the board, a set of "flip" qubits standing for the presses you
might make, and an **oracle** — a piece of circuit that recognises a winning
combination without being told what it is. Grover then alternates the oracle with
a **diffusion** step, and each round nudges probability towards the answers. After
enough rounds, measuring the flip qubits gives you a solution.

That is the interesting part: the oracle only *checks* a combination, yet Grover
finds the one that works in noticeably fewer tries than testing them one by one.

The quantum code comes from the **IBM Quantum Challenge 2020**, and runs on the
local Aer simulator — no IBM Quantum account, no network.

## Credits and links

Built by **Luka Dojcinovic** — [Luka-D/Quantum-Lights-Out](https://github.com/Luka-D/Quantum-Lights-Out),
with the quantum algorithm from the IBM Quantum Challenge 2020.

- [Lights Out on Wikipedia](https://en.wikipedia.org/wiki/Lights_Out_(game))
- [IBM Quantum Learning: Grover's algorithm](https://learning.quantum.ibm.com/course/fundamentals-of-quantum-algorithms/grover-algorithm)

*See the [Demo List](01-demo-list) for everything else on the image.*
