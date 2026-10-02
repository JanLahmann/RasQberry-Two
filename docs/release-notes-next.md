<!-- Draft header for the next release (beta round 4). Paste it above the
generated changelog in the GitHub release body; GitHub hides these comments.
CONDITIONAL: A/B default - the lines marked [A/B default] apply only if this
round ships the A/B fixes (batches B2 and B4) and the menu update test H-34
passes. Otherwise use the alternative given in the comment next to them. -->

## What's new for you

**Which image**

- **New default: the A/B image** [A/B default]. It holds two systems on one card: updates go into Slot B, and if the new system does not start, the Pi goes back to Slot A.
  <!-- If A/B is not the default: "The standard image stays the default. The A/B image is recommended for cards of 64GB or more: updates install in place and you can go back." -->
- **64GB or larger card:** the A/B image. **16GB or 32GB card:** the A/B image runs as one system, or take the standard image ("single system" in Imager) [A/B default]. On a small card, a new release means writing a new card.
- **Raspberry Pi Imager:** pick **RasQberry Two Beta** and skip OS customisation. Login `rasqberry`, password `Qiskit1!`.

**First start**

- The first start prepares the card and restarts on its own. It takes a few minutes: do not unplug.
- A/B image on a card of 64GB or more: the card is split into two systems automatically. To keep the card as written, put an empty file `no-auto-expand` (or `no-auto-expand.txt`) on the CONFIG drive before the first start.
- A setup checklist opens once on the first desktop login: Wi-Fi, an optional password change, the LED panel check, Download all demos, touch mode.
- VNC is switched on once at the first start and stays off if you switch it off.

**Updating later (A/B image)**

- **Software & Image Updates** → **Check for a newer image** → **Install now**, or **Slot Manager** → **Install an update into Slot B (testing)**: about 1.7GB, 20–30 minutes, then the Pi restarts into Slot B.
- When Slot B works, **Slot Manager** → **Make Slot B the stable system (copy B to A)** makes it your stable system again.
- **Kept:** your own programs (`~/My-Quantum-Programs`), the Shared folder, your IBM Quantum account (`~/.qiskit`), Wi-Fi networks and LED settings live on `/data`; your password, hostname, language, keyboard and SSH keys are copied to the new system. **Not kept:** installed demos download again; other files in your home folder stay in the other slot.
- **Going back:** **Slot Manager** → **Restart into Slot A (stable)**. If a new system does not start properly, the Pi goes back to the old one by itself, at the latest after 15 minutes; if the screen stays black, switch it off and on. If it still does not start, set `boot_partition=2` under `[all]` in `autoboot.txt` on the CONFIG drive.
- **Standard image:** OS updates through the taskbar updater or `sudo apt full-upgrade`. A new RasQberry release means writing a new card: back up your notebooks and `~/.qiskit` first.

**Coming from an earlier beta**

- A standard card cannot become an A/B card. Back up your notebooks and `~/.qiskit`, then write the new image.
- A/B cards from beta round 3: the round-3 update menu stops with a false "corrupted" error. On Slot A, run it from a terminal with the output in a file: `sudo rq_update_slot.sh <URL of the -ab image> <release tag> --slot B > ~/update.log 2>&1`. Or write a new card.
- **Raspberry Pi 4:** the A/B image needs a recent bootloader. If the card does not start, update it with Imager: **Misc utility images** → **Bootloader** → **SD Card Boot**.

**Known issues**

- doQumentation (Workshop Server): code cells fail, because the current upstream image has no Qiskit ([doQumentation#958](https://github.com/JanLahmann/doQumentation/issues/958)).
- Report problems in [Issues](https://github.com/JanLahmann/RasQberry-Two/issues) and paste the output of `rq_info.sh --json`.

Guides: [installation](https://rasqberry.org/02-software/01-installation-overview/) · [A/B image](https://rasqberry.org/02-software/03-ab-boot/) · [demos](https://rasqberry.org/03-quantum-computing-demos/00-overview/)
