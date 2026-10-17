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
two systems: the card stays in the Pi for good, new releases install over the
air, and you can always go back ([A/B image](/02-software/03-ab-boot/)); on a
smaller card it runs as one system.
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
`rasqberry.local`. **User** is optional too: the name you enter becomes the
login (home folder `/home/<name>`) and the password replaces `Qiskit1!`. If the
name cannot be used (e.g. the system already uses it), the login stays
`rasqberry` and the first login says why. Without **User**: `rasqberry` /
`Qiskit1!`.

Customisation works on both images. It applies at the first start of a newly
written card only, not after an update.

### Without Wi-Fi, cable or screen

If the Pi finds no network about two minutes after its first start, it opens
its own Wi-Fi **RasQberry-Setup-XXXX** (password `rasqberry`); the LED panel
scrolls its name and password. Join it with a phone or laptop: a page opens that
lists the Wi-Fi networks nearby. Choose yours and enter its password; the Pi
joins it, and the LED panel then shows its address. The setup Wi-Fi ends as soon
as the Pi has a network (a cable, or a Wi-Fi it knows), after 30 minutes with
nobody on it, and after an hour at the latest. It does not come back once the Pi
has had a network.

### A booth hotspot from the first start

To start the Pi as a hotspot for a booth or classroom (see
[Wi-Fi hotspot](/02-software/02-system-options/#2-wi-fi-hotspot)), put a file
`rasqberry-hotspot.txt` on the card's boot partition after writing it (on an
A/B card: the partition named CONFIG, which a computer shows):

```
HOTSPOT_AT_BOOT=yes
HOTSPOT_SSID=RasQberry-Booth
HOTSPOT_PASSWORD=choose-a-password
```

The password needs 8 to 63 characters: letters, digits, spaces and
punctuation, without accents. Names and passwords may contain spaces and quotes.
The Pi saves the settings at its first start and leaves the file as
`rasqberry-hotspot.applied.txt`, without the password; a setting it did not take
is listed there. Without a usable password, the Pi makes one and scrolls it on
the LED panel at the start. If the hotspot does not start and the Pi has no
network, the setup Wi-Fi opens instead.

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
`rasqberry` with password `Qiskit1!`, or the user set in Imager.

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

The desktop has a folder for each demo group. Everything else is in the RasQberry
menu: double-click **RasQberry Configuration** on the desktop (or run
`sudo raspi-config`), then **0 RasQberry**:

| Menu item | What it does |
|---|---|
| Quantum Demos | Learning paths, the demo groups (LED panel, Play, Big projects, Learn & code, Workshops & events, Contributed demos), Manage demos (download all, catalogue, update, remove) |
| Setup Checklist | The first-start steps again |
| Desktop Settings | Touch mode, opening rasqberry.org at desktop login, the sound delay for a Bluetooth speaker (development image) |
| IBM Quantum account | Save, check or forget your API key |
| Remote Access & Security | Password, SSH and VNC, the Pi's name, Raspberry Pi Connect |
| Wi-Fi Hotspot | The Pi's own Wi-Fi for a booth or class: on/off, join card, name and password, start at boot ([more](/02-software/02-system-options/#2-wi-fi-hotspot)) |
| Software & Image Updates | Check for a newer image; on the A/B image also the Slot Manager |
| System Info | Version, Python and Qiskit versions, A/B slot |
| Advanced | Edit a RasQberry Two setting, refresh the demo list, update from a GitHub branch |
| Shut Down Safely | Switches the LEDs off and shuts the Pi down; switch the power off when the Pi's green light stays off |

**Software on the image** (exact versions on your Pi: **System Info**, or `rq_info.sh`):

| Component | Version |
|-----------|---------|
| Raspberry Pi OS | Trixie (Debian 13), 64-bit |
| Python | 3.13 |
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
- **Still stuck?** Run `rq_info.sh --report` (**System Info** names it too): it saves
  a report file in your home folder. Attach it to a
  [GitHub issue](https://github.com/JanLahmann/RasQberry-Two/issues), or e-mail it
  to info@rasqberry.org.
