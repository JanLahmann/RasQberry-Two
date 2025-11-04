#!/bin/bash -e

echo "=== Installing Touchscreen Support (Virtual Keyboard) ==="

# Install matchbox-keyboard (lightweight virtual keyboard for touchscreens)
echo "=> Installing matchbox-keyboard"
apt-get install -y matchbox-keyboard

# Note: Florence was removed from Debian Bookworm repositories
# matchbox-keyboard is the recommended virtual keyboard for Raspberry Pi OS

# Install desktop icon for virtual keyboard
echo "=> Installing virtual keyboard desktop icon"
STAGE_DIR="$(dirname "$0")"
DESKTOP_DIR="/home/${FIRST_USER_NAME}/Desktop"

if [ -f "${STAGE_DIR}/files/desktop-bookmarks/virtual-keyboard.desktop" ]; then
    mkdir -p "${DESKTOP_DIR}"
    cp "${STAGE_DIR}/files/desktop-bookmarks/virtual-keyboard.desktop" "${DESKTOP_DIR}/"
    chmod +x "${DESKTOP_DIR}/virtual-keyboard.desktop"
    chown -R ${FIRST_USER_NAME}:${FIRST_USER_NAME} "${DESKTOP_DIR}"
    echo "Desktop icon installed: ${DESKTOP_DIR}/virtual-keyboard.desktop"
fi

echo ""
echo "Virtual keyboard installed:"
echo "  - matchbox-keyboard (lightweight, touchscreen-optimized)"
echo ""
echo "To use:"
echo "  - Click the 'Virtual Keyboard' icon on desktop"
echo "  - Or run 'matchbox-keyboard' from terminal"
echo "  - Desktop icon also available in Accessories menu"