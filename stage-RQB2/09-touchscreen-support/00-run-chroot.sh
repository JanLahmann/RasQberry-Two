#!/bin/bash -e
#
# Install touchscreen support (runs in CHROOT)
# Files are already installed by 00-run.sh
#

echo "=== Installing Touchscreen Support (Virtual Keyboard) ==="

# Install wvkbd - Wayland-native on-screen keyboard
# wvkbd provides a docked keyboard that works natively with Wayland/labwc
apt-get install -y wvkbd

# Disable squeekboard autostart (default RPi OS keyboard) - we use wvkbd instead
# Move the autostart file to prevent squeekboard from starting
echo "=> Disabling squeekboard autostart (using wvkbd instead)"
if [ -f /etc/xdg/autostart/squeekboard.desktop ]; then
    mv /etc/xdg/autostart/squeekboard.desktop /etc/xdg/autostart/squeekboard.desktop.disabled
    echo "Squeekboard autostart disabled (file renamed)"
fi

# Copy desktop icon to user desktop
echo "=> Installing virtual keyboard desktop icon"
DESKTOP_DIR="/home/${FIRST_USER_NAME}/Desktop"

if [ -f "/usr/share/applications/virtual-keyboard.desktop" ]; then
    mkdir -p "${DESKTOP_DIR}"
    cp "/usr/share/applications/virtual-keyboard.desktop" "${DESKTOP_DIR}/"
    chmod +x "${DESKTOP_DIR}/virtual-keyboard.desktop"
    chown -R ${FIRST_USER_NAME}:${FIRST_USER_NAME} "${DESKTOP_DIR}"
    echo "Desktop icon installed: ${DESKTOP_DIR}/virtual-keyboard.desktop"
fi

# Add keyboard toggle icon to panel (wf-panel-pi for Wayland)
echo "=> Adding keyboard toggle to panel"
add_keyboard_to_panel() {
    local panel_config="$1"
    if [ -f "$panel_config" ]; then
        # Find next available launcher number
        local max_num=$(grep -oP 'launcher_\K[0-9]+' "$panel_config" 2>/dev/null | sort -n | tail -1)
        if [ -z "$max_num" ]; then
            max_num=0
        fi
        local next_num=$(printf "%06d" $((10#$max_num + 1)))

        # Add keyboard launcher if not already present
        if ! grep -q "virtual-keyboard.desktop" "$panel_config" 2>/dev/null; then
            echo "launcher_${next_num}=virtual-keyboard.desktop" >> "$panel_config"
            echo "Added keyboard toggle to panel: $panel_config"
        fi
    fi
}

# Add to skel for new users
SKEL_PANEL_CONFIG="/etc/skel/.config/wf-panel-pi.ini"
if [ -f "$SKEL_PANEL_CONFIG" ]; then
    add_keyboard_to_panel "$SKEL_PANEL_CONFIG"
fi

# Add to first user's panel config
if [ -n "${FIRST_USER_NAME}" ]; then
    USER_PANEL_CONFIG="/home/${FIRST_USER_NAME}/.config/wf-panel-pi.ini"
    if [ -f "$USER_PANEL_CONFIG" ]; then
        add_keyboard_to_panel "$USER_PANEL_CONFIG"
        chown "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$USER_PANEL_CONFIG"
    fi
fi

echo ""
echo "Virtual keyboard toggle installed:"
echo "  - Uses wvkbd (Wayland-native keyboard)"
echo "  - Keyboard icon added to panel"
echo ""
echo "To use:"
echo "  - Click keyboard icon in panel to show/hide"
echo "  - Or run 'toggle-keyboard.sh' from terminal"
