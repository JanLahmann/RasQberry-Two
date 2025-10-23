# Quantum Fractals

Create stunning animated fractal art using quantum computing! This demo combines quantum circuits with Julia set fractals to visualize quantum states in beautiful, artistic ways.

## Overview

Quantum Fractals uses quantum computing to generate parameters for Julia set fractals, creating mesmerizing animations that visualize how quantum states evolve. Each frame of the animation corresponds to a different quantum circuit measurement, resulting in unique fractal patterns that showcase the connection between quantum mechanics and mathematical beauty.

![Quantum Fractals Demo](/demo-screenshots/quantum-fractals.png)
*Quantum-generated fractal animation showing Julia set evolution*

## How It Works

The demo combines several concepts:

1. **Quantum Circuits**: Creates quantum circuits with varying parameters
2. **State Vector Extraction**: Measures the quantum state to get complex number amplitudes
3. **Julia Set Generation**: Uses these quantum-derived complex numbers as parameters for Julia set fractals
4. **Animation**: Generates multiple frames to create animated fractal art
5. **Bloch Sphere Correlation**: Relates the fractal evolution to rotations on the Bloch sphere

### The Quantum-Fractal Connection

- Each quantum measurement provides complex numbers (quantum amplitudes)
- These complex numbers serve as parameters (c values) for Julia set calculations
- Different quantum states → different fractal patterns
- Animation frames correspond to quantum circuit evolution

## Features

- **Animated Fractals**: Creates GIF animations showing fractal evolution
- **Quantum State Visualization**: Relates fractals to Bloch sphere rotations
- **Multiple Complex Numbers**: Can use both 1-qubit and 2-qubit quantum states
- **Real Quantum Hardware**: Can run on both simulators and real quantum computers
- **Artistic Output**: Generates beautiful, mathematically-grounded art

## What You'll Learn

- **Quantum Visualization**: Novel ways to visualize quantum states
- **Julia Sets**: Understanding fractal mathematics
- **Quantum-Classical Hybrid**: How quantum computing can enhance classical algorithms
- **Complex Numbers**: The role of complex amplitudes in quantum mechanics
- **State Evolution**: How quantum states change over time

## Running the Demo

### From RasQberry Configuration Menu

1. Open a terminal on your RasQberry
2. Run: `sudo raspi-config`
3. Navigate to: **0 RasQberry** → **Quantum Computing Demos** → **Quantum Fractals**
4. The demo will generate animated fractals

### Desktop Icon

- Look for the **"Quantum Fractals"** icon on your RasQberry desktop
- Double-click to launch the demo
- Fractal generation will begin automatically

### Desktop Menu

1. Click on the desktop menu
2. Navigate to: **Applications** → **RasQberry** → **Quantum Fractals**
3. The demo will start generating fractals

### Command Line (Advanced)

```bash
cd ~/RasQberry-Two
source venv/RQB2/bin/activate
./RQB2-bin/fractals.sh
```

## What You'll See

The demo generates:

1. **Fractal Images**: Individual frames showing Julia set fractals with quantum-derived parameters
2. **Animated GIF**: Animation showing how fractals evolve as quantum parameters change
3. **Bloch Sphere Views**: Visualization of the corresponding quantum states
4. **Progress Output**: Terminal feedback showing generation progress

The fractals are saved to an `img/` directory in the demo folder.

## Hardware Requirements

- Raspberry Pi (Pi 5 recommended, Pi 4 supported)
- Display (monitor or VNC connection)
- **Sufficient RAM** (2GB minimum, 4GB+ recommended for larger fractals)
- Web browser (Chromium included in RasQberry)
- **No LEDs required** for this demo

## Configuration Options

### Adjustable Parameters (in fractals.py)

- **frame_resolution**: Image size (default: 200x200 pixels)
- **number_of_frames**: Animation length (default: 60 frames)
- **GIF_ms_intervals**: Animation speed (default: 200ms per frame = 5 fps)
- **zoom**: Fractal zoom level
- **julia_iterations**: Fractal calculation detail

### Quantum Circuit Options

