#!/bin/bash -e
# Enable SPI support and increase buffer size for WS2812 LED strips.

on_chroot << EOF
	SUDO_USER="${FIRST_USER_NAME}" raspi-config nonint do_spi 0
EOF

# Increase SPI buffer size for large LED strips (256+ LEDs)
# Default is 4096 bytes, increase to 8192 to support more LEDs
if [ -f "${ROOTFS_DIR}/boot/firmware/cmdline.txt" ]; then
	CMDLINE_FILE="${ROOTFS_DIR}/boot/firmware/cmdline.txt"
elif [ -f "${ROOTFS_DIR}/boot/cmdline.txt" ]; then
	CMDLINE_FILE="${ROOTFS_DIR}/boot/cmdline.txt"
else
	echo "ERROR: Could not find cmdline.txt"
	exit 1
fi

# Add spidev.bufsiz=8192 if not already present
if ! grep -q "spidev.bufsiz" "${CMDLINE_FILE}"; then
	# Add to end of the single line (cmdline.txt is one line)
	sed -i '$ s/$/ spidev.bufsiz=8192/' "${CMDLINE_FILE}"
	echo "Added spidev.bufsiz=8192 to cmdline.txt"
else
	echo "spidev.bufsiz already configured in cmdline.txt"
fi
