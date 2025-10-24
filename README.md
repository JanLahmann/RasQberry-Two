# RasQberry
## The RasQberry project: Exploring Quantum Computing and Qiskit with a Raspberry Pi and a 3D Printer - or: Building a Functional Model of a Quantum Computer at Home

*Note:* If you are looking for the functional model of IBM Quantum System ONE, please go to [https://rasqberry.one](https://rasqberry.one). Here is the new project, building a functional model of IBM Quantum System TWO, including several additional updates, e.g. 64-bit OS, Raspberry Pi 5, Qiskit 1.x, more Quantum Computing Demos, integration into raspi-config, etc.

## Quick Installation of RasQberry

Quick setup instructions:<br/>
Initialize an SD card with Raspberry Pi Imager, using the new RasQberry image based on "bookworm, 64-bit". 

The latest RasQberry images can be found at [https://github.com/JanLahmann/RasQberry-Two/releases](https://github.com/JanLahmann/RasQberry-Two/releases)

Alternatively, this image can be accessed with the Raspberry Pi Imager using a custom repository. On a Mac, run the following command in a terminal

```python
/Applications/Raspberry\ Pi\ Imager.app/Contents/MacOS/rpi-imager --repo https://RasQberry.org/RQB-images.json
```

or on Windows
```python
"C:\Program Files (x86)\Raspberry Pi Imager\rpi-imager.exe" --repo https://RasQberry.org/RQB-images.json
```

This image includes Qiskit 1.x and several Quantum computing Demos.

Further instructions will be released, soon.


### working with Qiskit

Qiskit is available in the default venv called RQB2. In case this venv is not activated, you can activate with

```python
. /home/pi/RasQberry-Two/venv/RQB2/bin/activate
```

and list the available Qiskit modules:

```python
(RQB2) pi@raspberrypi:~ $ pip list | grep qiskit
qiskit                 1.1.1
qiskit-qasm3-import    0.5.0
```

## Building the RasQberry 3D model of IBM Quantum System Two

STL files for a 3D model of IBM Quantum System Two are available in the [3D-model branch](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model)