#!/usr/bin/env python3
"""
Post-installation fix for LED-Painter GPIO busy issue.

This script modifies display_to_LEDs_from_file.py to use a persistent global
NeoPixel object instead of creating a new one on each call. This prevents
"GPIO busy" errors when displaying multiple times.

Usage: Run this after cloning the LED-Painter repository.
"""

import sys
import os

def fix_gpio_busy(file_path):
    """Modify display_to_LEDs_from_file.py to use persistent NeoPixel object."""

    with open(file_path, 'r') as f:
        lines = f.readlines()

    # Find the line after PIXEL_ORDER definition to insert global variable
    for i, line in enumerate(lines):
        if 'PIXEL_ORDER = neopixel.GRB' in line:
            # Insert global NeoPixel variable and getter function after PIXEL_ORDER
            lines.insert(i + 1, '\n')
            lines.insert(i + 2, '# Global NeoPixel object - created once and reused\n')
            lines.insert(i + 3, '_pixels = None\n')
            lines.insert(i + 4, '\n')
            lines.insert(i + 5, 'def _get_pixels(brightness=1.0):\n')
            lines.insert(i + 6, '    """Get or create the global NeoPixel object."""\n')
            lines.insert(i + 7, '    global _pixels\n')
            lines.insert(i + 8, '    if _pixels is None:\n')
            lines.insert(i + 9, '        _pixels = neopixel.NeoPixel(\n')
            lines.insert(i + 10, '            board.D18,\n')
            lines.insert(i + 11, '            NUM_PIXELS,\n')
            lines.insert(i + 12, '            pixel_order=PIXEL_ORDER,\n')
            lines.insert(i + 13, '            brightness=brightness,\n')
            lines.insert(i + 14, '            auto_write=False\n')
            lines.insert(i + 15, '        )\n')
            lines.insert(i + 16, '    else:\n')
            lines.insert(i + 17, '        # Update brightness if different\n')
            lines.insert(i + 18, '        _pixels.brightness = brightness\n')
            lines.insert(i + 19, '    return _pixels\n')
            lines.insert(i + 20, '\n')
            break

    # Replace NeoPixel initialization in display_to_LEDs function
    in_neopixel_init = False
    lines_to_remove = []

    for i, line in enumerate(lines):
        if '# Neopixel initialization' in line or '# Use board.D18' in line:
            in_neopixel_init = True
        elif in_neopixel_init:
            if 'pixels = neopixel.NeoPixel(' in line:
                # Mark this line and following lines for removal
                lines_to_remove.append(i)
                # Find the closing parenthesis
                depth = 1
                for j in range(i + 1, len(lines)):
                    if '(' in lines[j]:
                        depth += lines[j].count('(')
                    if ')' in lines[j]:
                        depth -= lines[j].count(')')
                        if depth == 0:
                            lines_to_remove.extend(range(i + 1, j + 1))
                            # Insert replacement
                            lines[i] = '    # Get the persistent NeoPixel object\n'
                            lines.insert(i + 1, '    pixels = _get_pixels(brightness)\n')
                            lines.insert(i + 2, '\n')
                            in_neopixel_init = False
                            break
                break

    # Remove the old initialization lines (in reverse to preserve indices)
    for i in reversed(lines_to_remove):
        if i != lines_to_remove[0]:  # Keep the first line as we replaced it
            del lines[i]

    with open(file_path, 'w') as f:
        f.writelines(lines)

    print(f"✓ Fixed GPIO busy issue in {file_path}")
    return True

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: led-painter-fix-gpio-busy.py <path-to-display_to_LEDs_from_file.py>")
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    try:
        fix_gpio_busy(file_path)
        print("LED-Painter GPIO busy fix applied successfully!")
    except Exception as e:
        print(f"Error applying fix: {e}")
        sys.exit(1)