#!/usr/bin/env python3
"""
RasQberry LED Test Utility
Comprehensive LED strip testing with manual and automated scan modes
"""

import time
import sys
import argparse

# Add /usr/bin to path to import rq_led_utils
sys.path.insert(0, '/usr/bin')

import board
import neopixel_spi as neopixel
from rq_led_utils import get_led_config, create_neopixel_strip, chunked_show, chunked_fill


def print_header():
    """Print test header"""
    print()
    print("=" * 60)
    print("  RasQberry LED Strip Test Utility")
    print("=" * 60)
    print()


def block_test(pixels, num_leds, chunk_size, delay_ms, brightness, block_size=10, cycles=3):
    """
    Test LED strip by lighting blocks sequentially

    Args:
        pixels: NeoPixel strip object
        num_leds: Number of LEDs to test
        chunk_size: LEDs per chunk for updates
        delay_ms: Delay between chunks in milliseconds
        brightness: Brightness level (0.0-1.0)
        block_size: Number of LEDs per block
        cycles: Number of test cycles

    Returns:
        True if test completed, False if interrupted
    """
    print(f"Block Test: {block_size} LEDs at a time, {cycles} cycles")
    print(f"  Parameters: chunk_size={chunk_size}, delay={delay_ms}ms, brightness={int(brightness*100)}%")
    print()

    test_color = (int(255 * brightness), 0, int(128 * brightness))  # Purple

    try:
        for cycle in range(cycles):
            print(f"  Cycle {cycle + 1}/{cycles}...", end=" ", flush=True)

            # Light blocks sequentially
            for start in range(0, num_leds, block_size):
                end = min(start + block_size, num_leds)

                # Turn on block
                for i in range(start, end):
                    pixels[i] = test_color
                chunked_show(pixels, chunk_size=chunk_size, delay_ms=delay_ms)

                time.sleep(0.3)  # Hold lit for 300ms for visibility

                # Turn off block
                for i in range(start, end):
                    pixels[i] = (0, 0, 0)
                chunked_show(pixels, chunk_size=chunk_size, delay_ms=delay_ms)

                time.sleep(0.1)  # Brief pause before next block

            print("✓")

        print()
        return True

    except KeyboardInterrupt:
        print(" [Interrupted]")
        return False


def full_strip_test(pixels, num_leds, chunk_size, delay_ms, brightness, cycles=5):
    """
    Test full LED strip by lighting all LEDs

    Args:
        pixels: NeoPixel strip object
        num_leds: Number of LEDs to test
        chunk_size: LEDs per chunk for updates
        delay_ms: Delay between chunks in milliseconds
        brightness: Brightness level (0.0-1.0)
        cycles: Number of test cycles

    Returns:
        True if test completed, False if interrupted
    """
    print(f"Full Strip Test: All {num_leds} LEDs, {cycles} cycles")
    print(f"  Parameters: chunk_size={chunk_size}, delay={delay_ms}ms, brightness={int(brightness*100)}%")
    print()

    colors = [
        (int(255 * brightness), 0, 0),  # Red
        (0, int(255 * brightness), 0),  # Green
        (0, 0, int(255 * brightness)),  # Blue
    ]

    try:
        for cycle in range(cycles):
            color = colors[cycle % len(colors)]
            color_name = ["Red", "Green", "Blue"][cycle % len(colors)]
            print(f"  Cycle {cycle + 1}/{cycles} ({color_name})...", end=" ", flush=True)

            # Light all LEDs
            chunked_fill(pixels, color, chunk_size=chunk_size, delay_ms=delay_ms)
            time.sleep(0.5)

            # Clear all LEDs
            chunked_fill(pixels, (0, 0, 0), chunk_size=chunk_size, delay_ms=delay_ms)
            time.sleep(0.2)

            print("✓")

        print()
        return True

    except KeyboardInterrupt:
        print(" [Interrupted]")
        return False


def run_manual_test(num_leds, chunk_size, delay_ms, brightness, pixel_order):
    """Run manual test with specified parameters"""
    print_header()
    print(f"Configuration:")
    print(f"  LEDs: {num_leds}")
    print(f"  Chunk size: {chunk_size}")
    print(f"  Delay: {delay_ms}ms")
    print(f"  Brightness: {int(brightness * 100)}%")
    print(f"  Pixel order: {pixel_order}")
    print()
    print("Press Ctrl+C to skip a test or stop")
    print()

    # Load hardware config
    config = get_led_config()
    pixel_order_const = getattr(neopixel, pixel_order)

    # Create LED strip
    spi = board.SPI()
    pixels = create_neopixel_strip(
        spi,
        num_leds,
        pixel_order_const,
        brightness=brightness,
        pi_model=config['pi_model']
    )

    try:
        # Run tests
        if not block_test(pixels, num_leds, chunk_size, delay_ms, brightness):
            return False

        if not full_strip_test(pixels, num_leds, chunk_size, delay_ms, brightness):
            return False

        print("✓ All tests completed successfully!")
        print()
        return True

    finally:
        # Clear LEDs on exit
        chunked_fill(pixels, (0, 0, 0), chunk_size=chunk_size, delay_ms=delay_ms)


