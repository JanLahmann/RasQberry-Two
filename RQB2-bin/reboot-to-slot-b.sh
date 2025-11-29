#!/bin/bash
# ============================================================================
# RasQberry A/B Boot - Reboot to Slot B
# ============================================================================
# Purpose: Switch from Slot A to Slot B and reboot
#
# This script:
# 1. Enables tryboot mode (tells firmware to try Slot B)
# 2. Reboots the system
# 3. Health check runs in Slot B (60-second window)
# 4. If successful: Slot B becomes default
#    If failed/timeout: Rolls back to Slot A automatically
#
# Usage: sudo reboot-to-slot-b
# ============================================================================

set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root (use sudo)"
    exit 1
fi

BOOT_DIR="/boot/firmware"

# Check if A/B boot is configured
if [ ! -f "${BOOT_DIR}/tryboot.txt" ]; then
    echo "Error: A/B boot not configured"
    echo "Please run setup-ab-boot.sh first"
    exit 1
fi

# Check current slot
CURRENT_SLOT="A"
if [ -f "${BOOT_DIR}/current-slot" ]; then
    CURRENT_SLOT=$(cat "${BOOT_DIR}/current-slot")
fi

echo "=== RasQberry A/B Boot - Switch to Slot B ==="
echo
echo "Current slot: $CURRENT_SLOT"

if [ "$CURRENT_SLOT" = "B" ]; then
    echo "Already running in Slot B"
    echo "Use 'sudo reboot' to return to Slot A (if tryboot failed)"
    exit 0
fi

# Enable tryboot for next boot
echo
echo "Enabling tryboot mode..."
echo "1" > /proc/sys/kernel/reboot_mode

echo
echo "System will now:"
echo "  1. Reboot into Slot B"
echo "  2. Health check runs (60 seconds)"
echo "  3. If healthy: Slot B becomes default"
echo "     If unhealthy/timeout: Rolls back to Slot A"
echo
echo "After booting Slot B, check /boot/firmware/current-slot to verify"
echo

# Give user a chance to cancel
sleep 2

echo "Rebooting to Slot B..."
reboot