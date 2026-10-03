---
leadspace:
  variant: light
  title: RasQberry Two
  copy: "Exploring Quantum Computing and Qiskit with a Raspberry Pi and a 3D Printer - or:  <span class=\"text-gradient\">Building a Functional Model of a Quantum Computer at Home</span>"
  size: tall
  cta:
    primary:
      label: Open in Raspberry Pi Imager
      url: "rpi-imager://open?repo=https://RasQberry.org/RQB-images.json"
    secondary:
      label: Get started
      url: /#2-getting-started
    tertiary:
      label: View on GitHub
      url: https://github.com/JanLahmann/RasQberry-Two
      icon: logo-github
      target: _blank
  bg:
    image:
      src: /Artwork/RQB2-Website.png
      alt: lead space background image
---

RasQberry Two is a functional model of IBM Quantum System Two. It combines
Qiskit, a Raspberry Pi and a 3D-printed model for teaching, meetups and demo
booths. Its demos and serious games show superposition, interference and
entanglement on screen and on the model's LED panel.

**Note:** Looking for the model of IBM Quantum System One? Go to
[rasqberry.one](https://rasqberry.one). RasQberry Two adds a 64-bit OS, the
Raspberry Pi 5, Qiskit 2.x, more demos and a menu in raspi-config.

<div className="callout">
  <p><strong>Running a workshop or event?</strong> We help you prepare it, free, as part of our open-source community work: an image made for your event, your branding and tested demos.</p>
  <a className="cta-button" href="/workshops/">Workshops &amp; events</a>
</div>

## See It In Action

<div className="media-grid">
  <div className="media-item">
    <img src="/Artwork/RasQberry2model.png" alt="RasQberry Two 3D Model" className="media-image" />
    <p className="media-caption">3D-printed model inspired by IBM Quantum System Two</p>
  </div>
  <div className="media-item">
    <video controls className="media-video" poster="/Artwork/RasQberry-demo-desktop.png" preload="none">
      <source src="/videos/RasQberry-beta-2026-06-04.mp4" type="video/mp4" />
      Your browser does not support the video tag.
    </video>
    <p className="media-caption">Demo video showing RasQberry Two beta with quantum computing demos</p>
  </div>
  <div className="media-item">
    <a href="/demo-screenshots/rasqberry-demo-4000ms.gif" target="_blank" title="Click for slow-motion version (4s per frame)">
      <img src="/demo-screenshots/rasqberry-demo-1000ms.gif" alt="RasQberry Demo Screenshots" className="media-image" loading="lazy" />
    </a>
    <p className="media-caption">Interactive quantum computing demos - Bloch sphere visualisation, quantum games, circuit composer, and fractal animations (<a href="/demo-screenshots/rasqberry-demo-4000ms.gif" target="_blank">slow-motion version</a>)</p>
  </div>
</div>

## Getting Started

Already running RasQberry Two? Go to [First boot](/#3-first-boot).

**1. Write the image.** Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/) 2.0.3 or newer, then:

<p><a className="cta-button" href="rpi-imager://open?repo=https://RasQberry.org/RQB-images.json">▶ Write RasQberry Two to your SD card</a></p>
<p className="cta-note">Opens Raspberry Pi Imager with the RasQberry images.</p>

In Imager, confirm **Switch repository**, then choose your Pi under **Device**,
**RasQberry Two Beta** under **OS** and your card under **Storage**.
**Customisation** (Wi-Fi, time zone, keyboard, SSH key) is optional; keep the
user name `rasqberry` ([details](/02-software/01-installation-overview/#3-customisation)).
Card: 128 GB high-speed (A2/U3) recommended, 16 GB minimum
([card sizes](/02-software/01-installation-overview/#2-which-image)). The link did
nothing? See [other ways](/02-software/01-installation-overview/#3-if-the-link-does-not-open-imager).

**2. Start the Pi.** The first start takes a few minutes and restarts on its
own: do not unplug it. The desktop opens without a login; over SSH and VNC the
login is `rasqberry` with password `Qiskit1!`.

**3. Answer the setup questions** (below), then start a demo.

### First boot

On the first desktop login a short setup checklist opens once. It offers only
the steps that still need a decision from you:

- **Connect to Wi-Fi.** Only when the Pi has no network connection.
- **Change the password.** Optional: keep the demo password for a booth.
- **Check the LED panel.** An IBM logo appears on the panel and you pick the
  colour in which it reads upright. That tells RasQberry how your panel is wired.
  No panel? Say so, and the LED demos use an on-screen view.
- **Download all demos.** Optional; otherwise each demo downloads on its first start.
- **Turn on touch mode.** Only when a touchscreen is attached.

On the [A/B image](/02-software/03-ab-boot/) the card is prepared for two systems
during the first start, on cards of 64 GB or more.

To see the checklist again, double-click the **RasQberry Setup** icon on the
desktop (or run `rq_firstlogin.sh --all`). Most steps are also in
`sudo raspi-config` → **0 RasQberry**.

Then try something: double-click a demo icon on the desktop, or pick one from the
[demo list](/03-quantum-computing-demos/01-demo-list/).

**Your feedback is highly appreciated.** Tell us what works and what doesn't, or
report a bug, in a [GitHub issue](https://github.com/JanLahmann/RasQberry-Two/issues).

## Working with Qiskit

Qiskit 2.x is pre-installed in the virtual environment `~/RasQberry-Two/venv/RQB2`; see
[Installation Overview](02-software/01-installation-overview)
for versions and how to activate it.

## Building the RasQberry 3D Model

STL files for the 3D-printed model are available in the [3D-model branch](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model). The model consists of several printed parts that assemble together to create the complete RasQberry Two enclosure.

<div className="centered-media">
  <img src="/Artwork/RasQberry2exploded.png" alt="RasQberry Two Exploded View" className="media-image" />
  <p className="media-caption">Exploded view showing all 3D-printed components</p>
</div>

For detailed assembly instructions, see the [Hardware Assembly Guide](01-3d-model/02-hardware-assembly-guide).

## Contributing

RasQberry Two is an open-source educational project. We welcome contributions:

1. **Test & report issues** - Try RasQberry and [report bugs](https://github.com/JanLahmann/RasQberry-Two/issues)
2. **Share ideas & feature requests** - Open a [GitHub Discussion](https://github.com/JanLahmann/RasQberry-Two/discussions) or [issue](https://github.com/JanLahmann/RasQberry-Two/issues)
3. **Improve documentation** - Fix typos or add troubleshooting tips using the "Edit this page on GitHub" link on each page
4. **Create quantum demos** - Build new interactive demonstrations

**Get Started:** Visit our [Contributing Guide](05-contributing/) to learn more.

## Stay Updated

Follow our [Announcements on GitHub Discussions](https://github.com/JanLahmann/RasQberry-Two/discussions/categories/announcements) for the latest news and updates.

Subscribe to our [newsletter](/newsletter) for occasional updates on new releases, quantum computing demos, and community news. We send not more than one email per month.

## Need Help?

Start with [Troubleshooting](/02-software/01-installation-overview/#2-troubleshooting).
You can also ask our [AI documentation assistant](https://notebooklm.google.com/notebook/d68081c6-19c4-4191-9092-77fb2674e344) based on [Google NotebookLM](https://notebooklm.google.com/) (needs a Google login), or [open an issue](https://github.com/JanLahmann/RasQberry-Two/issues). <a href="https://notebooklm.google.com/notebook/d68081c6-19c4-4191-9092-77fb2674e344" target="_blank"><img src="/Artwork/notebooklm-icon.svg" alt="NotebookLM" width="20" height="20" style={{verticalAlign: 'middle'}} /></a>
