#!/usr/bin/env python3
"""
Test LED strip with direct SPI buffer control
Bypasses neopixel_spi library chunking to test full 256 LEDs

Usage:
    sudo PYTHONPATH=/usr/bin ~/RasQberry-Two/venv/RQB2/bin/python3 test_led_buffer_direct.py
"""

import board
import neopixel_spi as neopixel
import time
from rq_led_utils import get_led_config

def test_all_leds_white(num_pixels=256):
    """Test all LEDs at once with white color"""
    print(f"\nTesting {num_pixels} LEDs - ALL WHITE")
    print("=" * 60)

    config = get_led_config()
    pixel_order_str = config['pixel_order']
    pixel_order = getattr(neopixel, pixel_order_str)
    pi_model = config['pi_model']

    spi = board.SPI()

    # Create strip with explicit parameters
    params = {'auto_write': False}
    if pi_model == 'Pi4':
        params['bit0'] = 0b10000000

    # Try with different bpp values
    for bpp_value in [3, 4]:
        print(f"\nTrying bpp={bpp_value}...")
        try:
            pixels = neopixel.NeoPixel_SPI(
                spi,
                num_pixels,
                brightness=0.1,
                pixel_order=pixel_order,
                bpp=bpp_value,
                **params
            )

            # Set all to white
            pixels.fill((255, 255, 255))
            pixels.show()
            time.sleep(0.001)

            print(f"✓ bpp={bpp_value} succeeded")
            print(f"  Check LEDs - how many are lit?")
            time.sleep(8)

            # Turn off
            pixels.fill((0, 0, 0))
            pixels.show()
            time.sleep(0.001)
            time.sleep(2)

        except Exception as e:
            print(f"✗ bpp={bpp_value} failed: {e}")
            continue

def test_chunked_writes(num_pixels=256):
    """Test manual chunking to see if that helps"""
    print(f"\nTesting MANUAL CHUNKED writes")
    print("=" * 60)

    config = get_led_config()
    pixel_order_str = config['pixel_order']
    pixel_order = getattr(neopixel, pixel_order_str)
    pi_model = config['pi_model']

    spi = board.SPI()

    params = {'auto_write': False}
    if pi_model == 'Pi4':
        params['bit0'] = 0b10000000

    pixels = neopixel.NeoPixel_SPI(
        spi,
        num_pixels,
        brightness=0.1,
        pixel_order=pixel_order,
        **params
    )

    # Write in chunks of 128 LEDs
    chunk_size = 128
    for chunk_start in range(0, num_pixels, chunk_size):
        chunk_end = min(chunk_start + chunk_size, num_pixels)
        print(f"Writing LEDs {chunk_start} to {chunk_end-1}...")

        for i in range(chunk_start, chunk_end):
            pixels[i] = (0, 255, 0)  # Green

        pixels.show()
        time.sleep(0.01)  # 10ms delay between chunks

    print(f"✓ All {num_pixels} LEDs should be GREEN")
    print(f"  Check how many are lit...")
    time.sleep(10)

    # Turn off
    pixels.fill((0, 0, 0))
    pixels.show()
    time.sleep(0.001)


def main():
    print("\n" + "="*60)
    print("DIRECT SPI BUFFER TEST")
    print("="*60)

    try:
        # Test 1: Different bpp values
        test_all_leds_white(256)

        # Test 2: Manual chunking
        test_chunked_writes(256)

        print("\n" + "="*60)
        print("TESTS COMPLETE")
        print("="*60)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()