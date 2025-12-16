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

> **Legal Notice**: RasQberry is an independent educational project and is not affiliated with, endorsed by, or sponsored by IBM Corporation. IBM, IBM Quantum, Qiskit, and IBM Quantum System Two are trademarks of International Business Machines Corporation. This project creates an educational tool inspired by IBM's quantum computing systems for teaching purposes.

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
    <img src="/demo-screenshots/rasqberry-demo-1000ms.gif" alt="RasQberry Demo Screenshots" className="media-image" />
    <p className="media-caption">Interactive quantum computing demos - Bloch sphere visualization, quantum games, circuit composer, and fractal animations</p>
  </div>
</div>


## Getting Started

### Option 1: Custom Pi Imager Launcher (Recommended)

The easiest way to get RasQberry is with our pre-configured Pi Imager launcher:

**macOS** (one-line command):
```bash
curl -sSL https://rasqberry.org/install-rpi-imager-launcher.sh | bash
```

**Windows** (PowerShell as Administrator):
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://rasqberry.org/install-rpi-imager-launcher.ps1'))
```

This creates a "Pi Imager for RasQberry" launcher on your Desktop that opens Pi Imager with all RasQberry images pre-loaded. Select an image, write to SD card, and boot your Pi!

### Option 2: Download Page

Visit **[rasqberry.org/latest/](/latest/)** to browse and download all available RasQberry images including stable, beta, development, and A/B boot images.

After downloading, write the image to an SD card using [Raspberry Pi Imager](https://www.raspberrypi.com/software/) (no customizations needed), then boot your Pi.

<details>
<summary>More options: Run Pi Imager manually or automation URLs</summary>

**Run Pi Imager with our RasQberry custom repo:**

macOS:
```bash
/Applications/Raspberry\ Pi\ Imager.app/Contents/MacOS/rpi-imager --repo https://RasQberry.org/RQB-images.json
```

Windows:
```bash
"C:\Program Files (x86)\Raspberry Pi Imager\rpi-imager.exe" --repo https://RasQberry.org/RQB-images.json
```

**Automation URLs:** `/latest/stable`, `/latest/beta`, `/latest/dev` redirect to the latest images. API: [RQB-releases.json](/RQB-releases.json)
</details>

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

> **Beta Note**: Additional features, demos, and improvements are continuously being added to [beta releases](https://github.com/JanLahmann/RasQberry-Two/releases).


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

RasQberry is an open-source educational project, and we welcome contributions from the community!

**Ways to Contribute:**
- 🎮 Create new quantum computing demos
- 📚 Improve documentation
- 🐛 Report bugs or fix issues
- 💡 Share your ideas and projects

Whether you're a quantum computing enthusiast, educator, developer, or student, there's a way for you to contribute and help make quantum computing more accessible.

**Get Started:** Visit our [Contributing Guide](05-contributing/) to learn how you can be part of the RasQberry community!

## Stay Updated

<details>
<summary>Subscribe for occasional updates on new releases, quantum computing demos, and community news. We send not more than one email per month.</summary>

<div className="newsletter-section">
  <div className="sender-form-field" data-sender-form-id="aKrR6x"></div>
</div>

</details>
