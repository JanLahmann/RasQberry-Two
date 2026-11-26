# LED Text & Logo Display

The model's LED panel (24×8 LEDs) shows qubits, text, logos and color effects.

<img src="/demo-screenshots/led-panel-ibm-logo.webp" width="1000" height="424" alt="The LED panel in the dark, showing the IBM logo in rainbow colors" className="media-image" />

No panel? LED demos open the same view on screen:

<img src="/demo-screenshots/virtual-led-panel.webp" width="575" height="262" loading="lazy" alt="The on-screen LED panel showing the IBM logo in green, red and blue" className="media-image" style={{maxWidth: "575px"}} />

## What you can do

- **Show text:** scrolling, static or flashing, in eight colors.
- **Show logos:** IBM, RasQberry, or your own image.
- **Run effects:** rainbow, color gradients, a logo slideshow.
- **See qubits:** RasQ-LED, Quantum Lights Out and Quantum Raspberry Tie measure
  circuits and light the panel ([all LED demos](/03-quantum-computing-demos/01-demo-list/#2-led-panel)).
- **Write your own:** a small Python API (below).

All in `sudo raspi-config` → **0 RasQberry** → **Quantum Demos** → **LED panel**.
The **LED panel** folder on the desktop has the LED demos.

## Wiring

Three jumper wires from the Pi to the panel's input plug: **5V** to pin 2, **GND** to
pin 6, **data** to pin 12 (GPIO 18), on the Pi 4 and the Pi 5. The panel then runs on
the Pi's power supply: keep the brightness at 0.4 or lower (the default). There is no
ready-made 24×8 panel: cut a flexible 32×8 panel to 24 columns (192 LEDs), or chain four
4×12 panels ([bill of materials](/01-3d-model/01-bill-of-materials/#2-bill-of-materials)).
Photos, chaining and power: [wiring the LED arrays](/01-3d-model/02-hardware-assembly-guide/#3-wiring-up-the-led-arrays).

## Set up your panel first

The **LED Setup Wizard** finds out how your panel is wired and which way up it
hangs: it shows the IBM logo in up to four colors, and you pick the one that reads
upright. It knows a 32×8 panel cut to 24×8 and four 4×12 panels; other layouts get a
step-by-step walkthrough. **LED panel** → **LED setup & tests** → **LED Setup Wizard**
(or `sudo rq_led_setup_wizard.sh`); the setup checklist offers a short version.
The result, `LED_LAYOUT`, survives [A/B updates](/02-software/03-ab-boot/).

## Text and logos

**LED panel** → **Text & logos**: **Display Custom Text**, **Display Logo from
Library**, and the text, color and logo demos. From a terminal:
`sudo rq_led_display_text.sh` or `sudo rq_led_display_logo.sh`.

Your own logo: in **Display Logo from Library** (or `sudo rq_led_display_logo.sh`),
choose **Browse for custom image...**, then a PNG or JPG. 24×8 pixels fits
exactly; other sizes are resized. Simple, high-contrast shapes work best. The
built-in logos are in `/usr/config/LED-Logos`.

## Configuration

Settings are in `/usr/config/rasqberry_environment.env`; change them with
**0 RasQberry** → **Advanced** → **Edit a RasQberry Two setting**:

- `LED_LAYOUT`: set by the wizard (`single-24x8` by default; also `quad-4x12`,
  `quad-2x2-12x4`, `triple-8x8`, `single-8x32`). The LED count and matrix size
  follow from it.
- `LED_DEFAULT_BRIGHTNESS`: 0.0–1.0, default 0.4. Easier: **LED setup & tests** →
  **LED brightness**.
- `LED_PIXEL_ORDER`: color order of your LEDs (default GRB).
- `LED_GPIO_PIN`: data pin (default 18).

## Troubleshooting

- **Upside down or scrambled:** run the LED Setup Wizard. Static text shows about
  four characters.
- **Settings come back after a restart:** `LED_` lines in `rasqberry_boot.env` on
  the boot drive (bootfs, or BOOT-A on the A/B image) win at every start: put a `#`
  in front or change them there.
- **Wrong colors:** check `LED_PIXEL_ORDER` (RGB or GRB).
- **LEDs stay dark:** one program drives the panel at a time. Stop a running demo
  (**Quantum Demos** → **Stop a running LED demo**) or restart, then test with
  `rq_demo_run.sh led-demos led-test`. Check the [wiring](#2-wiring) and power: on a Pi 5, LEDs that
  stop after a while mean a weak power supply: RasQberry notices and offers a lower
  brightness. Better: the official 27 W supply.
- **Switch the LEDs off:** **Clear All LEDs** in the **LED panel** folder, or
  `sudo rq_clear_leds.sh` (`--stop` also stops a program holding the panel).

## For developers

Four functions are the supported LED API; programs using them keep working with
later releases. Everything else in `rq_led_utils` is internal and may change.

```python
from rq_led_utils import get_pixels, matrix_size, set_xy, clear_all_leds

pixels = get_pixels(brightness=0.2)  # the LED strip (one shared object)
width, height = matrix_size()        # (24, 8) on the RasQberry panels
set_xy(pixels, 0, 0, (255, 0, 0))    # top-left LED red
set_xy(pixels, width - 1, height - 1, (0, 0, 255))  # bottom-right blue
pixels.show()                        # nothing changes before show()
clear_all_leds()
```

- x runs from 0 (left) to width-1, y from 0 (top) to height-1. `set_xy` follows
  `LED_LAYOUT`, so one program works on both kits; positions off the panel are
  ignored. Avoid `pixels[number]`: raw numbers follow the wiring, not rows.
- Run it with `rq_python my_program.py`. On a Pi 5, Thonny and `python3` in the
  RasQberry environment work too; a Pi 4 needs `rq_python` (the LED driver needs
  root there). Never `sudo python3`.
- Examples: `~/My-Quantum-Programs/03_led_hello.py` and `04_bell_on_leds.py`. The
  menu's demos are `/usr/bin/demo_led_*.py`, e.g. `rq_python /usr/bin/demo_led_ibm_logo.py`.
