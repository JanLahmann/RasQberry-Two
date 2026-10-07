#!/usr/bin/env python3
"""
Turn off all LEDs on the LED panel.

Uses the singleton NeoPixel from rq_led_utils (Pi 5 compatibility). Exits
with status 1 when the panel could not be cleared - for example while another
program holds it ("GPIO busy") - so callers no longer report "cleared" after
a failure (R-148).

    turn_off_LEDs.py             clear through the configured outputs
    turn_off_LEDs.py --physical  only the LED panel, without the on-screen or
                                 browser view (used at shutdown)
    turn_off_LEDs.py --close-window
                                 also close the on-screen view an LED demo
                                 opened (the end of a demo, R-100)
"""

import os
import sys

# Clearing updates an open on-screen LED view but does not open one
os.environ.setdefault('RQ_LED_NO_WINDOW', '1')

from rq_led_utils import (clear_all_leds, get_led_config,  # noqa: E402
                          guard_pi5_led_writes, _wait_for_last_frame,
                          reap_virtual_led_gui)


def turn_off_LEDs():
    """
    Turn off all LEDs using the shared singleton NeoPixel object.

    Returns:
        bool: True if the LEDs were cleared.
    """
    return clear_all_leds() is not False


def turn_off_physical():
    """
    Clear only the physical LED panel: no on-screen view, no browser view, no
    renderer. For the shutdown unit (rasqberry-led-clear.service), where no
    desktop is left to show a window.

    Returns:
        bool: True if the panel was cleared.
    """
    try:
        import board
        import neopixel
        guard_pi5_led_writes()
        config = get_led_config()
        pixels = neopixel.NeoPixel(
            getattr(board, f"D{config['led_gpio_pin']}"),
            config['led_count'],
            brightness=0.1,
            auto_write=False,
            pixel_order=getattr(neopixel, config['pixel_order']),
        )
        pixels.fill((0, 0, 0))
        pixels.show()
        _wait_for_last_frame()   # Pi 5: let the frame out before exiting
        # No deinit(): on a Pi 4 it can block in the PWM driver (see
        # kill_child_bounded in rq_led_setup_wizard.sh); exiting frees it.
        return True
    except Exception as e:  # GPIO busy, no panel library, ...
        print(f"Error clearing LEDs: {e}")
        return False


def main():
    """Clear the LEDs; exit status 1 if that failed."""
    if "--physical" in sys.argv[1:]:
        ok = turn_off_physical()
    else:
        print("Turning off all LEDs...")
        ok = turn_off_LEDs()
    if "--close-window" in sys.argv[1:]:
        # The on-screen view starts detached, as root for an LED demo, and
        # stayed open after the demo; the desktop user could not stop it
        # (R-100). Only a view RasQberry started itself is closed.
        reap_virtual_led_gui()
    if ok:
        print("Done!")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
