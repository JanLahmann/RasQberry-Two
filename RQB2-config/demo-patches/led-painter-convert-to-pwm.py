#!/usr/bin/env python3
"""
LED-Painter: Convert from SPI to PWM/PIO drivers with persistent NeoPixel object.

This script modifies LED-Painter files to:
1. Convert from SPI-based neopixel to PWM/PIO based neopixel
2. Use persistent global NeoPixel object to prevent GPIO busy errors
3. Update imports and initialization code

Works with the LED-Painter repository as-is, no patch file needed.
"""

import sys
import os
import re


def convert_display_to_leds(file_path):
    """Convert display_to_LEDs_from_file.py from SPI to PWM/PIO with persistent object."""

    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Change import from neopixel_spi to neopixel
    content = re.sub(
        r'import neopixel_spi as neopixel',
        'import neopixel',
        content
    )

    # 2. Add persistent NeoPixel object after PIXEL_ORDER definition
    pixel_order_pattern = r'(PIXEL_ORDER = neopixel\.\w+)'
    if re.search(pixel_order_pattern, content):
        replacement = r'\1\n\n# Global NeoPixel object - created once and reused to prevent GPIO busy errors\n_pixels = None\n\ndef _get_pixels(brightness=1.0):\n    """Get or create the global NeoPixel object."""\n    global _pixels\n    if _pixels is None:\n        _pixels = neopixel.NeoPixel(\n            board.D18,\n            NUM_PIXELS,\n            pixel_order=PIXEL_ORDER,\n            brightness=brightness,\n            auto_write=False\n        )\n    else:\n        # Update brightness if different\n        _pixels.brightness = brightness\n    return _pixels\n'
        content = re.sub(pixel_order_pattern, replacement, content, count=1)

    # 3. Replace SPI-based NeoPixel initialization with persistent object getter
    # Match the old SPI initialization block
    spi_init_pattern = r'    # Neopixel initialization\s+spi = board\.SPI\(\)\s+pixels = neopixel\.NeoPixel_SPI\([^)]+\)'
    spi_init_replacement = '    # Get the persistent NeoPixel object (PWM/PIO driver)\n    pixels = _get_pixels(brightness)'

    content = re.sub(spi_init_pattern, spi_init_replacement, content, flags=re.DOTALL)

    # Alternative pattern if the above doesn't match (multiline with more whitespace)
    if 'NeoPixel_SPI' in content:
        # More aggressive replacement
        lines = content.split('\n')
        new_lines = []
        skip_until_closing_paren = False

        for i, line in enumerate(lines):
            if 'spi = board.SPI()' in line:
                # Skip this line
                continue
            elif 'pixels = neopixel.NeoPixel_SPI(' in line:
                # Replace with our new initialization
                new_lines.append('    # Get the persistent NeoPixel object (PWM/PIO driver)')
                new_lines.append('    pixels = _get_pixels(brightness)')
                skip_until_closing_paren = True
                continue
            elif skip_until_closing_paren:
                if ')' in line and 'brightness' in lines[i-1]:
                    # Found the closing paren, stop skipping
                    skip_until_closing_paren = False
                continue
            else:
                new_lines.append(line)

        content = '\n'.join(new_lines)

    with open(file_path, 'w') as f:
        f.write(content)

    return True


def convert_turn_off_leds(file_path):
    """Convert turn_off_LEDs.py from SPI to PWM/PIO."""

    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Change import
    content = re.sub(
        r'import neopixel_spi as neopixel',
        'import neopixel',
        content
    )

    # 2. Replace SPI initialization with PWM/PIO
    spi_pattern = r'        spi = board\.SPI\(\)\s+pixels = neopixel\.NeoPixel_SPI\([^)]+\)'
    pwm_replacement = '        # Use board.D18 for GPIO 18 (PWM/PIO driver auto-detects Pi 4 vs Pi 5)\n        pixels = neopixel.NeoPixel(board.D18, NUM_PIXELS, pixel_order=PIXEL_ORDER, auto_write=False)'

    content = re.sub(spi_pattern, pwm_replacement, content, flags=re.DOTALL)

    with open(file_path, 'w') as f:
        f.write(content)

    return True


def update_requirements(file_path):
    """Update requirements.txt to use PWM/PIO drivers."""

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


def disable_turn_off_in_main(file_path):
    """Disable redundant turn_off_LEDs call in LED_painter.py to prevent GPIO conflict."""

    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found, skipping")
        return False

    with open(file_path, 'r') as f:
        content = f.read()

    # Comment out the turn_off_LEDs() call before display_to_LEDs()
    content = re.sub(
        r'(\s+)turn_off_LEDs\(\)(\s+display_to_LEDs)',
        r'\1# turn_off_LEDs()  # Disabled: causes GPIO conflict\n\1# display_to_LEDs() now clears pixels internally\2',
        content
    )

    with open(file_path, 'w') as f:
        f.write(content)

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
        # Convert display_to_LEDs_from_file.py
        display_file = os.path.join(demo_dir, 'display_to_LEDs_from_file.py')
        if os.path.exists(display_file):
            convert_display_to_leds(display_file)
            print(f"✓ Converted {display_file}")
        else:
            print(f"⚠ File not found: {display_file}")

        # Convert turn_off_LEDs.py
        turn_off_file = os.path.join(demo_dir, 'turn_off_LEDs.py')
        if os.path.exists(turn_off_file):
            convert_turn_off_leds(turn_off_file)
            print(f"✓ Converted {turn_off_file}")
        else:
            print(f"⚠ File not found: {turn_off_file}")

        # Update requirements.txt
        req_file = os.path.join(demo_dir, 'requirements.txt')
        if os.path.exists(req_file):
            update_requirements(req_file)
            print(f"✓ Updated {req_file}")
        else:
            print(f"⚠ File not found: {req_file}")

        # Disable redundant turn_off_LEDs call
        main_file = os.path.join(demo_dir, 'LED_painter.py')
        if os.path.exists(main_file):
            disable_turn_off_in_main(main_file)
            print(f"✓ Updated {main_file}")

        print("\n✓ LED-Painter successfully converted to PWM/PIO drivers!")
        print("  - Using persistent NeoPixel object (prevents GPIO busy errors)")
        print("  - Compatible with both Pi 4 (PWM) and Pi 5 (PIO)")

    except Exception as e:
        print(f"\nError during conversion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
