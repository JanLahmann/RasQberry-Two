# RasQberry Installation Overview

Write RasQberry Two to an SD card, start your Pi, and keep it up to date.

## What you need

- **Raspberry Pi 5** (recommended, 2 GB RAM is enough) or **Raspberry Pi 4B** (4 GB RAM).
- **MicroSD card:** 128 GB high-speed (A2, U3) recommended, 16 GB minimum.
- **Official power supply:** 27 W USB-C for the Pi 5, 15 W for the Pi 4. Ordinary
  chargers are too weak for a bright LED panel. An active cooler for the Pi 5.
- **Internet:** most demos download on their first start.
- Optional: the LED panel, a display, keyboard and mouse. Without a display, use
  [VNC](/02-software/02-system-options/).

All parts, including the 3D-printed case: [bill of materials](/01-3d-model/01-bill-of-materials/).

## Which image?

Pick **RasQberry Two Beta**, whatever your card. From 64 GB it holds two systems:
releases install over the air and you can always go back ([A/B image](/02-software/03-ab-boot/)).
**RasQberry Two Beta — single system** is always one system.

| Card | What fits |
|---|---|
| **128 GB (recommended)** | Two systems, all Docker demos |
| 64 GB | Two systems, some Docker demos |
| 32 GB | One system, with the Docker demos |
| 16 GB | One system, without the Docker demos |

Docker demos (Qoffee-Maker, Quantum Mixer, Qiskit Live, Workshop & Qiskit Server)
take 2–4 GB each, per system.

## Write the card

{/* Old anchor, kept for links from the README */}
<span id="3-one-click-open-in-raspberry-pi-imager-recommended" />

Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/) 2.0.3 or newer, then:

<p><a className="cta-button" href="rpi-imager://open?repo=https://RasQberry.org/RQB-images.json" data-umami-event="RasQberry Two: imager open" data-umami-event-where="installation" data-umami-event-stream="beta">▶ Write RasQberry Two to your SD card</a></p>

1. Let your browser open Imager and confirm **Switch repository**.
2. **Device:** your Pi. **OS:** **RasQberry Two Beta** (untested builds are under
   **RasQberry developer builds**). **Storage:** your card; writing erases it.
3. **Customisation** (optional, below), then **Write**. Put the card in the Pi and switch it on.

### Customisation

Imager can prepare the Pi so it needs no screen:

- **Localisation:** time zone and keyboard (also sets the Wi-Fi country).
- **Wi-Fi:** your network and password.
- **User:** your login name and password instead of `rasqberry` / `Qiskit1!`. If the
  name can't be used (the system already has it), the login stays `rasqberry` and the
  first login says why.
- **Remote access:** SSH is on. **Use public key authentication** accepts only
  your key and needs the **User** step.
- **Hostname:** the Pi becomes `<name>.local` instead of `rasqberry.local`.

Customisation applies to the first start of a newly written card only.

### If the link does not open Imager

- **Add the repository by hand:** in Imager, **App Options** → **Content Repository**
  → **Use custom URL** → `https://RasQberry.org/RQB-images.json` → **Apply & Restart**.
- **Start Imager from a terminal:**

  ```bash
  # macOS
  /Applications/Raspberry\ Pi\ Imager.app/Contents/MacOS/rpi-imager --repo https://RasQberry.org/RQB-images.json

  # Windows
  "C:\Program Files (x86)\Raspberry Pi Imager\rpi-imager.exe" --repo https://RasQberry.org/RQB-images.json
  ```

- **Download the image** from [rasqberry.org/latest/](/latest/) and write it with
  **Choose OS** → **Use custom**. Imager then offers no customisation.

## First start

