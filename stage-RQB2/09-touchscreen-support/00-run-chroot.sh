#!/bin/bash -e

echo "=== Installing Touchscreen Support (Virtual Keyboard) ==="

# Install matchbox-keyboard (lightweight virtual keyboard for touchscreens)
echo "=> Installing matchbox-keyboard"
apt-get install -y matchbox-keyboard

# Note: Florence was removed from Debian Bookworm repositories
# matchbox-keyboard is the recommended virtual keyboard for Raspberry Pi OS

# Install toggle script
echo "=> Installing keyboard toggle script"
STAGE_DIR="$(dirname "$0")"
if [ -f "${STAGE_DIR}/files/toggle-keyboard.sh" ]; then
    cp "${STAGE_DIR}/files/toggle-keyboard.sh" /usr/local/bin/
    chmod +x /usr/local/bin/toggle-keyboard.sh
    echo "Toggle script installed: /usr/local/bin/toggle-keyboard.sh"
fi

# Install desktop icon for virtual keyboard
echo "=> Installing virtual keyboard desktop icon"
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
echo "  - Click 'Toggle Keyboard' icon on desktop to show/hide"
echo "  - Or run 'toggle-keyboard.sh' from terminal"