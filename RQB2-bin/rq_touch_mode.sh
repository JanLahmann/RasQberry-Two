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
ENV_FILE="/etc/rasqberry/rasqberry_environment.env"

# Source environment file for configurable touch mode settings
if [ -f "$ENV_FILE" ]; then
    # shellcheck source=/dev/null
    source "$ENV_FILE"
fi

# Touch mode settings (from env file or defaults)
TOUCH_PANEL_HEIGHT="${TOUCH_PANEL_HEIGHT:-64}"
TOUCH_PANEL_ICON_SIZE="${TOUCH_PANEL_ICON_SIZE:-48}"
TOUCH_DESKTOP_ICON_SIZE="${TOUCH_DESKTOP_ICON_SIZE:-72}"
TOUCH_DESKTOP_GRID_SPACING="${TOUCH_DESKTOP_GRID_SPACING:-140}"
TOUCH_TERMINAL_FONT_SIZE="${TOUCH_TERMINAL_FONT_SIZE:-16}"
TOUCH_DOUBLE_CLICK_MS="${TOUCH_DOUBLE_CLICK_MS:-500}"

# Default (non-touch) settings - fixed values
DEFAULT_PANEL_HEIGHT=36
DEFAULT_PANEL_ICON_SIZE=24
DEFAULT_TERMINAL_FONT_SIZE=10
DEFAULT_DOUBLE_CLICK_MS=400
DEFAULT_GRID_SPACING=110

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
ONBOARD_AUTOSTART_DST="$USER_HOME/.config/autostart/onboard-autostart.desktop"
SQUEEKBOARD_AUTOSTART_DST="$USER_HOME/.config/autostart/squeekboard.desktop"
CHROMIUM_FLAGS_DIR="$USER_HOME/.config/chromium-flags.conf.d"
PCMANFM_CONFIG_DIR="$USER_HOME/.config/pcmanfm/LXDE-pi"
LIBFM_CONFIG="$USER_HOME/.config/libfm/libfm.conf"
LXTERMINAL_CONFIG="$USER_HOME/.config/lxterminal/lxterminal.conf"

# Wayfire panel config (Wayland - used on newer Raspberry Pi OS)
WF_PANEL_CONFIG="$USER_HOME/.config/wf-panel-pi.ini"

# LXDE panel config paths (X11 - fallback for older setups)
USER_PANEL_CONFIG="$USER_HOME/.config/lxpanel/LXDE-pi/panels/panel"
SYSTEM_PANEL_CONFIG="/etc/xdg/lxpanel/LXDE-pi/panels/panel"

# Detect which panel system is in use
is_wayland() {
    [ -f "$WF_PANEL_CONFIG" ] || pgrep -x wayfire >/dev/null 2>&1
}

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

