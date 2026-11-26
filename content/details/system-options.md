# System options details

Background for the [system options page](/02-software/02-system-options/): every rule and
setting.

## Wi-Fi without a screen

A new Pi that has never had a network opens the Wi-Fi **RasQberry-Setup-XXXX** after
about two minutes, password `rasqberry` (an LED panel scrolls both). Join it with your
phone: a page lists the networks in range; pick yours. It closes after 30 minutes unused
(an hour at most); switch the Pi off and on to open it again.

Wi-Fi in the menu: `sudo raspi-config` → **1 System Options** → **S1 Wireless LAN**. The
Pi remembers its networks and reconnects by itself. Its IP address in a terminal:
`hostname -I`; the LED panel also scrolls it at start-up.

## Hotspot settings

In **0 RasQberry** → **Wi-Fi Hotspot**:

- **Show name, password and QR codes** prints the join details over SSH.
- **Name and password:** `RasQberry-XXXX` and a random password, unless you set your own.
- **Start at boot**, **share this Pi's internet**, and the **band** (5 GHz; 2.4 GHz for
  older devices).
- **SSH/VNC from the hotspot:** always or never, instead of the default rule on the
  system options page.

To set the hotspot up before the first start, put a file `rasqberry-hotspot.txt` on the
card's boot partition (the CONFIG partition on the A/B image) with lines such as
`HOTSPOT_SSID=Booth`, `HOTSPOT_PASSWORD=…`, `HOTSPOT_AT_BOOT=yes`.

## The SSH window for the published password

On the very first start, wait for the Pi's restart before you log in. The Pi asks for
`Qiskit1!`, then the new password twice.

To change the rules, edit `rasqberry_boot.env` on the boot drive (bootfs; BOOT-A or
BOOT-B on the A/B image): remove the `#` and set a value. `DEFAULT_PW_WINDOW_MIN=30`
gives 30 minutes (`0`: keys only); `DEFAULT_PW_WINDOW_VNC=yes` turns VNC on as well, for
a classroom or booth.

## SSH keys

Once you have your own password, `ssh-copy-id <user>@rasqberry.local` lets you log in
with your key. Imager can also put your key on the card before the first start
([Imager customization](/details/installation/#2-imager-customisation)).

## VNC clients

The Mac's Screen Sharing, TightVNC and UltraVNC can't connect. Give the Pi a minute after
switching it on. Switched off in `sudo raspi-config` → **3 Interface Options** → **VNC**,
VNC stays off.

## Raspberry Pi Connect

The desktop and a terminal in your browser. The Connect icon in the taskbar → **Turn On
Raspberry Pi Connect** → **Sign In**, then open
[connect.raspberrypi.com](https://connect.raspberrypi.com). Imager can sign it in before
the first start.

## Sound output and delay

Pair a speaker with the Bluetooth icon → **Add Device**; right-click the volume icon to
pick the output. **Calibrate** (under **Sound delay**) plays ticks with flashes on the
LED panel; adjust the delay until they come together.

## Changing the password

Besides the setup checklist: **0 RasQberry** → **Remote Access & Security**, `passwd`, or
`sudo raspi-config` → **1 System Options** → **S3 Password**.
