#!/bin/bash -e
#
# Enable serial console for boot debugging
#

echo "=== Enabling Serial Console for Debugging ==="

CONFIG_TXT="${ROOTFS_DIR}/boot/firmware/config.txt"
CMDLINE_TXT="${ROOTFS_DIR}/boot/firmware/cmdline.txt"

# Enable UART in config.txt
if [ -f "$CONFIG_TXT" ]; then
    echo "=> Configuring config.txt for serial console"

    # Check if enable_uart is already set
    if grep -q "^enable_uart=" "$CONFIG_TXT"; then
        sed -i 's/^enable_uart=.*/enable_uart=1/' "$CONFIG_TXT"
    else
        echo "" >> "$CONFIG_TXT"
        echo "# Enable serial console for debugging" >> "$CONFIG_TXT"
        echo "enable_uart=1" >> "$CONFIG_TXT"
    fi

    echo "UART enabled in config.txt"
else
    echo "ERROR: config.txt not found at $CONFIG_TXT"
    exit 1
fi

# Add console to cmdline.txt if not present
if [ -f "$CMDLINE_TXT" ]; then
    echo "=> Configuring cmdline.txt for serial console"

    # Check if serial console is already configured
    if ! grep -q "console=serial0" "$CMDLINE_TXT"; then
        # Read current cmdline
        CURRENT_CMDLINE=$(cat "$CMDLINE_TXT")

        # Add serial console AFTER tty1 so it becomes primary output
        # Format: console=tty1 console=serial0,115200
        # The LAST console gets all kernel messages
        NEW_CMDLINE=$(echo "$CURRENT_CMDLINE" | sed 's/console=tty1/console=tty1 console=serial0,115200/')

        # If no console=tty1 found, just append
        if [ "$NEW_CMDLINE" = "$CURRENT_CMDLINE" ]; then
            NEW_CMDLINE="$CURRENT_CMDLINE console=serial0,115200"
        fi

        echo "$NEW_CMDLINE" > "$CMDLINE_TXT"
        echo "Serial console added to cmdline.txt"
    else
        echo "Serial console already configured in cmdline.txt"
    fi

    echo "Final cmdline.txt:"
    cat "$CMDLINE_TXT"
else
    echo "ERROR: cmdline.txt not found at $CMDLINE_TXT"
    exit 1
fi

echo "=> Serial console enabled successfully"
echo "   Connect via: screen /dev/ttyUSB0 115200"
echo "   Or: minicom -D /dev/ttyUSB0 -b 115200"