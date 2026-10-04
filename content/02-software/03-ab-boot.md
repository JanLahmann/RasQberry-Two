# A/B Image: Two Systems, One Card

The A/B image is the recommended RasQberry Two image (**RasQberry Two Beta** in
Raspberry Pi Imager). On a card of 64 GB or more it holds **two systems**, Slot A
and Slot B. **The SD card can stay in the Pi for good:** new releases install
over the air, each into the system you are not running, while the running one
stays as it is, so a failed update never leaves you without a working Pi.

## Card sizes

| Card | What you get |
|---|---|
| **128 GB, A2/U3 (recommended)** | Two systems, each with room for all Docker demos, and a shared data partition (10% of the card) |
| 64 GB | Two systems (about 28 GB each) and the shared data partition. Room for some Docker demos |
| 16 GB or 32 GB | One system that uses the whole card (Docker demos need 32 GB). There are no updates in place: write a new card for each release |

The standard image (**RasQberry Two Beta — single system**) is still published. It
is always one system, like the A/B image on a small card.

## First start

The first start prepares the card. It takes a few minutes and the Pi restarts
on its own: do not unplug it. It is done when the desktop appears.

On a card of 64 GB or more, the card is split into the two systems
automatically. To keep it as one system, create an empty file named
`no-auto-expand` on the **CONFIG** drive before the first start.

## Update

1. `sudo raspi-config` → **0 RasQberry** → **Software & Image Updates** →
   **Check for a newer image** tells you whether a new release is out. A
   terminal or SSH login also shows a one-line notice.
2. **Slot Manager** → **Install an update into the other system**. It downloads
   about 1.7 GB and takes 10–20 minutes, then the Pi restarts into the new system.
3. If the update works, the new system becomes the one the Pi starts from. If
   it doesn't, the Pi goes back to the other one by itself.

Updates take turns between Slot A and Slot B. The slot you left keeps the
previous system, so you can go back to it.

RasQberry warns you before a downgrade (an older release, or a development
build over a beta), and before it replaces your only beta or stable system.
Then it suggests the safer way: switch to that system first and install the
update into the other slot.

## What an update keeps

- the **Shared** and **My-Quantum-Programs** folders in your home folder
- your IBM Quantum account (`~/.qiskit`)
- Wi-Fi networks and LED panel settings
- your password, the Pi's name, time zone, language and keyboard
- SSH keys, so remote logins keep working

Each system has its own demos: after an update they download again on their
first start, Docker demos included (2–4 GB each). Other files in your home folder
stay in the other slot: switch back to fetch them.

## Go back

- **Use the other system:** **Slot Manager** → **Switch to Slot A** (or B).
- **The screen stays black after an update:** switch the Pi off and on again.
  It starts the previous system.
- **Still nothing on the screen:** put the card in a computer and open the
  **CONFIG** drive. In `autoboot.txt`, under `[all]`, set `boot_partition=2`
  (Slot A), save, and put the card back.

**System Info** in the RasQberry menu shows what each slot holds and which one
you are running.

## Raspberry Pi 4

The A/B image needs a recent bootloader. If a Pi 4 does not start from the
card, update its bootloader with Raspberry Pi Imager (**Misc utility images** →
**Bootloader** → **SD Card Boot**), then try again.

## Details

The partition layout, the boot mechanism and the command-line tools are in
[docs/ab-boot.md](https://github.com/JanLahmann/RasQberry-Two/blob/development/docs/ab-boot.md).
