#!/bin/bash
#
# RasQberry Touch Mode Toggle
# Enables/disables comprehensive touch-friendly settings for touch screen displays
#
# Usage:
#   rq_touch_mode.sh enable   - Enable touch mode
#   rq_touch_mode.sh disable  - Disable touch mode
#   rq_touch_mode.sh toggle   - Toggle touch mode
#   rq_touch_mode.sh status   - Show current status
#

set -euo pipefail

# Configuration paths
STATE_FILE="/var/lib/rasqberry/touch-mode.conf"
GTK_CSS_SRC="/usr/config/touch-mode/gtk-touch.css"
ONBOARD_AUTOSTART_SRC="/usr/config/touch-mode/onboard-autostart.desktop"

# User-specific paths (resolved at runtime)
get_user_home() {
    if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        getent passwd "$SUDO_USER" | cut -d: -f6
    else
        echo "$HOME"
    fi
}

USER_HOME=$(get_user_home)
GTK_CSS_DST="$USER_HOME/.config/gtk-3.0/gtk.css"
ONBOARD_AUTOSTART_DST="$USER_HOME/.config/autostart/onboard.desktop"
CHROMIUM_FLAGS_DIR="$USER_HOME/.config/chromium-flags.conf.d"

# LXDE panel config paths - user takes precedence over system
USER_PANEL_CONFIG="$USER_HOME/.config/lxpanel/LXDE-pi/panels/panel"
SYSTEM_PANEL_CONFIG="/etc/xdg/lxpanel/LXDE-pi/panels/panel"

# Find active panel config (user config takes precedence)
get_panel_config() {
    if [ -f "$USER_PANEL_CONFIG" ]; then
        echo "$USER_PANEL_CONFIG"
    elif [ -f "$SYSTEM_PANEL_CONFIG" ]; then
        echo "$SYSTEM_PANEL_CONFIG"
    else
        echo ""
    fi
}

PANEL_CONFIG=$(get_panel_config)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}INFO:${NC} $1"; }
warn() { echo -e "${YELLOW}WARN:${NC} $1"; }
error() { echo -e "${RED}ERROR:${NC} $1"; }

# Get current touch mode state
get_state() {
    if [ -f "$STATE_FILE" ]; then
        grep -E "^TOUCH_MODE=" "$STATE_FILE" 2>/dev/null | cut -d= -f2
    else
        echo "disabled"
    fi
}

