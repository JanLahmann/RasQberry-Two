#!/bin/bash -e
#
# Install IP display service for boot-time LED display
# This service displays the device's IP address on the LED matrix for 30 seconds at boot

# Install netifaces package in the virtual environment
# Uses wheel cache from Qiskit stage for faster installation
VENV_PATH="/home/rasqberry/RasQberry-Two/venv/RQB2"
WHEEL_DIR="/tmp/wheels"

if [ -d "$VENV_PATH" ]; then
    echo "Installing netifaces in virtual environment..."
    # Use wheel cache if available (populated by 03-install-qiskit)
    if [ -d "$WHEEL_DIR" ] && [ -n "$(ls -A $WHEEL_DIR/*.whl 2>/dev/null)" ]; then
        echo "Using wheel cache for fast install..."
        "$VENV_PATH/bin/pip3" install --prefer-binary --find-links="$WHEEL_DIR" netifaces
    else
        echo "No wheel cache - installing from PyPI..."
        "$VENV_PATH/bin/pip3" install --use-pep517 netifaces
    fi
else
    echo "WARNING: Virtual environment not found at $VENV_PATH"
    echo "netifaces will need to be installed manually"
fi

# Create systemd service file
cat > /etc/systemd/system/rasqberry-ip-display.service << 'EOF'
[Unit]
Description=RasQberry IP Display on LED Matrix
Documentation=https://github.com/JanLahmann/RasQberry-Two/issues/120
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
# Wait a bit after network is up to allow DHCP to complete
ExecStartPre=/bin/sleep 5
# Display IP address on LEDs (60 seconds per IP, auto-calculated)
ExecStart=/home/rasqberry/RasQberry-Two/venv/RQB2/bin/python3 /usr/bin/rq_display_ip.py --duration 60 --speed 0.08 --brightness 0.3
# Service runs once at boot
RemainAfterExit=no
StandardOutput=journal
StandardError=journal

# Restart on failure (in case network isn't ready)
Restart=on-failure
RestartSec=10
StartLimitBurst=3

[Install]
WantedBy=multi-user.target
EOF

# Enable the service to run at boot
systemctl enable rasqberry-ip-display.service

echo "IP display service installed and enabled"