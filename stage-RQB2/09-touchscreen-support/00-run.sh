#!/bin/bash -e
#
# Install touchscreen support files (runs on HOST, not in chroot)
# Files are copied to ROOTFS_DIR for the chroot script to use
#

STAGE_DIR="$(dirname "$0")"

echo "=== Installing Touchscreen Support Files ==="

# toggle-keyboard.sh and virtual-keyboard.desktop are installed from
# RQB2-system/ by 01-deploy-files (#294).

echo "=> Touchscreen support files installed"
