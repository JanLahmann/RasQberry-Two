---
leadspace:
  title: RasQberry Two
  copy: "The RasQberry project: Exploring Quantum Computing and Qiskit with a Raspberry Pi and a 3D Printer - or: Building a Functional Model of a Quantum Computer at Home"
  size: tall
  cta:
    primary:
      label: View On GitHub
      url: https://github.com/JanLahmann/RasQberry-Two
      icon: logo-github
      target: _blank
  bg:
    image:
      src: /Artwork/RQB2-Website.png
      alt: lead space background image
---

RasQberry is a functional model of IBM Quantum System Two. It integrates Qiskit, a Raspberry Pi and a 3D printed model of IBM Q System Two to explore various state-of-the-art technologies and create a tool that can be used for education and in meetings, meetups, demo booths, etc. A spectrum of Quantum Computing demos and Serious Games for Quantum Computing (that illustrate e.g. superposition, interference and entanglement) will be made available on the RasQberry platform for an engaging introduction to Quantum Computing.

**Note:** If you are looking for the functional model of IBM Quantum System ONE, please go to [https://rasqberry.one](https://rasqberry.one). Here is the new project, building a functional model of IBM Quantum System TWO, including several additional updates, e.g. 64-bit OS, Raspberry Pi 5, Qiskit 1.x, more Quantum Computing Demos, integration into raspi-config, etc.

### Using the Developer Image

Currently, additional functionality (menu, config & code improvements; additional quantum computing demos; etc) is being added to the [alpha releases](https://github.com/JanLahmann/RasQberry-Two/releases).

**Quick instructions for using the alpha releases:**

1. Download the .xz file in a release (e.g. "image_2025-04-25-rasqberry-two-full.img.xz") to your laptop
1. Write the image to SD card  with the Pi Imager without any customisations.
1. Insert the SD card to your Raspberry Pi (Pi 5 is our standard version; Pi will also be supported in the future), and boot the raspberry.
1. Login via ssh. user "rasqberry", PW: "Qiskit1!".
2. vnc might not work out of the box. Enable vnc through raspi-config (interface options, VNC, yes), or simply run `sudo raspi-config nonint do_vnc 0`
1. after login, run `sudo raspi-config` and explore the first menu item which let's you access the current version of our demos. Need to have LEDs connected for most of them.
1. Please report issues in github https://github.com/JanLahmann/RasQberry-Two/issues


### Quick Installation of RasQberry using the Raspberry Pi Imager

Quick setup instructions:<br/>
Initialize an SD card with Raspberry Pi Imager, using the new RasQberry image based on "bookworm, 64-bit".

Currently (during the beta phase), the image can be found at [https://github.com/JanLahmann/RasQberry-Two/releases](https://github.com/JanLahmann/RasQberry-Two/releases)

Alternatively, some of the images can be accessed with the Raspberry Pi Imager using a custom repository. On a Mac, run the following command in a terminal

```python
/Applications/Raspberry\ Pi\ Imager.app/Contents/MacOS/rpi-imager --repo https://RasQberry.org/RQB-images.json
```

or on Windows

```python
"C:\Program Files (x86)\Raspberry Pi Imager\rpi-imager.exe" --repo https://RasQberry.org/RQB-images.json
```

This image includes Qiskit 1.x and several Quantum computing Demos.

Further instructions will be released, soon.

### Working with Qiskit

Qiskit is available in the default venv called RQB2. In case this venv is not activated, you can activate with

```python
. /home/rasqberry/RasQberry-Two/venv/RQB2/bin/activate
```

and list the available Qiskit modules:

```python
(RQB2) rasqberry@raspberrypi:~ $ pip list | grep qiskit
qiskit                 1.1.1
qiskit-qasm3-import    0.5.0
```

## Building the RasQberry 3D model of IBM Quantum System Two

STL files for a 3D model of IBM Quantum System Two will be available soon at [GitHub: JanLahmann/RasQberry-Two-3Dmodel](https://github.com/JanLahmann/RasQberry-Two-3Dmodel)
