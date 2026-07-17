# Quantum Computing Demos Overview

Welcome to the RasQberry Quantum Computing Demos! This collection of interactive demonstrations brings quantum computing concepts to life through visualizations, games, and artistic creations.

## What Are These Demos?

These demos are designed to make quantum computing accessible and engaging. Each demo illustrates different quantum concepts through hands-on experiences, from visualizing quantum states to solving puzzles with quantum algorithms.

## Demo Categories

### 🎨 Visualization & Art

**[Bloch Sphere](bloch-sphere)** - Interactive single-qubit state visualization
Perfect for beginners. See how quantum gates transform qubit states in real-time on the Bloch sphere.

**[Fractals](fractals)** - Quantum-generated fractal art
Create beautiful animated Julia set fractals using quantum-derived parameters. Art meets quantum mechanics!

**[Raspberry Tie](raspberry-tie)** - LED display of quantum circuit results
Run quantum circuits on IBM Quantum and visualize results on the LED array. Your quantum computer with lights!

### 🎮 Games & Puzzles

**[Quantum Lights Out](quantum-lights-out)** - Quantum puzzle solver
Watch a quantum algorithm solve the classic Lights Out puzzle step-by-step on your LED panel.

**[Qoffee Maker](qoffee-maker)** - Quantum beverage selection
Design quantum circuits to select your favorite beverage. Fun introduction to quantum measurement!

**[Fun with Quantum](http://fun-with-quantum.org)** - Serious games collection
Jupyter notebooks featuring quantum games: coin games (superposition), GHZ game (entanglement), and more.

### 🔬 Advanced Concepts

**GHZ with Multiple Qubits** - Multi-qubit entanglement
Explore GHZ states with up to 192 qubits, visualized on the LED display.

**Quantum Paradoxes** - Famous thought experiments
Implementations of Schrödinger's Cat, Quantum Zeno Effect, teleportation, and more.

## Getting Started

### Running Demos

Most demos can be started in multiple ways:

1. **RasQberry Menu** (Recommended)
   ```bash
   sudo raspi-config
   ```
   Navigate to: **0 RasQberry** → **Quantum Computing Demos**

2. **Desktop Icons**
   Double-click the demo icon on your desktop

3. **Desktop Menu**
   **Applications** → **RasQberry** → [Demo Name]

4. **Command Line**
   Every demo starts the same way — `rq_demo_run.sh <demo-id>`, e.g.
   `rq_demo_run.sh quantum-fractals`. The ids are listed on the
   [Demo List](01-demo-list); the demo is installed on first use if it is not
   there yet.

### What you need

Every demo needs a RasQberry image on a Pi 5 (recommended) or Pi 4, and a display
— a monitor, or VNC.

Beyond that it varies: some need the LED panel, some a network connection, a few
an IBM Quantum token. The [Demo List](01-demo-list) states it per demo, taken from
the same manifests the image installs from, so it stays right as demos come and
go.

## Educational Value

Each demo teaches different quantum concepts:

| Demo | Quantum Concepts | Best For |
|------|-----------------|----------|
| **Bloch Sphere** | Single-qubit states, quantum gates | Beginners |
| **Qoffee Maker** | Quantum measurement, superposition | Beginners |
| **Raspberry Tie** | Quantum circuits, IBM Quantum platform | Intermediate |
| **Quantum Lights Out** | Quantum algorithms, problem solving | Intermediate |
| **Fractals** | Quantum visualization, complex numbers | Intermediate |
| **GHZ Demo** | Multi-qubit entanglement, GHZ states | Advanced |
| **Fun with Quantum** | Various concepts through games | All levels |

## Quick Demo Recommendations

**New to Quantum Computing?**
1. Start with [Bloch Sphere](bloch-sphere) - understand single qubits
2. Try [Qoffee Maker](qoffee-maker) - learn about measurement
3. Explore [Fun with Quantum games](http://fun-with-quantum.org)

**Have LEDs Connected?**
1. [Raspberry Tie](raspberry-tie) - see your quantum circuits in lights
2. [Quantum Lights Out](quantum-lights-out) - quantum puzzle solving

**Want to Create Art?**
1. [Fractals](fractals) - generate stunning quantum fractals

**Ready for Advanced Topics?**
1. GHZ Demo - explore multi-qubit entanglement
2. Quantum Paradoxes - famous thought experiments

## All Demos

For a complete list with descriptions and screenshots, see the [Demo List](01-demo-list).

## Resources

### Learning Quantum Computing
- [IBM Quantum Learning](https://learning.quantum.ibm.com/)
- [Qiskit Documentation](https://docs.qiskit.org/)
- [Qiskit YouTube Channel](https://www.youtube.com/@qiskit)
- [IBM Quantum Composer](https://quantum.ibm.com/composer)

### RasQberry Documentation
- [Software Installation](../02-software/01-installation-overview)
- [Hardware Assembly](../01-3d-model/02-hardware-assembly-guide)
- [3D Model Files](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model)

## Contributing

Found a bug or want to suggest improvements?
- [Report Issues on GitHub](https://github.com/JanLahmann/RasQberry-Two/issues)
- Use the "Edit this page" link at the bottom to suggest documentation improvements

## Community

- **RasQberry Project**: Building quantum computing education tools
- **Open Source**: All code and 3D models are freely available
- **Global Community**: Contributors and users worldwide

Ready to explore quantum computing? Choose a demo above and start your quantum journey!
