#!/bin/bash
set -euo pipefail

################################################################################
# rq_clear_leds.sh - RasQberry Clear All LEDs
#
# Description:
#   Turns off all NeoPixel LEDs
#   Simple utility script for LED management
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load environment
load_rqb2_env
verify_env_vars USER_HOME REPO STD_VENV BIN_DIR

info "Clearing all LEDs..."

# Activate virtual environment (required for neopixel_spi and LED utilities)
activate_venv || die "Virtual environment not available"

# Find LED script
LED_SCRIPT=$(find_led_script "turn_off_LEDs.py") || die "LED control script not found"

# Run LED clearing script
# Note: SPI access doesn't require root - user is in 'spi' group via raspi-config
python3 "$LED_SCRIPT"

info "All LEDs cleared"
