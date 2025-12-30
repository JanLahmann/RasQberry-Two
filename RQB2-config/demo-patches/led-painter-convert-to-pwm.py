#!/usr/bin/env python3
"""
LED-Painter: Convert from SPI to PWM/PIO drivers using shared rq_led_utils module.

This script modifies LED-Painter files to:
1. Convert display_to_LEDs_from_file.py to use rq_led_utils singleton
2. Convert turn_off_LEDs.py to use rq_led_utils.clear_all_leds()
3. Update LED_painter.py to use the shared module for atexit
4. Update requirements.txt for PWM/PIO drivers

Uses the system-wide rq_led_utils module (/usr/bin/rq_led_utils.py) which provides
a singleton NeoPixel object to prevent GPIO conflicts on Pi 5.
"""

import sys
import os


DISPLAY_TO_LEDS_MODULE = '''# Standard
import json
import argparse
import atexit
import sys

# Add /usr/bin to path for rq_led_utils
sys.path.insert(0, '/usr/bin')

# Local - use RasQberry shared LED utilities (singleton NeoPixel)
from rq_led_utils import get_pixels, clear_all_leds
from LED_array_indices import LED_ARRAY_INDICES

# Constants
NUM_PIXELS = 192


def display_to_LEDs(array_data, args):
    """
    Display pixel data to the LED array.

    Args:
        array_data (dict): Data to display. Format: {index: [R, G, B]} for each pixel.
        args: Namespace with console (bool) and brightness (float) attributes.
    """
    console = args.console
    brightness = args.brightness

    # Get the shared NeoPixel object from rq_led_utils
    pixels = get_pixels(brightness)

    # Display to LED array
    for index, color in array_data.items():
        red, green, blue = color[0], color[1], color[2]
        LED_array_index = LED_ARRAY_INDICES[int(index)]
        pixels[LED_array_index] = (red, green, blue)

    pixels.show()

    if console:
        print("LED Array Data:")
        print(array_data)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="LED array pixel values file", type=str, default=None)
    parser.add_argument("-c", "--console", help="Print values to console", action="store_true")
    parser.add_argument("-b", "--brightness", help="LED brightness (0.0-1.0)", type=float, default=1.0)
    return parser.parse_args()


def main():
    args = parse_arguments()
    atexit.register(clear_all_leds)

    if args.file:
        array_data_file = args.file
    else:
        array_data_file = input("Enter LED color values file path: ")

    try:
        with open(array_data_file) as file:
            array_data = json.load(file)
    except Exception as e:
        print(f"Error loading file: {e}")
        return

    try:
        print("Displaying to LEDs...")
        display_to_LEDs(array_data, args)
        print("Done")
    except Exception as e:
        print(f"Error displaying to LEDs: {e}")


if __name__ == "__main__":
    main()
'''

TURN_OFF_LEDS_MODULE = '''"""Turn off all LEDs using the shared RasQberry LED utilities."""
import sys

# Add /usr/bin to path for rq_led_utils
sys.path.insert(0, '/usr/bin')

from rq_led_utils import clear_all_leds


def turn_off_LEDs():
    """Turn off all LEDs using the shared singleton NeoPixel object."""
    clear_all_leds()


def main():
    print("Turning off all LEDs...")
    turn_off_LEDs()
    print("Done!")


if __name__ == "__main__":
    main()
'''


def convert_display_to_leds(demo_dir):
    """Replace display_to_LEDs_from_file.py with version using shared module."""
    file_path = os.path.join(demo_dir, 'display_to_LEDs_from_file.py')
    with open(file_path, 'w') as f:
        f.write(DISPLAY_TO_LEDS_MODULE)
    return True


def convert_turn_off_leds(demo_dir):
    """Replace turn_off_LEDs.py with version using shared module."""
    file_path = os.path.join(demo_dir, 'turn_off_LEDs.py')
    with open(file_path, 'w') as f:
        f.write(TURN_OFF_LEDS_MODULE)
    return True


