---
description: "RasQberry Two system settings: Wi-Fi, the Pi's own Wi-Fi hotspot, remote access with SSH, VNC or Raspberry Pi Connect, sound over HDMI or Bluetooth, and the password."
---
# System Options

Connect your RasQberry, open its own Wi-Fi for a booth or class, reach it from your
computer, and add sound. Most settings are in **0 RasQberry** (double-click
**RasQberry Configuration**); every rule and setting in full: [details](/details/system-options/).

## Wi-Fi

No network at the first start? The setup checklist offers Wi-Fi; later, use the network
icon in the taskbar. No screen either? The Pi opens its own setup Wi-Fi, where your phone
picks your network ([how](/details/system-options/#2-wi-fi-without-a-screen)).

## Wi-Fi hotspot

The Pi's own Wi-Fi, for booths and classrooms where the venue's Wi-Fi keeps devices
apart. Phones and laptops join it and open the demos at `http://10.42.0.1`.

<img src="/installation-images/hotspot-menu.webp" width="800" height="575" loading="lazy" alt="The Wi-Fi Hotspot menu: hotspot on or off, name, password and QR codes, join card, start at boot, share internet, band, SSH/VNC from the hotspot" className="media-image" />

- **Start it:** **0 RasQberry** → **Wi-Fi Hotspot** → **Hotspot**.
- **Let people join:** **Join card** shows the name, password and QR codes.
- **More:** start at boot, share internet, the band, and setting it up before the first
  start ([hotspot settings](/details/system-options/#2-hotspot-settings)).

## Remote access

On most networks the Pi is `rasqberry.local`; otherwise use its IP address (**System
Info**). Log in with the user from Imager, otherwise `rasqberry` / `Qiskit1!`.

### First access without a screen

Without a user or SSH key from Imager, the Pi protects its published password:

1. **Log in over SSH within 15 minutes** of the Pi joining the network:
   `ssh rasqberry@rasqberry.local`, password `Qiskit1!`. Missed it? Switch the Pi off and on.
2. **Set your own password** when asked. It is also your password for VNC and `sudo`.
3. **VNC comes on** once the password is changed.

For a classroom or booth, the window and VNC can be changed
([how](/details/system-options/#2-the-ssh-window-for-the-published-password)).

### SSH, VNC and Raspberry Pi Connect

- **SSH:** `ssh <user>@rasqberry.local` ([log in with a key](/details/system-options/#2-ssh-keys)).
- **VNC (the desktop):** connect **RealVNC Viewer** or **TigerVNC** to `rasqberry.local`
  ([other clients](/details/system-options/#2-vnc-clients)). Start display demos there,
  not over SSH: over SSH they have no screen.
- **Raspberry Pi Connect:** the desktop in your browser, from anywhere, with a free
  Raspberry Pi ID ([turn it on](/details/system-options/#2-raspberry-pi-connect)).

## Sound

Sound plays over HDMI or a Bluetooth speaker. A Bluetooth speaker plays late:
**0 RasQberry** → **Desktop Settings** → **Sound delay** → **Calibrate**
([pairing and calibration](/details/system-options/#2-sound-output-and-delay)).

## Password

Everyone who reads this website knows `Qiskit1!`. On a shared network, set your own in
the setup checklist ([other ways](/details/system-options/#2-changing-the-password)).
Keep it only for a booth (then see [first access without a screen](#3-first-access-without-a-screen)).
