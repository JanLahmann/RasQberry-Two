#!/bin/bash
# RasQberry LED Text Display - Interactive launcher
# Prompts user for text, mode, and color, then displays on LED matrix

set -euo pipefail

# Load common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load and verify environment
load_rqb2_env
verify_env_vars REPO USER_HOME STD_VENV BIN_DIR

# ============================================================================
# Main function
# ============================================================================

main() {
    info "RasQberry LED Text Display"

    # Prompt for text
    TEXT=$(whiptail --inputbox "Enter text to display on LEDs:\n(Max ~4 chars for centered text)" 10 60 \
           "RASQBERRY" --title "LED Text Display" 3>&1 1>&2 2>&3) || {
        info "User cancelled"
        exit 0
    }

    # Validate text is not empty
    if [ -z "$TEXT" ]; then
        die "Text cannot be empty"
    fi

    # Prompt for display mode
    MODE=$(whiptail --menu "Display mode:" 15 60 3 \
           "scroll" "Scrolling text" \
           "static" "Static centered text" \
           "flash" "Flashing text" \
           --title "LED Text Display" 3>&1 1>&2 2>&3) || {
        info "User cancelled"
        exit 0
    }

    # Prompt for color
    COLOR=$(whiptail --menu "Choose color:" 18 60 8 \
            "white" "White" \
            "red" "Red" \
            "green" "Green" \
            "blue" "Blue" \
            "yellow" "Yellow" \
            "cyan" "Cyan" \
            "magenta" "Magenta" \
            "orange" "Orange" \
            --title "LED Text Display" 3>&1 1>&2 2>&3) || {
        info "User cancelled"
        exit 0
    }

    # Show summary and confirm
    if ! whiptail --yesno "Ready to display:\n\nText: $TEXT\nMode: $MODE\nColor: $COLOR\n\nContinue?" 12 60 --title "Confirm"; then
        info "User cancelled"
        exit 0
    fi

    # Activate virtual environment
    activate_venv

    # Create temporary Python script to display text
    TEMP_SCRIPT=$(mktemp)
    trap "rm -f '$TEMP_SCRIPT'" EXIT

    cat > "$TEMP_SCRIPT" << 'PYTHON_EOF'
#!/usr/bin/env python3
import sys
from rq_led_utils import create_neopixel_strip, display_scrolling_text, display_static_text, display_flashing_text, get_led_config

# Parse arguments
text = sys.argv[1]
mode = sys.argv[2]
color_name = sys.argv[3]

# Color mapping
colors = {
    'white': (255, 255, 255),
    'red': (255, 0, 0),
    'green': (0, 255, 0),
    'blue': (0, 0, 255),
    'yellow': (255, 255, 0),
    'cyan': (0, 255, 255),
    'magenta': (255, 0, 255),
    'orange': (255, 128, 0),
}
color = colors.get(color_name, (255, 255, 255))

# Get configuration
config = get_led_config()

# Create NeoPixel strip
pixels = create_neopixel_strip(
    config['led_count'],
    config['pixel_order'],
    brightness=config['led_default_brightness']
)

# Display based on mode
try:
    if mode == 'scroll':
        display_scrolling_text(pixels, text, duration_seconds=30, scroll_speed=0.05, color=color)
    elif mode == 'static':
        display_static_text(pixels, text, duration_seconds=5, color=color)
    elif mode == 'flash':
        display_flashing_text(pixels, text, flash_count=5, flash_speed=0.3, color=color)
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
except KeyboardInterrupt:
    print("\nInterrupted by user")
finally:
    # Turn off LEDs
    pixels.fill((0, 0, 0))
    pixels.show()
PYTHON_EOF

    # Execute display
    info "Displaying text on LED matrix..."
    python3 "$TEMP_SCRIPT" "$TEXT" "$MODE" "$COLOR" || die "Failed to display text"

    info "Display complete!"
}

# Run main function
main