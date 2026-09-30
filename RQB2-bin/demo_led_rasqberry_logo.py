#!/usr/bin/env python3
"""
Demo: Display RasQberry cube logo from PNG file.

Displays the RasQberry cube logo with fade-in/fade-out effects.
This demo showcases the new PIL-based logo display with animations.
"""

import sys
import os

# Add RQB2-bin to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rq_led_logo import display_logo
from rq_led_utils import get_logo_dir


def main():
    """Main demo function."""
    print("RasQberry LED Cube Logo Demo")
    print("=" * 50)

    # Get logo path (prefers the user copy, falls back to /usr/config/LED-Logos)
    logo_dir = get_logo_dir()
    logo_path = os.path.join(logo_dir, "rasqberry-cube-24x8.png")

    # Check if logo exists
    if not os.path.exists(logo_path):
        print(f"ERROR: Logo file not found: {logo_path}")
        print(f"Please run: python3 {os.path.join(logo_dir, 'create_logos.py')}")
        sys.exit(1)

    print(f"Logo: {logo_path}")
    print("Duration: 15 seconds")
    print("Brightness: 60%")
    print("Effects: Fade-in and fade-out")
    print()

    # Display logo with fade effects
    print("Displaying RasQberry cube logo...")
    print("Press Ctrl+C to stop")
    print()

    try:
        display_logo(
            logo_path,
            duration=15,
            brightness=0.6,
            fade_in=True,
            fade_out=True
        )
        print("Display complete!")
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()