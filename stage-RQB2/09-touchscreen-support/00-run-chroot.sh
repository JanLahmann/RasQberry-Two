#!/bin/bash -e
#
# Install touchscreen support (runs in CHROOT)
# Files are already installed by 01-deploy-files
#
# trixie: Raspberry Pi OS's own on-screen keyboard (squeekboard) stays as it
# is. It pops up by itself in text fields, the Wi-Fi password popup included,
# and the panel's keyboard icon (the squeek widget) shows or hides it;
# raspi-config -> Display Options -> On-screen Keyboard switches it. wvkbd is
# not installed: it only toggled from its panel launcher, and tapping that
# closed the Wi-Fi password popup (user feedback, 2026-10).
# bookworm: wvkbd with a toggle launcher in the panel, in place of squeekboard.

# trixie (wf-panel-pi 1.x) has this file, bookworm (wf-panel-pi 0.x) not
SYS_PANEL_CONFIG="/etc/xdg/wf-panel-pi/wf-panel-pi.ini"
if [ -f "$SYS_PANEL_CONFIG" ]; then
    echo "=== Touchscreen support: Raspberry Pi OS's on-screen keyboard (squeekboard) ==="
    if [ -f /etc/xdg/autostart/squeekboard.desktop ]; then
        echo "squeekboard autostart: $(sed -n 's/^Exec=//p' /etc/xdg/autostart/squeekboard.desktop | head -1)"
    else
        echo "Note: no /etc/xdg/autostart/squeekboard.desktop (raspi-config -> Display Options -> On-screen Keyboard)"
    fi
    exit 0
fi

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

# Add keyboard toggle icon to panel (wf-panel-pi for Wayland)
# Note: No desktop icon needed since it's in the panel
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

# bookworm (wf-panel-pi 0.x): ~/.config/wf-panel-pi.ini with launcher_NNNNNN lines
# Add to skel for new users (create if missing)
SKEL_PANEL_DIR="/etc/skel/.config"
SKEL_PANEL_CONFIG="${SKEL_PANEL_DIR}/wf-panel-pi.ini"
mkdir -p "$SKEL_PANEL_DIR"
if [ ! -f "$SKEL_PANEL_CONFIG" ]; then
    # Create default panel config with keyboard launcher
    cat > "$SKEL_PANEL_CONFIG" << 'EOT'
[panel]
launcher_000001=lxde-x-www-browser.desktop
launcher_000002=pcmanfm.desktop
launcher_000003=lxterminal.desktop
launcher_000004=virtual-keyboard.desktop
EOT
    echo "Created panel config with keyboard: $SKEL_PANEL_CONFIG"
else
    add_keyboard_to_panel "$SKEL_PANEL_CONFIG"
fi

# Add to first user's panel config (create if missing)
if [ -n "${FIRST_USER_NAME}" ]; then
    USER_PANEL_DIR="/home/${FIRST_USER_NAME}/.config"
    USER_PANEL_CONFIG="${USER_PANEL_DIR}/wf-panel-pi.ini"
    mkdir -p "$USER_PANEL_DIR"
    if [ ! -f "$USER_PANEL_CONFIG" ]; then
        cp "$SKEL_PANEL_CONFIG" "$USER_PANEL_CONFIG"
        echo "Created user panel config: $USER_PANEL_CONFIG"
    else
        add_keyboard_to_panel "$USER_PANEL_CONFIG"
    fi
    chown -R "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$USER_PANEL_DIR"
fi

echo ""
echo "Virtual keyboard toggle installed:"
echo "  - Uses wvkbd (Wayland-native keyboard)"
echo "  - Keyboard icon added to panel"
echo ""
echo "To use:"
echo "  - Click keyboard icon in panel to show/hide"
echo "  - Or run 'toggle-keyboard.sh' from terminal"
