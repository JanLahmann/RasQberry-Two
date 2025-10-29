#!/bin/bash -e
#
# Install IP display service for boot-time LED display
# This service displays the device's IP address on the LED matrix for 30 seconds at boot

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
# Display IP address on LEDs for 30 seconds
ExecStart=/home/rasqberry/RasQberry-Two/RQB2-bin/rq_display_ip.py --duration 30 --speed 0.08 --brightness 0.3
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