def run_automated_scan(num_leds, pixel_order, brightness=0.1):
    """
    Run automated parameter scan to find optimal settings

    Tests parameter space from conservative to aggressive:
    - Chunk sizes: 4, 8, 16, 32
    - Delays: 16ms, 8ms, 4ms, 2ms, 1ms

    Args:
        num_leds: Number of LEDs to test
        pixel_order: Pixel color order (RGB, GRB, etc.)
        brightness: Brightness level 0.0-1.0 (default: 0.1)
    """
    print_header()
    print("Automated Parameter Scan")
    print(f"Testing {num_leds} LEDs with various chunk size and delay combinations")
    print(f"Brightness: {int(brightness * 100)}%")
    print()
    print("This will test from conservative (safe) to aggressive (fast) settings")
    print("Press Ctrl+C to stop the scan")
    print()

    # Load hardware config
    config = get_led_config()
    pixel_order_const = getattr(neopixel, pixel_order)

    # Create LED strip
    spi = board.SPI()
    pixels = create_neopixel_strip(
        spi,
        num_leds,
        pixel_order_const,
        brightness=brightness,
        pi_model=config['pi_model']
    )

    # Parameter space to scan
    chunk_sizes = [4, 8, 16, 32]
    delays = [16, 8, 4, 2, 1]

    results = []
    test_num = 0
    total_tests = len(chunk_sizes) * len(delays)

    print(f"{'Test':<6} {'Chunk':<7} {'Delay':<8} {'Result'}")
    print("-" * 40)

    try:
        for chunk_size in chunk_sizes:
            for delay_ms in delays:
                test_num += 1

                # Quick test: light all LEDs once
                try:
                    test_color = (int(255 * brightness), 0, int(128 * brightness))
                    chunked_fill(pixels, test_color, chunk_size=chunk_size, delay_ms=delay_ms)
                    time.sleep(0.3)
                    chunked_fill(pixels, (0, 0, 0), chunk_size=chunk_size, delay_ms=delay_ms)
                    time.sleep(0.1)

                    result = "✓ PASS"
                    success = True

                except Exception as e:
                    result = f"✗ FAIL: {str(e)[:20]}"
                    success = False

                results.append({
                    'chunk_size': chunk_size,
                    'delay_ms': delay_ms,
                    'success': success
                })

                print(f"{test_num:<6} {chunk_size:<7} {delay_ms}ms{' ':<4} {result}")

        # Summary
        print()
        print("=" * 60)
        print("Scan Complete - Summary")
        print("=" * 60)
        print()

        passed = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]

        print(f"Passed: {len(passed)}/{len(results)} configurations")
        print()

        if passed:
            # Find optimal (fastest) settings
            optimal = max(passed, key=lambda r: (r['chunk_size'], -r['delay_ms']))
            print("Recommended optimal settings:")
            print(f"  LED_CHUNK_SIZE={optimal['chunk_size']}")
            print(f"  LED_CHUNK_DELAY_MS={optimal['delay_ms']}")
            print()

        if failed:
            print(f"Failed configurations ({len(failed)}):")
            for r in failed:
                print(f"  - chunk_size={r['chunk_size']}, delay={r['delay_ms']}ms")
            print()

        print("Note: These results may vary based on:")
        print("  - LED strip quality and length")
        print("  - Power supply stability")
        print("  - Cable quality and length")
        print("  - System load")
        print()

    except KeyboardInterrupt:
        print()
        print("[Scan interrupted by user]")
        print()

    finally:
        # Clear LEDs
        chunked_fill(pixels, (0, 0, 0), chunk_size=8, delay_ms=8)


def main():
    parser = argparse.ArgumentParser(
        description='RasQberry LED Strip Test Utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with defaults (192 LEDs, chunk_size=8, delay=8ms)
  %(prog)s

  # Test with custom parameters
  %(prog)s --leds 256 --chunk-size 16 --delay 4

  # Automated parameter scan
  %(prog)s --scan

  # Test with lower brightness
  %(prog)s --brightness 0.01
"""
    )

    # Load defaults from environment
    config = get_led_config()
    default_leds = config.get('led_count', 192)
    default_chunk = int(config.get('led_chunk_size', 8))
    default_delay = int(config.get('led_chunk_delay_ms', 8))
    default_brightness = float(config.get('led_default_brightness', 0.1))  # 10% default
    default_pixel_order = config.get('pixel_order', 'GRB')

    parser.add_argument('--leds', type=int, default=default_leds,
                        help=f'Number of LEDs (default: {default_leds})')
    parser.add_argument('--chunk-size', type=int, default=default_chunk,
                        help=f'Chunk size (default: {default_chunk})')
    parser.add_argument('--delay', type=int, default=default_delay,
                        help=f'Delay in ms (default: {default_delay})')
    parser.add_argument('--brightness', type=float, default=default_brightness,
                        help=f'Brightness 0.0-1.0 (default: {default_brightness})')
    parser.add_argument('--pixel-order', default=default_pixel_order,
                        choices=['RGB', 'GRB', 'RGBW', 'GRBW'],
                        help=f'Pixel order (default: {default_pixel_order})')
    parser.add_argument('--scan', action='store_true',
                        help='Run automated parameter scan')

    args = parser.parse_args()

    try:
        if args.scan:
            run_automated_scan(args.leds, args.pixel_order, args.brightness)
        else:
            success = run_manual_test(
                args.leds,
                args.chunk_size,
                args.delay,
                args.brightness,
                args.pixel_order
            )
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