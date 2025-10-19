#!/usr/bin/env python3
#
# RasQ-LED Quantum Circuit Demo
# Creates quantum circuits with different entanglement patterns and visualizes on LEDs
#
# Usage: python3 RasQ-LED.py

import subprocess
import time
import math
import os
import sys
from dotenv import dotenv_values

# Load environment variables from system-wide configuration
config = dotenv_values("/usr/config/rasqberry_environment.env")
n_qbit = int(config.get("N_QUBIT", 156))  # Default to 156 qubits if not configured
LED_COUNT = int(config.get("LED_COUNT", 192))
LED_PIN = int(config.get("LED_PIN", 21))

print(f"Configuration: {n_qbit} qubits, {LED_COUNT} LEDs on GPIO {LED_PIN}")

# Import Qiskit 2.x classes
try:
    from qiskit import QuantumCircuit
    # AerSimulator may be provided by the qiskit-aer package or in qiskit.providers.aer
    try:
        from qiskit.providers.aer import AerSimulator
    except ModuleNotFoundError:
        from qiskit_aer import AerSimulator
    print("Qiskit imported successfully")
except ImportError as e:
    print(f"Error importing Qiskit: {e}")
    print("Make sure Qiskit is installed in the current environment")
    sys.exit(1)

# Set the backend
backend = AerSimulator()

# Set number of shots
shots = 1

# Global variables
circuit = None
measurement = ""

def find_display_script():
    """Find the RasQ-LED-display script in common locations"""
    script_locations = [
        # Same directory as this script
        os.path.join(os.path.dirname(__file__), "RasQ-LED-display.py"),
        # System paths
        "/usr/bin/RasQ-LED-display.py",
        # Legacy paths
        "/home/pi/RasQberry/demos/bin/RasQ-LED-display.py"
    ]

    for script_path in script_locations:
        if os.path.exists(script_path):
            print(f"Found display script: {script_path}")
            return script_path

    print("Error: Could not find RasQ-LED-display script")
    print("Searched locations:")
    for path in script_locations:
        print(f"  {path}")
    return None

def init_circuit():
    """Initialize quantum circuit and measurement variables"""
    global circuit, measurement
    circuit = QuantumCircuit(n_qbit, n_qbit)
    measurement = ""

def set_up_circuit(factor):
    """Set up quantum circuit with specified entanglement pattern

    Args:
        factor: Size of entanglement groups
                1 = no entanglement
                n_qbit = complete entanglement
                other = block entanglement
    """
    global circuit
    circuit = QuantumCircuit(n_qbit, n_qbit)

    if factor == 0:
        factor = n_qbit

    # Relevant qubits are the first qubits in each subgroup
    relevant_qbit = 0

    for i in range(0, n_qbit):
        if (i % factor) == 0:
            # Apply Hadamard to first qubit of each group
            circuit.h(i)
            relevant_qbit = i
        else:
            # Entangle with the first qubit of the group
            circuit.cx(relevant_qbit, i)

    # Measure all qubits
    circuit.measure(range(n_qbit), range(n_qbit))

def get_factors(number):
    """Get all factors of a number for entanglement group sizes"""
    factor_list = []

    # Search for factors, including factor 1 and n_qbit itself
    for i in range(1, math.ceil(number / 2) + 1):
        if number % i == 0:
            factor_list.append(i)

    factor_list.append(n_qbit)
    return factor_list

def circ_execute():
    """Execute the quantum circuit and get measurement result"""
    global measurement
    try:
        # Execute the circuit on the AerSimulator
        job = backend.run(circuit, shots=shots)
        result = job.result()
        counts = result.get_counts()
        measurement = list(counts.items())[0][0]
        print(f"Quantum measurement: {measurement}")
        return True
    except Exception as e:
        print(f"Error executing quantum circuit: {e}")
        return False

