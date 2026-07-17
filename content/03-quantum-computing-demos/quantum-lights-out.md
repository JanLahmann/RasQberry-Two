# Quantum Lights Out

A quantum computing implementation of the classic [Lights Out puzzle game](https://en.wikipedia.org/wiki/Lights_Out_(game)), solved using quantum algorithms and visualized on the RasQberry Two LED panel.

## Overview

Quantum Lights Out transforms the classic puzzle game into an educational quantum computing demonstration. Watch as a quantum algorithm solves the puzzle step-by-step, with each move displayed on your RasQberry's LED panel.

![Quantum Lights Out Animation](https://github.com/user-attachments/assets/23778cc3-99d3-4872-9463-fcd3b8f09b4f)

## How It Works

The game starts with a random configuration of lit and unlit LEDs. The goal is to turn all lights off by pressing buttons, where each button toggles its own state and the states of its adjacent neighbors. The quantum algorithm finds the optimal solution sequence.

### The Quantum Approach

- **Problem Encoding**: The puzzle state is encoded into a quantum circuit
- **Linear Algebra**: Uses Gaussian elimination over GF(2) (binary field)
- **Solution Finding**: Quantum algorithm determines which buttons to press
- **Visualization**: Each step of the solution is displayed on the LED panel

## Running the Demo

### From RasQberry Configuration Menu

1. Open a terminal on your RasQberry
2. Run: `sudo raspi-config`
3. Navigate to: **0 RasQberry** → **Quantum Computing Demos** → **Quantum Lights Out**
4. The demo will start automatically

### Desktop Icon

- Look for the **"Quantum Lights Out"** icon on your RasQberry desktop
- Double-click to launch the demo
- The LED panel will display the puzzle and solution sequence

### Desktop Menu

1. Click on the desktop menu
2. Navigate to: **Applications** → **RasQberry** → **Quantum Lights Out**
3. The demo will start automatically

### Command Line (Advanced)

```bash
rq_demo_run.sh quantum-lights-out
```

## What You'll See

1. **Initial State**: Random configuration of lit LEDs
2. **Solution Calculation**: Brief pause while quantum algorithm solves
3. **Step Display**: Each move shown sequentially on LED panel
4. **Final State**: All lights off (puzzle solved!)

## Hardware Requirements

- Raspberry Pi (Pi 5 recommended, Pi 4 supported)
- **RasQberry Two LED Panel** (required for visualization)
- LED strip connected to GPIO pin 18 (default configuration)
- Minimum 25 LEDs for 5x5 grid (60 LEDs recommended for full RasQberry setup)

## The Classic Lights Out Game

In the original game:
- Grid of lights (typically 5x5)
- Pressing any light toggles it and its orthogonal neighbors
- Goal: Turn all lights off
- Strategy involves linear algebra over binary field

### Quantum Connection

This demo demonstrates:
- **Problem Mapping**: Real-world puzzles to quantum circuits
- **Linear Systems**: Quantum approaches to system solving
- **Visualization**: Making quantum algorithms tangible
- **Physical Feedback**: LED panel makes quantum computing visible

## Tips

- **Watch Carefully**: Each LED update represents a button press in the solution
- **Count Moves**: Note the efficiency of the quantum solution
- **Try Different Sizes**: Modify the grid size in the code
- **Repeat**: Each run generates a new random puzzle
- **Explain to Others**: Great demo for workshops and presentations

## Credits

Developed by **Luka Dojcinovic**

- **Repository**: [Luka-D/Quantum-Lights-Out](https://github.com/Luka-D/Quantum-Lights-Out)
- **Purpose**: Educational demonstration of quantum problem-solving with visual feedback

## Learn More

### Lights Out Game
- [Lights Out Wikipedia](https://en.wikipedia.org/wiki/Lights_Out_(game))
- [Mathematical Analysis](https://en.wikipedia.org/wiki/Lights_Out_(game)#Mathematical_analysis)

### Quantum Computing Concepts
- [IBM Quantum Learning](https://learning.quantum.ibm.com/)
- [Qiskit Documentation](https://docs.qiskit.org/)
- [Qiskit YouTube Channel](https://www.youtube.com/@qiskit)
- [IBM Quantum Documentation](https://docs.quantum.ibm.com/)

## Technical Details

### Algorithm
- Uses Gaussian elimination over GF(2) (binary finite field)
- Converts puzzle to system of linear equations
- Solves using classical linear algebra (efficiently solvable)
- Each solution step displayed with LED animation

### Grid Size
Default is typically 5x5, but can be customized in the code for different LED panel sizes.

## Related Demos

- [Raspberry Tie](raspberry-tie) - Quantum circuits with LED visualization
- [Bloch Sphere](bloch-sphere) - Single-qubit gate visualization
- [Qoffee Maker](qoffee-maker) - Quantum coffee selection
- [Demo List](01-demo-list) - All available demos

---

*IBM Quantum and Qiskit are trademarks of IBM Corporation. This demo uses open-source Qiskit software.*
