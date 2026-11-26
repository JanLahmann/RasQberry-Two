# RasQberry Installation Overview

Write RasQberry Two to an SD card, start your Pi, and keep it up to date.

## What you need

- **Raspberry Pi 5** (8 GB RAM recommended, 2 GB is enough) or **Raspberry Pi 4B** (4 GB RAM or more).
- **MicroSD card:** 16 GB minimum; recommended 128 GB, A2/U3.
- **Official power supply** (27 W for the Pi 5, 15 W for the Pi 4) and, on the Pi 5, an active cooler.
- **Internet:** most demos download on their first start.
- Optional: the LED panel, a display, keyboard and mouse. Without a display, use
  [VNC](/02-software/02-system-options/).

All parts, including the 3D-printed case: [bill of materials](/01-3d-model/01-bill-of-materials/).

## Which image?

Pick **RasQberry Two Beta**, whatever your card. From 64 GB it holds two systems, so
new releases install over the air and you can always go back
([A/B image](/02-software/03-ab-boot/)). Docker demos need 32 GB or more
([card sizes](/details/installation/#2-card-sizes-and-docker-demos)).

## Write the card

{/* Old anchor, kept for links from the README */}
<span id="3-one-click-open-in-raspberry-pi-imager-recommended" />

Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/) 2.0.3 or newer, then:

<p><a className="cta-button" href="rpi-imager://open?repo=https://RasQberry.org/RQB-images.json" data-umami-event="RasQberry Two: imager open" data-umami-event-where="installation" data-umami-event-stream="beta">▶ Write RasQberry Two to your SD card</a></p>

1. Let your browser open Imager and confirm **Switch repository**.
2. **Device:** your Pi. **OS:** **RasQberry Two Beta**. **Storage:** your card; writing erases it.
3. **Customisation** (optional), then **Write**. Put the card in the Pi and switch it on.

### Customisation

Set your Wi-Fi, time zone, user name, password and SSH key in Imager, and the Pi needs no screen
([all options](/details/installation/#2-imager-customisation)).

### If the link does not open Imager

Add `https://RasQberry.org/RQB-images.json` in Imager under **App Options** → **Content
Repository** → **Use custom URL** ([other ways](/details/installation/#2-if-the-link-does-not-open-imager)).

## First start

The first start takes a few minutes, and the Pi may restart on its own: don't unplug it.
Then the desktop opens with the setup checklist. Without a screen, log in over SSH or VNC
with the user from Imager ([first access without a screen](/02-software/02-system-options/#3-first-access-without-a-screen)).

### Setup checklist

It offers what still needs you: keyboard and time zone, Wi-Fi, your own password, the LED
panel, and downloading all demos. Every step can wait; the **RasQberry Setup** icon opens
the list again ([all steps](/details/installation/#2-first-start-and-the-setup-checklist)).

## The RasQberry menu

Demo icons and group folders are on the desktop. Everything else is in the menu: open
**RasQberry Configuration**, then **0 RasQberry**
([what each entry does](/details/installation/#2-the-rasqberry-menu)).

<img src="/installation-images/rasqberry-menu.webp" width="800" height="577" loading="lazy" alt="The RasQberry main menu: Quantum Demos, Setup Checklist, Desktop Settings, IBM Quantum account, Remote Access & Security, Wi-Fi Hotspot, Software & Image Updates, System Info, Advanced, Shut Down Safely" className="media-image" />

## Keeping up to date

- **System updates:** the update icon in the taskbar.
- **New RasQberry releases:** on the A/B image, install into the other system
  ([how](/02-software/03-ab-boot/)). Otherwise write a new card: copy your notebooks
  and `~/.qiskit` (a hidden folder: Ctrl+H in the file manager) to a USB stick
  first. The Pi tells you when a release is out.

All images: [rasqberry.org/latest/](/latest/).

## Troubleshooting

- **Can't find the Pi:** try `rasqberry.local`, or read the IP address from the LED panel
  at start-up or in **System Info**.
- **VNC doesn't connect:** it stays off until you set your own password
  ([remote access](/02-software/02-system-options/)).
- **"Failed to run demo":** the message names the cause, usually no network on a first start.
- **LED panel stays dark:** [LED troubleshooting](/03-quantum-computing-demos/led-display/).
- Disk full, other problems, and how to send us a report: [troubleshooting details](/details/installation/#2-troubleshooting).
