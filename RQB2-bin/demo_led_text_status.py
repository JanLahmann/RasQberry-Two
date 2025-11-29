#!/usr/bin/env python3
"""
Demo: Display static status messages.

Displays a boot sequence with static text messages in different colors.
This demo showcases the new static text display functionality.
"""

import sys
import os

# Add RQB2-bin to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rq_led_utils import create_neopixel_strip, display_static_text, get_led_config


def main():
    """Main demo function."""
    print("RasQberry LED Static Status Demo")
    print("=" * 50)

    # Get configuration
    config = get_led_config()
    print(f"LED Count: {config['led_count']}")
    print(f"Matrix: {config['matrix_width']}x{config['matrix_height']}")
    print(f"Layout: {config['layout']}")
    print()

    # Create NeoPixel strip
    print("Initializing LED strip...")
    pixels = create_neopixel_strip(
        config['led_count'],
        config['pixel_order'],
        brightness=config['led_default_brightness']
    )

    # Display boot sequence
    print("Displaying boot sequence...")
    print()

    try:
        # Step 1: BOOT
        print("Status: BOOT")
        display_static_text(pixels, "BOOT", duration_seconds=2, color=(255, 255, 0))  # Yellow

        # Step 2: INIT
        print("Status: INIT")
        display_static_text(pixels, "INIT", duration_seconds=2, color=(255, 128, 0))  # Orange

        # Step 3: READY
        print("Status: READY")
        display_static_text(pixels, "READY", duration_seconds=3, color=(0, 255, 0))  # Green

        print()
        print("Boot sequence complete!")

    except KeyboardInterrupt:
        print("\nDemo interrupted by user")

    # Turn off LEDs
    print("Turning off LEDs...")
    pixels.fill((0, 0, 0))
    pixels.show()

    print("Demo complete!")


if __name__ == "__main__":
    main()