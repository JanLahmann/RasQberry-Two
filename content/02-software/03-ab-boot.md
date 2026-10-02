# A/B Image: Two Systems, One Card

{/* CONDITIONAL: A/B default. If A/B is not the default of this release, replace
the next paragraph with: "Alongside the standard image we publish an A/B image.
It is recommended for cards of 64GB or more: updates install in place and you
can always go back." */}

The A/B image is the recommended RasQberry Two image. On a card of 64GB or more
it holds **two systems**, Slot A and Slot B. An update goes into Slot B while
Slot A keeps the system that works, so a failed update never leaves you without
a working Pi.

## Card sizes

| Card | What you get |
|---|---|
| 64GB or more | Two systems (about 26GB each on a 64GB card) and a shared data partition (10% of the card) |
| 16GB or 32GB | One system that uses the whole card. There are no updates in place: write a new card for each release |

The standard image is still published. It is always one system, like the A/B
image on a small card.

## First start

The first start prepares the card. It takes a few minutes and the Pi restarts
on its own: do not unplug it. It is done when the desktop appears.

On a card of 64GB or more, the card is split into the two systems
automatically. To keep it as one system, create an empty file named
`<opt-out marker>` on the **CONFIG** drive before the first start.

## Update

1. `sudo raspi-config` → **0 RasQberry** → **Software & Image Updates** →
   **Check for a newer image** tells you whether a new release is out. A
   terminal or SSH login also shows a one-line notice.
2. **Slot Manager** → **Update Slot B with new image**. It downloads about
   1.7GB and takes 20–30 minutes, then the Pi restarts into Slot B.
3. If Slot B starts properly, it is kept. If not, the Pi goes back to Slot A
   by itself.
4. Once you are happy with Slot B, **Slot Manager** → **Promote Slot B to
   Slot A** copies it to Slot A, which becomes your stable system again. Restart afterwards.
   The next update goes into Slot B again.

Promoting replaces everything in Slot A, including the files in your home folder
there. Keep anything you want to keep in the **Shared** folder.

## What an update keeps

The shared data partition (`/data`) carries these into the new system:

- the **Shared** folder in your home folder
- your IBM Quantum account (`~/.qiskit`)
- Wi-Fi networks
- LED panel settings
- SSH keys, so remote logins keep working

Installed demos are downloaded again on their first start. Other files in your
home folder stay in the other slot: switch back to fetch them.

## Go back

- **Use the other system:** **Slot Manager** → **Switch to Slot A** (or B).
- **The Pi does not start after an update:** switch it off and on again. It
  starts the previous system.
- **It still does not start:** put the card in a computer and open the
  **CONFIG** drive. In `autoboot.txt`, under `[all]`, set `boot_partition=2`
  (Slot A), save, and put the card back.

**System Info** in the RasQberry menu shows the version and the slot you are
running.

## Raspberry Pi 4

The A/B image needs a recent bootloader. If a Pi 4 does not start from the
card, update its bootloader with Raspberry Pi Imager (**Misc utility images** →
**Bootloader** → **SD Card Boot**), then try again.

## Details

The partition layout, the boot mechanism and the command-line tools are in
[docs/ab-boot.md](https://github.com/JanLahmann/RasQberry-Two/blob/development/docs/ab-boot.md).
