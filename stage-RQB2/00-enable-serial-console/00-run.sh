#!/bin/bash -e
#
# Configure console output and boot verbosity
# Controlled by CONSOLE_TYPE and BOOT_VERBOSITY environment variables
#

echo "=== Configuring Console Output ==="

# Get configuration from environment (defaults to production settings)
CONSOLE_TYPE="${CONSOLE_TYPE:-hdmi}"
BOOT_VERBOSITY="${BOOT_VERBOSITY:-splash}"

echo "Configuration: CONSOLE_TYPE=${CONSOLE_TYPE}, BOOT_VERBOSITY=${BOOT_VERBOSITY}"

CONFIG_TXT="${ROOTFS_DIR}/boot/firmware/config.txt"
CMDLINE_TXT="${ROOTFS_DIR}/boot/firmware/cmdline.txt"

# =============================================================================
# UART Configuration (config.txt)
# =============================================================================
if [ -f "$CONFIG_TXT" ]; then
    echo "=> Configuring config.txt"

    if [ "$CONSOLE_TYPE" = "serial" ]; then
        # Enable UART for serial console
        if grep -q "^enable_uart=" "$CONFIG_TXT"; then
            sed -i 's/^enable_uart=.*/enable_uart=1/' "$CONFIG_TXT"
        else
            echo "" >> "$CONFIG_TXT"
            echo "# Enable serial console (GPIO 14/15)" >> "$CONFIG_TXT"
            echo "enable_uart=1" >> "$CONFIG_TXT"
        fi
        echo "   UART enabled in config.txt"
    else
        # HDMI mode: disable or remove UART setting
        if grep -q "^enable_uart=" "$CONFIG_TXT"; then
            sed -i '/^enable_uart=/d' "$CONFIG_TXT"
            echo "   UART setting removed from config.txt (HDMI mode)"
        else
            echo "   UART not configured (HDMI mode)"
        fi
    fi
else
    echo "ERROR: config.txt not found at $CONFIG_TXT"
    exit 1
fi

# =============================================================================
# Console and Verbosity Configuration (cmdline.txt)
# =============================================================================
if [ -f "$CMDLINE_TXT" ]; then
    echo "=> Configuring cmdline.txt"

    # Read current cmdline
    CURRENT_CMDLINE=$(cat "$CMDLINE_TXT")
    NEW_CMDLINE="$CURRENT_CMDLINE"

    # -------------------------------------------------------------------------
    # Console Configuration
    # -------------------------------------------------------------------------
    if [ "$CONSOLE_TYPE" = "serial" ]; then
        # Serial mode: make serial0 the primary console (last in list)

        # First, ensure serial console is present
        if ! echo "$NEW_CMDLINE" | grep -q "console=serial0"; then
            # Add serial console after tty1
            if echo "$NEW_CMDLINE" | grep -q "console=tty1"; then
                NEW_CMDLINE=$(echo "$NEW_CMDLINE" | sed 's/console=tty1/console=tty1 console=serial0,115200/')
            else
                # No tty1 found, just append
                NEW_CMDLINE="$NEW_CMDLINE console=serial0,115200"
            fi
        fi

        # Swap order so serial0 is last (primary)
        # Pattern: console=tty1 console=serial0,115200 -> console=serial0,115200 console=tty1 -> swap back
        # Actually we want: console=tty1 console=serial0,115200 (serial last = serial primary)
        if echo "$NEW_CMDLINE" | grep -q "console=serial0.*console=tty1"; then
            # serial is before tty1, swap them
            NEW_CMDLINE=$(echo "$NEW_CMDLINE" | sed 's/console=serial0,[0-9]* console=tty1/console=tty1 console=serial0,115200/')
        fi
        echo "   Serial console configured as primary"

    else
        # HDMI mode: ensure tty1 is primary (last in list)

        # Remove serial console if present
        NEW_CMDLINE=$(echo "$NEW_CMDLINE" | sed 's/ *console=serial0,[0-9]*//g')
        echo "   HDMI console configured as primary"
    fi

    # -------------------------------------------------------------------------
    # Boot Verbosity Configuration
    # -------------------------------------------------------------------------
    if [ "$BOOT_VERBOSITY" = "verbose" ]; then
        # Verbose mode: remove quiet, splash, plymouth settings
        NEW_CMDLINE=$(echo "$NEW_CMDLINE" | sed 's/ quiet / /g; s/ splash / /g; s/ plymouth\.ignore-serial-consoles / /g')
        # Also handle if they're at the end of line
        NEW_CMDLINE=$(echo "$NEW_CMDLINE" | sed 's/ quiet$//; s/ splash$//; s/ plymouth\.ignore-serial-consoles$//')
        echo "   Verbose boot enabled (quiet/splash removed)"

    else
        # Splash mode: ensure quiet, splash, plymouth settings are present
        if ! echo "$NEW_CMDLINE" | grep -q " quiet "; then
            # Check if quiet is at end
            if ! echo "$NEW_CMDLINE" | grep -q " quiet$"; then
                NEW_CMDLINE="$NEW_CMDLINE quiet"
            fi
        fi
        if ! echo "$NEW_CMDLINE" | grep -q " splash"; then
            NEW_CMDLINE="$NEW_CMDLINE splash"
        fi
        if ! echo "$NEW_CMDLINE" | grep -q "plymouth.ignore-serial-consoles"; then
            NEW_CMDLINE="$NEW_CMDLINE plymouth.ignore-serial-consoles"
        fi
        echo "   Splash boot enabled (quiet/splash/plymouth configured)"
    fi

    # Clean up any double spaces
    NEW_CMDLINE=$(echo "$NEW_CMDLINE" | sed 's/  */ /g')

    # Write updated cmdline
    echo "$NEW_CMDLINE" > "$CMDLINE_TXT"

    echo ""
    echo "Final cmdline.txt:"
    cat "$CMDLINE_TXT"
else
    echo "ERROR: cmdline.txt not found at $CMDLINE_TXT"
    exit 1
fi

echo ""
echo "=> Console configuration complete"
if [ "$CONSOLE_TYPE" = "serial" ]; then
    echo "   Connect via: screen /dev/ttyUSB0 115200"
    echo "   Or: minicom -D /dev/ttyUSB0 -b 115200"
fi
