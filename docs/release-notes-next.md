<!-- Draft header for the next release (beta round 4). Paste it above the
generated changelog in the GitHub release body; GitHub hides these comments.
Release day: switch on AB_IMAGER_CUSTOMISATION in .github/scripts/consolidate_json.py
on main (or set RQB_AB_CUSTOMISATION=true). Until then Imager skips the
customisation step for the A/B image, and the first bullet on Imager below is
only true for the standard image. -->

## What's new for you

**Which image and card**

- **New default: the A/B image.** It holds two systems on one card: an update goes into the one you are not running, and if the update doesn't work, the Pi goes back to the other one.
- **Card:** 128 GB high-speed (A2/U3) recommended: two systems, each with room for all Docker demos. 64 GB: two systems. On a smaller card the A/B image runs as one system by itself, and a new release means writing a new card. The Docker demos need 32 GB. The standard image is still in Imager as "single system".
- **Raspberry Pi Imager:** pick **RasQberry Two Beta**. OS customisation now works on both images: Wi-Fi, keyboard and time zone, SSH key, password, hostname. Keep the user name `rasqberry` (another name is not used: the password and SSH key go to `rasqberry`). It applies at the first start of a newly written card only, not after an update. Without customisation: login `rasqberry`, password `Qiskit1!`.

**First start**

- The first start prepares the card and restarts on its own. It takes a few minutes: do not unplug.
- A/B image on a card of 64 GB or more: the card is split into two systems automatically. To keep the card as written, put an empty file `no-auto-expand` (or `no-auto-expand.txt`) on the CONFIG drive before the first start.
- A setup checklist opens at the first desktop or SSH login, until someone answers it: keyboard and time zone, Wi-Fi, an optional password change, a name for the Pi, the LED panel check, Download all demos, touch mode.
- The LED panel check asks which kit you have (one 24x8 panel or four 4x12 panels), without a pre-selected answer, and has a "no LED panel" answer. Text, logos and the IP address scroll follow it: they are no longer scrambled on the four-panel kit. **Configure Matrix Layout** is gone.
- VNC is switched on once at the first start and stays off if you switch it off.
- RasQberry menu: **Remote Access & Security** changes the password, switches SSH and VNC on or off and names the Pi; **Desktop Settings** has touch mode and the browser at login. **System Info** shows the Pi's name, address, model and RAM, power and free space; an SSH login shows the name and address, and `rq_help` lists the commands.

**Updating later (A/B image)**

- **Software & Image Updates** → **Check for a newer image** → **Install now**, or **Slot Manager** → **Install an update into the other system**: about 1.7 GB, 10–20 minutes, then the Pi restarts into it. Every release in the list is checked against its SHA256 before anything is written.
- Updates take turns: each goes into the slot you are not running, Slot A or B, and becomes the start slot when it works. The other slot keeps the previous system. RasQberry warns before a downgrade and before it replaces your last beta or stable system.
- **Kept:** your own programs (`~/My-Quantum-Programs`), the Shared folder, your IBM Quantum account (`~/.qiskit`), Wi-Fi networks and LED settings live on `/data`; your password, hostname, language, keyboard and SSH keys are copied to the new system. **Not kept:** installed demos, Docker demos included, download again; other files in your home folder stay in the other slot.
- **Going back:** **Slot Manager** → **Switch to Slot A** (or B). If an update doesn't work, the Pi goes back to the previous system by itself, at the latest after 15 minutes; if the screen stays black, switch it off and on. If that does not help, set `boot_partition=2` (Slot A; `3` for Slot B) under `[all]` in `autoboot.txt` on the CONFIG drive.
- **Standard image:** OS updates through the taskbar updater or `sudo apt full-upgrade`. A new RasQberry release means writing a new card: back up your notebooks and `~/.qiskit` first.

**In the taskbar**

- **Slot badge (A/B image):** shows the running slot, A or B. Green: confirmed. Amber: a new system is being checked, or a restart is due. Red with "!": an update or switch didn't work and the Pi went back. Click it for both slots, System Info and updates.
- **Update notices:** a new release shows once, with a short "What's new" and where it would go; an SSH login shows it as one line. Betas and stable releases appear a few days after release, and not on every Pi at once. On the standard image and on cards with one system, a grey badge appears only while a new release is available.

**Coming from an earlier beta**

