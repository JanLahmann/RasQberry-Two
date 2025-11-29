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


def main():
    """Main demo function."""
    print("RasQberry LED Cube Logo Demo")
    print("=" * 50)

    # Get repository name from environment or use default
    repo_name = os.environ.get('REPO', 'RasQberry-Two')

    # Get logo path
    config_dir = os.path.expanduser(f"~/{repo_name}/RQB2-config")
    logo_path = os.path.join(config_dir, "LED-Logos", "rasqberry-cube-24x8.png")

    # Check if logo exists
    if not os.path.exists(logo_path):
        print(f"ERROR: Logo file not found: {logo_path}")
        print(f"Please run: python3 ~/{repo_name}/RQB2-config/LED-Logos/create_logos.py")
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