#!/usr/bin/env python3
"""
Demo: Slideshow of multiple logos.

Displays all available logos in a slideshow format.
This demo showcases multiple logo files in sequence.
"""

import sys
import os
import glob

# Add RQB2-bin to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rq_led_logo import display_logo


def main():
    """Main demo function."""
    print("RasQberry LED Logo Slideshow Demo")
    print("=" * 50)

    # Get logo directory
    config_dir = os.path.expanduser("~/RasQberry-Two/RQB2-config")
    logo_dir = os.path.join(config_dir, "LED-Logos")

    # Find all 24x8 PNG files in logo directory
    pattern = os.path.join(logo_dir, "*-24x8.png")
    logos = sorted(glob.glob(pattern))

    if not logos:
        print(f"ERROR: No logos found in {logo_dir}")
        print("Please run: python3 RQB2-config/LED-Logos/create_logos.py")
        sys.exit(1)

    print(f"Logo directory: {logo_dir}")
    print(f"Found {len(logos)} logos:")
    for logo in logos:
        print(f"  - {os.path.basename(logo)}")
    print()
    print("Duration per logo: 5 seconds")
    print("Brightness: 50%")
    print()

    # Display each logo
    print("Starting slideshow...")
    print("Press Ctrl+C to stop")
    print()

    try:
        for i, logo in enumerate(logos, 1):
            basename = os.path.basename(logo)
            print(f"[{i}/{len(logos)}] Displaying: {basename}")

            display_logo(logo, duration=5, brightness=0.5)

            print(f"     Complete!")

        print()
        print("Slideshow complete!")

    except KeyboardInterrupt:
        print("\nSlideshow interrupted by user")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()