---
description: "RasQberry Two system settings: Wi-Fi, the Pi's own Wi-Fi hotspot, remote access with SSH, VNC or Raspberry Pi Connect, sound over HDMI or Bluetooth, and the password."
---
# System Options

Connect your RasQberry, open its own Wi-Fi for a booth or class, reach it from your
computer, and add sound. Settings are in `sudo raspi-config` (or double-click
**RasQberry Configuration**); password, SSH, VNC and the Pi's name also in
**0 RasQberry** → **Remote Access & Security**. Raspberry Pi Imager can set Wi-Fi,
a user and an SSH key before the first start
([customisation](/details/installation/#2-imager-customisation)).

## Wi-Fi

No network at the first start? The setup checklist offers Wi-Fi. Later: the network
icon in the taskbar, or `sudo raspi-config` → **1 System Options** → **S1 Wireless LAN**.
The Pi remembers its networks and reconnects by itself.

**No screen and no network?** A new Pi that has never had a network opens the Wi-Fi
**RasQberry-Setup-XXXX** after about two minutes, password `rasqberry` (an LED panel
scrolls both). Join it with your phone: a page lists the networks in range; pick
yours. It closes after 30 minutes unused (an hour at most); switch the Pi off and on
to open it again.

The Pi's IP address: **System Info** in **0 RasQberry**, `hostname -I`, or the LED
panel at start-up.

## Wi-Fi hotspot

The Pi's own Wi-Fi, for booths and classrooms where the venue's Wi-Fi keeps devices
apart. Phones and laptops join it and open the demos at `http://10.42.0.1`.

<img src="/installation-images/hotspot-menu.webp" width="800" height="575" loading="lazy" alt="The Wi-Fi Hotspot menu: hotspot on or off, name, password and QR codes, join card, start at boot, share internet, band, SSH/VNC from the hotspot" className="media-image" />

- **Start it:** **0 RasQberry** → **Wi-Fi Hotspot** → **Hotspot**.
- **Let people join:** **Join card** opens a page with the name, password and QR
  codes, to show or print. Over SSH, **Show name, password and QR codes** prints them.
- **Name and password:** `RasQberry-XXXX` and a random password, unless you set your own.
- **Start at boot**, **share this Pi's internet**, and the **band** (5 GHz; 2.4 GHz
  for older devices) are in the same menu.
- **One Wi-Fi can't do both:** the hotspot takes a USB Wi-Fi adapter if there is one.
  Otherwise the built-in Wi-Fi leaves your network while the hotspot runs; a network
  cable keeps the Pi online.
- **SSH and VNC from the hotspot:** by default only once no account that can use
  `sudo` still has `Qiskit1!`, because the hotspot's password is on a public card.
  **SSH/VNC from the hotspot** sets it to always or never.
- **Before the first start:** a file `rasqberry-hotspot.txt` on the card's boot
  partition (the CONFIG partition on the A/B image) with lines such as
  `HOTSPOT_SSID=Booth`, `HOTSPOT_PASSWORD=…`, `HOTSPOT_AT_BOOT=yes` sets the hotspot up.

## Remote access

On most networks the Pi is `rasqberry.local`; otherwise use its IP address. Log in
with the user from Imager, otherwise `rasqberry` / `Qiskit1!`.

### First access without a screen

Without a user or SSH key from Imager, the Pi protects its published password:

1. **Log in over SSH within 15 minutes:** `ssh rasqberry@rasqberry.local`, password
   `Qiskit1!`. The 15 minutes start when the Pi is on the network; on the very first
   start, wait for its restart. Missed it? Switch the Pi off and on.
2. **Set your own password.** The Pi asks right away: `Qiskit1!`, then the new
   password twice. It is also your password for VNC and `sudo`.
3. **VNC comes on** once the password is changed.

With a screen, change the password in the setup checklist instead. To change the
rules, edit `rasqberry_boot.env` on the boot drive (bootfs; BOOT-A or BOOT-B on the
A/B image): remove the `#` and set a value. `DEFAULT_PW_WINDOW_MIN=30` gives 30
minutes (`0`: keys only); `DEFAULT_PW_WINDOW_VNC=yes` turns VNC on as well, for a
classroom or booth.

### SSH

SSH is on: `ssh rasqberry@rasqberry.local`, or `ssh <user>@rasqberry.local` with
your own user. Once you have your own password, `ssh-copy-id <user>@rasqberry.local`
lets you log in with your key.

### VNC (the desktop)

VNC comes on once the Pi has your own password. Use **RealVNC Viewer** or
**TigerVNC** and connect to `rasqberry.local`; the Mac's Screen Sharing, TightVNC
and UltraVNC can't connect. Give the Pi a minute after switching on. Switched off in
**3 Interface Options** → **VNC**, it stays off.

Start display demos on the desktop, locally or over VNC: over SSH they have no screen.

### Raspberry Pi Connect

The desktop and a terminal in your browser, from anywhere: the Connect icon in the
taskbar → **Turn On Raspberry Pi Connect** → **Sign In** (a free Raspberry Pi ID),
then open [connect.raspberrypi.com](https://connect.raspberrypi.com). Imager can sign
it in before the first start.

## Sound

Sound plays over HDMI or a Bluetooth speaker (Bluetooth icon → **Add Device**;
right-click the volume icon to pick the output). A Bluetooth speaker plays late:
**0 RasQberry** → **Desktop Settings** → **Sound delay** → **Calibrate** plays ticks
with flashes on the LED panel; adjust until they come together.

## Password

Everyone who reads this website knows `Qiskit1!`. On a shared network, set your own:
in the setup checklist, with `passwd`, or **1 System Options** → **S3 Password**.
Keep it only for a booth (then see [first access without a screen](#3-first-access-without-a-screen)).
