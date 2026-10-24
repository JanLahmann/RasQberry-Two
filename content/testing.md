# Testing RasQberry Two

Thank you for helping us test RasQberry Two! About ten testers try every demo and
every function on their own Pis, so we find what breaks and what is hard to follow.

Testing runs by invitation. Would you like to help? Write to
[info@rasqberry.org](mailto:info@rasqberry.org) and tell us which Pi and hardware you have.

## Before you start: the right version

Test the **latest beta** or the **latest development image**, nothing older:

- **Latest beta:** in Raspberry Pi Imager, **RasQberry Two Beta**.
- **Latest development image:** in Imager, **RasQberry developer builds** →
  **RasQberry Two Dev A/B (development …)** with the newest date (**RasQberry Two Dev
  (development …)** is its single-system image). Other entries in that folder are
  experiments; leave them out.

The A/B image is best: on a card of 64 GB or more it updates over the air, so you stay
on the newest version. Missions that need the development image test what is not in
the beta yet.
**System Info** in the RasQberry menu shows your version; tell Ket which one you use.

## How it works

- **Talk to Ket, our AI tester helper** (bottom right on this page). Tell Ket your Pi model, your
  hardware (LED panel, touchscreen, Bluetooth speaker) and which demos you like, and it
  suggests missions that fit. Sign in with a tester name or ID you choose freely (any
  name, it need not be your real one), so it can keep track of your missions. The tester
  passphrase you got from us unlocks it.