- A standard card cannot become an A/B card. Back up your notebooks and `~/.qiskit`, then write the new image.
- A/B cards from beta round 3: the round-3 update menu stops with a false "corrupted" error. On Slot A, run it from a terminal with the output in a file: `sudo rq_update_slot.sh <URL of the -ab image> <release tag> --slot B > ~/update.log 2>&1`. Or write a new card.
- **Raspberry Pi 4:** the A/B image needs a recent bootloader. If the card does not start, update it with Imager: **Misc utility images** → **Bootloader** → **SD Card Boot**.

**Learning paths and new demos**

- **Learning paths (beta):** four short tours through the demos (a stand, a school lesson, entanglement, your first program). Each step says what to try and what to notice and starts the demo for you; at the end, **Keep going** and **Where to go next** suggest what to do after. The **Learning paths** icon, **Quantum Demos** → **Learning paths**, or [on the website](https://rasqberry.org/03-quantum-computing-demos/02-learning-paths/).
- **Workshop & Qiskit Server** (built on doQumentation): one Pi serves the IBM Quantum tutorials, guides and courses to a class's laptops over the network, with live Qiskit code. Opening it again while it runs keeps it running and shows the addresses; only the window that started it offers to stop it. It also starts over SSH without a screen and prints the addresses. Anyone on the network can run code on the Pi: use a network you trust, not public Wi-Fi. Restarting it restores the original notebooks.
- **Qiskit Tutorials on this Pi:** the same tutorials just for you, on this Pi only (not on the network), with less memory. It opens the browser and stops with its window.
- **Beta demos:** new and less-tested demos say "(beta)" in the menus (Learning paths, Workshop & Qiskit Server, Qiskit Tutorials on this Pi, traQmania, the Fun with Quantum website and family) and ask for your feedback when they start.
- **My Quantum Programs** opens JupyterLab at `Hello-World.ipynb`, the first circuit from doQumentation. Existing folders get it once; your files are never replaced. JupyterLab no longer asks about Jupyter news.
- **Grokking the Bloch Sphere** shows tips (what to try, what to notice) and a short explanation with links to IBM Quantum Learning. One menu entry, with the online version as a second choice.
- The **Fun with Quantum** desktop icon offers the games, the website (works offline) and the family. Its website copy now includes the Workshops page.

**Running demos**

- Every demo stops the same way: Enter or Ctrl+C in its window, or close the window (desktop icon, RasQberry menu, SSH). Docker demos stop with their window; the Workshop & Qiskit Server keeps running until you stop it. **Quantum Demos** → **Stop Docker demos** stops any of them. A browser tab a demo opened stays open.
- Website demos (Composer, Grokking the Bloch Sphere online, catalogue demos) open their tab from every icon.
- Every demo is pinned to a tested version for this release (notebooks by commit, Docker images by digest). **Quantum Demos** → **Update demos** moves one demo to a newer upstream version (for the Workshop & Qiskit Server: the latest doQumentation build or one in between, with date, size and Qiskit version), or back.
- Quantum Mixer downloads a ready image instead of building for 15–30 minutes. Quantum Lab keeps what you save in `my-work` (`~/RasQberry-Two/work/quantum-lab`).
- Notebook demos also start over SSH and print an `ssh -L` command for your computer.
- The desktop icon **RasQberry Configuration (raspi-config)** (was RasQberry Menu) opens raspi-config with **0 RasQberry**.

**LEDs and IBM Quantum account**

- **LEDs** → **LED brightness**. If the Pi 5's LED panel stops because the power supply is too weak, RasQberry says so, restarts the LED driver and offers a lower brightness. Use the official 27 W power supply.
- **IBM Quantum account:** every demo runs on a simulator without one. For real quantum computers, create your own free account at quantum.cloud.ibm.com and use **IBM Quantum account** → **Save my API key**: the key is checked before it is saved. Running the credentials notebook of IBM Quantum Tutorials or Courses unedited no longer replaces a saved key.

**Problems and feedback**

- Report problems in [Issues](https://github.com/JanLahmann/RasQberry-Two/issues) and paste the output of `rq_info.sh --json`.
- The Pi reports anonymous counts (installs, update checks and results, update notice clicks, demo starts, learning paths, LED stalls) to the project's Umami statistics; no IDs are sent.

Guides: [installation](https://rasqberry.org/02-software/01-installation-overview/) · [A/B image](https://rasqberry.org/02-software/03-ab-boot/) · [demos](https://rasqberry.org/03-quantum-computing-demos/00-overview/) · [learning paths](https://rasqberry.org/03-quantum-computing-demos/02-learning-paths/)
