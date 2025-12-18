# Raspberry Tie

![Raspberry Tie](/qrtimages/New Logo Screen.png)

Run quantum circuits on IBM Quantum processors or simulators and visualize the results on the RasQberry LED array! The Raspberry Tie displays quantum measurement results as colored pixels on the 8×8 LED matrix, with patterns corresponding to IBM quantum processor topologies.

## Overview

Raspberry Tie brings quantum computing to life through physical LED visualization. Submit quantum circuits to IBM Quantum backends (real or simulated) and watch the measurement results light up on your RasQberry's LED array in real-time.

## Features

- **LED Visualization**: Results displayed as red (0) and blue (1) pixels on the 8×8 LED matrix
- **Multiple Display Modes**: Supports 5-qubit (bowtie/tee), 12-qubit (hex), and 16-qubit layouts
- **Backend Options**: Local Aer simulator, IBM Quantum simulators, or real quantum hardware
- **Interactive Mode**: Menu-driven setup for easy demo configuration
- **Accelerometer Support**: Auto-rotates display based on Pi orientation
- **SVG Alternative**: Browser-based display option when LEDs aren't available

## What You'll Learn

- **Quantum Measurement**: See how quantum states collapse to classical bits
- **Processor Topologies**: Understand how qubits are arranged on real quantum computers
- **Backend Comparison**: Experience differences between simulators and real hardware
- **IBM Quantum Platform**: Work with IBM's quantum computing infrastructure

## Running the Demo

### From RasQberry Configuration Menu

1. Open a terminal on your RasQberry
2. Run: `sudo raspi-config`
3. Navigate to: **0 RasQberry** → **Quantum Computing Demos** → **Raspberry Tie**
4. Follow the interactive prompts to configure the demo

### Desktop Icon

- Look for the **"Raspberry Tie"** icon on your RasQberry desktop
- Double-click to launch the demo with interactive configuration

### Desktop Menu

1. Click on the desktop menu
2. Navigate to: **Applications** → **RasQberry** → **Raspberry Tie**

### Command Line (Advanced)

```bash
cd ~/RasQberry-Two
source venv/RQB2/bin/activate
python3 RQB2-bin/quantum-raspberry-tie.py
```

**Command-line options:**
```bash
# Interactive mode (recommended)
python3 quantum-raspberry-tie.py -int

# Specify display mode
python3 quantum-raspberry-tie.py -bowtie  # 5-qubit bowtie
python3 quantum-raspberry-tie.py -tee     # 5-qubit tee
python3 quantum-raspberry-tie.py -hex     # 12-qubit hex
python3 quantum-raspberry-tie.py -16      # 16-qubit

# Use specific backend
python3 quantum-raspberry-tie.py -aer     # Local Aer simulator
python3 quantum-raspberry-tie.py -real    # Real quantum hardware
```

## Display Modes

### 5-Qubit Displays

**Bowtie**

<img src='/qrtimages/ibm_qubit_cpu.jpg' width='200' alt='IBM 5 qubit processor' />
<img src='/qrtimages/RaspberryTieOutput.png' width='200' alt='Bowtie display output' />

The classic 5-qubit "bowtie" layout matching IBM's early quantum processors. Each colored pixel represents one qubit's measurement result.

**Tee**

<img src='/qrtimages/5-qubit tee.png' width='200' alt='Tee display output' />

A 5-qubit layout based on the "tee" connectivity of later IBM processors, offering lower noise characteristics.

### 12-Qubit Display (Hex)

<img src='/qrtimages/12-qubit display.png' width='200' alt='12-qubit hex display' />

The "heavy hex" topology used in modern IBM quantum processors. This diamond-shaped layout is topologically equivalent to a hexagon with qubits at vertices and edge midpoints.

### 16-Qubit Display

<img src='/qrtimages/ibm_16_qubit_processor-100722935-large.3x2.jpg' width='200' alt='IBM 16 qubit processor' />
<img src='/qrtimages/16-bitRpi-result.JPG' width='200' alt='16-qubit display output' />

Layout corresponding to IBM's experimental 16-qubit processors, arranged in four rows.

## Understanding the Display

- **Blue pixels**: Qubit measured as |1⟩
- **Red pixels**: Qubit measured as |0⟩
- **Purple/lavender pixels**: Unmeasured qubits (when using fewer than max qubits)

