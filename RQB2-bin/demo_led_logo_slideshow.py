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
from rq_led_utils import get_logo_dir


def main():
    """Main demo function."""
    print("RasQberry LED Logo Slideshow Demo")
    print("=" * 50)

    # Get logo directory (prefers the user copy, falls back to /usr/config)
    logo_dir = get_logo_dir()

    # Find all 24x8 PNG files in logo directory
    pattern = os.path.join(logo_dir, "*-24x8.png")
    logos = sorted(glob.glob(pattern))

    if not logos:
        print(f"ERROR: No logos found in {logo_dir}")
        print(f"Please run: python3 {os.path.join(logo_dir, 'create_logos.py')}")
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