---
leadspace:
  variant: light
  title: RasQberry Two
  copy: "Exploring Quantum Computing and Qiskit with a Raspberry Pi and a 3D Printer - or:  <span class=\"text-gradient\">Building a Functional Model of a Quantum Computer at Home</span>"
  size: tall
  cta:
    primary:
      label: View On GitHub
      url: https://github.com/JanLahmann/RasQberry-Two
      icon: logo-github
      target: _blank
  bg:
    image:
      src: /Artwork/RQB2-Website.png
      alt: lead space background image
---

RasQberry is a functional model of IBM Quantum System Two. It integrates Qiskit, a Raspberry Pi and a 3D printed model of IBM Q System Two to explore various state-of-the-art technologies and create a tool that can be used for education and in meetings, meetups, demo booths, etc. A spectrum of Quantum Computing demos and Serious Games for Quantum Computing (that illustrate e.g. superposition, interference and entanglement) will be made available on the RasQberry platform for an engaging introduction to Quantum Computing.

**Note:** If you are looking for the functional model of IBM Quantum System ONE, please go to [https://rasqberry.one](https://rasqberry.one). Here is the new project, building a functional model of IBM Quantum System TWO, including several additional updates, e.g. 64-bit OS, Raspberry Pi 5, Qiskit 1.x, more Quantum Computing Demos, integration into raspi-config, etc.

## See It In Action

<div className="media-grid">
  <div className="media-item">
    <img src="/Artwork/RasQberry2model.png" alt="RasQberry Two 3D Model" className="media-image" />
    <p className="media-caption">3D-printed model inspired by IBM Quantum System Two</p>
  </div>
  <div className="media-item">
    <video controls className="media-video" poster="/Artwork/RasQberry2model.png">
      <source src="/videos/RasQberry-beta-2026-06-04.mp4" type="video/mp4" />
      Your browser does not support the video tag.
    </video>
    <p className="media-caption">Demo video showing RasQberry Two beta with quantum computing demos</p>
  </div>
  <div className="media-item">
    <a href="/demo-screenshots/rasqberry-demo-4000ms.gif" target="_blank" title="Click for slow-motion version (4s per frame)">
      <img src="/demo-screenshots/rasqberry-demo-1000ms.gif" alt="RasQberry Demo Screenshots" className="media-image" />
    </a>
    <p className="media-caption">Interactive quantum computing demos - Bloch sphere visualization, quantum games, circuit composer, and fractal animations (<a href="/demo-screenshots/rasqberry-demo-4000ms.gif" target="_blank">slow-motion version</a>)</p>
  </div>
</div>

## Stay Updated

Follow our [Announcements on GitHub Discussions](https://github.com/JanLahmann/RasQberry-Two/discussions/categories/announcements) for the latest news and updates.

Subscribe to our [newsletter](/newsletter) for occasional updates on new releases, quantum computing demos, and community news. We send not more than one email per month.

## Getting Started

### Option 1: Download Page

Visit **[rasqberry.org/latest/](/latest/)** to browse and download all available RasQberry images including stable, beta, and development builds.

After downloading, write the image to an SD card using [Raspberry Pi Imager](https://www.raspberrypi.com/software/) (no customizations needed), then boot your Pi.

### Option 2: Run Pi Imager with RasQberry Repository

Run Pi Imager with our custom repository to see all RasQberry images directly in the imager:

**macOS:**
```bash
/Applications/Raspberry\ Pi\ Imager.app/Contents/MacOS/rpi-imager --repo https://RasQberry.org/RQB-images.json
```

**Windows:**
```bash
"C:\Program Files (x86)\Raspberry Pi Imager\rpi-imager.exe" --repo https://RasQberry.org/RQB-images.json
```

### Option 3: Pi Imager Desktop Launcher (Recommended)

Install a pre-configured Pi Imager launcher that automatically loads RasQberry images:

**macOS** (one-line command):
```bash
curl -sSL https://rasqberry.org/install-rpi-imager-launcher.sh | bash
```

**Windows** (PowerShell as Administrator):
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://rasqberry.org/install-rpi-imager-launcher.ps1'))
```

This creates a "Pi Imager for RasQberry" launcher on your Desktop.

### First Boot Setup

Once your RasQberry Two is running:

1. **Connect** via SSH or VNC (both work out of the box)
   - Username: `rasqberry`
   - Password: `Qiskit1!`

2. **Explore Demos** through the menu system:
   - Run `sudo raspi-config` and select the first menu item
   - Or use desktop icons to launch demos directly
   - Note: Most demos require LED strips connected to GPIO pin 21

3. **Report Issues** at [GitHub Issues](https://github.com/JanLahmann/RasQberry-Two/issues)

> **Note**: Additional features, demos, and improvements are continuously being added. Check [/latest/](/latest/) for the newest releases.


## Working with Qiskit

Qiskit comes pre-installed in the default virtual environment (RQB2).

**Activate the environment:**
```bash
source /home/rasqberry/RasQberry-Two/venv/RQB2/bin/activate
```

**Check installed packages:**
```bash
(RQB2) rasqberry@raspberrypi:~ $ pip list | grep qiskit
qiskit                 2.0.1
qiskit-aer             0.15.1
qiskit-ibm-runtime     0.30.0
qiskit-qasm3-import    0.5.1
```

> **Note**: Package versions shown are examples. Use `pip list | grep qiskit` to see your current installation.

## Building the RasQberry 3D Model

STL files for the 3D-printed model are available in the [3D-model branch](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model). The model consists of several printed parts that assemble together to create the complete RasQberry Two enclosure.

<div className="centered-media">
  <img src="/Artwork/RasQberry2exploded.png" alt="RasQberry Two Exploded View" className="media-image" />
  <p className="media-caption">Exploded view showing all 3D-printed components</p>
</div>

For detailed assembly instructions, see the [Hardware Assembly Guide](01-3d-model/hardware-assembly-guide).

## Contributing

RasQberry is an open-source educational project. We welcome contributions:

1. **Test & report issues** - Try RasQberry and [report bugs](https://github.com/JanLahmann/RasQberry-Two/issues)
2. **Share ideas & feature requests** - Open a [GitHub Discussion](https://github.com/JanLahmann/RasQberry-Two/discussions) or [issue](https://github.com/JanLahmann/RasQberry-Two/issues)
3. **Improve documentation** - Fix typos or add troubleshooting tips using the "Edit this page on GitHub" link on each page
4. **Create quantum demos** - Build new interactive demonstrations

**Get Started:** Visit our [Contributing Guide](05-contributing/) to learn more.
