# System Options

Wi-Fi, remote access and the password are set in the standard Raspberry Pi
configuration tool. Open a terminal and run:

```
sudo raspi-config
```

## Wi-Fi

If the Pi has no network on the first start, the setup checklist offers to
connect to Wi-Fi. Later: **1 System Options** → **S1 Wireless LAN**, then enter
the network name (SSID) and the passphrase.

<img width="850" height="276" alt="raspi-config Wireless LAN" src="https://github.com/user-attachments/assets/d50544dc-3502-4824-a434-a74496b835dc" />

To see the Pi's IP address, run `hostname -I`, or look at **System Info** in
**0 RasQberry**. The LED panel also scrolls it at start-up.

## Remote access

On most networks the Pi is reachable as `rasqberry.local`; otherwise use its IP
address. The login is `rasqberry` with password `Qiskit1!` unless you changed it.

### SSH

SSH is on. From a terminal on your computer:

```
ssh rasqberry@rasqberry.local
```

Confirm the host key the first time, then enter the password.

### VNC (the desktop)

VNC is switched on once, at the first start. If you switch it off
(**3 Interface Options** → **VNC**), it stays off.

Use **RealVNC Viewer** or **TigerVNC** and connect to `rasqberry.local`. The Pi
only accepts encrypted logins, so the Mac's built-in Screen Sharing and some
free Windows viewers (TightVNC, UltraVNC) cannot connect. VNC starts with the
desktop, so give the Pi a minute after switching on.

Display demos started over SSH have no screen to open on: start them on the
desktop, locally or over VNC.

## Password

Everyone who reads this website knows the default password. On a shared
network, change it: the setup checklist offers this once on the first login
(skip it to keep the demo password, for example at a booth). Later, run
`passwd`, or use **1 System Options** → **S3 Password**.
