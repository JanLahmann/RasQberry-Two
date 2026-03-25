# LED Text & Logo Display

Display custom text, logos, and visual effects on the RasQberry LED matrix.

## Overview

The LED Display feature allows you to:
- Display custom text with various colors and effects
- Show pre-built logos (IBM, RasQberry, custom)
- Run animated text and color effect demos
- Create your own logo images

## Accessing via raspi-config

Navigate to: **Main Menu → Quantum Demos → Test LEDs → Text & Logo Display**

### Available Options

| Option | Description |
|--------|-------------|
| **Display Custom Text** | Enter text, choose mode (scroll/static/flash), and color |
| **Display Logo from Library** | Select from pre-built logos with fade effects |
| **Text Demos** | Scrolling welcome, status messages, alert flash |
| **Color Effect Demos** | Rainbow scroll, rainbow cycle, color gradient |
| **Logo Demos** | IBM logo, RasQberry logo, slideshow |

## Command Line Usage

### Display Custom Text

```bash
# Interactive text display
rq_led_display_text.sh
```

The script prompts for:
- Text to display
- Mode: scroll, static, or flash
- Color: white, red, green, blue, yellow, cyan, magenta, orange

### Display Logos

```bash
# Interactive logo selection
rq_led_display_logo.sh
```

Features:
- Browse pre-built logos from library
- Load custom PNG/JPG images
- Configurable duration and fade effects

## Python API

### Display Text

```python
from rq_led_utils import (
    create_neopixel_strip,
    display_scrolling_text,
    display_static_text,
    display_flashing_text,
    get_led_config
)

# Get configuration
config = get_led_config()

# Create LED strip
pixels = create_neopixel_strip(
    config['led_count'],
    config['pixel_order'],
    brightness=config['led_default_brightness']
)

# Display modes
display_scrolling_text(pixels, "HELLO", duration_seconds=10, color=(255, 0, 0))
display_static_text(pixels, "IBM", duration_seconds=5, color=(0, 255, 255))
display_flashing_text(pixels, "ALERT", flash_count=5, color=(255, 255, 0))

# Clean up
pixels.fill((0, 0, 0))
pixels.show()
```

### Display Logos

```python
from rq_led_logo import display_logo

# Display logo with effects
display_logo(
    "path/to/logo.png",
    duration=10,           # seconds
    brightness=0.5,        # 0.0 to 1.0
    fade_in=True,          # smooth fade in
    fade_out=True          # smooth fade out
)
```

## Demo Scripts

Run these directly from the command line:

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
# Activate virtual environment first
source ~/RasQberry-Two/venv/RQB2/bin/activate

# Run a demo
python3 /usr/bin/demo_led_ibm_logo.py
```

## Creating Custom Logos

### Logo Requirements

- **Format**: PNG or JPG
- **Size**: 24×8 pixels (width × height)
- **Colors**: RGB, will be mapped to LED matrix

### Generate Logo Library

```bash
cd ~/RasQberry-Two/RQB2-config/LED-Logos
python3 create_logos.py
```

This creates pre-built logos:
- `ibm-24x8.png` - IBM logo
- `rasqberry-24x8.png` - RasQberry logo
- Additional themed logos

### Custom Logo from Any Image

The display script automatically resizes images to fit the 8×24 matrix. For best results:
1. Use high-contrast images
2. Simple designs work best on low-resolution matrix
3. Avoid fine details that won't be visible

## Configuration

LED display uses your configured matrix settings from `/usr/config/rasqberry_environment.env`:

- `LED_COUNT` - Number of LEDs (default: 192)
- `LED_MATRIX_WIDTH` - Width in pixels (default: 24)
- `LED_MATRIX_HEIGHT` - Height in pixels (default: 8)
- `LED_DEFAULT_BRIGHTNESS` - Default brightness 0.0-1.0
- `LED_MATRIX_LAYOUT` - single or quad panel layout

See [Boot Configuration](/02-software/installation-overview) for details on modifying LED settings.

## Troubleshooting

### Text not displaying correctly

- Check LED matrix orientation (`LED_MATRIX_Y_FLIP`)
- Verify matrix layout matches your hardware (`LED_MATRIX_LAYOUT`)
- Try shorter text for static mode (max ~4 characters visible)

### Colors appear wrong

- Check `LED_PIXEL_ORDER` setting (RGB vs GRB)
- Some LED strips use different color orderings

### LEDs not turning on

1. Check virtual environment is activated
2. Verify SPI is enabled: `ls /dev/spidev*`
3. Run LED test: `python3 /usr/bin/rq_test_leds.py`
4. Check wiring and power supply

### Turn off LEDs

```bash
# From command line
source ~/RasQberry-Two/venv/RQB2/bin/activate
python3 /usr/bin/turn_off_LEDs.py

# Or via raspi-config menu
# Quantum Demos → Test LEDs → Clear LEDs
```