# Logout user to apply changes (works on Wayland/labwc)
do_logout() {
    warn "Logging out in 3 seconds to apply changes..."
    sleep 3
    # Try labwc exit first (Wayland), fall back to loginctl
    if pgrep -x labwc >/dev/null 2>&1; then
        pkill -SIGTERM labwc
    else
        loginctl terminate-user "${SUDO_USER:-$USER}" 2>/dev/null || pkill -u "${SUDO_USER:-$USER}"
    fi
}

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

    # 1. Enable on-screen keyboard autostart (remove any Hidden=true overrides)
    mkdir -p "$(dirname "$ONBOARD_AUTOSTART_DST")"
    # Remove override files so system autostart can run
    rm -f "$ONBOARD_AUTOSTART_DST" "$SQUEEKBOARD_AUTOSTART_DST"
    info "On-screen keyboard autostart enabled (removed overrides)"

    # 2. Apply GTK touch CSS
    if [ -f "$GTK_CSS_SRC" ]; then
        mkdir -p "$(dirname "$GTK_CSS_DST")"
        cp "$GTK_CSS_SRC" "$GTK_CSS_DST"
        info "GTK touch CSS applied"
    else
        warn "GTK touch CSS not found at $GTK_CSS_SRC"
    fi

    # 3. Update panel (Wayland: wf-panel-pi, X11: lxpanel)
    if is_wayland && [ -f "$WF_PANEL_CONFIG" ]; then
        # Wayland: wf-panel-pi
        if [ ! -f "${WF_PANEL_CONFIG}.touch-backup" ]; then
            cp "$WF_PANEL_CONFIG" "${WF_PANEL_CONFIG}.touch-backup"
        fi
        # Update icon_size in [panel] section (wf-panel-pi uses icon_size not iconsize)
        if grep -q "icon_size=" "$WF_PANEL_CONFIG"; then
            sed -i "s/icon_size=.*/icon_size=$TOUCH_PANEL_ICON_SIZE/" "$WF_PANEL_CONFIG"
        else
            sed -i "/^\[panel\]/a icon_size=$TOUCH_PANEL_ICON_SIZE" "$WF_PANEL_CONFIG"
        fi
        info "Wayfire panel updated (icon_size=$TOUCH_PANEL_ICON_SIZE)"
    else
        # X11: lxpanel
        PANEL_CONFIG=$(get_panel_config)
        if [ -n "$PANEL_CONFIG" ]; then
            if [ "$PANEL_CONFIG" = "$SYSTEM_PANEL_CONFIG" ]; then
                mkdir -p "$(dirname "$USER_PANEL_CONFIG")"
                cp "$SYSTEM_PANEL_CONFIG" "$USER_PANEL_CONFIG"
                PANEL_CONFIG="$USER_PANEL_CONFIG"
                info "Copied system panel config to user config"
            fi
            if [ ! -f "${PANEL_CONFIG}.touch-backup" ]; then
                cp "$PANEL_CONFIG" "${PANEL_CONFIG}.touch-backup"
            fi
            sed -i "s/height=.*/height=$TOUCH_PANEL_HEIGHT/" "$PANEL_CONFIG"
            sed -i "s/iconsize=.*/iconsize=$TOUCH_PANEL_ICON_SIZE/" "$PANEL_CONFIG"
            info "LXDE panel updated (height=$TOUCH_PANEL_HEIGHT, iconsize=$TOUCH_PANEL_ICON_SIZE)"
        else
            info "Panel config not found (will apply on next desktop login)"
        fi
    fi

    # 4. Set Chromium touch flags
    mkdir -p "$CHROMIUM_FLAGS_DIR"
    echo "--touch-events=enabled" > "$CHROMIUM_FLAGS_DIR/touch.conf"
    info "Chromium touch flags set"

    # 5. Adjust double-click timing (if xfconf available)
    if command -v xfconf-query >/dev/null 2>&1; then
        xfconf-query -c xsettings -p /Net/DoubleClickTime -s "$TOUCH_DOUBLE_CLICK_MS" 2>/dev/null || true
        info "Double-click time set to ${TOUCH_DOUBLE_CLICK_MS}ms"
    fi

    # 6. Increase desktop icon size (in libfm.conf) and adjust grid spacing (in pcmanfm configs)
    # big_icon_size is read from libfm.conf [ui] section, NOT desktop-items*.conf
    if [ -f "$LIBFM_CONFIG" ]; then
        if [ ! -f "${LIBFM_CONFIG}.touch-backup" ]; then
            cp "$LIBFM_CONFIG" "${LIBFM_CONFIG}.touch-backup"
        fi
        # Update big_icon_size in [ui] section
        if grep -q "^big_icon_size=" "$LIBFM_CONFIG"; then
            sed -i "s/^big_icon_size=.*/big_icon_size=$TOUCH_DESKTOP_ICON_SIZE/" "$LIBFM_CONFIG"
        else
            # Add to [ui] section if it exists, otherwise append
            if grep -q "^\[ui\]" "$LIBFM_CONFIG"; then
                sed -i "/^\[ui\]/a big_icon_size=$TOUCH_DESKTOP_ICON_SIZE" "$LIBFM_CONFIG"
            fi
        fi
        info "Desktop icon size set to ${TOUCH_DESKTOP_ICON_SIZE}px (libfm.conf)"
    fi

    # Adjust grid spacing in pcmanfm desktop-items configs
    if [ -d "$PCMANFM_CONFIG_DIR" ]; then
        # Calculate scaled grid positions based on TOUCH_DESKTOP_GRID_SPACING
        # Default grid is 110px, touch grid from env (default 140px)
        # Formula: new_pos = 10 + ((old_pos - 10) * TOUCH_GRID / DEFAULT_GRID)
        local g1=$(( 10 + ((120 - 10) * TOUCH_DESKTOP_GRID_SPACING / DEFAULT_GRID_SPACING) ))
        local g2=$(( 10 + ((230 - 10) * TOUCH_DESKTOP_GRID_SPACING / DEFAULT_GRID_SPACING) ))
        local g3=$(( 10 + ((340 - 10) * TOUCH_DESKTOP_GRID_SPACING / DEFAULT_GRID_SPACING) ))
        local g4=$(( 10 + ((450 - 10) * TOUCH_DESKTOP_GRID_SPACING / DEFAULT_GRID_SPACING) ))

        for conf in "$PCMANFM_CONFIG_DIR"/desktop-items*.conf; do
            [ -f "$conf" ] || continue
            # Backup original if not already backed up
            if [ ! -f "${conf}.touch-backup" ]; then
                cp "$conf" "${conf}.touch-backup"
            fi
            # Scale grid spacing based on configured touch grid spacing
            sed -i "s/^x=120\$/x=$g1/" "$conf"
            sed -i "s/^x=230\$/x=$g2/" "$conf"
            sed -i "s/^x=340\$/x=$g3/" "$conf"
            sed -i "s/^x=450\$/x=$g4/" "$conf"
            sed -i "s/^y=120\$/y=$g1/" "$conf"
            sed -i "s/^y=230\$/y=$g2/" "$conf"
            sed -i "s/^y=340\$/y=$g3/" "$conf"
            sed -i "s/^y=450\$/y=$g4/" "$conf"
        done
        info "Desktop grid spacing set to ${TOUCH_DESKTOP_GRID_SPACING}px"
    fi

    # 7. Increase terminal font size
    if [ -f "$LXTERMINAL_CONFIG" ]; then
        if [ ! -f "${LXTERMINAL_CONFIG}.touch-backup" ]; then
            cp "$LXTERMINAL_CONFIG" "${LXTERMINAL_CONFIG}.touch-backup"
        fi
        # Change font size from default to configured touch size
        sed -i "s/fontname=Monospace [0-9]*/fontname=Monospace $TOUCH_TERMINAL_FONT_SIZE/" "$LXTERMINAL_CONFIG"
        info "Terminal font size increased (${TOUCH_TERMINAL_FONT_SIZE}pt)"
    fi

    # 8. Update state file
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
        chown -R "$SUDO_USER:$SUDO_USER" "$USER_HOME/.config/pcmanfm" 2>/dev/null || true
        chown -R "$SUDO_USER:$SUDO_USER" "$USER_HOME/.config/lxterminal" 2>/dev/null || true
    fi

    echo ""
    info "Touch mode ENABLED"
    echo ""
    echo "Settings applied:"
    echo "  - On-screen keyboard: autostart enabled"
    echo "  - GTK buttons/scrollbars: enlarged (48px min)"
    echo "  - Panel: height=${TOUCH_PANEL_HEIGHT}px, icons=${TOUCH_PANEL_ICON_SIZE}px"
    echo "  - Desktop icons: ${TOUCH_DESKTOP_ICON_SIZE}px (grid: ${TOUCH_DESKTOP_GRID_SPACING}px)"
    echo "  - Terminal font: ${TOUCH_TERMINAL_FONT_SIZE}pt"
    echo "  - Chromium: touch events enabled"
    echo "  - Double-click time: ${TOUCH_DOUBLE_CLICK_MS}ms"
    echo ""

    # Auto-logout to apply changes
    do_logout
}

