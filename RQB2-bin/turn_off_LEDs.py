#!/usr/bin/env python3
#
# Turn off all LEDs on the NeoPixel strip
# Uses PWM/PIO driver for Pi4/Pi5 compatibility

from rq_led_utils import get_led_config, create_neopixel_strip, chunked_clear


def turn_off_LEDs():
    """
    A simple function that turns off all LEDs.

    Args:
        None

    Returns:
        None
    """
    # Load configuration from environment
    config = get_led_config()
    NUM_PIXELS = config['led_count']
    pixel_order_str = config['pixel_order']

    try:
        # Create NeoPixel strip (auto-detects Pi4 PWM or Pi5 PIO)
        pixels = create_neopixel_strip(
            NUM_PIXELS,
            pixel_order_str,
            brightness=config['led_default_brightness']
        )

        # Turn off all pixels
        chunked_clear(pixels)
        print(f"Turned off {NUM_PIXELS} LEDs ({config['pi_model']}, {pixel_order_str} pixel order, GPIO{config['led_gpio_pin']})")

    except Exception as e:
        print("Error turning off LEDs: ", e)


def main():
    print("Turning off all LEDs...")
    turn_off_LEDs()
    print("Done!")


if __name__ == "__main__":
    main()
