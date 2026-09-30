#!/usr/bin/env python3
"""
Demo: Display IBM logo from PNG file.

Displays the IBM logo on the LED matrix.
This demo showcases the new PIL-based logo display functionality.
"""

import sys
import os

# Add RQB2-bin to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rq_led_logo import display_logo
from rq_led_utils import get_logo_dir


def main():
    """Main demo function."""
    print("RasQberry LED IBM Logo Demo")
    print("=" * 50)

    # Get logo path (prefers the user copy, falls back to /usr/config/LED-Logos)
    logo_dir = get_logo_dir()
    logo_path = os.path.join(logo_dir, "ibm-logo-24x8.png")

    # Check if logo exists
    if not os.path.exists(logo_path):
        print(f"ERROR: Logo file not found: {logo_path}")
        print(f"Please run: python3 {os.path.join(logo_dir, 'create_logos.py')}")
        sys.exit(1)

    print(f"Logo: {logo_path}")
    print("Duration: 10 seconds")
    print("Brightness: 50%")
    print()

    # Display logo
    print("Displaying IBM logo...")
    print("Press Ctrl+C to stop")
    print()

    try:
        display_logo(logo_path, duration=10, brightness=0.5)
        print("Display complete!")
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()