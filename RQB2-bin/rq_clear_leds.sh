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

info "Clearing all LEDs..."

# Use the common library function
clear_leds

info "All LEDs cleared"
