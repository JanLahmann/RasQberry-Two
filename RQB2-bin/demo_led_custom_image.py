#!/usr/bin/env python3
"""
Demo: Display custom image provided by user.

Allows users to display any PNG/JPG image on the LED matrix.
The image will be automatically resized to fit the matrix.
"""

import sys
import os

# Add RQB2-bin to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rq_led_logo import display_logo


def main():
    """Main demo function."""
    print("RasQberry LED Custom Image Demo")
    print("=" * 50)

    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: demo_led_custom_image.py <image_path> [duration] [brightness]")
        print()
        print("Arguments:")
        print("  image_path  : Path to PNG or JPG image file (required)")
        print("  duration    : Display duration in seconds (default: 10)")
        print("  brightness  : Brightness 0.0-1.0 (default: 0.5)")
        print()
        print("Examples:")
        print("  demo_led_custom_image.py ~/my_logo.png")
        print("  demo_led_custom_image.py ~/my_logo.png 15 0.7")
        sys.exit(1)

    # Parse arguments
    image_path = sys.argv[1]
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    brightness = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5

    # Expand path
    image_path = os.path.expanduser(image_path)

    # Check if file exists
    if not os.path.exists(image_path):
        print(f"ERROR: Image file not found: {image_path}")
        sys.exit(1)

    print(f"Image: {image_path}")
    print(f"Duration: {duration} seconds")
    print(f"Brightness: {brightness * 100:.0f}%")
    print()

    # Display image
    print("Displaying image on LED matrix...")
    print("(Image will be resized to fit matrix dimensions)")
    print("Press Ctrl+C to stop")
    print()

    try:
        display_logo(image_path, duration=duration, brightness=brightness)
        print("Display complete!")
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except IOError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()