# Disable touch mode
disable_touch_mode() {
    info "Disabling touch mode..."

    # 1. Disable on-screen keyboards (both onboard and squeekboard)
    # Create user autostart files with Hidden=true to override system-wide autostart
    mkdir -p "$(dirname "$ONBOARD_AUTOSTART_DST")"
    cat > "$ONBOARD_AUTOSTART_DST" << 'DESKTOP_EOF'
[Desktop Entry]
Type=Application
Name=Onboard
Hidden=true
DESKTOP_EOF
    cat > "$SQUEEKBOARD_AUTOSTART_DST" << 'DESKTOP_EOF'
[Desktop Entry]
Type=Application
Name=Squeekboard
Hidden=true
DESKTOP_EOF
    info "On-screen keyboards disabled (onboard + squeekboard)"

    # 2. Remove GTK touch CSS
    if [ -f "$GTK_CSS_DST" ]; then
        rm -f "$GTK_CSS_DST"
        info "GTK touch CSS removed"
    fi

    # 3. Restore panel defaults (Wayland: wf-panel-pi, X11: lxpanel)
    if is_wayland && [ -f "$WF_PANEL_CONFIG" ]; then
        # Wayland: wf-panel-pi
        if [ -f "${WF_PANEL_CONFIG}.touch-backup" ]; then
            cp "${WF_PANEL_CONFIG}.touch-backup" "$WF_PANEL_CONFIG"
            info "Wayfire panel restored from backup"
        elif [ -f "$WF_PANEL_CONFIG" ]; then
            sed -i "s/icon_size=.*/icon_size=$DEFAULT_PANEL_ICON_SIZE/" "$WF_PANEL_CONFIG"
            info "Wayfire panel restored (icon_size=$DEFAULT_PANEL_ICON_SIZE)"
        fi
    else
        # X11: lxpanel
        PANEL_CONFIG=$(get_panel_config)
        if [ -n "$PANEL_CONFIG" ]; then
            if [ -f "${USER_PANEL_CONFIG}.touch-backup" ]; then
                cp "${USER_PANEL_CONFIG}.touch-backup" "$USER_PANEL_CONFIG"
                info "LXDE panel restored from backup"
            elif [ -f "$USER_PANEL_CONFIG" ]; then
                sed -i "s/height=.*/height=$DEFAULT_PANEL_HEIGHT/" "$USER_PANEL_CONFIG"
                sed -i "s/iconsize=.*/iconsize=$DEFAULT_PANEL_ICON_SIZE/" "$USER_PANEL_CONFIG"
                info "LXDE panel restored (height=$DEFAULT_PANEL_HEIGHT, iconsize=$DEFAULT_PANEL_ICON_SIZE)"
            fi
        fi
    fi

    # 4. Remove Chromium touch flags
    rm -f "$CHROMIUM_FLAGS_DIR/touch.conf"
    info "Chromium touch flags removed"

    # 5. Restore double-click timing
    if command -v xfconf-query >/dev/null 2>&1; then
        xfconf-query -c xsettings -p /Net/DoubleClickTime -s "$DEFAULT_DOUBLE_CLICK_MS" 2>/dev/null || true
        info "Double-click time restored to ${DEFAULT_DOUBLE_CLICK_MS}ms"
    fi

    # 6. Restore desktop icon size (in libfm.conf) and grid spacing (in pcmanfm configs)
    if [ -f "${LIBFM_CONFIG}.touch-backup" ]; then
        cp "${LIBFM_CONFIG}.touch-backup" "$LIBFM_CONFIG"
        info "Desktop icon size restored (libfm.conf)"
    elif [ -f "$LIBFM_CONFIG" ]; then
        # Restore default big_icon_size=48
        sed -i "s/^big_icon_size=.*/big_icon_size=48/" "$LIBFM_CONFIG"
        info "Desktop icon size restored to 48px"
    fi

    if [ -d "$PCMANFM_CONFIG_DIR" ]; then
        for conf in "$PCMANFM_CONFIG_DIR"/desktop-items*.conf; do
            [ -f "$conf" ] || continue
            if [ -f "${conf}.touch-backup" ]; then
                cp "${conf}.touch-backup" "$conf"
            fi
        done
        info "Desktop grid spacing restored to default"
    fi

    # 7. Restore terminal font size
    if [ -f "${LXTERMINAL_CONFIG}.touch-backup" ]; then
        cp "${LXTERMINAL_CONFIG}.touch-backup" "$LXTERMINAL_CONFIG"
        info "Terminal font size restored"
    elif [ -f "$LXTERMINAL_CONFIG" ]; then
        sed -i "s/fontname=Monospace [0-9]*/fontname=Monospace $DEFAULT_TERMINAL_FONT_SIZE/" "$LXTERMINAL_CONFIG"
        info "Terminal font size restored (${DEFAULT_TERMINAL_FONT_SIZE}pt)"
    fi

    # 8. Update state file
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
    echo "  - Panel: height=${DEFAULT_PANEL_HEIGHT}px, icons=${DEFAULT_PANEL_ICON_SIZE}px"
    echo "  - Desktop icons: default size"
    echo "  - Terminal font: ${DEFAULT_TERMINAL_FONT_SIZE}pt"
    echo "  - Chromium: touch events default"
    echo "  - Double-click time: ${DEFAULT_DOUBLE_CLICK_MS}ms"
    echo ""

    # Auto-logout to apply changes
    do_logout
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

    # On-screen keyboards (check both onboard and squeekboard)
    local kbd_disabled=0
    if [ -f "$ONBOARD_AUTOSTART_DST" ] && grep -q "Hidden=true" "$ONBOARD_AUTOSTART_DST" 2>/dev/null; then
        kbd_disabled=$((kbd_disabled + 1))
    fi
    if [ -f "$SQUEEKBOARD_AUTOSTART_DST" ] && grep -q "Hidden=true" "$SQUEEKBOARD_AUTOSTART_DST" 2>/dev/null; then
        kbd_disabled=$((kbd_disabled + 1))
    fi
    if [ "$kbd_disabled" -eq 2 ]; then
        echo -e "  On-screen keyboard: ${YELLOW}autostart disabled${NC}"
    elif [ "$kbd_disabled" -eq 0 ]; then
        echo -e "  On-screen keyboard: ${GREEN}autostart enabled${NC}"
    else
        echo -e "  On-screen keyboard: ${YELLOW}partially disabled${NC}"
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
    echo "  - On-screen keyboard (onboard/squeekboard) autostart"
    echo "  - GTK3 button and scrollbar sizes"
    echo "  - Panel height and icon size"
    echo "  - Desktop icon size and grid spacing"
    echo "  - Terminal font size"
    echo "  - Chromium touch event handling"
    echo "  - Double-click timing"
    echo ""
    echo "Settings are configurable via /etc/rasqberry/rasqberry_environment.env:"
    echo "  TOUCH_PANEL_HEIGHT, TOUCH_PANEL_ICON_SIZE, TOUCH_DESKTOP_ICON_SIZE,"
    echo "  TOUCH_DESKTOP_GRID_SPACING, TOUCH_TERMINAL_FONT_SIZE, TOUCH_DOUBLE_CLICK_MS"
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