The pixel patterns correspond to qubit connectivity on IBM quantum processors, helping visualize the physical hardware topology.

## Hardware Requirements

- Raspberry Pi (Pi 5 recommended, Pi 4 supported)
- **4× WS2812 LED panels** (4×12 pixels each) - Required for LED display
- Connected to GPIO pin 21
- Display (monitor or VNC) for configuration
- Internet connection (for IBM Quantum backends)

**Alternative**: If no LEDs are connected, an SVG browser display is available.

See the [Bill of Materials](../01-3d-model/bill-of-materials) and [Hardware Assembly Guide](../01-3d-model/hardware-assembly-guide) for LED panel details and assembly instructions.

## Backend Options

### Local Aer Simulator (Default)
- **Type**: Fast local simulation
- **Requirements**: No IBM account needed
- **Behavior**: Ideal quantum behavior, no noise

### IBM Quantum Simulators
- **Type**: Cloud-based simulation
- **Requirements**: IBM Quantum account
- **Behavior**: Can model noise from real devices

### Real Quantum Hardware
- **Type**: Actual quantum computer
- **Requirements**: IBM Quantum account
- **Behavior**: Real quantum effects including noise and errors
- **Note**: Jobs may queue; results take longer

## Configuration

### Interactive Mode

The `-int` flag launches an interactive menu to configure:
1. Number of qubits (5, 12, or 16)
2. Display mode (bowtie, tee, hex, or 16-qubit rows)
3. Simulator vs. real backend
4. Specific backend selection

### IBM Quantum Setup

To use IBM Quantum backends:

1. Create account at [IBM Quantum](https://quantum.ibm.com/)
2. Get your API token from account settings
3. Save credentials:
   ```bash
   python3
   >>> from qiskit_ibm_runtime import QiskitRuntimeService
   >>> QiskitRuntimeService.save_account(channel="ibm_quantum", token="YOUR_TOKEN")
   ```

The demo will prompt for credentials if needed.

## SVG Display Mode

When LEDs aren't available, the demo creates browser-viewable output:

<img src='/qrtimages/SVG%20display%20tee.png' width='200' alt='SVG tee display' />
<img src='/qrtimages/svg%20display%2012%20on%20hex12.png' width='200' alt='SVG 12-qubit display' />

The demo generates:
- `svg/qubits.html` - Auto-refreshing wrapper (every 2 seconds)
- `svg/pixels.html` - SVG rendering of current LED state

Open `svg/qubits.html` in a browser to watch the demo without physical LEDs.

## Performance Tips

- **Start with Local**: Use Aer simulator for fastest results
- **Monitor Queue Times**: Real hardware jobs may take minutes to hours
- **Check Connectivity**: Ensure stable internet for IBM Quantum backends
- **Use Interactive Mode**: Easier than command-line flags for demos

## Educational Context

Perfect for teaching:

- **Quantum Measurement**: Physical representation of state collapse
- **IBM Quantum Platform**: Hands-on experience with real quantum systems
- **Processor Architecture**: Understanding qubit connectivity and topology
- **Backend Comparison**: Simulator vs. real hardware differences

## Credits

Developed by **Kevin Roche**

- **GitHub**: [KPRoche/quantum-raspberry-tie](https://github.com/KPRoche/quantum-raspberry-tie)
- **Requirements**: Qiskit 1.x, Python 3, SenseHat libraries

## Learn More

### IBM Quantum
- [IBM Quantum Platform](https://quantum.ibm.com/)
- [Qiskit Documentation](https://docs.qiskit.org/)
- [IBM Quantum Learning](https://learning.quantum.ibm.com/)

### Hardware
- [Bill of Materials](../01-3d-model/bill-of-materials) - Component list including LED panels
- [Hardware Assembly Guide](../01-3d-model/hardware-assembly-guide) - Assembly instructions

### Source Code
- [GitHub Repository](https://github.com/KPRoche/quantum-raspberry-tie)

## Related Demos

- [Bloch Sphere](bloch-sphere) - Understand single-qubit states
- [Quantum Lights Out](quantum-lights-out) - Another LED-based demo
- [Qoffee Maker](qoffee-maker) - Quantum circuit design
- [Demo List](01-demo-list) - All available demos

---

*IBM Quantum and Qiskit are trademarks of IBM Corporation. This demo uses open-source Qiskit software.*
