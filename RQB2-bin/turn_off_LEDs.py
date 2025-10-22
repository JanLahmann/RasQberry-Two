#!/usr/bin/env python3
#
# Turn off all LEDs on the NeoPixel strip
# Uses SPI driver for Pi4/Pi5 compatibility

import board
import neopixel_spi as neopixel
from rq_led_utils import get_led_config, create_neopixel_strip


def turn_off_LEDs():
    """
    A simple function that iterates through every LED and turns it off.

    Args:
        None

    Returns:
        None
    """
    # Load configuration from environment
    config = get_led_config()
    NUM_PIXELS = config['led_count']
    pixel_order_str = config['pixel_order']
    pixel_order = getattr(neopixel, pixel_order_str)

    try:
        spi = board.SPI()

        # Create NeoPixel strip with hardware-specific parameters
        pixels = create_neopixel_strip(
            spi,
            NUM_PIXELS,
            pixel_order,
            brightness=0.1,
            pi_model=config['pi_model']
        )

        # Turn off all pixels
        for index in range(NUM_PIXELS):
            # Setting pixel to 0 value will turn it off
            pixels[index] = 0x000000

        pixels.show()
        print(f"Turned off {NUM_PIXELS} LEDs ({config['pi_model']}, {pixel_order_str} pixel order)")

    except Exception as e:
        print("Error turning off LEDs: ", e)


def main():
    print("Turning off all LEDs...")
    turn_off_LEDs()
    print("Done!")


if __name__ == "__main__":
    main()