- **1-qubit circuits**: Simpler, faster generation
- **2-qubit circuits**: More complex fractal patterns
- **Simulator**: Fast, ideal quantum behavior
- **Real hardware**: Can connect to IBM Quantum for authentic quantum results

## Technical Details

### Julia Sets

Julia sets are fractals defined by iterating:
```
z(n+1) = z(n)² + c
```

Where `c` is a complex number constant. Different values of `c` create different fractal shapes.

### Quantum Input

The quantum circuit provides the `c` parameter(s):
- **1-qubit**: Uses one complex amplitude as `c`
- **2-qubit**: Can use multiple amplitudes for multi-parameter fractals

## Performance Tips

- **Start Small**: Use lower resolution (100x100) for faster testing
- **Fewer Frames**: Reduce to 30 frames for quicker animations
- **Close Browsers**: Free up RAM by closing unnecessary applications
- **Use Simulators**: Faster than waiting for real quantum hardware
- **Watch RAM Usage**: Monitor with `htop` if generation is slow

## Educational Context

Perfect for teaching:

- **Quantum Visualization**: Alternative ways to understand quantum states
- **Fractal Mathematics**: Julia sets and complex dynamics
- **Quantum Art**: Intersection of science and creativity
- **Complex Numbers**: Practical application of complex number mathematics
- **Quantum-Classical Hybrid Algorithms**: Combining quantum and classical computing

## Variations and Experiments

Try these modifications:

- **Different Quantum Gates**: Modify the circuit to use different gates
- **Multiple Qubits**: Expand to 3+ qubits for more parameters
- **Color Schemes**: Change the fractal coloring
- **Zoom Animations**: Animate zooming into specific fractal regions
- **Real Hardware Noise**: Compare simulator vs. real quantum computer results

## Credits

Developed by **Wiktor Mazin** (Principal Data Scientist, IBM Quantum Ambassador) and team

- **Original Project**: [Visualizing Quantum Computing using Fractals](https://github.com/wmazin/Visualizing-Quantum-Computing-using-fractals)
- **Medium Article 1**: [Creating Fractal Art with Qiskit](https://medium.com/qiskit/creating-fractal-art-with-qiskit-df69427026a0)
- **Medium Article 2**: [Fractal Animations with Quantum Computing on a Raspberry Pi](https://medium.com/qiskit/fractal-animations-with-quantum-computing-on-a-raspberry-pi-8834ef43d423)
- **RasQberry Port**: Adapted for RasQberry-Two by Jan-R. Lahmann

## Learn More

### Fractals and Julia Sets
- [Julia Set on Wikipedia](https://en.wikipedia.org/wiki/Julia_set)
- [Fractal Mathematics](https://mathworld.wolfram.com/JuliaSet.html)

### Quantum Computing Visualization
- [Qiskit Visualization Documentation](https://docs.qiskit.org/stable/visualization.html)
- [IBM Quantum Learning](https://learning.quantum.ibm.com/)
- [Qiskit YouTube Channel](https://www.youtube.com/@qiskit)

### Source Code
- [GitHub: wmazin/Visualizing-Quantum-Computing-using-fractals](https://github.com/wmazin/Visualizing-Quantum-Computing-using-fractals)

## Gallery Ideas

Try creating these fractal series:

- **Quantum Gate Tour**: One animation per gate type (X, Y, Z, H, etc.)
- **Bloch Sphere Journey**: Animate a complete rotation around the Bloch sphere
- **Superposition Showcase**: Visualize equal superposition states
- **Entanglement Patterns**: Use 2-qubit entangled states
- **Noise Comparison**: Side-by-side simulator vs. real hardware

## Related Demos

- [Bloch Sphere](bloch-sphere.md) - Understand the quantum states being visualized
- [Raspberry Tie](raspberry-tie.md) - Another quantum visualization approach
- [Qoffee Maker](qoffee-maker.md) - Quantum circuit design
- [Quantum Lights Out](quantum-lights-out.md) - Quantum puzzle solving
- [Demo List](01-demo-list.md) - All available demos
