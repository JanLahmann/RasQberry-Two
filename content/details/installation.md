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

## Power

Ordinary USB-C chargers are too weak for a bright LED panel; use the official supply.

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

Besides adding the repository by hand ([installation page](/02-software/01-installation-overview/#3-if-the-link-does-not-open-imager)):

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
`~/RasQberry-Two/venv/RQB2`. Every terminal has it active; elsewhere (a script, a
launcher), activate it first:

```bash
source ~/RasQberry-Two/venv/RQB2/bin/activate
```

Code written for Qiskit 1.x may need the
[migration guide](https://quantum.cloud.ibm.com/docs/en/migration-guides/qiskit-2.0).

The simulator is Qiskit Aer. For real IBM quantum computers, save your API key first
(**0 RasQberry** → **IBM Quantum account**); your code then needs no key:

```python
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime import QiskitRuntimeService

backend = AerSimulator()                         # the built-in simulator
service = QiskitRuntimeService()                 # the key saved in the menu
backend = service.least_busy(operational=True)   # a real quantum computer
```

**More packages:** `pip install <package>` in a terminal, no `sudo`. Demos, JupyterLab
and Thonny share this environment: leave Qiskit's own packages alone, and check first
with `pip install --dry-run <package>` that nothing Qiskit changes. Packages stay until
an A/B update, a new card or a repair of the environment. Keep their names, without
versions, in `~/My-Quantum-Programs/requirements.txt` (that folder survives A/B updates)
and install them again with `pip install -r ~/My-Quantum-Programs/requirements.txt`.

## Updates

- **System updates:** the update icon in the taskbar, or
  `sudo apt update && sudo apt full-upgrade`.
- **New RasQberry releases:** on the A/B image, install into the other system
  ([how](/02-software/03-ab-boot/)). On one system (the single-system image, or the beta
  image on a card under 64 GB), write a new card
  ([back up first](/02-software/01-installation-overview/#2-keeping-up-to-date)).
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

The installation page lists the common problems; these come up less often:

- **"Failed to run demo" over SSH:** a display demo needs the desktop; start it there or
  over VNC.
- **Disk full:** Docker demos need 32 GB or more (card sizes above).
- **Still stuck?** `rq_info.sh --report` saves a report in your home folder. Attach it to
  a [GitHub issue](https://github.com/JanLahmann/RasQberry-Two/issues) or e-mail it to
  info@rasqberry.org.
