<!-- Draft header for the next release (beta round 4). Paste it above the
generated changelog in the GitHub release body; GitHub hides these comments.
Release day: switch on AB_IMAGER_CUSTOMISATION in .github/scripts/consolidate_json.py
on main (or set RQB_AB_CUSTOMISATION=true). Until then Imager skips the
customisation step for the A/B image, and the first bullet on Imager below is
only true for the standard image. -->

## Since beta-2026-10-04

- **Raspberry Pi OS Trixie:** RasQberry Two now runs on Trixie (Debian 13, 64-bit) with Python 3.13, the new desktop (labwc and the new taskbar) and Chromium from Debian. Every demo, the LED drivers on the Pi 4 and Pi 5, and A/B updates from the Bookworm beta were tested on both Pis.
- **Quantum Lab:** starts again. QuBins removed the image build this release pinned, so the first start failed with "The registry does not offer ...". It now uses QuBins 2.5-xl (Qiskit 2.5.2), and when a publisher removes a pinned build again, the Docker demos download the image's named tag instead and say so in one line.
- **Wi-Fi at the first start:** when the router turns the Pi away at first, the Pi now tries again by itself instead of staying offline until someone connects it by hand.
- **Workshop & Qiskit Server:** the participants' address now also shows as a QR code.
- **LED panel:** until the setup checklist's LED check is answered, the address scroll at start-up alternates between the layouts of the two kits, so every second pass is readable on the four-panel kit too.
- **Updates need much less free space:** an A/B update now unpacks the image straight into the other slot instead of into a 12 GB file first. It needs the download plus 0.5 GB free (about 2.5 GB) instead of 15 GB, so a 64 GB card with all Docker demos can update too.
- **On-screen LED view:** it now closes when the LED demo ends; the demo loop keeps one view until the loop stops.
- **LED Demos from a terminal:** `rq_demo_run.sh led-demos` without a part shows the list of LED demos (without a terminal: the commands for each) instead of an error.
- **Demo catalogue:** the install question says who provides each demo (traQmania: the Fun with Quantum family; the SAP demos: SAP).
- **Catalogue web and Docker demos:** their desktop icons open a window, so the demo stops like the others (Enter, Ctrl+C or closing the window). SAP Quantum Learning used to keep running with no way to stop it.
- **Catalogue Docker demos (traQmania):** when one stops right after it starts, its log is kept and its last lines are shown.
- **Workshop & Qiskit Server:** the start text says that running code in the notebooks needs the internet for now.
- **Plain words:** the update picker says "release stream" instead of "channel"; the Slot Manager status shows sizes in GB and the names Slot A and Slot B; the LED settings say "LED panel" and "on-screen view"; a failed catalogue install and the Workshop & Qiskit Server no longer name pip or Docker commands.
- **Slot Manager:** it offers only what works (no switch or rollback while the other slot is empty) and shows no internal tags. **Slot details** says in plain words what each slot holds and what the next restart does, and fits the screen over SSH. When nothing newer is out, the update picker says "You have the newest beta release". After an update is written, System Info and the slot badge show the new system at once, and the badge's tooltip no longer covers its menu.
- **Password:** changing it, in the menu or the setup checklist, uses two password boxes with Cancel instead of a prompt that Esc and Ctrl+C could not leave.
- **Remote Access & Security:** says "key only" when SSH takes no password (Imager's public-key setting). SSH logins no longer show a misleading "Last login" line.
- **LED panel stops (Pi 5):** the message names only what the Pi reported during that demo: too little power (then it offers a lower brightness), too hot (with what helps: the Active Cooler and its fan), or neither. A demo now waits until the previous one has let go of the LED panel, and a hiccup on the very first frame is recovered without a message. RasQ-LED keeps one LED driver open for the whole run, runs until you stop it and ends without an error message.
- **First LED demo after the LED check (Pi 4):** the panel no longer stays dark. The LED check left the LED hardware half-stopped; it now finishes cleanly, and LED programs reset it if needed. The address scroll after "Saved" shows on the Pi 5 too.
- **LED stall message:** its title says what happened: "LED panel stalled briefly" when the panel went on after a restart, "LED panel stopped" only when it really stopped.
- **Stopping an LED demo (Pi 4):** the LED driver now gives its graphics memory back. Each stop used to keep a little, so a Demo Loop running for days could run out.
- **System Info:** says whether the Pi is too hot now or was slowed down earlier, with one line of advice, and "Slot B: empty" like the menu.
- **LED settings:** the LED check says "Saved: four 4x12 panels" and scrolls the address once in that layout; the setup checklist names the kit the same way. LED brightness and **Turn off all LEDs** confirm in one line, the "LED panel in use" dialog names the demo, and turning the browser view off stops its server.
- **LED-Painter:** a picture reaches both the panel and the on-screen view. Before it starts, another program on the panel is named, with the offer to stop it, and if the LED renderer does not start, one line says that the panel stays dark.
- **Demo Loop:** choose which demos it shows (**Continuous Demo Loop** → **Choose the demos**); the Demo Loop icon shows the same ones, and the choice stays after an update.
- **Learning paths:** the step texts match what the demos do ("Your first program" uses Hello World instead of the CHSH tutorial, which fails on the Pi for now). The window gets its title back after a demo, and "Tell us how it went" opens the feedback form (it needs a free GitHub account). The setup checklist's last screen recommends "First 15 minutes".
- **Browser demos:** the browser window covers the demo's terminal, so the stop line says how to get back to it (click it in the taskbar).
- **Browser demo windows:** they open maximised every time. Some opened 480 px to the right with their buttons off-screen, or at the homepage's size.
- **Stop Docker demos** (Quantum Demos): finds the running Workshop & Qiskit Server, Quantum Lab, Qoffee-Maker and Quantum Mixer, and says what it stopped. It used to return without a word.
- **Qoffee-Maker:** shows the app instead of a line of raw text ("AppBox(...)").
- **Quantum Lab:** opens on a welcome page without the Jupyter news question, and has a desktop icon. **IBM Quantum Tutorials and Courses** show only the notebooks, each in its own workspace, and point to **IBM Quantum account** → **Save my API key**; they stop without a "Killed" line and close their tab.
- **Workshop & Qiskit Server and `ssh -L` commands:** they use the name avahi announces, so with two Pis of the same name, participants reach this one. Grokking the Bloch Sphere also starts over SSH and prints an `ssh -L` command.
- **Downloads:** Download all demos shows the MB received, fetches the small demos first and gives realistic times. A Docker demo's first start shows one progress line instead of Docker's list of layers.
- **Demo catalogue:** a Docker demo says "Registered" with the size it downloads on its first start, the descriptions fit the screen, and removing a demo says so. **Update demos** marks only notebook demos "(notebooks)", Composer no longer says it needs an account, and Quantum Lights Out is described as Grover's search solving the puzzles by itself.
- **Raspberry Pi Imager:** ready for Raspberry Pi Connect from Imager: its sign-in goes to the Pi's user, also when Imager's user name could not be used.
- **Your own user name (#319):** the user name typed in Imager becomes the login, with its home folder `/home/<name>`; the Python environment, autologin, sudo and the LED services move along. If the name cannot be used (e.g. it is taken by the system), the user stays `rasqberry` and the first login says why. After an A/B update the new system takes the name over before the first login. Installing an older release that only knows `rasqberry` is blocked unless you type RASQBERRY.

- **Firmware check:** at start-up the Pi looks at its bootloader firmware. When it is older than about six months and a newer one is available (or, on a Pi 5, its crypto service is missing), the desktop says so once and how to update with Raspberry Pi's own tools (`sudo rpi-eeprom-update -a`, then restart, or `sudo raspi-config` → Advanced Options → Bootloader Version). System Info and the setup checklist show it too. RasQberry never updates the firmware itself.
- **Firmware updates on A/B cards:** Raspberry Pi's tools now put the update on the card's first partition (CONFIG), where the Pi 4 looks for it. Before, `sudo rpi-eeprom-update -a` on an A/B card put it into the running slot, where it can stop a Pi 4 from starting.
- **Raspberry Pi Connect:** Remote Access & Security and System Info say whether Connect is on and signed in, and how to turn it on.
- **SSH from a Mac:** no more "setlocale: cannot change locale" lines at login.
- **Setup checklist:** the password step says the Pi "uses the published demo password", which is also right when that password was typed in Imager. System Info opened from the slot badge says "Press Enter to close this window".
- **Demo password:** while the Pi has the published demo password (no password set in Imager), the setup checklist's password step is ticked, and its last screen, the SSH login and Remote Access & Security say so (the latter also whether SSH and VNC accept it).
- **After an A/B update:** the LED panel settings come back every time (they were lost when `/data` was mounted late), and Raspberry Pi Connect stays signed in and on.
- **Small fixes:** "Switch SSH off?" defaults to Cancel; the Connect box mentions the firmware only when that can help; the firmware notice opens without a highlighted sentence; the checklist no longer says "Wi-Fi (connected)" on a Pi connected by cable; on a card with one system the Docker dialogs no longer mention "the other slot", and the SD-card note gives the size System Info shows; Enter stops the IBM LED Demo at once.

## What's new for you

**Which image and card**

- **New default: the A/B image.** It holds two systems on one card: an update goes into the one you are not running, and if the update doesn't work, the Pi goes back to the other one.
- **Card:** 128 GB high-speed (A2/U3) recommended: two systems, each with room for all Docker demos. 64 GB: two systems. On a smaller card the A/B image runs as one system by itself, and a new release means writing a new card. The Docker demos need 32 GB. The standard image is still in Imager as "single system".
- **Raspberry Pi Imager:** pick **RasQberry Two Beta**. OS customisation now works on both images: Wi-Fi, keyboard and time zone, SSH key, password, hostname. The user name you type becomes your login (home `/home/<name>`). It applies at the first start of a newly written card only; updates keep the name. Without customisation: login `rasqberry`, password `Qiskit1!`.

**First start**

- The first start prepares the card and restarts on its own. It takes a few minutes: do not unplug.
- A/B image on a card of 64 GB or more: the card is split into two systems automatically. To keep the card as written, put an empty file `no-auto-expand` (or `no-auto-expand.txt`) on the CONFIG drive before the first start.
- A setup checklist opens at the first desktop or SSH login, until someone answers it: keyboard and time zone, Wi-Fi, an optional password change, a name for the Pi, the LED panel check, Download all demos, touch mode.
- The LED panel check asks which kit you have (one 24x8 panel or four 4x12 panels), without a pre-selected answer, and has a "no LED panel" answer. Text, logos and the IP address scroll follow it: they are no longer scrambled on the four-panel kit. **Configure Matrix Layout** is gone.
- VNC is switched on once at the first start and stays off if you switch it off.
- RasQberry menu: **Remote Access & Security** changes the password, switches SSH and VNC on or off and names the Pi; **Desktop Settings** has touch mode and the browser at login. **System Info** shows the Pi's name, address, model and RAM, power and free space; **Shut Down Safely** switches the LEDs off and shuts the Pi down. An SSH login shows the name and address, and `rq_help` lists the commands.

**Updating later (A/B image)**

- **Software & Image Updates** → **Check for a newer image** → **Install now**, or **Slot Manager** → **Install an update into the other system**: about 1.7 GB, 10–20 minutes, then the Pi restarts into it. Every release in the list is checked against its SHA256 before anything is written.
- Updates take turns: each goes into the slot you are not running, Slot A or B, and becomes the start slot when it works. The other slot keeps the previous system. RasQberry warns before a downgrade and before it replaces your last beta or stable system.
- **Kept:** your own programs (`~/My-Quantum-Programs`), the Shared folder, your IBM Quantum account (`~/.qiskit`), Wi-Fi networks and LED settings live on `/data`; your password, hostname, language, keyboard, SSH keys and Raspberry Pi Connect (signed in, on or off) are copied to the new system. **Not kept:** installed demos, Docker demos included, download again; other files in your home folder stay in the other slot.
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
- **Workshop & Qiskit Server** (built on doQumentation): one Pi serves the IBM Quantum tutorials, guides and courses to a class's laptops over the network, with live Qiskit code. Opening it again while it runs keeps it running and shows the addresses; only the window that started it offers to stop it. It also starts over SSH without a screen and prints the addresses. Anyone on the network can run code on the Pi: use a network you trust, not public Wi-Fi. Running code in the notebooks needs the internet for now. Restarting it restores the original notebooks.
- **Qiskit Tutorials on this Pi:** the same tutorials just for you, on this Pi only (not on the network), with less memory. It opens the browser and stops with its window.
- **Beta demos:** new and less-tested demos say "(beta)" in the menus (Learning paths, Workshop & Qiskit Server, Qiskit Tutorials on this Pi, traQmania, the Fun with Quantum website and family) and ask for your feedback when they start.
- **My Quantum Programs** opens JupyterLab at `Hello-World.ipynb`, the first circuit from doQumentation. Existing folders get it once; your files are never replaced. JupyterLab no longer asks about Jupyter news.
- **Grokking the Bloch Sphere** shows tips (what to try, what to notice) and a short explanation with links to IBM Quantum Learning. One menu entry, with the online version as a second choice.
- The **Fun with Quantum** desktop icon offers the games, the website (works offline) and the family. Its website copy now includes the Workshops page.

**Running demos**

- Every demo stops the same way: Enter or Ctrl+C in its window, or close the window (desktop icon, RasQberry menu, SSH). Docker demos stop with their window; the Workshop & Qiskit Server keeps running until you stop it. **Quantum Demos** → **Stop Docker demos** stops any of them. A demo that runs on the Pi opens in a browser window of its own, maximised (Qoffee-Maker full screen), which closes when the demo stops.
- Website demos (Composer, Grokking the Bloch Sphere online, catalogue demos) open their tab from every icon.
- Every demo is pinned to a tested version for this release (notebooks by commit, Docker images by digest). **Quantum Demos** → **Update demos** moves one demo to a newer upstream version (for the Workshop & Qiskit Server: the latest doQumentation build or one in between, with date, size and Qiskit version), or back.
- Quantum Mixer downloads a ready image instead of building for 15–30 minutes. Quantum Lab keeps what you save in `my-work` (`~/RasQberry-Two/work/quantum-lab`).
- Notebook demos also start over SSH and print an `ssh -L` command for your computer.
- The desktop icon **RasQberry Configuration (raspi-config)** (was RasQberry Menu) opens raspi-config with **0 RasQberry**.

**LEDs and IBM Quantum account**

- **LEDs** → **LED brightness**. If the Pi 5's LED panel stops, RasQberry says why (too little power, or too hot), restarts the LED driver and, for a weak power supply, offers a lower brightness. Use the official 27 W power supply and, for long runs, the Active Cooler.
- **IBM Quantum account:** every demo runs on a simulator without one. For real quantum computers, create your own free account at quantum.cloud.ibm.com and use **IBM Quantum account** → **Save my API key**: the key is checked before it is saved. Running the credentials notebook of IBM Quantum Tutorials or Courses unedited no longer replaces a saved key.

**Problems and feedback**

- **Raspberry Pi Connect from Imager doesn't sign in:** update the firmware (`sudo rpi-eeprom-update -a`, then restart; [Raspberry Pi's guide](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#update-the-bootloader-configuration)), then sign in with the Connect icon in the taskbar.
- Report problems in [Issues](https://github.com/JanLahmann/RasQberry-Two/issues) and paste the output of `rq_info.sh --json`.
- The Pi reports anonymous counts (installs, update checks and results, update notice clicks, demo starts, learning paths, LED stalls) to the project's Umami statistics; no IDs are sent.

Guides: [installation](https://rasqberry.org/02-software/01-installation-overview/) · [A/B image](https://rasqberry.org/02-software/03-ab-boot/) · [demos](https://rasqberry.org/03-quantum-computing-demos/00-overview/) · [learning paths](https://rasqberry.org/03-quantum-computing-demos/02-learning-paths/)