def update_led_painter(demo_dir):
    """Update LED_painter.py to use shared module for atexit."""
    file_path = os.path.join(demo_dir, 'LED_painter.py')
    if not os.path.exists(file_path):
        return False

    with open(file_path, 'r') as f:
        content = f.read()

    # Add sys.path for rq_led_utils import at the top of imports
    if 'sys.path.insert' not in content:
        content = content.replace(
            'import sys',
            'import sys\n\n# Add /usr/bin to path for rq_led_utils\nsys.path.insert(0, \'/usr/bin\')'
        )

    # Add import for clear_all_leds from shared module
    if 'from turn_off_LEDs import turn_off_LEDs' in content:
        content = content.replace(
            'from turn_off_LEDs import turn_off_LEDs',
            'from turn_off_LEDs import turn_off_LEDs\nfrom rq_led_utils import clear_all_leds'
        )

    # Use clear_all_leds for atexit instead of turn_off_LEDs
    content = content.replace(
        'atexit.register(turn_off_LEDs)',
        'atexit.register(clear_all_leds)'
    )

    # Comment out redundant turn_off_LEDs call before display_to_LEDs
    import re
    content = re.sub(
        r'(\s+)turn_off_LEDs\(\)(\s+)(display_to_LEDs)',
        r'\1# turn_off_LEDs()  # Disabled: display_to_LEDs handles pixel state\2\3',
        content
    )

    with open(file_path, 'w') as f:
        f.write(content)

    return True


def update_requirements(demo_dir):
    """Update requirements.txt to use PWM/PIO drivers."""
    file_path = os.path.join(demo_dir, 'requirements.txt')
    if not os.path.exists(file_path):
        return False

    with open(file_path, 'r') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        if 'adafruit-circuitpython-neopixel-spi' in line:
            # Comment out SPI driver and add PWM/PIO drivers
            new_lines.append(f'# {line}')
            new_lines.append('adafruit-circuitpython-neopixel>=6.3.0\n')
            new_lines.append('# Pi 5 specific driver (automatically selected when needed)\n')
            new_lines.append('Adafruit-Blinka-Raspberry-Pi5-Neopixel; platform_machine == "aarch64"\n')
        else:
            new_lines.append(line)

    with open(file_path, 'w') as f:
        f.writelines(new_lines)

    return True


def main():
    if len(sys.argv) != 2:
        print("Usage: led-painter-convert-to-pwm.py <led-painter-directory>")
        sys.exit(1)

    demo_dir = sys.argv[1]
    if not os.path.isdir(demo_dir):
        print(f"Error: Directory not found: {demo_dir}")
        sys.exit(1)

    print("Converting LED-Painter from SPI to PWM/PIO drivers...")

    try:
        # Replace display_to_LEDs_from_file.py
        convert_display_to_leds(demo_dir)
        print(f"✓ Converted display_to_LEDs_from_file.py (uses rq_led_utils singleton)")

        # Replace turn_off_LEDs.py
        convert_turn_off_leds(demo_dir)
        print(f"✓ Converted turn_off_LEDs.py (uses rq_led_utils.clear_all_leds)")

        # Update LED_painter.py
        main_file = os.path.join(demo_dir, 'LED_painter.py')
        if os.path.exists(main_file):
            update_led_painter(demo_dir)
            print(f"✓ Updated LED_painter.py (uses shared module for atexit)")

        # Update requirements.txt
        req_file = os.path.join(demo_dir, 'requirements.txt')
        if os.path.exists(req_file):
            update_requirements(demo_dir)
            print(f"✓ Updated requirements.txt")

        print("\n✓ LED-Painter successfully converted to PWM/PIO drivers!")
        print("  - Uses rq_led_utils.get_pixels() singleton (prevents GPIO conflicts)")
        print("  - Uses rq_led_utils.clear_all_leds() for cleanup")
        print("  - Compatible with both Pi 4 (PWM) and Pi 5 (PIO)")

    except Exception as e:
        print(f"\nError during conversion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
