#!/usr/bin/env python3
"""
RasQberry LED Test Utility

Lights the LED strip in blocks and as a whole to check wiring, power and
LED count. Uses the PWM (Pi 4) or PIO (Pi 5) driver via rq_led_utils.

The old chunk size / delay options and the parameter scan are gone: they
tuned a workaround for the retired SPI driver and had no effect since (#132).
"""

import time
import sys
import argparse

# Add /usr/bin to path to import rq_led_utils
sys.path.insert(0, '/usr/bin')

from rq_led_utils import get_led_config, create_neopixel_strip

COLORS = [
    ((255, 0, 0), "Red"),
    ((0, 255, 0), "Green"),
    ((0, 0, 255), "Blue"),
    ((255, 255, 0), "Yellow"),
    ((255, 0, 255), "Magenta"),
    ((0, 255, 255), "Cyan"),
    ((255, 128, 0), "Orange"),
    ((128, 0, 255), "Purple"),
    ((255, 255, 255), "White"),
]


def print_header():
    """Print the test header."""
    print()
    print("=" * 60)
    print("  RasQberry LED Panel Test")
    print("=" * 60)
    print()


def scaled(color, brightness):
    """
    Scale an RGB colour by a brightness factor.

    Args:
        color (tuple): (r, g, b), 0-255 each.
        brightness (float): 0.0-1.0.

    Returns:
        tuple: The scaled colour.
    """
    return tuple(int(c * brightness) for c in color)


def fill(pixels, color):
    """Set every LED to one colour and show it."""
    pixels.fill(color)
    pixels.show()


def block_test(pixels, num_leds, brightness, block_size=10, cycles=3):
    """
    Light blocks of LEDs one after another along the strip.

    Args:
        pixels: NeoPixel strip object.
        num_leds (int): Number of LEDs to test.
        brightness (float): Brightness level (0.0-1.0).
        block_size (int): Number of LEDs per block.
        cycles (int): Number of passes along the strip.

    Returns:
        bool: True if the test completed, False if interrupted.
    """
    print(f"Block Test: {block_size} LEDs at a time, {cycles} cycles")
    print()
    test_color = scaled((255, 0, 128), brightness)  # Purple

    try:
        for cycle in range(cycles):
            print(f"  Cycle {cycle + 1}/{cycles}...", end=" ", flush=True)
            for start in range(0, num_leds, block_size):
                end = min(start + block_size, num_leds)
                for i in range(start, end):
                    pixels[i] = test_color
                pixels.show()
                time.sleep(0.3)  # hold lit for visibility
                for i in range(start, end):
                    pixels[i] = (0, 0, 0)
                pixels.show()
                time.sleep(0.1)
            print("✓")
        print()
        return True
    except KeyboardInterrupt:
        print(" [Interrupted]")
        return False


def full_strip_test(pixels, num_leds, brightness, cycles=5):
    """
    Light the whole strip in red, green and blue in turn.

    Args:
        pixels: NeoPixel strip object.
        num_leds (int): Number of LEDs to test.
        brightness (float): Brightness level (0.0-1.0).
        cycles (int): Number of colour cycles.

    Returns:
        bool: True if the test completed, False if interrupted.
    """
    print(f"Full Strip Test: All {num_leds} LEDs, {cycles} cycles")
    print()
    try:
        for cycle in range(cycles):
            color, name = COLORS[cycle % 3]
            print(f"  Cycle {cycle + 1}/{cycles} ({name})...", end=" ", flush=True)
            fill(pixels, scaled(color, brightness))
            time.sleep(0.5)
            fill(pixels, (0, 0, 0))
            time.sleep(0.2)
            print("✓")
        print()
        return True
    except KeyboardInterrupt:
        print(" [Interrupted]")
        return False


def make_strip(num_leds, brightness, pixel_order):
    """Create the LED strip (auto-detects Pi 4 PWM or Pi 5 PIO)."""
    return create_neopixel_strip(num_leds, pixel_order, brightness=brightness)


