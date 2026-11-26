# Workshops & events

You run a workshop, class, hackathon or maker event, and we help you prepare
RasQberry Two for it: free, as part of our open-source community work.

## How we can help

- **An image made for your event**, with **your branding**: logo, splash screen,
  wallpaper, LED logo and browser start page.
- **Extensions** for your topic.
- **Testing**: we check every function you plan to use.
- **Advice** on tools, setup and agenda: how many Pis, offline use, LED panels.
- **The development image:** some features, such as the Workshop & Qiskit Server
  below, are only in the [development image](/testing/#2-before-you-start-the-right-version).
  Need one? We check the development image for your event and, where we can, move
  what you need into the beta.
- **Student accounts** without admin rights for your class: [get in touch](#2-get-in-touch)
  and we build them with you. Today everyone at the Pi has admin rights. Your own
  password keeps others from logging in over the network.

You bring the Raspberry Pis; we help you get them ready.

### Hackathons and maker events

Participants build something of their own with Qiskit and the LED panel. Bring Pis
with the image already written; LED panels are optional, because the LED demos
also show on screen. Starting points: the
[LED panel from your own code](/03-quantum-computing-demos/led-display/#2-for-developers) and
[your own Qiskit programs](/03-quantum-computing-demos/00-overview/#2-your-own-qiskit-programs).
Several Pis in one room: [at a booth or in class](/03-quantum-computing-demos/00-overview/#2-at-a-booth-or-in-class).

## One of your Pis as a server for the whole group

<a href="/testing/#2-before-you-start-the-right-version"><span className="beta-tag">dev image</span></a> The **Workshop & Qiskit Server** runs on one of your Pis and serves the
participants' laptops over the local network: IBM Quantum tutorials and courses,
with the Qiskit code running on the Pi. It is based on
[doQumentation](https://doqumentation.org). We help you size it for your group.
The code runs on the Pi, also without the internet; only IBM Quantum computers
need it.
How to run a whole class offline from one Pi: the
[doQumentation offline workshop guide](https://doqumentation.org/workshop-offline).

To start it, double-click **Workshop & Qiskit Server** in the desktop folder
**Workshops & events** (or RasQberry → Quantum Demos → Workshops & events). The Pi shows the address and a QR code for the
participants; open the same entry again to stop it.

**Network:** the participants' devices must be on the same network as the Pi.
Guest Wi-Fi and networks with client isolation block the connection between
devices. Check with the venue, or bring the network along: the Pi's own
[Wi-Fi hotspot](/02-software/02-system-options/#2-wi-fi-hotspot). Start the server
once beforehand, while the Pi is online (it downloads its image), and keep a network
cable in for IBM Quantum computers. For a large group, try it out first or bring a
small travel router. Participants join
by opening the address or scanning the QR code the Pi shows.

## For a stand

Demos that draw visitors in, on a large monitor and on the model. The
**Demo Loop** (RasQberry → Quantum Demos → Workshops & events) runs them one after another
without anyone at the keyboard, and can start by itself at login; the learning path **First 15 minutes** is a good
guided tour for visitors who stay.

- **LED demos on the model**: circuits, logos and color effects on the LED panel.
- **Quantum Lights Out**: Grover's search solves the puzzle, step by step on the LEDs.
- **Grokking the Bloch Sphere**: apply gates to a qubit and watch the sphere turn.
- **Quantum Fractals**: fractals that change with the state of one qubit.
- **Quantum Coin Game**: play heads or tails against a quantum computer, and lose.

**Bring along:** the Pi with its power supply, a monitor with an HDMI cable (micro HDMI
on a Pi 5 or 4), keyboard and mouse, a network cable, a power strip, and a second card
with the image already written.

## Past events

RasQberry Two was shown at the IBM Quantum Developer Conference in November 2025,
and IBM Quantum [featured it on LinkedIn](https://www.linkedin.com/posts/qiskit-ugcPost-7406757487208730624-4Tpr/)
in December 2025.

<Qdc2025 />

## Get in touch

Please get in touch early, about four weeks before your event.

**[▶ Request support](https://github.com/JanLahmann/Fun-with-Quantum/issues/new?template=workshop-request.yml&title=%5BWorkshop%5D%20RasQberry%20Two%3A%20&project=RasQberry%20Two)** opens a public GitHub issue. You need a free GitHub account.

<EventsEmail />

Using other Fun with Quantum projects as well? See [fun-with-quantum.org/workshops](https://fun-with-quantum.org/workshops/).
