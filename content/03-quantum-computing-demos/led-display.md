# LED Text & Logo Display

Display custom text, logos, and visual effects on the RasQberry LED panel.

## Overview

The LED Display feature allows you to:
- Display custom text with various colours and effects
- Show pre-built logos (IBM, RasQberry, custom)
- Run animated text and color effect demos
- Create your own logo images

## Set up your panel first

RasQberry needs to know how your LED panel is wired and which way up it is
mounted. The **LED Setup Wizard** finds out without any measuring: it shows an
IBM logo in up to four colours, and you pick the colour in which the logo reads
upright. It handles the single 24×8 panel and the quad 4×12 panel, either way up;
other arrangements get a step-by-step walkthrough.

Run it from `sudo raspi-config` → **0 RasQberry** → **Quantum Demos** →
**LED panel** → **LED setup & tests** → **LED Setup Wizard**
(or `sudo rq_led_setup_wizard.sh`). The first-login checklist offers a short
version of the same check.

The result is stored as `LED_LAYOUT`. On an [A/B image](/02-software/03-ab-boot/)
it is kept when you update the other slot.

## Accessing via raspi-config

Run `sudo raspi-config` and navigate to:
**0 RasQberry → Quantum Demos → LED panel → Text & logos**

### Available Options

| Option | Description |
|--------|-------------|
| **Display Custom Text** | Enter text, choose mode (scroll/static/flash), and colour |
| **Display Logo from Library** | Select from pre-built logos with fade effects |
| **Text Demos** | Scrolling welcome, status messages, alert flash |
| **Colour Effect Demos** | Rainbow scroll, rainbow cycle, colour gradient |
| **Logo Demos** | IBM logo, RasQberry logo, slideshow |

## Command Line Usage

### Display Custom Text

```bash
# Interactive text display
sudo rq_led_display_text.sh
```

The script prompts for:
- Text to display
- Mode: scroll, static, or flash
- Colour: white, red, green, blue, yellow, cyan, magenta, orange

### Display Logos

```bash
# Interactive logo selection
sudo rq_led_display_logo.sh
```

Features:
- Browse pre-built logos from library
- Load custom PNG/JPG images
- Configurable duration and fade effects

## Custom Logos

The logos ship in `/usr/config/LED-Logos` (`ibm-logo-24x8.png`,
`rasqberry-icon-24x8.png`, `rasqberry-cube-24x8.png`, and 16×8 variants).
To show your own image, choose **Browse for custom image...** in
`rq_led_display_logo.sh` (or **Display Logo from Library** in the menu) and
enter the path to a PNG or JPG.

- **Size**: 24×8 pixels (width × height) fits the panel exactly; other sizes are
  resized automatically.
- Use high-contrast images with simple shapes; fine details disappear at this
  resolution.

## Configuration

LED settings live in `/usr/config/rasqberry_environment.env`. Change them with
`sudo raspi-config` → **0 RasQberry** → **Advanced** → **Edit a RasQberry Two setting**:

- `LED_LAYOUT` - panel layout, set by the LED Setup Wizard (default: `single-24x8`;
  also `quad-4x12`, `quad-2x2-12x4`, `triple-8x8`, `single-8x32`). The LED count
  and matrix size follow from the layout.
- `LED_DEFAULT_BRIGHTNESS` - default brightness 0.0-1.0 (default: 0.4); easier:
  **LEDs** → **LED brightness**
- `LED_PIXEL_ORDER` - colour order of your LEDs (default: GRB)
- `LED_GPIO_PIN` - data pin (default: 18)

`LED_MATRIX_LAYOUT`, `LED_MATRIX_WIDTH`, `LED_MATRIX_HEIGHT` and
`LED_MATRIX_Y_FLIP` are deprecated and only read on old images.

## Troubleshooting

### Text or logo upside down or scrambled

- Run the LED Setup Wizard (see above) to set `LED_LAYOUT` for your panel.
- Try shorter text for static mode (max ~4 characters visible)

### Colours appear wrong

- Check `LED_PIXEL_ORDER` setting (RGB vs GRB)
- Some LEDs use a different colour order

### LEDs not turning on

1. Make sure no other demo is still running. The panel is driven by one process
   at a time, so a demo left running holds it and the next one finds it busy.
   Stop the running demo (**Quantum Demos** → **Stop a running LED demo**), or reboot.
2. Run the LED test: `rq_demo_run.sh led-demos led-test`
3. Check wiring and power supply. On a Pi 5, LEDs that stop after a while mean the
   power supply is too weak: RasQberry says so and offers a lower brightness. Use
   the official 27 W supply, or lower **LED panel** → **LED setup & tests** → **LED brightness**.

### Turn off LEDs

```bash
sudo rq_clear_leds.sh          # --stop also stops a program that holds the panel
```

Or use the desktop icon **Clear All LEDs**, or **Quantum Demos** → **LED panel** → **Clear All LEDs**.

## For developers

### Python API

Four functions are the supported LED API; programs that use them keep working
with later releases. Everything else in `rq_led_utils` is internal and may change.

```python
from rq_led_utils import get_pixels, matrix_size, set_xy, clear_all_leds

pixels = get_pixels(brightness=0.2)  # the LED strip (one shared object)
width, height = matrix_size()        # (24, 8) on the RasQberry panels
set_xy(pixels, 0, 0, (255, 0, 0))    # top-left LED red
set_xy(pixels, width - 1, height - 1, (0, 0, 255))  # bottom-right blue
pixels.show()                        # nothing changes before show()
clear_all_leds()
```

- **Coordinates**: x runs from 0 (left) to width-1, y from 0 (top) to height-1.
  `set_xy` maps them to the configured `LED_LAYOUT` (`single-24x8` or
  `quad-4x12`, either way up), so the same program works on both kits.
  Positions off the panel are ignored. Avoid `pixels[number]`: raw numbers
  follow the wiring, not rows.
- **Run it** with `rq_python my_program.py`. On a Pi 5, `python3` in the
  RasQberry environment and Thonny work too; a Pi 4 needs `rq_python` (the LED
  driver needs root). Never `sudo python3`.
- Examples: `~/My-Quantum-Programs/03_led_hello.py` and `04_bell_on_leds.py`.

### Demo scripts

These are what the menu entries run:

| Script | Description |
|--------|-------------|
| `demo_led_text_scroll_welcome.py` | Scrolling "Welcome to RasQberry" |
| `demo_led_text_status.py` | Status message display |
| `demo_led_text_alert.py` | Flashing alert text |
| `demo_led_text_rainbow_scroll.py` | Rainbow-colored scrolling text |
| `demo_led_text_rainbow_static.py` | Static text with color cycling |
| `demo_led_text_gradient.py` | Text with gradient colors |
| `demo_led_ibm_logo.py` | Display IBM logo |
| `demo_led_rasqberry_logo.py` | Display RasQberry logo |
| `demo_led_logo_slideshow.py` | Cycle through all logos |

Example:
```bash
rq_python /usr/bin/demo_led_ibm_logo.py
```
