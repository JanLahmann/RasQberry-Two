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


def main():
    """Main demo function."""
    print("RasQberry LED IBM Logo Demo")
    print("=" * 50)

    # Get repository name from environment or use default
    repo_name = os.environ.get('REPO', 'RasQberry-Two')

    # Get logo path
    config_dir = os.path.expanduser(f"~/{repo_name}/RQB2-config")
    logo_path = os.path.join(config_dir, "LED-Logos", "ibm-logo-24x8.png")

    # Check if logo exists
    if not os.path.exists(logo_path):
        print(f"ERROR: Logo file not found: {logo_path}")
        print(f"Please run: python3 ~/{repo_name}/RQB2-config/LED-Logos/create_logos.py")
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