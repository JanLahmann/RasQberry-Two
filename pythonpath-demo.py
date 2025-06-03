#!/usr/bin/env python3
"""
Demo: How PYTHONPATH manipulation enables version-specific imports
"""

import sys
import os

def demo_pythonpath_manipulation():
    print("=== Python Import Path Demo ===")
    print("Current sys.path:")
    for i, path in enumerate(sys.path):
        print(f"  {i}: {path}")
    
    print("\n=== Adding version-specific path ===")
    # This simulates what we'd do for Qiskit 1.4
    legacy_path = "/home/rasqberry/RasQberry-Two/venv/RQB2-unified/legacy/qiskit-1.4"
    
    # Insert at the beginning (highest priority)
    sys.path.insert(0, legacy_path)
    
    print("Updated sys.path:")
    for i, path in enumerate(sys.path):
        if "legacy" in path:
            print(f"  {i}: {path} ← NEW: Legacy Qiskit 1.4")
        else:
            print(f"  {i}: {path}")
    
    print("\n=== Import Resolution ===")
    print("When Python sees 'import qiskit':")
    print("1. Checks legacy/qiskit-1.4/ FIRST")
    print("2. If not found, falls back to standard site-packages/qiskit/")

def demo_version_switching():
    """Show how to switch between Qiskit versions dynamically"""
    
    def set_qiskit_version(version):
        """Set up PYTHONPATH for specific Qiskit version"""
        # Remove any existing legacy paths
        sys.path = [p for p in sys.path if 'legacy' not in p]
        
        if version == "1.4":
            legacy_path = "/home/rasqberry/RasQberry-Two/venv/RQB2-unified/legacy/qiskit-1.4"
            sys.path.insert(0, legacy_path)
            print(f"✓ Switched to Qiskit 1.4 (using {legacy_path})")
        elif version == "latest":
            print("✓ Using latest Qiskit (standard site-packages)")
        else:
            print(f"❌ Unknown version: {version}")
    
    print("\n=== Dynamic Version Switching ===")
    set_qiskit_version("latest")
    # import qiskit  # Would get latest version
    
    set_qiskit_version("1.4")
    # import qiskit  # Would get 1.4 version from legacy path

if __name__ == "__main__":
    demo_pythonpath_manipulation()
    demo_version_switching()