#!/usr/bin/env python3
"""
Qiskit Version Manager for RasQberry
Allows switching between Qiskit versions in a unified environment
"""

import sys
import os
import importlib.util

class QiskitVersionManager:
    """Manages multiple Qiskit versions in a single environment"""
    
    def __init__(self, venv_base="/home/rasqberry/RasQberry-Two/venv/RQB2-unified"):
        self.venv_base = venv_base
        self.legacy_base = os.path.join(venv_base, "legacy")
        self.current_version = None
        
        # Version mappings
        self.versions = {
            "latest": None,  # Use standard site-packages
            "2.x": None,     # Alias for latest
            "1.4": os.path.join(self.legacy_base, "qiskit-1.4"),
            "0.44": os.path.join(self.legacy_base, "qiskit-0.44")
        }
    
    def set_version(self, version):
        """Switch to specific Qiskit version"""
        if version not in self.versions:
            raise ValueError(f"Unknown version: {version}. Available: {list(self.versions.keys())}")
        
        # Clean up previous version paths
        self._cleanup_paths()
        
        legacy_path = self.versions[version]
        if legacy_path and os.path.exists(legacy_path):
            # Insert legacy path at the beginning for highest priority
            sys.path.insert(0, legacy_path)
            print(f"✓ Switched to Qiskit {version} (using {legacy_path})")
        else:
            print(f"✓ Using Qiskit {version} (standard installation)")
        
        self.current_version = version
    
    def _cleanup_paths(self):
        """Remove any legacy Qiskit paths from sys.path"""
        sys.path = [p for p in sys.path if not p.startswith(self.legacy_base)]
    
    def get_version_info(self):
        """Get information about current Qiskit version"""
        try:
            import qiskit
            return {
                "version": qiskit.__version__,
                "path": qiskit.__file__,
                "manager_version": self.current_version
            }
        except ImportError:
            return {"error": "Qiskit not found"}
    
    def demo_switching(self):
        """Demonstrate version switching"""
        print("=== Qiskit Version Switching Demo ===\n")
        
        for version in ["latest", "1.4"]:
            print(f"--- Testing {version} ---")
            self.set_version(version)
            
            # Show where Python would look for qiskit
            for i, path in enumerate(sys.path[:5]):  # Show first 5 paths
                marker = " ← QISKIT SEARCH PATH" if "qiskit" in path.lower() else ""
                print(f"  {i}: {path}{marker}")
            
            print()

# Example usage functions for RasQberry demos
def run_demo_with_qiskit_version(demo_function, qiskit_version="latest"):
    """Run a demo with specific Qiskit version"""
    manager = QiskitVersionManager()
    
    try:
        # Set desired version
        manager.set_version(qiskit_version)
        
        # Now any 'import qiskit' will use the specified version
        result = demo_function()
        
        # Show version info
        info = manager.get_version_info()
        print(f"Demo completed using Qiskit {info.get('version', 'unknown')}")
        
        return result
        
    except Exception as e:
        print(f"Error running demo with Qiskit {qiskit_version}: {e}")
        return None

def quantum_fractals_demo():
    """Example: Quantum Fractals demo requiring Qiskit 1.4"""
    import qiskit  # This will use whatever version was set
    print(f"Running Quantum Fractals with Qiskit {qiskit.__version__}")
    # ... actual demo code would go here
    return "Fractals generated successfully"

def latest_features_demo():
    """Example: Demo using latest Qiskit features"""
    import qiskit
    print(f"Running latest features demo with Qiskit {qiskit.__version__}")
    # ... demo code using new Qiskit 2.x features
    return "Latest features demonstrated"

if __name__ == "__main__":
    # Demo the version manager
    manager = QiskitVersionManager()
    manager.demo_switching()
    
    print("\n=== Demo Usage Examples ===")
    
    # Run quantum fractals with Qiskit 1.4
    print("\n1. Running Quantum Fractals (requires Qiskit 1.4):")
    run_demo_with_qiskit_version(quantum_fractals_demo, "1.4")
    
    # Run latest features demo with current Qiskit
    print("\n2. Running Latest Features Demo:")
    run_demo_with_qiskit_version(latest_features_demo, "latest")