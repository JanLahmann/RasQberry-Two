#!/usr/bin/env python3
"""
Demo: Flashing alert message.

Displays a flashing alert message in red color.
This demo showcases the new flashing text functionality.
"""

import sys
import os

# Add RQB2-bin to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rq_led_utils import create_neopixel_strip, display_flashing_text, get_led_config


def main():
    """Main demo function."""
    print("RasQberry LED Flashing Alert Demo")
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

    # Display flashing alert
    print("Displaying flashing alert...")
    print("Press Ctrl+C to stop")
    print()

    try:
        display_flashing_text(
            pixels,
            "ERROR",
            flash_count=5,
            flash_speed=0.3,
            color=(255, 0, 0)  # Red
        )

        print()
        print("Alert sequence complete!")

    except KeyboardInterrupt:
        print("\nDemo interrupted by user")

    # Turn off LEDs
    print("Turning off LEDs...")
    pixels.fill((0, 0, 0))
    pixels.show()

    print("Demo complete!")


if __name__ == "__main__":
    main()