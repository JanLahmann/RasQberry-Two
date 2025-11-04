#!/bin/bash -e

echo "=== Installing Touchscreen Support (Virtual Keyboard) ==="

# Install matchbox-keyboard (lightweight virtual keyboard for touchscreens)
echo "=> Installing matchbox-keyboard"
apt-get install -y matchbox-keyboard

# Install Florence as alternative (more feature-rich)
echo "=> Installing Florence virtual keyboard"
apt-get install -y florence at-spi2-core

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
echo "Virtual keyboards installed:"
echo "  - matchbox-keyboard (lightweight, default)"
echo "  - florence (feature-rich alternative)"
echo ""
echo "To use:"
echo "  - Click the 'Virtual Keyboard' icon on desktop"
echo "  - Or run 'matchbox-keyboard' from terminal"
echo "  - Or run 'florence' for more features"
echo "  - Desktop icons also available in Accessories menu"