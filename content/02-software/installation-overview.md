# RasQberry Installation Overview

Below you can find the list of steps that are needed to write the RasQberry Two image to
an SD card and use it in your Raspberry Pi version 4 or 5.

## Download Options

### Stable Download URLs

Use these URLs to always get the latest release for each stream:

| Stream | URL | Description |
|--------|-----|-------------|
| **Stable** | [rasqberry.org/latest/stable](https://rasqberry.org/latest/stable) | Production-ready releases |
| **Beta** | [rasqberry.org/latest/beta](https://rasqberry.org/latest/beta) | Pre-release with latest features |
| **Dev** | [rasqberry.org/latest/dev](https://rasqberry.org/latest/dev) | Development builds (unstable) |

These URLs automatically redirect to the latest image for each release stream.

### GitHub Releases

All releases are also available on [GitHub Releases](https://github.com/JanLahmann/RasQberry-Two/releases).

### API Endpoint

For automation and programmatic access, use the [RQB-releases.json](https://rasqberry.org/RQB-releases.json) endpoint which contains metadata for all streams including download URLs, file sizes, and checksums.

## Using Pi Imager with RasQberry Repository

### Simplified Installation with Desktop Launcher

For the easiest experience, install a pre-configured Pi Imager launcher that automatically loads RasQberry images.

**On macOS** (one-line command):

```bash
curl -sSL https://rasqberry.org/install-rpi-imager-launcher.sh | bash
```

This creates a "Pi Imager for RasQberry" app on your Desktop with the RasQberry icon.

**On Windows** (PowerShell as Administrator):

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://rasqberry.org/install-rpi-imager-launcher.ps1'))
```

This creates a "Pi Imager for RasQberry" shortcut on your Desktop.

### About the RasQberry Image

The RasQberry image contains a desktop environment that was adjusted for the
rasqberry-two. Several demos can be found via the desktop menu to start right away with
several Quantum Demos.

This image also contains the RasQberry-two menu structure from the repository
https://github.com/JanLahmann/RasQberry-Two. In your raspi-config menu (open via
command: sudo raspi-config) you can find based on this repositoy the following
rasQberry menu entries.

One-Click Install Run standard RQB2 setup automatically
System Update Update the system and create swapfile
Initial Config Basic configurations (PATH, LOCALE, Python venv, etc)
Qiskit Install Install latest version of Qiskit
Quantum Demos Install Quantum Demos

Please note that currently, only the last menu option “install quantum demos” should
be used. “one-click install” is not needed when using our RasQberry image (and it will
not work).

**! Note:** The standard user is rasqberry with the pwd: “Qiskit1!”
Currently, modifying the username is not supported - and will not work.
We recommend to not change any settings in “Edit Settings” in the Raspberry Pi Imager
(step 7 - 13 below). FYI: ssh and vnc are enabled by default.

![alt text](/installation-images/image.png)

![alt text](/installation-images/image-1.png)

![alt text](/installation-images/image-2.png)

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

4. Click the `Choose OS` button. Select the operating system `RasQberry Two (64-bit)`

   ![alt text](/installation-images/image-5.png)

   ![alt text](/installation-images/image-6.png)

   ![alt text](/installation-images/image-7.png)

5. Click `Choose Storage` and select the SD Card you inserted in step 2 (e.g. Apple SDCX Reader Media xxx GB).

   ![alt text](/installation-images/image-8.png)

6. Click `Next`.

7. Select `Edit Settings`.

   ![alt text](/installation-images/image-9.png)

8. In the `General` tab, select `Set locale settings` (e.g. for Germany time zone: Europe / Berlin and Keyboard layout: de). User configuration here is optional. The standard user info is:\
   <br />Username: `rasqberry`
   <br />Password: `Qiskit1!`
   <br />
   **! NOTE:** There is no need to specify a username/password in the configuration settings. Doing so might lead to a gray screen when attempting to connect via VNC.

   ![alt text](/installation-images/image-10.png)

9. No further selections are needed in the `Services` tab.

   ![alt text](/installation-images/image-11.png)

10. **Optional**: Select the checkboxes as you can see in the picture below.

    ![alt text](/installation-images/image-12.png)

11. Click `Yes` to apply OS customization settings.

    ![alt text](/installation-images/image-13.png)

12. Click `Yes` to erase all existing data from the SD card and copy the above selected RasQberry image to the SD card.

    ![alt text](/installation-images/image-14.png)

13. The writing process for the RasQberry Pi image will begin and will be completed after verification of the writing process.

    ![alt text](/installation-images/image-15.png)

14. Take the SD Card out of the SD Card reader and put it into your Raspberry Pi 5. Connect power and the RasQberry Pi will boot.
