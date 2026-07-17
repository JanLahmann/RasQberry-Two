# Raspberry Tie

![Raspberry Tie](/qrtimages/New Logo Screen.png)

Run a quantum circuit — on a simulator or on real IBM Quantum hardware — and watch
the measured qubits light up on the panel, laid out the way the qubits are
actually arranged on the processor.

**Needs:** the LED panel · a display · an IBM Quantum token for the `real` variant
**Start it with:** `rq_demo_run.sh quantum-raspberry-tie`

## Run it

Double-click the **Raspberry Tie** icon on the desktop.

It is also under **Applications → RasQberry → Raspberry Tie**, or in
`sudo raspi-config` → **0 RasQberry** → **Quantum Computing Demos**.

From a terminal you can pick the backend:

```bash
rq_demo_run.sh quantum-raspberry-tie            # local Aer simulator (default)
rq_demo_run.sh quantum-raspberry-tie noise      # simulator with a noise model
rq_demo_run.sh quantum-raspberry-tie real       # real IBM Quantum hardware
```

The `real` variant needs a network connection and an IBM Quantum token, and your
job may sit in a queue before it runs.

## What you'll see

Each qubit is a coloured pixel: **blue** for a qubit measured as |1⟩, **red** for
|0⟩, and a paler shade for qubits that were not measured. The pixels are not in a
line — they are placed to match the connectivity of a real IBM processor, so a
5-qubit run makes the "bowtie", and larger runs the heavy-hex pattern used by
current devices.

<img src='/qrtimages/RaspberryTieOutput.png' width='200' alt='Bowtie display output' />
<img src='/qrtimages/12-qubit display.png' width='200' alt='12-qubit hex display' />

Comparing the same circuit on the simulator and on real hardware is the thing
worth doing: the ideal result is crisp, and the real device shows you noise.

No LEDs? It also renders to an SVG you can open in a browser.

## Credits and documentation

Written and maintained by **Kevin Roche**. The upstream project documents the
display modes, backends and options in full — start there rather than here:

- **[KPRoche/quantum-raspberry-tie](https://github.com/KPRoche/quantum-raspberry-tie)** — the project and its documentation
- [IBM Quantum Platform](https://quantum.ibm.com/) — for a token, if you want the `real` variant
- [Bill of Materials](../01-3d-model/bill-of-materials) · [Hardware Assembly Guide](../01-3d-model/hardware-assembly-guide) — for the LED panel

*See the [Demo List](01-demo-list) for everything else on the image.*
