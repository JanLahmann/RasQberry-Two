# Imports for LED array
import board
import neopixel_spi as neopixel


def turn_off_LEDs():
    """
    A simple function that iterates through every LED and turns it off.

    Args:
        None

    Returns:
        None
    """
    NUM_PIXELS = 192
    PIXEL_ORDER = neopixel.RGB

    try:
        spi = board.SPI()

        pixels = neopixel.NeoPixel_SPI(
            spi, NUM_PIXELS, pixel_order=PIXEL_ORDER, auto_write=False
        )

        for index in range(NUM_PIXELS):
            # Setting pixel to 0 value will turn it off
            pixels[index] = 0x000000

        pixels.show()

    except Exception as e:
        print("Error turning off LEDs: ", e)


def main():
    print("Turning off all LEDs...")
    turn_off_LEDs()
    print("Done!")


if __name__ == "__main__":
    main()
