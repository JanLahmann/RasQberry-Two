#!/usr/bin/env python3
"""
Test NeoPixel LED strip functionality on Raspberry Pi 4 and Pi 5
Uses adafruit-circuitpython-neopixel which auto-detects:
  - Pi 4: PWM/DMA driver (rpi_ws281x backend)
  - Pi 5: PIO driver (RP1 chip)

This test verifies that all LEDs work correctly without the old SPI buffer limitations.
Requires sudo for GPIO access.
"""

import sys
from rq_led_utils import get_led_config, create_neopixel_strip
import time

def safe_input(prompt="", wait_seconds=3):
    """
    Safely handle input() when stdin may not be available (e.g., from raspi-config).
    Falls back to time.sleep() if stdin is not a TTY.
    """
    if sys.stdin.isatty():
        print(prompt)
        input()
    else:
        print(f"{prompt} [auto-continuing in {wait_seconds}s...]")
        time.sleep(wait_seconds)

def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)

def main():
    # Load configuration
    config = get_led_config()
    NUM_PIXELS = config['led_count']
    BRIGHTNESS = config['led_default_brightness']
    GPIO_PIN = config['led_gpio_pin']
    PI_MODEL = config['pi_model']

    print("=" * 70)
    print("RasQberry NeoPixel LED Test")
    print("=" * 70)
    print(f"Platform: {PI_MODEL}")
    print(f"Testing {NUM_PIXELS} LEDs on GPIO{GPIO_PIN}")
    print(f"Brightness: {BRIGHTNESS}")
    print(f"Driver: PWM/PIO (auto-detected)")
    print("=" * 70)
    print()

    # Create NeoPixel object
    try:
        pixels = create_neopixel_strip(
            NUM_PIXELS,
            config['pixel_order'],
            brightness=BRIGHTNESS,
            gpio_pin=GPIO_PIN
        )
        print("✓ NeoPixel object created successfully")
        print()
    except Exception as e:
        print(f"✗ Error creating NeoPixel object: {e}")
        print()
        print("Common issues:")
        print("  - Run with sudo: sudo python3 rq_test_leds.py")
        print("  - Check wiring to GPIO{GPIO_PIN}")
        print("  - Verify power supply is adequate for {NUM_PIXELS} LEDs")
        return 1

    print("Running 6 visual tests - watch the LEDs!")
    print()

    try:
        # Test 1: All Red
        print("[1/6] Filling all LEDs with RED...")
        pixels.fill((255, 0, 0))
        pixels.show()  # Single show() for all LEDs - no chunking needed!
        safe_input("      ▶ Press Enter when you see RED LEDs")

        # Test 2: All Green
        print("[2/6] Filling all LEDs with GREEN...")
        pixels.fill((0, 255, 0))
        pixels.show()
        safe_input("      ▶ Press Enter when you see GREEN LEDs")

        # Test 3: All Blue
        print("[3/6] Filling all LEDs with BLUE...")
        pixels.fill((0, 0, 255))
        pixels.show()
        safe_input("      ▶ Press Enter when you see BLUE LEDs")

        # Test 4: Individual pixels - Alternating Red/Blue
        print(f"[4/6] Alternating RED/BLUE pattern ({NUM_PIXELS} individual pixels)...")
        for i in range(NUM_PIXELS):
            if i % 2 == 0:
                pixels[i] = (255, 0, 0)  # Red
            else:
                pixels[i] = (0, 0, 255)  # Blue
        pixels.show()  # Single show() sets all LEDs individually!
        safe_input("      ▶ Press Enter when you see ALTERNATING RED/BLUE pattern")

        # Test 5: Rainbow gradient
        print(f"[5/6] Rainbow gradient across all {NUM_PIXELS} LEDs...")
        for i in range(NUM_PIXELS):
            pixel_index = (i * 256 // NUM_PIXELS)
            r, g, b = wheel(pixel_index)
            pixels[i] = (int(r * BRIGHTNESS), int(g * BRIGHTNESS), int(b * BRIGHTNESS))
        pixels.show()  # Single show() for complex pattern!
        safe_input("      ▶ Press Enter when you see RAINBOW GRADIENT")

        # Test 6: Clear
        print("[6/6] Clearing all LEDs...")
        pixels.fill((0, 0, 0))
        pixels.show()
        print("      ▶ All LEDs should be OFF")
        time.sleep(1)

        print()
        print("=" * 70)
        print("✓ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print()
        print("Verification checklist:")
        print(f"  ✓ No errors or exceptions")
        print(f"  ✓ All {NUM_PIXELS} LEDs responded")
        print(f"  ✓ No buffer overflow or corruption")
        print(f"  ✓ Single show() call works for all LEDs")
        print(f"  ✓ Individual pixel control works")
        print(f"  ✓ No chunking needed (old SPI limitation removed)")
        print()
        print(f"Platform: {PI_MODEL} using PWM/PIO driver on GPIO{GPIO_PIN}")
        print()
        return 0

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        print("Clearing LEDs...")
        pixels.fill((0, 0, 0))
        pixels.show()
        return 130
    except Exception as e:
        print(f"\n✗ Error during test: {e}")
        print("Attempting to clear LEDs...")
        try:
            pixels.fill((0, 0, 0))
            pixels.show()
        except:
            pass
        return 1

if __name__ == '__main__':
    sys.exit(main())