The first start takes a few minutes and the Pi restarts on its own, sometimes more
than once: don't unplug it. Then
the desktop opens with the setup checklist. Over SSH or VNC, log in with the user
from Imager; without one, see [first access without a screen](/02-software/02-system-options/#3-first-access-without-a-screen).

### Setup checklist

The checklist offers what still needs you:

- **Keyboard and time zone** (UK until you change them).
- **Wi-Fi**, when the Pi has no network.
- **Your own password.** Keep `Qiskit1!` only for a booth.
- **A name for this RasQberry**, when several share a network.
- **The LED panel:** pick the color in which the IBM logo reads upright. No panel?
  LED demos then show on screen.
- **Download all demos** now, or each on its first start.
- **Touch mode**, for a touchscreen.

Every step can wait: the **RasQberry Setup** icon opens the list again. After
**Don't show again** it stays in **0 RasQberry** → **Setup Checklist**.

## The RasQberry menu

Demo icons and group folders are on the desktop. Everything else is in the menu:
double-click **RasQberry Configuration** (or run `sudo raspi-config`), then **0 RasQberry**.

<img src="/installation-images/rasqberry-menu.webp" width="800" height="577" loading="lazy" alt="The RasQberry main menu: Quantum Demos, Setup Checklist, Desktop Settings, IBM Quantum account, Remote Access & Security, Wi-Fi Hotspot, Software & Image Updates, System Info, Advanced, Shut Down Safely" className="media-image" />

- **Quantum Demos:** learning paths, demo groups, download, update or remove demos.
- **Desktop Settings:** touch mode, browser at login, Bluetooth sound delay.
- **IBM Quantum account:** save your API key for real quantum hardware.
- **Remote Access & Security:** password, SSH, VNC, the Pi's name, Raspberry Pi Connect.
- **Wi-Fi Hotspot:** the Pi's own network for booths and classrooms.
- **Software & Image Updates:** newer images; the Slot Manager on the A/B image.
- **System Info:** versions of the image, Python and Qiskit.
- **Advanced:** edit a setting, refresh the demo list, update from a GitHub branch.
- **Shut Down Safely:** LEDs off, then shutdown; switch the power off once the
  green light stays off.

The image runs Raspberry Pi OS Trixie (64-bit) with Qiskit 2.x in
`~/RasQberry-Two/venv/RQB2` (`source ~/RasQberry-Two/venv/RQB2/bin/activate`). Code for Qiskit 1.x may need the
[migration guide](https://quantum.cloud.ibm.com/docs/en/migration-guides/qiskit-2.0).

## Keeping up to date

- **System updates:** the update icon in the taskbar, or
  `sudo apt update && sudo apt full-upgrade`.
- **New RasQberry releases:** on the A/B image, install into the other system
  ([how](/02-software/03-ab-boot/)). Otherwise write a new card; copy your
  notebooks and `~/.qiskit` to a USB stick first.
- A daily check tells you when a newer release is out.

## Downloads

- [rasqberry.org/latest/](/latest/): all current images. Direct links:
  [beta](https://rasqberry.org/latest/beta), [dev](https://rasqberry.org/latest/dev).
- [GitHub Releases](https://github.com/JanLahmann/RasQberry-Two/releases): every build with release notes.
- For scripts: [RQB-images.json](/RQB-images.json), [RQB-releases.json](/RQB-releases.json)
  (with checksums), [RQB-images-all.json](/RQB-images-all.json).

## Troubleshooting

- **Can't find the Pi:** try `rasqberry.local`. The LED panel scrolls the IP
  address at start-up; **System Info** shows it too.
- **VNC doesn't connect:** VNC stays off until you set your own password
  ([remote access](/02-software/02-system-options/)).
- **"Failed to run demo":** the message names the cause, usually no network on a
  first start, or a display demo started over SSH (start it on the desktop or
  over VNC).
- **Disk full:** Docker demos need 32 GB or more ([card sizes](#2-which-image)).
- **LED panel stays dark:** [LED troubleshooting](/03-quantum-computing-demos/led-display/).
- **Still stuck?** `rq_info.sh --report` saves a report in your home folder. Attach
  it to a [GitHub issue](https://github.com/JanLahmann/RasQberry-Two/issues) or
  e-mail it to info@rasqberry.org.

Questions? Ask [Ket](/?assistant=1).
