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

## Wi-Fi hotspot

For booths and classrooms, the Pi can open its own Wi-Fi: phones and laptops
join it and reach the demos, also where the venue's Wi-Fi keeps devices apart.
**0 RasQberry** → **Wi-Fi Hotspot**:

- **Hotspot on/off.** The network is **RasQberry-XXXX** with its own password,
  on 5 GHz (no trouble with Bluetooth speakers; 2.4 GHz for older devices is an
  option).
- **Join card:** a QR code to join, the name and password, and a second QR
  code for the demos - on the screen, or printed.
- Joining opens a page with the demos the Pi offers right now
  (`http://10.42.0.1`).
- **Share internet:** with a network cable (or a USB Wi-Fi adapter) the devices
  on the hotspot reach the internet through the Pi.
- **Start at boot**, e.g. for a booth without a screen.

The Pi's own Wi-Fi is either the hotspot or connected to a network, not both: a
cable or a USB Wi-Fi adapter keeps the Pi online while it runs the hotspot.
Command line: `sudo rq_hotspot.sh on|off|status|card`.

## Remote access

On most networks the Pi is reachable as `rasqberry.local`; otherwise use its IP
address. The login is `rasqberry` with password `Qiskit1!`, or the user and
password you set in Imager.

### SSH

SSH is on. From a terminal on your computer:

```
ssh rasqberry@rasqberry.local
```

With your own user name from Imager: `ssh <user>@rasqberry.local`. Confirm the
host key the first time, then enter the password.

### VNC (the desktop)

VNC is switched on once, at the first start. If you switch it off
(**3 Interface Options** → **VNC**), it stays off.

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
icon to choose the output. A Bluetooth speaker plays 100–300 ms late: on the
development image, **0 RasQberry** → **Desktop Settings** → **Sound delay** →
**Calibrate** plays ticks with flashes on the LED panel; adjust until they come
together.

## Password

Everyone who reads this website knows the default password. On a shared
network, change it: the setup checklist offers this once on the first login
(skip it to keep the demo password, for example at a booth). Later, run
`passwd`, or use **1 System Options** → **S3 Password**.
