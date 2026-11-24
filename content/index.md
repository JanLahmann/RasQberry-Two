---
title: "RasQberry Two: a quantum computer model to build at home"
description: "Build a functional model of a quantum computer at home: a 3D-printed IBM Quantum System Two with a Raspberry Pi, LEDs, Qiskit and quantum demos."
leadspace:
  variant: light
  title: RasQberry Two
  copy: "Quantum computing you can touch: <span class=\"text-gradient\">build a working model of a quantum computer at home</span> with a Raspberry Pi, a 3D printer, LEDs and Qiskit."
  size: tall
  cta:
    primary:
      label: Write RasQberry Two to your SD card
      url: "rpi-imager://open?repo=https://RasQberry.org/RQB-images.json"
      style: gradient
      umami:
        event: "RasQberry Two: imager open"
        where: home-hero
        stream: beta
    secondary:
      label: Get started
      url: /#2-getting-started
    tertiary:
      label: View on GitHub
      url: https://github.com/JanLahmann/RasQberry-Two
      icon: logo-github
      target: _blank
  ket: "Questions about your first steps? Ask our AI helper"
  pi:
    copy: "<span class=\"text-gradient\">Welcome! RasQberry Two runs on this Pi.</span> Start with the learning path <strong>First 15 minutes</strong>: double-click <strong>Learning paths</strong> on the desktop."
    cta:
      primary:
        label: First 15 minutes
        url: /03-quantum-computing-demos/02-learning-paths/#2-first-15-minutes
        style: gradient
        umami:
          event: "RasQberry Two: pi welcome click"
          target: first-15-minutes
      secondary:
        label: Setup checklist
        url: /02-software/01-installation-overview/#3-setup-checklist
        umami:
          event: "RasQberry Two: pi welcome click"
          target: setup-checklist
      tertiary:
        label: All demos
        url: /03-quantum-computing-demos/01-demo-list/
        umami:
          event: "RasQberry Two: pi welcome click"
          target: demo-list
    ket: "Questions about this RasQberry? Ask our AI helper"
  bg:
    image:
      src: /Artwork/RQB2-Website.webp
      alt: lead space background image
---

{/* BETA BOX: announces beta-2026-11-15-225917. For a newer beta, update the release tag in the "What's new" link; when a stable release ships, reword or remove the box. */}
<div className="callout callout--news">
  <p><strong>New beta:</strong> Wi-Fi hotspot for booths and classrooms, Bluetooth speakers, learning paths, safer first access and Qiskit 2.6. <a href="https://github.com/JanLahmann/RasQberry-Two/releases/tag/beta-2026-11-15-225917" target="_blank" rel="noopener noreferrer" data-umami-event="RasQberry Two: beta box click" data-umami-event-target="release-notes">What's new</a> · <a href="/testing/" data-umami-event="RasQberry Two: beta box click" data-umami-event-target="testing">Become a tester</a> · <a href="https://github.com/JanLahmann/RasQberry-Two/issues/new?template=demo-feedback.yml&demo=New%20beta" target="_blank" rel="noopener noreferrer" data-umami-event="RasQberry Two: beta box click" data-umami-event-target="feedback">Tell us what you think</a></p>
</div>

RasQberry Two is a working model of IBM Quantum System Two that you build
yourself. A Raspberry Pi runs real quantum programs with Qiskit; demos and games
show superposition, interference and entanglement on screen and on the model's
LED panel. Made for classrooms, meetups, booths and anyone curious.

## What you can do