- **Do the mission on your own.** A mission is a goal, not a recipe. Find your way with
  the [documentation](/) and Ket on the Pi's start page (the normal RasQberry helper), as any
  user would. On an image built before 16 October 2026, open
  [rasqberry.org/?from=pi&assistant=1](https://rasqberry.org/?from=pi&assistant=1) once in
  the Pi's browser: Ket then stays for that tab. In tester mode, Ket does not help with the
  mission itself; it points you there. Where the documentation or Ket leaves you stuck,
  that is a finding too.
- **Report back to Ket:** what worked, what didn't, confusing words, slow
  steps, ideas. It writes it down for us, and we follow up on GitHub.

Nearly everything is still an early beta that no person has tested yet: expect rough
edges. That is why we need you.

Most demos download on their first start: have internet then, or run **Download all
demos** first.

<div id="privacy"></div>

## What is recorded

Your messages are answered by Claude (Anthropic).
What we keep, and for how long: your tester name or ID (chosen by you, please no e-mail
address), your hardware and preferences, your conversations with Ket, the
findings you save, and which missions you started or finished. We keep them for 90 days,
then delete them. The tester passphrase is checked but never stored. We use this only to
find and fix problems in RasQberry; findings may become public GitHub issues, without
your name or ID. No IP address, no cookies.

## Missions

### Core RasQberry

- **First start**: Install RasQberry with Raspberry Pi Imager, with your own user name, password and Wi-Fi, and reach the desktop. Early beta, not yet tested by people: expect rough edges.
- **Setup Checklist**: Go through the Setup Checklist until its icon leaves the desktop: do each step, or skip it. Early beta, not yet tested by people: expect rough edges.
- **Desktop folders and menu**: Find each demo through its desktop folder and through the RasQberry menu. Early beta, not yet tested by people: expect rough edges.
- **Wi-Fi**: Join a Wi-Fi network, and see the Pi come back after the router restarts. Early beta, not yet tested by people: expect rough edges.
- **Update to a new release**: Install a release into the other system (a newer one, or the same again), start it, and go back. Early beta, not yet tested by people: expect rough edges. *(needs: internet, A/B image on a 64 GB card or larger)*
- **Slot icon and What's new**: Use the slot icon in the taskbar and read What's new after an update. Early beta, not yet tested by people: expect rough edges. *(needs: internet, A/B image on a 64 GB card or larger)*
- **Help and feedback**: Get help for a problem from the Pi: System Info, the helper and the website. Early beta, not yet tested by people: expect rough edges.

### RasQberry user

- **Download all demos**: Download all demos, then start a few without internet. Early beta, not yet tested by people: expect rough edges. *(needs: internet)*
- **Demo Loop**: Run the Demo Loop with demos of your choice, and let it start at login. Early beta, not yet tested by people: expect rough edges.
- **Learning paths**: Follow one learning path from start to end. Early beta, not yet tested by people: expect rough edges.
- **My Quantum Programs**: Write and run your own quantum program in My Quantum Programs. Early beta, not yet tested by people: expect rough edges.
- **IBM Quantum account**: Save your IBM Quantum API key and run a demo on a real quantum computer. Early beta, not yet tested by people: expect rough edges. *(needs: internet, IBM Quantum account)*
- **Add and remove a demo**: Add a demo from the catalogue, start it, and remove it again. Early beta, not yet tested by people: expect rough edges. *(needs: internet)*
- **LED views without a panel**: Watch an LED demo in the on-screen view and in the browser view. Early beta, not yet tested by people: expect rough edges.
- **Touchscreen**: Use the Pi by touch only: touch mode and the on-screen keyboard. Early beta, not yet tested by people: expect rough edges. *(needs: touchscreen)*

### RasQberry advanced configuration

- **LED panel setup**: Set up the LED panel: find its layout, check it, and set the brightness. Early beta, not yet tested by people: expect rough edges. *(needs: LED panel)*
- **Sound on a Bluetooth speaker**: Pair a Bluetooth speaker and calibrate the sound delay until tick and LED flash come together. Early beta, not yet tested by people: expect rough edges. *(needs: Bluetooth speaker, LED panel, development image)*
- **Remote access**: Reach the Pi from another computer: SSH, VNC and Raspberry Pi Connect. Early beta, not yet tested by people: expect rough edges. *(needs: internet)*
- **Wi-Fi hotspot**: Let phones and laptops join the Pi's own Wi-Fi and open its demos. Early beta, not yet tested by people: expect rough edges. *(coming soon)*
- **Updates on the single-system image**: Check for a newer image on the single-system image and follow what the Pi suggests. Early beta, not yet tested by people: expect rough edges. *(needs: internet, single-system image)*

### LED panel

- **LED Demos**: Try the LED demos: text, logos and colour effects on the LED panel. Early beta, not yet tested by people: expect rough edges. *(needs: LED panel)*
- **LED-Painter**: Paint a picture and show it on the LED panel. Early beta, not yet tested by people: expect rough edges. *(needs: LED panel, screen)*
- **Quantum Lights Out**: Watch Grover's search solve Lights Out, on the LED panel and in the console. Early beta, not yet tested by people: expect rough edges. *(needs: LED panel)*
- **Quantum Raspberry Tie**: Show measured qubits on the LED panel, from the simulator or, with an IBM Quantum account, a real quantum computer. Early beta, not yet tested by people: expect rough edges. *(needs: LED panel, screen)*
- **RasQ-LED Demo**: Show superposition and entanglement on the LED panel. Early beta, not yet tested by people: expect rough edges. *(needs: LED panel)*

### Big projects

- **Entangible**: Build a circuit with the printed gate tiles and let the camera read it. Early beta, not yet tested by people: expect rough edges. *(needs: camera (USB webcam or Pi camera), development image)*
- **Qoffee-Maker**: Order a coffee from a quantum computer, with or without a Home Connect machine. Early beta, not yet tested by people: expect rough edges. *(needs: screen, internet, SD card of 32 GB or more)*
- **Quantum Mixer**: Mix a cocktail, an ice cream or a coffee with a quantum circuit. Early beta, not yet tested by people: expect rough edges. *(needs: screen, SD card of 32 GB or more)*
- **racetraQ**: Race a car steered by a quantum agent and train your own. Early beta, not yet tested by people: expect rough edges. *(needs: internet, screen, SD card of 32 GB or more)*

### Play

- **Fun with Quantum: start here**: Open the Fun with Quantum start page and pick a game from it. Early beta, not yet tested by people: expect rough edges.
- **Fun with Quantum: Quantum Coin Game**: Play the Quantum Coin Game, first classically, then with the quantum H move. Early beta, not yet tested by people: expect rough edges.
- **Fun with Quantum: GHZ Game**: Play the GHZ Game and see how quantum players win. Early beta, not yet tested by people: expect rough edges.
- **Fun with Quantum: Hardy's Paradox**: Work through Hardy's Paradox. Early beta, not yet tested by people: expect rough edges.
- **Fun with Quantum: Mermin–Peres Magic Square**: Play the Mermin–Peres Magic Square. Early beta, not yet tested by people: expect rough edges.
- **Fun with Quantum: 3-SAT with Grover's Algorithm**: Solve a 3-SAT problem with Grover's algorithm. Early beta, not yet tested by people: expect rough edges.
- **Fun with Quantum: The CHSH Game**: Play the CHSH Game. Early beta, not yet tested by people: expect rough edges.
- **Fun with Quantum: The Quantum Prisoner's Dilemma**: Play the Quantum Prisoner's Dilemma. Early beta, not yet tested by people: expect rough edges.
- **Fun with Quantum: GHZ on Real Quantum Devices**: Run the GHZ experiment on a real quantum computer. Early beta, not yet tested by people: expect rough edges. *(needs: internet, IBM Quantum account)*
- **Fun with Quantum website: games in the browser**: Play the games in the browser on the Fun with Quantum website, also offline. Early beta, not yet tested by people: expect rough edges.
- **Fun with Quantum family: related projects**: Explore the other projects of the Fun with Quantum family. Early beta, not yet tested by people: expect rough edges. *(needs: internet)*
- **Quantum Fractals**: Watch the fractals change with the state of a qubit. Early beta, not yet tested by people: expect rough edges. *(needs: screen)*
- **Quantum Paradoxes**: Work through one of the quantum paradox notebooks. Early beta, not yet tested by people: expect rough edges.

### Learn & code

- **Grokking the Bloch Sphere**: Move a qubit around the Bloch sphere and follow the gates. Early beta, not yet tested by people: expect rough edges.
- **Grokking the Bloch Sphere: online version**: Open the online version from the Pi and move a qubit around the Bloch sphere. *(needs: screen, internet)*
- **Qiskit Tutorials on this Pi**: Open a tutorial in Qiskit Tutorials on this Pi and run its code. Early beta, not yet tested by people: expect rough edges. *(needs: SD card of 32 GB or more)*

### IBM and partner demos

- **IBM Quantum Composer**: Build a circuit in the IBM Quantum Composer and simulate it. *(needs: screen, internet)*
- **IBM Quantum Courses**: Open an IBM Quantum course and run its first code cells.
- **IBM Quantum Tutorials**: Open an IBM Quantum tutorial and run its code cells. Early beta, not yet tested by people: expect rough edges. *(needs: internet, IBM Quantum account)*
- **Qiskit Live (QuBins)**: Start Qiskit Live and run a notebook. Early beta, not yet tested by people: expect rough edges. *(needs: internet, SD card of 32 GB or more)*
- **SAP Quantum Learning**: Take the quiz and build a circuit in SAP Quantum Learning. Early beta, not yet tested by people: expect rough edges. *(needs: internet, screen)*
- **SAP Quantum LED**: Show the SAP logo on the LED panel, coloured by three qubits. Early beta, not yet tested by people: expect rough edges. *(needs: internet, LED panel)*

<div data-fwq-assistant="tester" data-public="1"></div>
