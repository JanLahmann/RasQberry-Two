#!/usr/bin/env python3
"""
Test script for RasQ-LED RPi 5 compatibility
Tests the updated SPI-based LED driver without requiring actual hardware
"""

def test_imports():
    """Test if all required modules can be imported"""
    print("Testing imports...")
    
    try:
        import board
        import neopixel_spi as neopixel
        print("✓ SPI LED driver imports successful")
    except ImportError as e:
        print(f"✗ SPI LED driver import failed: {e}")
        return False
    
    try:
        from qiskit import QuantumCircuit
        try:
            from qiskit.providers.aer import AerSimulator
        except ModuleNotFoundError:
            from qiskit_aer import AerSimulator
        print("✓ Qiskit imports successful")
    except ImportError as e:
        print(f"✗ Qiskit import failed: {e}")
        return False
    
    try:
        from dotenv import dotenv_values
        print("✓ dotenv import successful")
    except ImportError as e:
        print(f"✗ dotenv import failed: {e}")
        print("  Install with: pip install python-dotenv")
        return False
    
    return True

def test_config_loading():
    """Test configuration loading from different paths"""
    print("\nTesting configuration loading...")
    
    import os
    from dotenv import dotenv_values
    
    config_paths = [
        "/usr/config/rasqberry_environment.env",
        os.path.expanduser("~/.local/config/rasqberry_environment.env"),
        "rasqberry_environment.env"
    ]
    
    config_found = False
    for config_path in config_paths:
        if os.path.exists(config_path):
            config = dotenv_values(config_path)
            print(f"✓ Found config at: {config_path}")
            print(f"  LED_COUNT: {config.get('LED_COUNT', 'not set')}")
            print(f"  N_QUBIT: {config.get('N_QUBIT', 'not set')}")
            print(f"  LED_PIN: {config.get('LED_PIN', 'not set')}")
            config_found = True
            break
    
    if not config_found:
        print("⚠ No config file found, will use defaults")
    
    return True

def test_quantum_circuit():
    """Test quantum circuit creation and execution"""
    print("\nTesting quantum circuit creation...")
    
    try:
        from qiskit import QuantumCircuit
        try:
            from qiskit.providers.aer import AerSimulator
        except ModuleNotFoundError:
            from qiskit_aer import AerSimulator
        
        # Create a simple 4-qubit circuit
        circuit = QuantumCircuit(4, 4)
        circuit.h(0)  # Hadamard on first qubit
        circuit.cx(0, 1)  # Entangle first two qubits
        circuit.measure(range(4), range(4))
        
        # Execute on simulator
        backend = AerSimulator()
        job = backend.run(circuit, shots=1)
        result = job.result()
        counts = result.get_counts()
        measurement = list(counts.items())[0][0]
        
        print(f"✓ Quantum circuit test successful")
        print(f"  Circuit: 4 qubits, H(0), CNOT(0,1)")
        print(f"  Measurement result: {measurement}")
        
        return True
    except Exception as e:
        print(f"✗ Quantum circuit test failed: {e}")
        return False

def test_script_paths():
    """Test if the updated scripts exist and are executable"""
    print("\nTesting script availability...")
    
    import os
    
    scripts = [
        "RasQ-LED_rpi5.py",
        "RasQ-LED-display_rpi5.py"
    ]
    
    script_dir = os.path.dirname(__file__)
    all_found = True
    
    for script in scripts:
        script_path = os.path.join(script_dir, script)
        if os.path.exists(script_path):
            if os.access(script_path, os.X_OK):
                print(f"✓ {script} exists and is executable")
            else:
                print(f"⚠ {script} exists but not executable")
        else:
            print(f"✗ {script} not found")
            all_found = False
    
    return all_found

def main():
    """Run all tests"""
    print("RasQ-LED Raspberry Pi 5 Compatibility Test")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("Config Loading Test", test_config_loading),
        ("Quantum Circuit Test", test_quantum_circuit),
        ("Script Path Test", test_script_paths)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            if test_func():
                passed += 1
            else:
                print(f"❌ {test_name} failed")
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
    
    print(f"\n{'='*50}")
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed! RasQ-LED RPi 5 compatibility looks good.")
        print("\nNext steps:")
        print("1. Test on actual Raspberry Pi 5 hardware")
        print("2. Verify SPI is enabled: sudo raspi-config -> Interface Options -> SPI")
        print("3. Run: python3 RasQ-LED_rpi5.py")
    else:
        print("❌ Some tests failed. Check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    main()