<div className="feature-grid">
  <a className="feature" href="/03-quantum-computing-demos/01-demo-list/">
    <img src="/demo-screenshots/bloch-sphere.webp" width="800" height="463" loading="lazy" alt="Grokking the Bloch Sphere: a qubit as an arrow on a sphere, gate buttons and tips on what to try" />
    <strong>Demos and games</strong>
    <span>Bloch sphere, quantum coin game, Quantum Lights Out, Qoffee-Maker and more, each one click away.</span>
  </a>
  <a className="feature" href="/03-quantum-computing-demos/led-display/">
    <img src="/events/qdc2025-led-panels-800.webp" width="800" height="533" loading="lazy" alt="Two RasQberry models in front of a lit LED panel at an event" />
    <strong>Qubits in light</strong>
    <span>Measurements light up a 24×8 LED panel. No panel yet? The same view opens on screen.</span>
  </a>
  <a className="feature" href="/03-quantum-computing-demos/02-learning-paths/">
    <img src="/demo-screenshots/learning-paths.webp" width="800" height="518" loading="lazy" alt="The Learning paths menu on the Pi" />
    <strong>Learning paths</strong>
    <span>Guided tours from 15 minutes at a stand to a 26-hour course; each step starts its demo for you.</span>
  </a>
  <a className="feature" href="/03-quantum-computing-demos/00-overview/#2-your-own-qiskit-programs">
    <img src="/demo-screenshots/my-quantum-programs.webp" width="800" height="450" loading="lazy" alt="JupyterLab on the Pi with the Hello World notebook open" />
    <strong>Code with Qiskit</strong>
    <span>JupyterLab opens at Hello World. Run on the built-in simulator, or on a real IBM quantum computer with a free account.</span>
  </a>
  <a className="feature" href="/01-3d-model/02-hardware-assembly-guide/">
    <img src="/Artwork/RasQberry2exploded.webp" width="1200" height="822" loading="lazy" alt="Exploded view of the 3D-printed RasQberry Two parts" />
    <strong>Print and build the model</strong>
    <span>STL files, a bill of materials and a step-by-step guide. Turn the model in 3D below.</span>
  </a>
  <a className="feature" href="/03-quantum-computing-demos/00-overview/#2-at-a-booth-or-in-class">
    <img src="/events/qdc2025-booth-800.webp" width="800" height="533" loading="lazy" alt="A RasQberry booth: screen with the RasQberry desktop and several models" />
    <strong>Ready for class and booths</strong>
    <span>Its own Wi-Fi hotspot with a QR code to join, touch mode, a demo loop and Bluetooth speakers.</span>
  </a>
  <a className="feature" href="/02-software/03-ab-boot/">
    <img src="/installation-images/slot-manager-tile.webp" width="800" height="500" loading="lazy" alt="The Slot Manager: Slot A is running, and the next update goes into Slot B, the other system" />
    <strong>Updates without a new card</strong>
    <span>On cards of 64 GB or more, new releases install over the air and the previous system stays as a fallback.</span>
  </a>
  <a className="feature" href="/workshops/">
    <img src="/events/qdc2025-model-800.webp" width="800" height="533" loading="lazy" alt="A 3D-printed RasQberry Two model at an event" />
    <strong>Workshops and events</strong>
    <span>We help you prepare yours, free: an image for your event, your branding, tested demos.</span>
  </a>
</div>

## See it in action

<div className="media-grid">
  <div className="media-item">
    <video controls className="media-video" poster="/Artwork/RasQberry-demo-desktop.webp" preload="none">
      <source src="/videos/RasQberry-beta-2026-06-04.mp4" type="video/mp4" />
      Your browser does not support the video tag.
    </video>
    <p className="media-caption">RasQberry Two and its demos</p>
  </div>
  <div className="media-item">
    <video autoPlay muted loop playsInline className="media-video" poster="/demo-screenshots/rasqberry-demo-poster.jpg" aria-label="RasQberry demo screenshots">
      <source src="/demo-screenshots/rasqberry-demo.webm" type="video/webm" />
      <source src="/demo-screenshots/rasqberry-demo.mp4" type="video/mp4" />
    </video>
    <p className="media-caption">Bloch sphere, games, circuit composer and fractals (<a href="/demo-screenshots/rasqberry-demo-slow.mp4" target="_blank">slow motion</a>)</p>
  </div>
</div>

{/* Old anchors, kept so earlier links still land here */}
<span id="3-first-boot" />
<span id="2-working-with-qiskit" />

## Getting started

1. **Write the card.** Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/) 2.0.3 or newer and click the button below. In Imager, confirm **Switch repository**, then choose your Pi, **RasQberry Two Beta** and your card (128 GB recommended, 16 GB minimum). The button did nothing? [Other ways](/02-software/01-installation-overview/#3-if-the-link-does-not-open-imager).
2. **Start the Pi.** The first start takes a few minutes and restarts on its own. No screen? Read [first access without a screen](/02-software/02-system-options/#3-first-access-without-a-screen).
3. **Follow the [setup checklist](/02-software/01-installation-overview/#3-setup-checklist)**, then double-click a demo or a learning path.

<p><a className="cta-button" href="rpi-imager://open?repo=https://RasQberry.org/RQB-images.json" data-umami-event="RasQberry Two: imager open" data-umami-event-where="home-getting-started" data-umami-event-stream="beta">▶ Write RasQberry Two to your SD card</a></p>

Details, other ways to install and the first start without a screen: [installation](/02-software/01-installation-overview/).

## Explore the model in 3D

Click a part for its name and STL file, press **Assemble** to watch it come together, or **LEDs on** to light the panel.

<ModelViewer />

## Join in

- **Test new versions** with missions for your hardware: [become a tester](/testing/).
- **Share ideas, report bugs, add a demo:** [contributing](/05-contributing/).
- **Stuck?** See [troubleshooting](/02-software/01-installation-overview/#2-troubleshooting) or [open an issue](https://github.com/JanLahmann/RasQberry-Two/issues).
- **News:** [announcements](https://github.com/JanLahmann/RasQberry-Two/discussions/categories/announcements).
- Looking for the model of IBM Quantum System One? See [rasqberry.one](https://rasqberry.one).