# Enable touch mode
enable_touch_mode() {
    info "Enabling touch mode..."

    # Ensure state directory exists
    sudo mkdir -p "$(dirname "$STATE_FILE")"

    # 1. Enable on-screen keyboard autostart
    if [ -f "$ONBOARD_AUTOSTART_SRC" ]; then
        mkdir -p "$(dirname "$ONBOARD_AUTOSTART_DST")"
        cp "$ONBOARD_AUTOSTART_SRC" "$ONBOARD_AUTOSTART_DST"
        info "On-screen keyboard autostart enabled"
    else
        warn "Onboard autostart file not found at $ONBOARD_AUTOSTART_SRC"
    fi

    # 2. Apply GTK touch CSS
    if [ -f "$GTK_CSS_SRC" ]; then
        mkdir -p "$(dirname "$GTK_CSS_DST")"
        cp "$GTK_CSS_SRC" "$GTK_CSS_DST"
        info "GTK touch CSS applied"
    else
        warn "GTK touch CSS not found at $GTK_CSS_SRC"
    fi

    # 3. Update LXDE panel (height=48, iconsize=32)
    # Re-check panel config in case it was created during this session
    PANEL_CONFIG=$(get_panel_config)
    if [ -n "$PANEL_CONFIG" ]; then
        # If using system config, copy to user config first for modifications
        if [ "$PANEL_CONFIG" = "$SYSTEM_PANEL_CONFIG" ]; then
            mkdir -p "$(dirname "$USER_PANEL_CONFIG")"
            cp "$SYSTEM_PANEL_CONFIG" "$USER_PANEL_CONFIG"
            PANEL_CONFIG="$USER_PANEL_CONFIG"
            info "Copied system panel config to user config"
        fi
        # Backup original if not already backed up
        if [ ! -f "${PANEL_CONFIG}.touch-backup" ]; then
            cp "$PANEL_CONFIG" "${PANEL_CONFIG}.touch-backup"
        fi
        sed -i 's/height=.*/height=48/' "$PANEL_CONFIG"
        sed -i 's/iconsize=.*/iconsize=32/' "$PANEL_CONFIG"
        info "LXDE panel updated (height=48, iconsize=32)"
    else
        info "LXDE panel config not found (will apply on next desktop login)"
    fi

    # 4. Set Chromium touch flags
    mkdir -p "$CHROMIUM_FLAGS_DIR"
    echo "--touch-events=enabled" > "$CHROMIUM_FLAGS_DIR/touch.conf"
    info "Chromium touch flags set"

    # 5. Adjust double-click timing (if xfconf available)
    if command -v xfconf-query >/dev/null 2>&1; then
        xfconf-query -c xsettings -p /Net/DoubleClickTime -s 500 2>/dev/null || true
        info "Double-click time set to 500ms"
    fi

    # 6. Update state file
    sudo tee "$STATE_FILE" > /dev/null << EOF
TOUCH_MODE=enabled
ENABLED_AT=$(date -Iseconds)
ENABLED_BY=${SUDO_USER:-$USER}
EOF

    # Fix ownership of user config files
    if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        chown -R "$SUDO_USER:$SUDO_USER" "$USER_HOME/.config/gtk-3.0" 2>/dev/null || true
        chown -R "$SUDO_USER:$SUDO_USER" "$USER_HOME/.config/autostart" 2>/dev/null || true
        chown -R "$SUDO_USER:$SUDO_USER" "$CHROMIUM_FLAGS_DIR" 2>/dev/null || true
    fi

    echo ""
    info "Touch mode ENABLED"
    echo ""
    echo "Settings applied:"
    echo "  - On-screen keyboard: autostart enabled"
    echo "  - GTK buttons/scrollbars: enlarged (48px min)"
    echo "  - LXDE panel: height=48px, icons=32px"
    echo "  - Chromium: touch events enabled"
    echo "  - Double-click time: 500ms"
    echo ""
    warn "Restart desktop session (logout/login) for all changes to take effect"
}

# Disable touch mode
disable_touch_mode() {
    info "Disabling touch mode..."

    # 1. Remove on-screen keyboard autostart
    if [ -f "$ONBOARD_AUTOSTART_DST" ]; then
        rm -f "$ONBOARD_AUTOSTART_DST"
        info "On-screen keyboard autostart removed"
    fi

    # 2. Remove GTK touch CSS
    if [ -f "$GTK_CSS_DST" ]; then
        rm -f "$GTK_CSS_DST"
        info "GTK touch CSS removed"
    fi

    # 3. Restore LXDE panel defaults (height=36, iconsize=24)
    # Re-check panel config (use user config if available)
    PANEL_CONFIG=$(get_panel_config)
    if [ -n "$PANEL_CONFIG" ]; then
        if [ -f "${USER_PANEL_CONFIG}.touch-backup" ]; then
            # Restore from user backup
            cp "${USER_PANEL_CONFIG}.touch-backup" "$USER_PANEL_CONFIG"
            info "LXDE panel restored from backup"
        elif [ -f "$USER_PANEL_CONFIG" ]; then
            # Just update the values in user config
            sed -i 's/height=.*/height=36/' "$USER_PANEL_CONFIG"
            sed -i 's/iconsize=.*/iconsize=24/' "$USER_PANEL_CONFIG"
            info "LXDE panel restored (height=36, iconsize=24)"
        fi
    fi

    # 4. Remove Chromium touch flags
    rm -f "$CHROMIUM_FLAGS_DIR/touch.conf"
    info "Chromium touch flags removed"

    # 5. Restore double-click timing
    if command -v xfconf-query >/dev/null 2>&1; then
        xfconf-query -c xsettings -p /Net/DoubleClickTime -s 400 2>/dev/null || true
        info "Double-click time restored to 400ms"
    fi

    # 6. Update state file
    sudo tee "$STATE_FILE" > /dev/null << EOF
TOUCH_MODE=disabled
DISABLED_AT=$(date -Iseconds)
DISABLED_BY=${SUDO_USER:-$USER}
EOF

    echo ""
    info "Touch mode DISABLED"
    echo ""
    echo "Settings restored to defaults:"
    echo "  - On-screen keyboard: autostart disabled"
    echo "  - GTK buttons/scrollbars: system default"
    echo "  - LXDE panel: height=36px, icons=24px"
    echo "  - Chromium: touch events default"
    echo "  - Double-click time: 400ms"
    echo ""
    warn "Restart desktop session (logout/login) for all changes to take effect"
}

