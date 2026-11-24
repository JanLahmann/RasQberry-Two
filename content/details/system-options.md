# System options: details

Background for the [system options page](/02-software/02-system-options/): every rule and setting.

## Wi-Fi without a screen

A new Pi that has never had a network opens the Wi-Fi **RasQberry-Setup-XXXX** after
about two minutes, password `rasqberry` (an LED panel scrolls both). Join it with your
phone: a page lists the networks in range; pick yours. It closes after 30 minutes
unused (an hour at most); switch the Pi off and on to open it again.

Wi-Fi in the menu: `sudo raspi-config` → **1 System Options** → **S1 Wireless LAN**. The
Pi remembers its networks and reconnects by itself. Its IP address: **System Info**,
`hostname -I`, or the LED panel at start-up.

## Hotspot settings

All in **0 RasQberry** → **Wi-Fi Hotspot**:

- **Join card** opens a page with the name, password and QR codes, to show or print.
  Over SSH, **Show name, password and QR codes** prints them.
- **Name and password:** `RasQberry-XXXX` and a random password, unless you set your own.
- **Start at boot**, **share this Pi's internet**, and the **band** (5 GHz; 2.4 GHz for
  older devices).
- **One Wi-Fi can't do both:** the hotspot takes a USB Wi-Fi adapter if there is one.
  Otherwise the built-in Wi-Fi leaves your network while the hotspot runs; a network
  cable keeps the Pi online.
- **SSH and VNC from the hotspot:** by default only once no account that can use `sudo`
  still has `Qiskit1!`, because the hotspot's password is on a public card.
  **SSH/VNC from the hotspot** sets it to always or never.
- **Before the first start:** a file `rasqberry-hotspot.txt` on the card's boot partition
  (the CONFIG partition on the A/B image) with lines such as `HOTSPOT_SSID=Booth`,
  `HOTSPOT_PASSWORD=…`, `HOTSPOT_AT_BOOT=yes` sets the hotspot up.

## The SSH window for the published password

The 15 minutes start when the Pi is on the network; on the very first start, wait for its
restart. The Pi asks for `Qiskit1!`, then the new password twice.

To change the rules, edit `rasqberry_boot.env` on the boot drive (bootfs; BOOT-A or
BOOT-B on the A/B image): remove the `#` and set a value. `DEFAULT_PW_WINDOW_MIN=30`
gives 30 minutes (`0`: keys only); `DEFAULT_PW_WINDOW_VNC=yes` turns VNC on as well, for
a classroom or booth.

## SSH keys

Once you have your own password, `ssh-copy-id <user>@rasqberry.local` lets you log in
with your key. Imager can also put your key on the card before the first start
([customisation](/details/installation/#2-imager-customisation)).

## VNC clients

Besides RealVNC Viewer and TigerVNC, other clients fail: the Mac's Screen Sharing,
TightVNC and UltraVNC can't connect. Give the Pi a minute after switching on. Switched off in `sudo raspi-config`
→ **3 Interface Options** → **VNC**, it stays off.

## Raspberry Pi Connect

The desktop and a terminal in your browser. The Connect icon in the taskbar → **Turn On Raspberry Pi Connect** → **Sign In** (a free
Raspberry Pi ID), then open [connect.raspberrypi.com](https://connect.raspberrypi.com).
Imager can sign it in before the first start.

## Sound output and delay

Pair a speaker with the Bluetooth icon → **Add Device**; right-click the volume icon to
pick the output. **Calibrate** (under **Sound delay**) plays ticks with flashes on the LED
panel; adjust the delay until
they come together.

## Changing the password

In the setup checklist, with `passwd`, or `sudo raspi-config` → **1 System Options** →
**S3 Password**.
