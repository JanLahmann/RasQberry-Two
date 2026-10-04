# RasQberry Installation Overview

How to write the RasQberry Two image to an SD card, start it on a Raspberry Pi 4
or 5, keep it up to date, and what to do when something goes wrong.

## What you need

- **Raspberry Pi 5** (2 GB RAM is enough for most demos) or **Raspberry Pi 4B** (4 GB RAM).
  The Pi 5 is recommended; the [hardware assembly guide](/01-3d-model/02-hardware-assembly-guide/) assumes one.
- **MicroSD card:** 128 GB high-speed (A2, U3) recommended, 16 GB minimum
  (see below).
- **Official power supply:** the 27 W USB-C supply (5.1 V, 5 A) for the Pi 5, the 15 W
  USB-C supply for the Pi 4. Ordinary USB-C chargers give a Pi 5 only 3 A, too
  little with a bright LED panel. An active cooler for the Pi 5.
- **Internet access:** most demos download the first time you start them.
- Optional: the LED panel, a display, keyboard and mouse. Without a display you can
  use the desktop over [VNC](/02-software/02-system-options/).

The full parts list, including the 3D-printed case and LEDs, is in the
[Bill of Materials](/01-3d-model/01-bill-of-materials/).

## Which image?

Pick **RasQberry Two Beta**, the A/B image, whatever your card. From 64 GB it holds
two systems, so updates install in place and you can always go back
([A/B image](/02-software/03-ab-boot/)); on a smaller card it runs as one system.
**RasQberry Two Beta — single system** is the standard image, always one system.
We publish it for at least one more release.

| Card | What fits |
|---|---|
| **128 GB (recommended)** | Two systems with safe updates, and all Docker demos |
| 64 GB | Two systems with safe updates, and some Docker demos |
| 32 GB | One system, with the Docker demos |
| 16 GB | One system, without the Docker demos |

A high-speed card (A2, U3) makes the desktop and the demos start faster. Docker demos (Qoffee-Maker,
Quantum Mixer, Quantum Lab, Workshop & Qiskit Server) take 2–4 GB each, per system.

## Write the card

### One-click: Open in Raspberry Pi Imager (recommended)

With [Raspberry Pi Imager](https://www.raspberrypi.com/software/) 2.0.3 or newer
installed:

<p><a className="cta-button" href="rpi-imager://open?repo=https://RasQberry.org/RQB-images.json" data-umami-event="RasQberry Two: imager open" data-umami-event-where="installation" data-umami-event-stream="beta">▶ Write RasQberry Two to your SD card</a></p>
<p className="cta-note">Opens Raspberry Pi Imager with the RasQberry images.</p>

1. Let your browser open Imager, and confirm **Switch repository**.
2. **Device:** choose your Raspberry Pi model.
3. **OS:** pick **RasQberry Two Beta**. Development and branch builds are in
   **RasQberry developer builds**: they are untested.
4. **Storage:** choose your SD card. Writing erases everything on it.
5. **Customisation:** optional, see below, or **Skip customisation**.
6. **Write**, put the card in the Pi and switch it on.

### Customisation

Imager can set these, so the Pi is ready without a screen:

- **Localisation:** time zone and keyboard layout (this also sets the Wi-Fi country).
- **Wi-Fi:** your network and its password.
- **Remote access:** SSH is already on. To log in with a key, choose **Use public
  key authentication**; SSH then accepts only keys. This needs the **User** step.

**Hostname** is optional: the Pi is then `<name>.local` instead of
`rasqberry.local`. Leave **User** empty, unless you add an SSH key: then enter
the user name `rasqberry` and a password (it replaces `Qiskit1!`). Another user
name is not used: the password and SSH key always go to `rasqberry`.

Customisation works on both images. It applies at the first start of a newly
written card only, not after an update.

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
  Imager (**Choose OS** → **Use custom**). Imager then offers **no customisation**:
  for Wi-Fi, SSH key or keyboard, use the link or the repository above.

## First start

The first start takes a few minutes and the Pi restarts on its own: do not
unplug it. Then the desktop opens, without a login, and a short setup checklist
appears (see [First boot](/#3-first-boot)). Over SSH and VNC the login is
`rasqberry` with password `Qiskit1!`.

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
| Quantum Demos | All demos, Learning paths, the LEDs, Download all demos, Update demos, the demo catalogue |
| Setup Checklist | The first-start steps again |
| Desktop Settings | Touch mode, and opening rasqberry.org at desktop login |
| IBM Quantum account | Save, check or forget your API key |
| Remote Access & Security | Password, SSH and VNC, the Pi's name |
| Software & Image Updates | Check for a newer image; on the A/B image also the Slot Manager |
| System Info | Version, Python and Qiskit versions, A/B slot |
| Advanced | Edit a RasQberry Two setting, refresh the demo list, update from a GitHub branch |

**Software on the image** (exact versions on your Pi: **System Info**, or `rq_info.sh`):

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

SSH is on; VNC is switched on at the first start
([remote access](/02-software/02-system-options/)).

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
- **Disk full:** the Docker demos (Qoffee-Maker, Quantum Mixer, Quantum Lab,
  Workshop & Qiskit Server) take 2–4 GB each and need a card of 32 GB or more
  ([card sizes](#2-which-image)).
- **LED panel stays dark:** see [LED troubleshooting](/03-quantum-computing-demos/led-display/).
- **Still stuck?** [Open an issue](https://github.com/JanLahmann/RasQberry-Two/issues)
  and paste the output of `rq_info.sh --json`.