# Toggle touch mode
toggle_touch_mode() {
    current=$(get_state)
    if [ "$current" = "enabled" ]; then
        disable_touch_mode
    else
        enable_touch_mode
    fi
}

# Show status
show_status() {
    current=$(get_state)
    quiet_mode="${1:-}"

    if [ "$quiet_mode" = "--quiet" ] || [ "$quiet_mode" = "-q" ]; then
        echo "$current"
        return
    fi

    echo "=== RasQberry Touch Mode Status ==="
    echo ""
    if [ "$current" = "enabled" ]; then
        echo -e "Touch Mode: ${GREEN}ENABLED${NC}"
    else
        echo -e "Touch Mode: ${YELLOW}DISABLED${NC}"
    fi
    echo ""

    # Show individual settings
    echo "Current Settings:"

    # On-screen keyboard
    if [ -f "$ONBOARD_AUTOSTART_DST" ]; then
        echo -e "  On-screen keyboard: ${GREEN}autostart enabled${NC}"
    else
        echo -e "  On-screen keyboard: ${YELLOW}autostart disabled${NC}"
    fi

    # GTK CSS
    if [ -f "$GTK_CSS_DST" ]; then
        echo -e "  GTK touch CSS: ${GREEN}applied${NC}"
    else
        echo -e "  GTK touch CSS: ${YELLOW}not applied${NC}"
    fi

    # LXDE panel
    local status_panel_config
    status_panel_config=$(get_panel_config)
    if [ -n "$status_panel_config" ]; then
        height=$(grep "height=" "$status_panel_config" 2>/dev/null | head -1 | cut -d= -f2)
        iconsize=$(grep "iconsize=" "$status_panel_config" 2>/dev/null | head -1 | cut -d= -f2)
        echo "  LXDE panel: height=${height:-?}, iconsize=${iconsize:-?}"
    else
        echo "  LXDE panel: config not created yet"
    fi

    # Chromium flags
    if [ -f "$CHROMIUM_FLAGS_DIR/touch.conf" ]; then
        echo -e "  Chromium touch: ${GREEN}enabled${NC}"
    else
        echo -e "  Chromium touch: ${YELLOW}default${NC}"
    fi

    echo ""

    # State file info
    if [ -f "$STATE_FILE" ]; then
        echo "State file: $STATE_FILE"
        cat "$STATE_FILE" | sed 's/^/  /'
    fi
}

# Show usage
show_usage() {
    echo "RasQberry Touch Mode Toggle"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  enable   Enable touch-friendly mode"
    echo "  disable  Disable touch mode (restore defaults)"
    echo "  toggle   Toggle touch mode on/off"
    echo "  status   Show current status"
    echo "  status --quiet  Show just 'enabled' or 'disabled'"
    echo ""
    echo "Touch mode adjusts the following settings:"
    echo "  - On-screen keyboard (onboard) autostart"
    echo "  - GTK3 button and scrollbar sizes"
    echo "  - LXDE panel height and icon size"
    echo "  - Chromium touch event handling"
    echo "  - Double-click timing"
}

# Main
case "${1:-}" in
    enable|on)
        enable_touch_mode
        ;;
    disable|off)
        disable_touch_mode
        ;;
    toggle)
        toggle_touch_mode
        ;;
    status)
        show_status "${2:-}"
        ;;
    -h|--help|help)
        show_usage
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
