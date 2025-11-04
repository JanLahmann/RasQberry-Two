#!/usr/bin/env python3
"""
Demo: Static text with color gradient between two colors.

Displays text with a smooth gradient transition from one color to another,
creating an elegant color blend effect.
"""

import sys
import os

# Add RQB2-bin to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rq_led_utils import create_neopixel_strip, display_text_gradient, get_led_config


def main():
    """Main demo function."""
    print("RasQberry LED Color Gradient Demo")
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

    print("Displaying gradient text demos...")
    print()

    try:
        # Demo 1: Red to Blue gradient
        print("1. Red to Blue gradient...")
        display_text_gradient(
            pixels,
            "GRAD",
            duration_seconds=5,
            color1=(255, 0, 0),    # Red
            color2=(0, 0, 255)     # Blue
        )

        # Demo 2: Yellow to Cyan gradient
        print("2. Yellow to Cyan gradient...")
        display_text_gradient(
            pixels,
            "FADE",
            duration_seconds=5,
            color1=(255, 255, 0),  # Yellow
            color2=(0, 255, 255)   # Cyan
        )

        # Demo 3: Magenta to Green gradient
        print("3. Magenta to Green gradient...")
        display_text_gradient(
            pixels,
            "COOL",
            duration_seconds=5,
            color1=(255, 0, 255),  # Magenta
            color2=(0, 255, 0)     # Green
        )

        print()
        print("All gradient demos complete!")

    except KeyboardInterrupt:
        print("\nDemo interrupted by user")

    # Turn off LEDs
    print("Turning off LEDs...")
    pixels.fill((0, 0, 0))
    pixels.show()

    print("Demo complete!")


if __name__ == "__main__":
    main()