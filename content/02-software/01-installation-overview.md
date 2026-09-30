# RasQberry Installation Overview

Below you can find the list of steps that are needed to write the RasQberry Two image to
an SD card and use it in your Raspberry Pi version 4 or 5.

## What you need

- **Raspberry Pi 5** (2GB RAM is enough for most demos) or **Raspberry Pi 4B** (4GB RAM).
  The Pi 5 is recommended; the [hardware assembly guide](/01-3d-model/02-hardware-assembly-guide/) assumes one.
- **MicroSD card:** at least **32GB** for the standard image, at least **64GB** for the
  [A/B image](/02-software/03-ab-boot/) (two system slots for safe updates).
- **Official power supply** (27W USB-C for the Pi 5), and an active cooler for the Pi 5.
- **Internet access:** several demos are downloaded the first time you start them.
- Optional: the LED panel, a display, keyboard and mouse. Without a display you can use
  the desktop over VNC.

The full parts list, including the 3D-printed case and LEDs, is in the
[Bill of Materials](/01-3d-model/01-bill-of-materials/).

## Download Options

### Download Page

Visit **[rasqberry.org/latest/](/latest/)** to browse and download all available RasQberry images including stable, beta, and development builds.

### Direct Download URLs

Use these URLs to always get the latest release for each stream:

| Stream | URL | Description |
|--------|-----|-------------|
| **Stable** | [rasqberry.org/latest/stable](https://rasqberry.org/latest/stable) | Not published yet — use Beta until the first stable release |
| **Beta** | [rasqberry.org/latest/beta](https://rasqberry.org/latest/beta) | Pre-release with latest features |
| **Dev** | [rasqberry.org/latest/dev](https://rasqberry.org/latest/dev) | Development builds (unstable) |

These URLs automatically redirect to the latest image for each release stream.

### GitHub Releases

All releases are also available on [GitHub Releases](https://github.com/JanLahmann/RasQberry-Two/releases).

### JSON APIs

For automation and programmatic access:

| Endpoint | Description |
|----------|-------------|
| [RQB-images.json](/RQB-images.json) | Pi Imager format with latest stable/beta/dev images |
| [RQB-images-all.json](/RQB-images-all.json) | All image versions from all branches (for development/testing) |
| [RQB-releases.json](/RQB-releases.json) | Release metadata with download URLs, file sizes, and checksums |

## Using Pi Imager with RasQberry Repository

### One-click: Open in Raspberry Pi Imager (recommended)

If you already have **Raspberry Pi Imager** installed (version 2.0.3 or newer), just click this link — it opens Imager pre-loaded with the RasQberry images:

**[▶ Open in Raspberry Pi Imager](rpi-imager://open?repo=https://RasQberry.org/RQB-images.json)**

Imager shows a brief security confirmation, then the RasQberry images appear under **Choose OS**.

> **Don't have Raspberry Pi Imager yet?** [Download it here](https://www.raspberrypi.com/software/) first (it's the shipped default on all platforms), then click the link above.

### Manual: add the custom repository in Imager

If the one-click link doesn't launch Imager, add the repository by hand:

1. Open Raspberry Pi Imager.
2. Click **App Options** in the bottom-left corner of the window.
3. Under **Content Repository**, choose **Use custom URL**.
4. Paste: `https://RasQberry.org/RQB-images.json`
5. Click **Apply & Restart**. The RasQberry images appear under **Choose OS**.

A custom *URL* is remembered across app restarts (unlike a custom *file*, which must be re-selected each time).

### About the RasQberry Image

The RasQberry image contains a desktop environment with quantum computing demos accessible via desktop icons and the raspi-config menu.

**raspi-config Menu** (access via `sudo raspi-config`):

| Menu Item | Description |
|-----------|-------------|
| Quantum Demos | LED tests, Quantum Lights Out, Raspberry-Tie, Bloch Sphere, Fractals, IBM Tutorials, and more |
| Touch Mode Settings | Enable/disable touch screen mode |
| Browser at login | Turn Chromium opening rasqberry.org at desktop login on or off |
| Update Env File | Modify RasQberry environment variables |
| Software & Image Updates | Check for a newer image, update from a GitHub branch; on A/B images also partition expansion and the slot manager |
| System Info | Version, build origin, Python and Qiskit versions, A/B slot |

**Software on the image** (beta of 2026-09-30; exact versions on your Pi: **System Info** in the menu, or `rq_info.sh`):

| Component | Version |
|-----------|---------|
| Raspberry Pi OS | Bookworm (Debian 12), 64-bit |
| Python | 3.11 |
| Qiskit | 2.5 (Qiskit 2.x) |
| Qiskit Aer | 0.17 |
| Qiskit IBM Runtime | 0.50 |

Qiskit and the demos live in the virtual environment `~/RasQberry-Two/venv/RQB2`
(`source ~/RasQberry-Two/venv/RQB2/bin/activate`). The image ships Qiskit 2.x: code
written for Qiskit 1.x may need updating (see the
[Qiskit 2.0 migration guide](https://quantum.cloud.ibm.com/docs/en/migration-guides/qiskit-2.0)).

**Default credentials:**
- Username: `rasqberry`
- Password: `Qiskit1!`
- SSH and VNC are enabled by default

## Steps to write the RasQberry Image to your SD Card

**! Warning:** Ensure there is no important information stored on this SD Card before following these steps.

1. Download and install the Raspberry Pi Imager: https://www.raspberrypi.com/software/

2. Put a formatted SD into the SD card reader of your computer. If your computer does not have an SD Card reader slot, you can use a USB SD Card Reader.

3. Open the Raspberry Pi Imager with the following command in a terminal window. Depending on your OS the command will differ:

   Mac OS

   ```
   /Applications/Raspberry\ Pi\ Imager.app/Contents/MacOS/rpi-imager --repo https://rasqberry.org/RQB-images.json
   ```

   Windows

   ```
   "C:\Program Files (x86)\Raspberry Pi Imager\rpi-imager.exe" --repo https://rasqberry.org/RQB-images.json
   ```

   <br/>

4. Click `Choose OS` and select a RasQberry image:
   - **RasQberry Two Beta** - Pre-release with latest tested features
   - **RasQberry Two Dev** - Development builds (latest but may be unstable)

5. Click `Choose Storage` and select your SD Card.

6. Click `Next`.

7. When prompted about OS customization, select `No` - the RasQberry image is pre-configured and should be written without modifications.

8. Click `Yes` to erase all existing data and write the image to the SD card.

9. Wait for the writing and verification process to complete.

10. Insert the SD Card into your Raspberry Pi 4 or 5, connect power, and boot.

## Keeping up to date

Everything is in `sudo raspi-config` → **0 RasQberry** → **Software & Image Updates**,
on the standard and the A/B image:

- **Check for a newer image** compares your build with the latest release of the
  same channel (beta, dev or stable). A check also runs once a day in the
  background; when a newer image exists, a terminal or SSH login shows one line about it.
  From a terminal: `rq_update_check.sh`.
- **Update from GitHub Branch** refreshes the RasQberry scripts, configuration and
  system files (services, autostart entries) from a branch, and keeps your device
  settings such as the LED layout. It does not update the OS packages, the kernel
  or Qiskit — for that, write a new image (or, on the
  [A/B image](/02-software/03-ab-boot/), update the other slot).

**System Info** in the same menu (or `rq_info.sh`) shows the RasQberry version, the
branch and commit it was built from, the Python and Qiskit versions and, on A/B
images, the booted slot. When you [report a bug](https://github.com/JanLahmann/RasQberry-Two/issues),
paste the output of `rq_info.sh --json`.
