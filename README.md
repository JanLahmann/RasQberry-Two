# RasQberry
## The RasQberry project: Exploring Quantum Computing and Qiskit with a Raspberry Pi and a 3D Printer - or: Building a Functional Model of a Quantum Computer at Home

*Note:* If you are looking for the functional model of IBM Quantum System ONE, please go to [https://rasqberry.one](https://rasqberry.one). Here is the new project, building a functional model of IBM Quantum System TWO, including several additional updates, e.g. 64-bit OS, Raspberry Pi 5, Qiskit 2.x, more Quantum Computing Demos, integration into raspi-config, etc.

## Quick Installation of RasQberry

The full guide - what you need, the standard and A/B images, writing the SD card - is at
**[rasqberry.org](https://rasqberry.org/02-software/01-installation-overview/)**.

In short: with [Raspberry Pi Imager](https://www.raspberrypi.com/software/) 2.0.3 or newer
installed, use the [one-click link on rasqberry.org](https://rasqberry.org/02-software/01-installation-overview/#3-one-click-open-in-raspberry-pi-imager-recommended) to open Imager with the RasQberry images
and pick one under **Choose OS**. Alternatively start Imager with the RasQberry repository
from a terminal, e.g. on a Mac:

```bash
/Applications/Raspberry\ Pi\ Imager.app/Contents/MacOS/rpi-imager --repo https://RasQberry.org/RQB-images.json
```

All images are also on the [releases page](https://github.com/JanLahmann/RasQberry-Two/releases).

The image ships **Qiskit 2.x** in the virtual environment `RQB2`. To use it in a terminal:

```bash
source ~/RasQberry-Two/venv/RQB2/bin/activate
pip list | grep qiskit
```

**System Info** in `sudo raspi-config` → **0 RasQberry** shows which image you are running.

## Building the RasQberry 3D model of IBM Quantum System Two

STL files for a 3D model of IBM Quantum System Two are available in the [3D-model branch](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model)

---

<!-- FWQ-FAMILY:START format=list — generated from family.json in JanLahmann/Fun-with-Quantum, do not edit by hand -->
## Part of the Fun with Quantum family

This project is part of [**Fun with Quantum**](https://fun-with-quantum.org), a family of open-source quantum outreach projects: [Fun with Quantum](https://fun-with-quantum.org) · [RasQberry One](https://rasqberry.one) · [Quantego](https://quantego.org) · [Qutie](https://qutie.org) · [Qoffee-Maker](https://qoffee-maker.org) · [Entangible](https://entangible.org) · [CertiQ](https://certiq.dev) · [QuBins](https://qubins.org) · [QAMPoser](https://qamposer.org).

*God does play dice. Come play, build, learn.*
<!-- FWQ-FAMILY:END -->
