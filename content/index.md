---
leadspace:
  title: RasQberry Two
  copy: "The RasQberry project: Exploring Quantum Computing and Qiskit with a Raspberry Pi and a 3D Printer"
  size: tall
  cta:
    primary:
      label: View On GitHub
      url: https://github.com/JanLahmann/RasQberry-Two
      icon: logo-github
      target: _blank
  bg:
    image:
      src: https://picsum.photos/id/1076/1056/480
      alt: lead space background image
---

Note: If you are looking for the functional model of IBM Quantum System ONE, please go to ([https://rasqberry.one](https://rasqberry.one)). This is the new project, building a functional model of IBM Quantum System TWO, including several additional updates, e.g. 64-bit platform, Raspberry Pi 5, Qiskit 1.x, more Quantum Computing Demos, integration into raspi-config, etc.

## Quick Installation of RasQberry

Quick setup instructions:<br/>
Initialize an SD card with Raspberry Pi Imager, using the recommended "bookworm, 64-bit". (development was conducted with the default "pi" user, but other users should be possible as well)

Open the terminal/ssh window on your Raspberry Pi.

Download and execute the bootstrap script RasQ-init.sh, which will add the RasQberry sub-menu to raspi-config.

```python
wget https://github.com/JanLahmann/RasQberry-Two/raw/main/RasQ-init.sh -O RasQ-init.sh
. ./RasQ-init.sh
```

This will modify the raspi-config Configuration Tool and add a RasQberry menu at the top. You can now start raspi-config as usual:

```python
sudo raspi-config
```

Then select "0 RasQberry" to enter the RasQberry sub-menu.
"SU System Update" is optional, but recommended.
Run "IC Initial Config" for an initial configuration and to create the main python venv for RasQberry.
Now run " IQ Qiskit Install" and install your preferred Qiskit version (1.0 or 1.1). The installation will take about 2 min on a Raspberry Pi 4.

### File structure:

- RasQ-init.sh: bootstrap-script, which will add the RasQberry sub-menu to raspi-config
- RQB2_menu.sh: menu and sub-menu that integrate into raspi-config
- env-config.sh: script to set environment variables, as defined in env
- env: environment variables, being imported by env-config.sh
- rq_install_Qiskit\*: install procedure for different Qiskit versions

### working with Qiskit

To work with Qiskit, enter the default python venv

```python
. $HOME/$REPO/venv/$STD_VENV/bin/activate
```

which in the most cases is

```python
. /home/pi/RasQberry-Two/venv/RQB2/bin/activate
```

Then, qiskit should be usable:

```python
(RQB2) pi@raspberrypi:~ $ pip list | grep qiskit
qiskit                 1.1.1
qiskit-qasm3-import    0.5.0
```

Please let us know in case additional modules are needed.
