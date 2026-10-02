# RasQberry Installation Overview

How to write the RasQberry Two image to an SD card, start it on a Raspberry Pi 4
or 5, keep it up to date, and what to do when something goes wrong.

## What you need

- **Raspberry Pi 5** (2GB RAM is enough for most demos) or **Raspberry Pi 4B** (4GB RAM).
  The Pi 5 is recommended; the [hardware assembly guide](/01-3d-model/02-hardware-assembly-guide/) assumes one.
- **MicroSD card:** 16GB or more, 32GB recommended. Two systems with safe updates
  need 64GB or more (see below).
- **Official power supply:** the 27W USB-C supply (5.1V, 5A) for the Pi 5, the 15W
  USB-C supply for the Pi 4. Ordinary USB-C chargers give a Pi 5 only 3A, too
  little with a bright LED panel. An active cooler for the Pi 5.
- **Internet access:** most demos download the first time you start them.
- Optional: the LED panel, a display, keyboard and mouse. Without a display you can
  use the desktop over [VNC](/02-software/02-system-options/).

The full parts list, including the 3D-printed case and LEDs, is in the
[Bill of Materials](/01-3d-model/01-bill-of-materials/).

## Which image?

{/* CONDITIONAL: A/B default. If A/B is not the default, the A/B row reads
"A/B image, recommended for 64GB+ cards" and the 16GB-32GB row reads
"Standard image". */}

| Your card | Image |
|---|---|
| 64GB or more | The **A/B image** (default): two systems on one card, so updates install in place and you can always go back. See [A/B image](/02-software/03-ab-boot/). |
| 16GB or 32GB | The A/B image runs as one system on a small card. The **standard image** does the same. Either way, a new release means writing a new card. |

## Write the card

### One-click: Open in Raspberry Pi Imager (recommended)

With [Raspberry Pi Imager](https://www.raspberrypi.com/software/) 2.0.3 or newer
installed, this opens it with the RasQberry images:

**[▶ Open in Raspberry Pi Imager](rpi-imager://open?repo=https://RasQberry.org/RQB-images.json)**

1. Confirm Imager's security prompt and choose your Raspberry Pi model.
2. Under **Choose OS**, pick **RasQberry Two Beta**. Development and branch builds
   are in **RasQberry developer builds**: they are untested.
3. Choose your SD card. Writing erases everything on it.
4. Skip OS customisation: the image is already set up. Wi-Fi is offered on the
   first start.
5. Write the card, put it in the Pi and switch on.

### If the link does not open Imager

- **Add the repository by hand.** In Imager: **App Options** (bottom left) →
  **Content Repository** → **Use custom URL** → paste
  `https://RasQberry.org/RQB-images.json` → **Apply & Restart**. Imager remembers it.
- **Start Imager from a terminal:**

  ```bash
  # macOS
  /Applications/Raspberry\ Pi\ Imager.app/Contents/MacOS/rpi-imager --repo https://RasQberry.org/RQB-images.json

  # Windows
  "C:\Program Files (x86)\Raspberry Pi Imager\rpi-imager.exe" --repo https://RasQberry.org/RQB-images.json
  ```

- **Download the image** from [rasqberry.org/latest/](/latest/) and write it with
  Imager (**Choose OS** → **Use custom**).

## First start

The first start takes a few minutes and the Pi restarts on its own: do not
unplug it. Then the desktop appears and a short setup checklist opens (see
[First boot](/#3-first-boot)). The login is `rasqberry` with password `Qiskit1!`.

## Downloads

- [rasqberry.org/latest/](/latest/): all current images (stable, beta, development).
- Direct links to the newest standard image of each stream:
  [/latest/stable](https://rasqberry.org/latest/stable) (not published yet),
  [/latest/beta](https://rasqberry.org/latest/beta),
  [/latest/dev](https://rasqberry.org/latest/dev).
- [GitHub Releases](https://github.com/JanLahmann/RasQberry-Two/releases): every build
  with its release notes.
- For scripts: [RQB-images.json](/RQB-images.json) (the Imager list),
  [RQB-releases.json](/RQB-releases.json) (newest release per stream, with checksums),
  [RQB-images-all.json](/RQB-images-all.json) (every build).

## About the image

The desktop has an icon for each demo. Everything else is in `sudo raspi-config`
→ **0 RasQberry**:

| Menu item | What it does |
|---|---|
| Quantum Demos | All demos, the LED tests, Download all demos, the demo catalogue |
| Touch Mode Settings | Settings for touchscreens, with an on-screen keyboard |
| Browser at login | Open rasqberry.org at desktop login, or not |
| Software & Image Updates | Check for a newer image; on the A/B image also the Slot Manager |
| System Info | Version, Python and Qiskit versions, A/B slot |
| Advanced | Edit RasQberry settings, update from a GitHub branch, refresh the demo list |

**Software on the image** (beta of 2026-09-30; exact versions on your Pi: **System Info**, or `rq_info.sh`):

| Component | Version |
|-----------|---------|
| Raspberry Pi OS | Bookworm (Debian 12), 64-bit |
| Python | 3.11 |
| Qiskit | 2.5 (Qiskit 2.x) |
| Qiskit Aer | 0.17 |
| Qiskit IBM Runtime | 0.50 |

Qiskit and the demos live in the virtual environment `~/RasQberry-Two/venv/RQB2`
(`source ~/RasQberry-Two/venv/RQB2/bin/activate`). Code written for Qiskit 1.x may
need updating: see the
[Qiskit 2.0 migration guide](https://quantum.cloud.ibm.com/docs/en/migration-guides/qiskit-2.0).

**Login:** user `rasqberry`, password `Qiskit1!`. SSH is on; VNC is switched on at
the first start ([remote access](/02-software/02-system-options/)).

## Keeping up to date

- **Operating system and security updates** work on both images: click the update
  icon in the taskbar, or run `sudo apt update && sudo apt full-upgrade` and
  restart. If an upgrade includes raspi-config, **0 RasQberry** is back after the
  restart.
- **A new RasQberry release** (new Qiskit, demos and fixes): on the A/B image,
  install it into the other slot ([how](/02-software/03-ab-boot/)). On the
  standard image or a small card, write a new card. That erases the card: copy
  your notebooks and `~/.qiskit` (your IBM Quantum account) to a USB stick first.
- **Check for a newer image** (in **Software & Image Updates**, or
  `rq_update_check.sh`) compares your build with the newest release of your
  channel. A daily check also shows a one-line notice at a terminal or SSH login.

## Troubleshooting

- **Cannot find the Pi on the network:** try `rasqberry.local`. The LED panel
  scrolls the IP address at start-up; on the Pi, **System Info** or `hostname -I`
  shows it.
- **VNC does not connect:** use RealVNC Viewer or TigerVNC; see
  [remote access](/02-software/02-system-options/).
- **"Failed to run demo":** the message names the cause. The usual ones: no
  network on a demo's first start, or a display demo started over SSH (start it
  on the desktop or over VNC instead).
- **Disk full:** the Docker demos (Qoffee-Maker, Quantum-Mixer, Quantum Lab,
  doQumentation) take 2–4GB each. On a 16GB card, install only the ones you need.
- **LED panel stays dark:** see [LED troubleshooting](/03-quantum-computing-demos/led-display/).
- **Known issue:** code cells in doQumentation (Workshop Server) fail, because the
  current upstream image has no Qiskit
  ([doQumentation#958](https://github.com/JanLahmann/doQumentation/issues/958)).
- **Still stuck?** [Open an issue](https://github.com/JanLahmann/RasQberry-Two/issues)
  and paste the output of `rq_info.sh --json`.