def call_display_on_strip(measurement_result):
    """Call the LED display script to show the measurement result"""
    display_script = find_display_script()
    if not display_script:
        return False

    try:
        # Note: No sudo needed for SPI-based driver
        result = subprocess.run([
            sys.executable, display_script, measurement_result
        ], capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            print(f"Display script error: {result.stderr}")
            return False

        return True
    except subprocess.TimeoutExpired:
        print("Display script timed out")
        return False
    except Exception as e:
        print(f"Error calling display script: {e}")
        return False

def clear_leds():
    """Clear all LEDs"""
    display_script = find_display_script()
    if display_script:
        try:
            subprocess.run([
                sys.executable, display_script, "0", "-c"
            ], capture_output=True, timeout=10)
        except:
            pass

def run_circuit(entanglement_size):
    """Run a quantum circuit with specified entanglement and display result

    Args:
        entanglement_size: Size of entangled blocks
                          1 = no entanglement
                          0 or n_qbit = complete entanglement
                          other = block entanglement of that size
    """
    init_circuit()

    if entanglement_size == 1:
        print("Building circuit without entanglement")
        set_up_circuit(1)
    elif entanglement_size == 0 or entanglement_size == n_qbit:
        print("Building circuit with complete entanglement")
        set_up_circuit(n_qbit)
    else:
        print(f"Building circuit with entangled blocks of size {entanglement_size}")
        set_up_circuit(entanglement_size)

    if circ_execute():
        call_display_on_strip(measurement)
        return True
    return False

def interactive_mode():
    """Interactive mode for manual circuit selection"""
    menu = """
RasQ-LED Quantum Entanglement Demo
==================================
Select circuit type:
1) No entanglement (independent qubits)
2) Complete entanglement (all qubits entangled)
3) All factor-based entanglement patterns (demo sequence)
q) Quit and clear LEDs

Your choice: """

    while True:
        try:
            player_action = input(menu).strip().lower()

            if player_action == '1':
                run_circuit(1)
            elif player_action == '2':
                run_circuit(n_qbit)
            elif player_action == "3":
                factors = get_factors(n_qbit)
                print(f"Running sequence with entanglement factors: {factors}")
                for factor in factors:
                    print(f"\n--- Entanglement block size: {factor} ---")
                    run_circuit(factor)
                    time.sleep(3)
            elif player_action == 'q':
                clear_leds()
                print("Goodbye!")
                break
            else:
                print("Please type '1', '2', '3' or 'q'")

        except KeyboardInterrupt:
            print("\nClearing LEDs and exiting...")
            clear_leds()
            break
        except Exception as e:
            print(f"Error: {e}")

def demo_loop(duration=2):
    """Run automated demo showing all entanglement patterns

    Args:
        duration: Number of complete cycles through all patterns
    """
    import select

    print()
    print("RasQ-LED Quantum Entanglement Visualization")
    print("=" * 50)
    print("This demo creates groups of entangled qubits and displays the measurement")
    print("results using LED colors (Red=0, Blue=1).")
    print()
    print("A Hadamard gate is applied to the first qubit of each group,")
    print("then CNOT gates create entanglement within each group.")
    print("The entanglement group size varies from 1 (no entanglement)")
    print("up to all qubits (complete entanglement).")
    print()
    print("Press Enter to stop the demo (or Ctrl+C)")
    print()

    try:
        for cycle in range(duration):
            print(f"\n--- Demo Cycle {cycle + 1}/{duration} ---")
            factors = get_factors(n_qbit)

            for factor in factors:
                # Check for Enter key press
                if select.select([sys.stdin], [], [], 0)[0]:
                    sys.stdin.readline()
                    print("\nDemo stopped by user")
                    clear_leds()
                    return

                print(f"Entanglement block size: {factor}")
                if run_circuit(factor):
                    time.sleep(3)
                else:
                    print("Skipping due to error")

        print("\nDemo complete!")

    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    finally:
        clear_leds()

def main():
    """Main entry point"""
    print("RasQ-LED Quantum Entanglement Demo")
    print("=" * 60)

    # Check if display script is available
    if not find_display_script():
        print("Cannot continue without display script")
        sys.exit(1)

    # Run in demo mode by default
    # Uncomment the next line to run interactive mode instead
    demo_loop(2)

    # For interactive mode, uncomment this line and comment the demo_loop line above:
    # interactive_mode()

if __name__ == '__main__':
    main()
