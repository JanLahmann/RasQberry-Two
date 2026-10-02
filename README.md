# RasQberry Two

**Exploring quantum computing and Qiskit with a Raspberry Pi and a 3D printer**: a functional model of IBM Quantum System Two, with quantum demos and games on screen and on the model's LED panel.

![The RasQberry Two model](https://rasqberry.org/Artwork/RasQberry2model.png)

Website and documentation: **[rasqberry.org](https://rasqberry.org)**. Looking for the model of IBM Quantum System One? Go to [rasqberry.one](https://rasqberry.one).

## Install

The full guide (what you need, which image for which SD card, first start) is at
**[rasqberry.org](https://rasqberry.org/02-software/01-installation-overview/)**.

In short: with [Raspberry Pi Imager](https://www.raspberrypi.com/software/) 2.0.3 or newer
installed, use the [one-click link on rasqberry.org](https://rasqberry.org/02-software/01-installation-overview/#3-one-click-open-in-raspberry-pi-imager-recommended) to open Imager with the RasQberry images
and pick **RasQberry Two Beta** under **Choose OS**. Alternatively start Imager with the RasQberry repository
from a terminal, e.g. on a Mac:

```bash
/Applications/Raspberry\ Pi\ Imager.app/Contents/MacOS/rpi-imager --repo https://RasQberry.org/RQB-images.json
```

All images are also on the [releases page](https://github.com/JanLahmann/RasQberry-Two/releases).

**Login:** user `rasqberry`, password `Qiskit1!` (on the Pi, over SSH and VNC).

The image ships **Qiskit 2.x** in the virtual environment `RQB2`, active in every terminal:

```bash
source ~/RasQberry-Two/venv/RQB2/bin/activate   # only needed in scripts
pip list | grep qiskit
```

**System Info** in `sudo raspi-config` → **0 RasQberry** shows which image you are running.

## Where things are

- **Source code:** the [`development`](https://github.com/JanLahmann/RasQberry-Two/tree/development) branch (work in progress) and [`beta`](https://github.com/JanLahmann/RasQberry-Two/tree/beta) (the current beta). The images are built from these; the scripts on `main` are older and not used by the images.
- **Demos:** [demo list](https://rasqberry.org/03-quantum-computing-demos/01-demo-list/).
- **3D model:** STL files in the [3D-model branch](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model); [bill of materials](https://rasqberry.org/01-3d-model/01-bill-of-materials/) and [assembly guide](https://rasqberry.org/01-3d-model/02-hardware-assembly-guide/) on the website.
- **Help and bugs:** [issues](https://github.com/JanLahmann/RasQberry-Two/issues) (paste the output of `rq_info.sh --json`) and [discussions](https://github.com/JanLahmann/RasQberry-Two/discussions).

---

<!-- FWQ-FAMILY:START format=list — generated from family.json in JanLahmann/Fun-with-Quantum, do not edit by hand -->
## Part of the Fun with Quantum family

This project is part of [**Fun with Quantum**](https://fun-with-quantum.org), a family of open-source quantum outreach projects: [Fun with Quantum](https://fun-with-quantum.org) · [RasQberry One](https://rasqberry.one) · [Quantego](https://quantego.org) · [Qutie](https://qutie.org) · [Qoffee-Maker](https://qoffee-maker.org) · [Entangible](https://entangible.org) · [CertiQ](https://certiq.dev) · [QuBins](https://qubins.org) · [doQumentation](https://doqumentation.org) · [QAMPoser](https://qamposer.org).

*God does play dice. Come play, build, learn.*
<!-- FWQ-FAMILY:END -->
