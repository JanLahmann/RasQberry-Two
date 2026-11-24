# Installation details

Background for the [installation page](/02-software/01-installation-overview/): every option, in full.

## Card sizes and Docker demos

| Card | What fits |
|---|---|
| **128 GB (recommended)** | Two systems, all Docker demos |
| 64 GB | Two systems, some Docker demos |
| 32 GB | One system, with the Docker demos |
| 16 GB | One system, without the Docker demos |

Docker demos (Qoffee-Maker, Quantum Mixer, Qiskit Live, Workshop & Qiskit Server)
take 2–4 GB each, per system. The **RasQberry Two Beta** image holds two systems from
64 GB ([A/B image](/02-software/03-ab-boot/)); **RasQberry Two Beta — single system** is
always one system. Untested builds are under **RasQberry developer builds**.

## Power and cooling

Use the official supply: 27 W USB-C for the Pi 5, 15 W for the Pi 4. Ordinary chargers
are too weak for a bright LED panel. Fit an active cooler on the Pi 5.

## Imager customisation

Imager can prepare the Pi so it needs no screen:

- **Localisation:** time zone and keyboard (also sets the Wi-Fi country).
- **Wi-Fi:** your network and password.
- **User:** your login name and password instead of `rasqberry` / `Qiskit1!`. If the
  name can't be used (the system already has it), the login stays `rasqberry` and the
  first login says why.
- **Remote access:** SSH is on. **Use public key authentication** accepts only your key
  and needs the **User** step.
- **Hostname:** the Pi becomes `<name>.local` instead of `rasqberry.local`.

Customisation applies to the first start of a newly written card only.

## If the link does not open Imager

You need Raspberry Pi Imager 2.0.3 or newer.

- **Add the repository by hand:** in Imager, **App Options** → **Content Repository** →
  **Use custom URL** → `https://RasQberry.org/RQB-images.json` → **Apply & Restart**.
- **Start Imager from a terminal:**

  ```bash
  # macOS
  /Applications/Raspberry\ Pi\ Imager.app/Contents/MacOS/rpi-imager --repo https://RasQberry.org/RQB-images.json

  # Windows
  "C:\Program Files (x86)\Raspberry Pi Imager\rpi-imager.exe" --repo https://RasQberry.org/RQB-images.json
  ```

- **Download the image** from [rasqberry.org/latest/](/latest/) and write it with
  **Choose OS** → **Use custom**. Imager then offers no customisation.

## First start and the setup checklist

The first start takes a few minutes, and the Pi restarts on its own, sometimes more than
once. Over SSH or VNC, log in with the user from Imager; without one, see
[first access without a screen](/02-software/02-system-options/#3-first-access-without-a-screen).

The checklist offers what still needs you:

- **Keyboard and time zone** (UK until you change them).
- **Wi-Fi**, when the Pi has no network.
- **Your own password.** Keep `Qiskit1!` only for a booth.
- **A name for this RasQberry**, when several share a network.
- **The LED panel:** pick the color in which the IBM logo reads upright. No panel? LED
  demos then show on screen.
- **Download all demos** now, or each on its first start.
- **Touch mode**, for a touchscreen.

Every step can wait: the **RasQberry Setup** icon opens the list again. After
**Don't show again**, it stays in **0 RasQberry** → **Setup Checklist**.

## The RasQberry menu

Open it with the **RasQberry Configuration** icon (or `sudo raspi-config`), then
**0 RasQberry**:

- **Quantum Demos:** learning paths, demo groups, download, update or remove demos.
- **Setup Checklist:** the first-start steps above.
- **Desktop Settings:** touch mode, browser at login, Bluetooth sound delay.
- **IBM Quantum account:** save your API key for real quantum hardware.
- **Remote Access & Security:** password, SSH, VNC, the Pi's name, Raspberry Pi Connect.
- **Wi-Fi Hotspot:** the Pi's own network for booths and classrooms.
- **Software & Image Updates:** newer images; the Slot Manager on the A/B image.
- **System Info:** versions of the image, Python and Qiskit, and the IP address.
- **Advanced:** edit a setting, refresh the demo list, update from a GitHub branch.
- **Shut Down Safely:** LEDs off, then shutdown; switch the power off once the green
  light stays off.

## Python and Qiskit

The image runs Raspberry Pi OS Trixie (64-bit) with Qiskit 2.x in
`~/RasQberry-Two/venv/RQB2`:

```bash
source ~/RasQberry-Two/venv/RQB2/bin/activate
```

Code written for Qiskit 1.x may need the
[migration guide](https://quantum.cloud.ibm.com/docs/en/migration-guides/qiskit-2.0).

## Updates

- **System updates:** the update icon in the taskbar, or
  `sudo apt update && sudo apt full-upgrade`.
- **New RasQberry releases:** on the A/B image, install into the other system
  ([how](/02-software/03-ab-boot/)). On the single-system image, write a new card; copy
  your notebooks and `~/.qiskit` to a USB stick first.
- A daily check tells you when a newer release is out.

## Downloads

- [rasqberry.org/latest/](/latest/): all current images. Direct links:
  [beta](https://rasqberry.org/latest/beta), [dev](https://rasqberry.org/latest/dev).
- [GitHub Releases](https://github.com/JanLahmann/RasQberry-Two/releases): every build
  with release notes.
- For scripts: [RQB-images.json](/RQB-images.json),
  [RQB-releases.json](/RQB-releases.json) (with checksums),
  [RQB-images-all.json](/RQB-images-all.json).

## Troubleshooting

- **Can't find the Pi:** try `rasqberry.local`. The LED panel scrolls the IP address at
  start-up; **System Info** shows it too.
- **VNC doesn't connect:** VNC stays off until you set your own password
  ([remote access](/02-software/02-system-options/)).
- **"Failed to run demo":** the message names the cause, usually no network on a first
  start, or a display demo started over SSH (start it on the desktop or over VNC).
- **Disk full:** Docker demos need 32 GB or more (card sizes above).
- **LED panel stays dark:** [LED troubleshooting](/03-quantum-computing-demos/led-display/).
- **Still stuck?** `rq_info.sh --report` saves a report in your home folder. Attach it to
  a [GitHub issue](https://github.com/JanLahmann/RasQberry-Two/issues) or e-mail it to
  info@rasqberry.org.
