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

## Features

- **Interactive Jupyter Notebook**: Design circuits in an intuitive interface
- **Multiple Beverages**: Coffee, cappuccino, espresso, tea, and more
- **Multiple Backends**: Choose from statevector, local simulator, or noisy simulator
- **Realistic Simulation**: Mock device mimics real quantum hardware behavior
- **Educational**: Learn about quantum measurement and superposition
- **Fun Demonstrations**: Great for events and workshops

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
cd ~/RasQberry-Two
source venv/RQB2/bin/activate
./RQB2-bin/qoffee-setup.sh    # First time setup
./RQB2-bin/qoffee-maker.sh    # Launch Jupyter
```

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

## Educational Value

Perfect for teaching:

- **Quantum Measurement**: How measurement collapses superposition
- **Binary Encoding**: Mapping numbers to outcomes
- **Circuit Design**: Strategic use of quantum gates
- **Probability**: Quantum probabilities vs. desired outcomes
- **Superposition**: Multiple states existing simultaneously
- **Noise Effects**: How real quantum computers behave (with mock device)

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

## Troubleshooting

### Jupyter won't open
- Check that Jupyter is installed: `jupyter --version`
- Manually start: `jupyter lab` from the qoffee directory
- Try different browser
- Check for port conflicts (default: 8888)

### Rocket icon doesn't appear
- **Check internet connection** - Rocket icon requires network access
- Refresh the page after internet connection is restored
- Try reloading the notebook
- Check browser console for errors (F12)

### Unexpected measurement results
- This is normal with mock device (noise simulation)
- Try increasing shots (measurements) for better statistics
- Use statevector simulator for deterministic testing
- Compare results across different backends

### Demo won't start
- Run setup first: `./RQB2-bin/qoffee-setup.sh`
- Check dependencies: `pip list | grep qiskit`
- Ensure virtual environment is activated
- Check Jupyter installation: `pip list | grep jupyter`

## Variations

### Quantum Mixer

A related demo with cocktail/mocktail selection instead of coffee. Uses the same quantum principles with different beverage options and Docker-based deployment.

See: [Quantum Mixer](quantum-mixer.md)

## Related Demos

- [Quantum Mixer](quantum-mixer.md) - Cocktail version of the same concept
- [Bloch Sphere](bloch-sphere.md) - Understand single-qubit gates
- [Raspberry Tie](raspberry-tie.md) - Circuit results on LED display
- [Fun with Quantum notebooks](http://fun-with-quantum.org) - More quantum games
- [Demo List](demo-list.md) - All available demos
