#!/bin/bash -e
#
# Install touchscreen support files (runs on HOST, not in chroot)
# Files are copied to ROOTFS_DIR for the chroot script to use
#

STAGE_DIR="$(dirname "$0")"

echo "=== Installing Touchscreen Support Files ==="

# Install toggle script
echo "=> Installing keyboard toggle script"
if [ -f "${STAGE_DIR}/files/toggle-keyboard.sh" ]; then
    install -v -m 755 "${STAGE_DIR}/files/toggle-keyboard.sh" \
      "${ROOTFS_DIR}/usr/local/bin/toggle-keyboard.sh"
    echo "Toggle script installed: /usr/local/bin/toggle-keyboard.sh"
fi

# Install virtual keyboard desktop file to system applications
echo "=> Installing virtual keyboard desktop file"
if [ -f "${STAGE_DIR}/files/desktop-bookmarks/virtual-keyboard.desktop" ]; then
    install -v -m 644 "${STAGE_DIR}/files/desktop-bookmarks/virtual-keyboard.desktop" \
      "${ROOTFS_DIR}/usr/share/applications/virtual-keyboard.desktop"
    echo "Desktop file installed: /usr/share/applications/virtual-keyboard.desktop"
fi

echo "=> Touchscreen support files installed"