def run_manual_test(num_leds, brightness, pixel_order):
    """
    Run the block test and the full strip test.

    Returns:
        bool: True if both completed.
    """
    print_header()
    config = get_led_config()
    print("Configuration:")
    print(f"  Platform: {config['pi_model']}")
    print(f"  LEDs: {num_leds}")
    print(f"  GPIO: {config['led_gpio_pin']}")
    print(f"  Brightness: {int(brightness * 100)}%")
    print(f"  Pixel order: {pixel_order}")
    print()
    if sys.stdin.isatty():  # run directly; a demo window says how to stop it
        print("Press Ctrl+C to skip a test or stop")
        print()

    pixels = make_strip(num_leds, brightness, pixel_order)
    try:
        if not block_test(pixels, num_leds, brightness):
            return False
        if not full_strip_test(pixels, num_leds, brightness):
            return False
        print("✓ All tests completed successfully!")
        print()
        return True
    finally:
        fill(pixels, (0, 0, 0))


def run_continuous_test(num_leds, brightness, pixel_order, cycles=None):
    """
    Cycle the whole strip through a sequence of colours.

    Args:
        num_leds (int): Number of LEDs.
        brightness (float): Brightness level (0.0-1.0).
        pixel_order (str): Pixel colour order (RGB, GRB, ...).
        cycles (int | None): Number of colours to show; None runs until Ctrl+C.
    """
    print_header()
    print("Continuous Colour Cycle")
    print(f"  LEDs: {num_leds}, brightness {int(brightness * 100)}%, pixel order {pixel_order}")
    print(f"  Cycles: {'until Ctrl+C' if cycles is None else cycles}")
    print()

    pixels = make_strip(num_leds, brightness, pixel_order)
    try:
        cycle = 0
        while cycles is None or cycle < cycles:
            for color, name in COLORS:
                cycle += 1
                if cycles is not None and cycle > cycles:
                    break
                start = time.time()
                fill(pixels, scaled(color, brightness))
                print(f"Cycle {cycle}: {name:<10} [shown in {time.time() - start:.3f}s]")
                time.sleep(0.5)
                fill(pixels, (0, 0, 0))
                time.sleep(0.5)
        print()
        print("✓ Test completed successfully!")
        print()
    except KeyboardInterrupt:
        print()
        print("[Test stopped by user]")
        print()
    finally:
        fill(pixels, (0, 0, 0))


def main():
    """Parse arguments and run the chosen test."""
    parser = argparse.ArgumentParser(
        description='RasQberry LED Panel Test',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run default tests (block + full strip)
  %(prog)s

  # Cycle colours until Ctrl+C, or for 20 colours
  %(prog)s --continuous
  %(prog)s --continuous --cycles 20

  # Test with lower brightness
  %(prog)s --brightness 0.05
"""
    )

    config = get_led_config()
    default_leds = config.get('led_count', 192)
    default_brightness = float(config.get('led_default_brightness', 0.1))
    default_pixel_order = config.get('pixel_order', 'GRB')

    parser.add_argument('--leds', type=int, default=default_leds,
                        help=f'Number of LEDs (default: {default_leds})')
    parser.add_argument('--brightness', type=float, default=default_brightness,
                        help=f'Brightness 0.0-1.0 (default: {default_brightness})')
    parser.add_argument('--pixel-order', default=default_pixel_order,
                        choices=['RGB', 'GRB', 'RGBW', 'GRBW'],
                        help=f'Pixel order (default: {default_pixel_order})')
    parser.add_argument('--continuous', '--continuous-show', action='store_true',
                        help='Cycle the whole strip through colours')
    parser.add_argument('--cycles', type=int, default=None,
                        help='Number of colours for --continuous (default: until Ctrl+C)')
    args = parser.parse_args()

    try:
        if args.continuous:
            run_continuous_test(args.leds, args.brightness, args.pixel_order, args.cycles)
        else:
            success = run_manual_test(args.leds, args.brightness, args.pixel_order)
            sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print()
        print("Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
