# Qoffee Maker

Use quantum computing to select your perfect beverage! The Qoffee Maker uses quantum measurements to determine which coffee or tea you'll get.

## Overview

Qoffee Maker ([qoffee-maker.org](https://qoffee-maker.org)) is a fun quantum computing demo that combines quantum circuits with beverage selection. Create the right quantum circuit, and the measurement result will determine your drink choice.

![Qoffee Maker](https://qoffee-maker.org/Bilder/Event%20Image.jpeg)

## Demo Interface

The Qoffee Maker provides an interactive interface where you can:
- Drag & drop quantum gates onto qubits to build your circuit
- Choose between different simulators (Theoretical, Simulator error-free, or Real quantum device simulation)
- See measurement probabilities for each beverage (000-111)
- View the resulting beverage selection with probability visualization
- Determine your beverage and order your drink!

![Qoffee Maker Demo Interface](/demo-screenshots/qoffee-maker-interface.png)
*The Qoffee Maker interface showing circuit builder, measurement probabilities, and beverage selection*

## How It Works

Each beverage is assigned a binary number. By carefully constructing a quantum circuit, you can influence (but not completely control!) which beverage the quantum measurement will select.

### The Quantum Challenge

- **Circuit Design**: Build a quantum circuit with specific gates in Jupyter notebook
- **Measurement**: The circuit's measurement result is a binary number
- **Beverage Selection**: The binary number maps to a specific beverage
- **Quantum Randomness**: True quantum randomness from simulators

## Running the Demo

### Preferred Method: Desktop Icon

1. Look for the **"Qoffee Maker"** icon on your RasQberry desktop
2. Double-click to launch Jupyter Lab
3. The Jupyter interface will open in your browser

### Starting the Notebook

1. In the Jupyter file browser, locate and click on **`qoffee.ipynb`**
2. The notebook will open in a new tab
3. Look for the **rocket icon** (🚀) in the top icon/menu row
4. Click the rocket icon to execute all cells and start the demo

### Alternative: Desktop Menu

1. Click on the desktop menu
2. Navigate to: **Applications** → **RasQberry** → **Qoffee Maker**
3. Follow the same steps to open `qoffee.ipynb` and click the rocket icon

### Command Line (Advanced)

```bash
rq_demo_run.sh qoffee-maker
```

Docker is installed on first run if it is missing; the demo asks before it
builds anything.

## Beverage Menu

The Qoffee Maker offers these beverages (from [qoffee-maker.org](https://qoffee-maker.org/Bilder/übersicht.png)):

![Beverage Overview](https://qoffee-maker.org/Bilder/übersicht.png)

## Getting Your Favorite Beverage

To get your favorite drink, you need to create a quantum circuit whose measurement result is the corresponding binary number.

### Example: Getting Cappuccino (011 = 3)

```python
# Create a circuit that measures to |011⟩
# This requires specific gate combinations
# The challenge: quantum superposition makes this non-trivial!
```

### Strategies

- **Superposition**: Use H gates to create equal probabilities
- **Controlled Gates**: Use CNOT to create correlations
- **Phase Manipulation**: Use Z, S, T gates for phase control
- **Multiple Attempts**: Quantum randomness means you might need several tries!

## Hardware Requirements

- Raspberry Pi (Pi 5 recommended, Pi 4 supported)
- Display (monitor or VNC connection)
- Web browser (Chromium included)
- **Internet connection required** (for Jupyter rocket icon functionality)

## Backend Options

The demo can run on different quantum simulators:

### 1. Statevector Simulator
- **Type**: Exact theoretical simulation
- **Behavior**: Deterministic, no noise
- **Use Case**: Understanding ideal quantum behavior
- **Speed**: Very fast
- **Results**: Perfect theoretical outcomes

### 2. Local Quantum Simulator (Aer)
- **Type**: Shot-based simulation
- **Behavior**: Sampling from quantum state
- **Use Case**: Realistic measurement statistics
- **Speed**: Fast
- **Results**: Statistical sampling, no noise

### 3. Noisy Simulator / Mock Device
- **Type**: Realistic quantum hardware simulation
- **Behavior**: Includes noise, decoherence, and gate errors
- **Use Case**: Understanding real quantum computing challenges
- **Speed**: Fast (faster than real hardware)
- **Results**: Realistic with errors, closest to actual quantum computers

### Why Use Different Backends?

- **Statevector**: Learn ideal quantum behavior
- **Aer**: Understand measurement statistics
- **Mock Device**: Prepare for real quantum hardware, understand noise effects

## Tips

- **Start Simple**: Try to get espresso (000) or hot water (111) first
- **Compare Backends**: Run same circuit on different backends
- **Try Mock Device**: See how noise affects your results
- **Understand Probabilities**: Your circuit creates probabilities, not certainties
- **Experiment**: Try different gate combinations
- **Share**: Great icebreaker at quantum computing events!

## Credits

Developed by **Max Simon** and **Jan-R. Lahmann**

- **Website**: [qoffee-maker.org](https://qoffee-maker.org)
- **Purpose**: Fun introduction to quantum measurement and circuit design
- **Context**: "Serious games for quantum computing"

## Learn More

### Quantum Concepts
- [IBM Quantum Learning: Measurement](https://learning.quantum.ibm.com/course/basics-of-quantum-information/single-systems#measurement)
- [Qiskit Documentation](https://docs.qiskit.org/)
- [IBM Quantum Composer](https://quantum.ibm.com/composer)
- [Qiskit YouTube Channel](https://www.youtube.com/@qiskit)

### Related Resources
- [Fun with Quantum](http://fun-with-quantum.org) - More quantum games by Jan-R. Lahmann
- [IBM Quantum Documentation](https://docs.quantum.ibm.com/)

## Related Demos

- [Bloch Sphere](bloch-sphere) - Understand single-qubit gates
- [Raspberry Tie](raspberry-tie) - Circuit results on LED display
- [Fun with Quantum notebooks](http://fun-with-quantum.org) - More quantum games
- [Demo List](01-demo-list) - All available demos

---

*IBM Quantum and Qiskit are trademarks of IBM Corporation. This demo uses open-source Qiskit software.*
