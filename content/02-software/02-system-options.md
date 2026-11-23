---
description: "RasQberry Two system settings: Wi-Fi, remote access with SSH, VNC or Raspberry Pi Connect, sound over HDMI or Bluetooth, and the password."
---
# System Options

Wi-Fi, remote access and the password are set in the standard Raspberry Pi
configuration tool. Open a terminal and run:

```
sudo raspi-config
```

The password, SSH, VNC and the Pi's name are also in **0 RasQberry** →
**Remote Access & Security**. Raspberry Pi Imager can set Wi-Fi, the password and
an SSH key before the first start
([customisation](/02-software/01-installation-overview/#3-customisation)).

## Wi-Fi

If the Pi has no network on the first start, the setup checklist offers to
connect to Wi-Fi. Later: the network icon in the taskbar, or **1 System Options** →
**S1 Wireless LAN**, then enter the network name (SSID) and the passphrase. The Pi
keeps its networks and reconnects by itself, also after the router restarts,
usually within a few minutes.

<img width="850" height="276" alt="raspi-config Wireless LAN" src="https://github.com/user-attachments/assets/d50544dc-3502-4824-a434-a74496b835dc" />

To see the Pi's IP address, run `hostname -I`, or look at **System Info** in
**0 RasQberry**. The LED panel also scrolls it at start-up.

## Remote access

On most networks the Pi is reachable as `rasqberry.local`; otherwise use its IP
address. The login is the user and password you set in Imager, otherwise
`rasqberry` with the published password `Qiskit1!`.

### First access without a screen

Without a user or SSH key from Imager, the Pi protects its published password:

1. **Log in over SSH within 15 minutes:** `ssh rasqberry@rasqberry.local`,
   password `Qiskit1!`. The 15 minutes start when the Pi is on the network; on
   the very first start, wait for its own restart first. Missed it? Switch the
   Pi off and on again.
2. **Set your own password.** The Pi asks right away: first `Qiskit1!`, then the
   new password twice. It is also the password for VNC and `sudo`.
3. **VNC comes on** once the password is changed.

After the 15 minutes, password login is closed until the next start. With a
screen, change the password in the setup checklist instead. For a booth or
classroom that keeps `Qiskit1!`: in `rasqberry_boot.env` on the boot drive
(bootfs; BOOT-A or BOOT-B on the A/B image) remove the `#` in front of
`DEFAULT_PW_WINDOW_MIN` (minutes, `0` = keys only) or `DEFAULT_PW_WINDOW_VNC`
(set to `yes`: VNC on as well).

### SSH

SSH is on. From a terminal on your computer:

```
ssh rasqberry@rasqberry.local
```

With your own user name from Imager: `ssh <user>@rasqberry.local`. Confirm the
host key the first time, then enter the password. To log in with a key from
then on, once you have your own password: `ssh-copy-id <user>@rasqberry.local`.

### VNC (the desktop)

VNC comes on once the Pi no longer has the published password: at the first
start with a password from Imager, otherwise after you change it. If you switch
it off (**3 Interface Options** → **VNC**), it stays off.

Use **RealVNC Viewer** or **TigerVNC** and connect to `rasqberry.local`. The Pi
only accepts encrypted logins, so the Mac's built-in Screen Sharing and some
free Windows viewers (TightVNC, UltraVNC) cannot connect. VNC starts with the
desktop, so give the Pi a minute after switching on.

Display demos started over SSH have no screen to open on: start them on the
desktop, locally or over VNC.

### Raspberry Pi Connect

The desktop and a terminal from a browser anywhere: click the Connect icon in the
taskbar → **Turn On Raspberry Pi Connect** → **Sign In** (a free Raspberry Pi ID),
then open [connect.raspberrypi.com](https://connect.raspberrypi.com). Imager can
sign it in before the first start. Its state: **0 RasQberry** → **Remote Access &
Security**.

## Sound

Sound plays over HDMI (a monitor with speakers) or a Bluetooth speaker. To pair
one: the Bluetooth icon in the taskbar → **Add Device**; right-click the volume
icon to choose the output. A Bluetooth speaker plays 100–300 ms late:
**0 RasQberry** → **Desktop Settings** → **Sound delay** →
**Calibrate** plays ticks with flashes on the LED panel; adjust until they come
together.

## Password

Everyone who reads this website knows the default password. On a shared
network, change it: the setup checklist offers this once on the first login
(skip it to keep the demo password, for example at a booth; then SSH and VNC
work as in [first access without a screen](#3-first-access-without-a-screen)). Later, run
`passwd`, or use **1 System Options** → **S3 Password**.
