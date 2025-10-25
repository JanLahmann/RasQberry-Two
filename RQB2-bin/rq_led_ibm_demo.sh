#!/bin/bash
set -euo pipefail

################################################################################
# rq_led_ibm_demo.sh - RasQberry LED IBM Demo Launcher
#
# Description:
#   Simple wrapper to run the IBM-themed LED demonstration
#   Displays IBM logo and animations on LED strip
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load environment and verify required variables
load_rqb2_env
verify_env_vars USER_HOME REPO BIN_DIR STD_VENV

# Check multiple possible locations for the script
LED_SCRIPT=""
for location in "$BIN_DIR/neopixel_spi_IBMtestFunc.py" \
                "/usr/bin/neopixel_spi_IBMtestFunc.py" \
                "$USER_HOME/$REPO/RQB2-bin/neopixel_spi_IBMtestFunc.py"; do
    if [ -f "$location" ]; then
        LED_SCRIPT="$location"
        break
    fi
done

[ -n "$LED_SCRIPT" ] || die "LED demo script not found. Searched:\n  - $BIN_DIR/neopixel_spi_IBMtestFunc.py\n  - /usr/bin/neopixel_spi_IBMtestFunc.py\n  - $USER_HOME/$REPO/RQB2-bin/neopixel_spi_IBMtestFunc.py"

info "Starting LED IBM Demo..."
debug "Script location: $LED_SCRIPT"
echo

# Activate virtual environment if available
activate_venv || warn "Virtual environment not available, continuing anyway..."

# Run the script
python3 "$LED_SCRIPT"

# Script handles its own exit prompt now
echo
read -p "Press Enter to close this window..."
