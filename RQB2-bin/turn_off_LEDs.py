#!/usr/bin/env python3
#
# Turn off all LEDs on the NeoPixel strip
# Uses singleton NeoPixel from rq_led_utils for Pi5 compatibility

from rq_led_utils import clear_all_leds


def turn_off_LEDs():
    """
    Turn off all LEDs using the shared singleton NeoPixel object.

    This prevents GPIO conflicts on Pi 5 by reusing the same NeoPixel
    instance across all modules.
    """
    clear_all_leds()


def main():
    print("Turning off all LEDs...")
    turn_off_LEDs()
    print("Done!")


if __name__ == "__main__":
    main()
