# Testing RasQberry Two

Thank you for helping us test RasQberry Two! About ten testers try every demo and
every function on their own Pis, so we find what breaks and what is hard to follow.

## How it works

- **Talk to the tester helper** (bottom right on this page). Tell it your Pi model, your
  hardware (LED panel, touchscreen, Bluetooth speaker) and which demos you like, and it
  suggests missions that fit. Choose your own tester name or ID, so it can keep track of
  your missions. The tester passphrase unlocks it: <!-- TODO: shared passphrase -->.
- **Do the mission on your own.** A mission is a goal, not a recipe. Find your way with
  the [documentation](/) and the normal RasQberry helper on the Pi's start page, as any
  user would. The tester helper does not help with the mission itself; it points you
  there. Where the documentation or the helper leaves you stuck, that is a finding too.
- **Report back to the tester helper:** what worked, what didn't, confusing words, slow
  steps, ideas. It writes it down for us, and we follow up on GitHub.

## What is recorded

<!-- TODO (Jan): check the wording once the tester helper is set up. -->
The tester helper keeps your conversation, with your tester name or ID, your Pi model,
hardware and RasQberry version, for 90 days. It stores no IP address and no cookies.
Use any tester name you like; it does not need to be your real name.

## Missions

### Setup

- **First start**: Install RasQberry with Raspberry Pi Imager, with your own user name, password and Wi-Fi, and reach the desktop.
- **Setup Checklist**: Finish the Setup Checklist: every item done or skipped.
- **LED panel setup**: Set up the LED panel: find its layout, check it, and set the brightness. *(needs: LED panel)*
- **Download all demos**: Download all demos, then start a few without internet. *(needs: internet)*

### Demos: LED panel

- **LED Demos**: Try the LED demos: text, logos and colour effects on the LED panel. *(needs: LED panel)*
- **LED-Painter**: Paint a picture and show it on the LED panel. *(needs: LED panel, screen)*
- **Quantum Lights Out**: Watch Grover's search solve Lights Out, on the LED panel and in the console. *(needs: LED panel)*
- **Quantum Raspberry Tie**: Show measured qubits on the LED panel, from the simulator and from a real quantum computer. *(needs: LED panel, screen)*
- **RasQ-LED Demo**: Show superposition and entanglement on the LED panel. *(needs: LED panel)*

### Demos: Play

- **Fun with Quantum family: related projects**: Explore the other projects of the Fun with Quantum family. Early beta, not yet tested by people: expect rough edges. *(needs: internet)*
- **Fun with Quantum website: games in the browser**: Play the games in the browser on the Fun with Quantum website, also offline. Early beta, not yet tested by people: expect rough edges.
- **Fun with Quantum: 3-SAT with Grover's Algorithm**: Solve a 3-SAT problem with Grover's algorithm.
- **Fun with Quantum: GHZ Game**: Play the GHZ Game and see how quantum players win.
- **Fun with Quantum: GHZ on Real Quantum Devices**: Run the GHZ experiment on a real quantum computer. *(needs: internet, IBM Quantum account)*
- **Fun with Quantum: Hardy's Paradox**: Work through Hardy's Paradox.
- **Fun with Quantum: Mermin–Peres Magic Square**: Play the Mermin–Peres Magic Square.
- **Fun with Quantum: Quantum Coin Game**: Play the Quantum Coin Game against a quantum computer.
- **Fun with Quantum: Start here: what the games are about**: Find out what the Fun with Quantum games are about.
- **Fun with Quantum: The CHSH Game**: Play the CHSH Game.
- **Fun with Quantum: The Quantum Prisoner's Dilemma**: Play the Quantum Prisoner's Dilemma.
- **Quantum Fractals**: Watch the fractals change with the state of a qubit. *(needs: screen)*
- **Quantum Paradoxes**: Work through one of the quantum paradox notebooks.

### Demos: Big projects

- **Entangible**: Build a circuit with the printed gate tiles and let the camera read it. Early beta, not yet tested by people: expect rough edges.
- **Qoffee-Maker**: Order a coffee from a quantum computer, with or without a Home Connect machine. *(needs: screen, internet)*
- **Quantum Mixer**: Mix a colour with a quantum circuit. *(needs: screen)*
- **racetraQ**: Race a car steered by a quantum agent and train your own. Early beta, not yet tested by people: expect rough edges. *(needs: internet)*

### Demos: Learn & code

- **Grokking the Bloch Sphere**: Move a qubit around the Bloch sphere and follow the gates.
- **Grokking the Bloch Sphere (Web)**: Explore the Bloch sphere in the web version. *(needs: screen, internet)*
- **IBM Quantum Composer**: Build a circuit in the IBM Quantum Composer and simulate it. *(needs: screen, internet)*
- **IBM Quantum Courses**: Open an IBM Quantum course and run its first code cells.
- **IBM Quantum Tutorials**: Open an IBM Quantum tutorial and run its code cells.
- **Quantum Lab (QuBins)**: Start the Quantum Lab and run a notebook. *(needs: internet)*

### Demos: Contributed demos

- **SAP Quantum Learning**: Take the quiz and build a circuit in SAP Quantum Learning. *(needs: internet)*
- **SAP Quantum LED**: Show the SAP logo on the LED panel, coloured by three qubits. *(needs: internet, LED panel)*

### Using the Pi

- **Desktop folders and menu**: Find each demo through its desktop folder and through the RasQberry menu.
- **LED views without a panel**: Watch an LED demo in the on-screen view and in the browser view.
- **Demo Loop**: Run the Demo Loop with demos of your choice, and let it start at login.
- **Learning paths**: Follow one learning path from start to end. Early beta, not yet tested by people: expect rough edges.
- **My Quantum Programs**: Write and run your own quantum program in My Quantum Programs.
- **Touchscreen**: Use the Pi by touch only: touch mode and the on-screen keyboard. *(needs: touchscreen)*
- **Sound on a Bluetooth speaker**: Pair a Bluetooth speaker, play a demo with sound and calibrate the sound delay. *(needs: Bluetooth speaker, LED panel)*
- **Help and feedback**: Get help for a problem from the Pi: System Info, the helper and the website.

### Connections

- **Wi-Fi**: Join a Wi-Fi network, and see the Pi come back after the router restarts.
- **Remote access**: Reach the Pi from another computer: SSH, VNC and Raspberry Pi Connect. *(needs: internet)*
- **IBM Quantum account**: Save your IBM Quantum API key and run a demo on a real quantum computer. *(needs: internet, IBM Quantum account)*
- **Wi-Fi hotspot**: Let phones and laptops join the Pi's own Wi-Fi and open its demos. *(coming soon)*

### Updates

- **Update to a new release**: Install a newer release into the other system, start it, and go back to the old one. *(needs: internet, A/B image)*
- **Slot icon and What's new**: Use the slot icon in the taskbar and read What's new after an update. *(needs: A/B image)*
- **Updates on the single-system image**: Check for a newer image on the single-system image and follow what the Pi suggests. *(needs: internet, single-system image)*

### Demos from the catalogue

- **Add, update and remove a demo**: Add a demo from the catalogue, update it, and remove it again. *(needs: internet)*

Postponed to a later round: the Workshop & Qiskit Server and the Qiskit
Tutorials on this Pi (doQumentation).
