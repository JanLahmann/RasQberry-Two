#!/bin/bash
#
# RasQberry Waveshare Display Auto-Setup Script
#
# Detects Waveshare displays and automatically configures:
#   - Display rotation via wlr-randr (for Wayland/labwc)
#   - Touch calibration (via udev rules, pre-installed)
#   - Kanshi config for persistent rotation
#
# Supported displays:
#   - Waveshare 079 (7.9" 400x1280)
#   - Other Waveshare HDMI touch displays
#
# This script runs at user login via autostart or can be called manually.

set -euo pipefail

# Configuration
KANSHI_SRC="/usr/config/touch-mode/kanshi-waveshare.conf"
KANSHI_USER_DIR="$HOME/.config/kanshi"
KANSHI_USER_CONF="$KANSHI_USER_DIR/config"
LOG_TAG="rq_waveshare"

# Logging helper
log() {
    logger -t "$LOG_TAG" "$1" 2>/dev/null || echo "[$(date '+%H:%M:%S')] $1"
}

# Check if running under Wayland
check_wayland() {
    if [ -z "${WAYLAND_DISPLAY:-}" ]; then
        # Try to find wayland socket
        if [ -S "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/wayland-0" ]; then
            export WAYLAND_DISPLAY="wayland-0"
            export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
        else
            log "Not running under Wayland, skipping display setup"
            return 1
        fi
    fi
    return 0
}

# Detect Waveshare display via DRM/KMS
detect_waveshare_drm() {
    local edid_path
    for edid_path in /sys/class/drm/card*-HDMI-*/edid; do
        if [ -f "$edid_path" ]; then
            # Check for Waveshare identifier in EDID
            if strings "$edid_path" 2>/dev/null | grep -qi "waveshare"; then
                # Extract output name (e.g., HDMI-A-1)
                local output_name
                output_name=$(basename "$(dirname "$edid_path")" | sed 's/card[0-9]*-//')
                echo "$output_name"
                return 0
            fi
        fi
    done
    return 1
}

# Detect Waveshare touch via USB
detect_waveshare_usb() {
    # Check for Waveshare USB vendor ID (0712)
    if lsusb 2>/dev/null | grep -q "0712:"; then
        return 0
    fi
    # Check for alternative Waveshare vendor ID (0eef)
    if lsusb 2>/dev/null | grep -q "0eef:0005"; then
        return 0
    fi
    return 1
}

# Get display info via wlr-randr
get_display_info() {
    local output="$1"
    wlr-randr 2>/dev/null | grep -A5 "^$output"
}

# Apply rotation to display
apply_rotation() {
    local output="$1"
    local transform="${2:-90}"

    log "Applying $transform degree rotation to $output"
    if wlr-randr --output "$output" --transform "$transform" 2>/dev/null; then
        log "Rotation applied successfully"
        return 0
    else
        log "Failed to apply rotation"
        return 1
    fi
}

# Setup kanshi config for persistence
setup_kanshi() {
    if [ ! -f "$KANSHI_SRC" ]; then
        log "Kanshi source config not found: $KANSHI_SRC"
        return 1
    fi

    mkdir -p "$KANSHI_USER_DIR"

    # Merge or create kanshi config
    if [ -f "$KANSHI_USER_CONF" ]; then
        # Check if waveshare profile already exists
        if ! grep -q "waveshare" "$KANSHI_USER_CONF" 2>/dev/null; then
            log "Adding Waveshare profile to existing kanshi config"
            echo "" >> "$KANSHI_USER_CONF"
            cat "$KANSHI_SRC" >> "$KANSHI_USER_CONF"
        fi
    else
        log "Creating new kanshi config with Waveshare profile"
        cp "$KANSHI_SRC" "$KANSHI_USER_CONF"
    fi

    # Restart kanshi if running
    if pgrep -x kanshi > /dev/null; then
        log "Reloading kanshi"
        pkill -HUP kanshi 2>/dev/null || true
    fi

    return 0
}

# Main function
main() {
    log "Starting Waveshare display detection"

    # Check for Wayland
    if ! check_wayland; then
        exit 0
    fi

    # Detect Waveshare display
    local waveshare_output
    if waveshare_output=$(detect_waveshare_drm); then
        log "Detected Waveshare display on $waveshare_output"

        # Apply rotation
        apply_rotation "$waveshare_output" "90"

        # Setup kanshi for persistence
        setup_kanshi

        log "Waveshare display setup complete"
    else
        log "No Waveshare display detected via DRM"

        # Check if touch is connected (display might be on different output)
        if detect_waveshare_usb; then
            log "Waveshare USB touch detected - display may need manual configuration"
        fi
    fi
}

# Run main
main "$@"
