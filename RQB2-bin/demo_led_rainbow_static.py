#!/usr/bin/env python3
"""
Demo: Static text with color cycling rainbow effect.

Displays stationary text while colors continuously cycle through
the rainbow spectrum, creating a mesmerizing color-changing effect.
"""

import sys
import os

# Add RQB2-bin to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rq_led_utils import create_neopixel_strip, display_static_text_rainbow, get_led_config


def main():
    """Main demo function."""
    print("RasQberry LED Rainbow Static Text Demo")
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

    # Display rainbow static text
    print("Displaying color-cycling text...")
    print("Press Ctrl+C to stop")
    print()

    try:
        display_static_text_rainbow(
            pixels,
            "COOL",
            duration_seconds=20,
            cycle_speed=0.05
        )
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")

    # Turn off LEDs
    print("Turning off LEDs...")
    pixels.fill((0, 0, 0))
    pixels.show()

    print("Demo complete!")


if __name__ == "__main__":
    main()