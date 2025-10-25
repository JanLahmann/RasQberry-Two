#!/bin/bash -e

echo "=> Enabling RasQberry A/B Boot Support Services"

# Files have already been copied by 00-run.sh
# This script only enables the systemd services

# Enable health check (runs once on boot)
echo "=> Enabling rasqberry-health-check.service"
systemctl enable rasqberry-health-check.service

# Enable update poller timer (runs every 30 seconds)
echo "=> Enabling rasqberry-update-poller.timer"
systemctl enable rasqberry-update-poller.timer

echo "=> RasQberry A/B Boot Support enabled"
echo ""
echo "NOTE: A/B boot requires manual partition setup:"
echo "  1. Boot the Pi"
echo "  2. Run: sudo /home/rasqberry/RasQberry-Two/tools/setup-ab-boot.sh"
echo ""
echo "After partition setup, the system will:"
echo "  - Run health checks on every boot"
echo "  - Poll GitHub every 30 seconds for new dev* releases"
echo "  - Automatically download and install updates to Slot B"
echo "  - Reboot into new images and validate them"
echo "  - Rollback automatically to Slot A if validation fails"
echo ""
echo "Slot A: STABLE (protected, manual updates only)"
echo "Slot B: TESTING (auto-updated from dev* releases)"