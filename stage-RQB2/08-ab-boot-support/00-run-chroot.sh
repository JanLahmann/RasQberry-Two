#!/bin/bash -e

echo "Installing RasQberry A/B Boot Support"

# Copy A/B boot scripts to /usr/local/bin
echo "Installing A/B boot management scripts..."

# Health check
if [ -f "/home/rasqberry/RasQberry-Two/RQB2-bin/rq_health_check.py" ]; then
    cp "/home/rasqberry/RasQberry-Two/RQB2-bin/rq_health_check.py" /usr/local/bin/
    chmod +x /usr/local/bin/rq_health_check.py
    echo "  ✓ Installed rq_health_check.py"
else
    echo "  ⚠ rq_health_check.py not found"
fi

# Slot manager
if [ -f "/home/rasqberry/RasQberry-Two/RQB2-bin/rq_slot_manager.sh" ]; then
    cp "/home/rasqberry/RasQberry-Two/RQB2-bin/rq_slot_manager.sh" /usr/local/bin/
    chmod +x /usr/local/bin/rq_slot_manager.sh
    echo "  ✓ Installed rq_slot_manager.sh"
else
    echo "  ⚠ rq_slot_manager.sh not found"
fi

# Update poller
if [ -f "/home/rasqberry/RasQberry-Two/RQB2-bin/rq_update_poller.py" ]; then
    cp "/home/rasqberry/RasQberry-Two/RQB2-bin/rq_update_poller.py" /usr/local/bin/
    chmod +x /usr/local/bin/rq_update_poller.py
    echo "  ✓ Installed rq_update_poller.py"
else
    echo "  ⚠ rq_update_poller.py not found"
fi

# Update slot
if [ -f "/home/rasqberry/RasQberry-Two/RQB2-bin/rq_update_slot.sh" ]; then
    cp "/home/rasqberry/RasQberry-Two/RQB2-bin/rq_update_slot.sh" /usr/local/bin/
    chmod +x /usr/local/bin/rq_update_slot.sh
    echo "  ✓ Installed rq_update_slot.sh"
else
    echo "  ⚠ rq_update_slot.sh not found"
fi

# Common library (required by shell scripts)
if [ -f "/home/rasqberry/RasQberry-Two/RQB2-bin/rq_common.sh" ]; then
    cp "/home/rasqberry/RasQberry-Two/RQB2-bin/rq_common.sh" /usr/local/bin/
    chmod +x /usr/local/bin/rq_common.sh
    echo "  ✓ Installed rq_common.sh"
else
    echo "  ⚠ rq_common.sh not found"
fi

# Install systemd services
echo "Installing systemd services..."

install -m 644 files/systemd/rasqberry-health-check.service /etc/systemd/system/
echo "  ✓ Installed rasqberry-health-check.service"

install -m 644 files/systemd/rasqberry-update-poller.service /etc/systemd/system/
echo "  ✓ Installed rasqberry-update-poller.service"

install -m 644 files/systemd/rasqberry-update-poller.timer /etc/systemd/system/
echo "  ✓ Installed rasqberry-update-poller.timer"

# Enable services
echo "Enabling systemd services..."

# Enable health check (runs once on boot)
systemctl enable rasqberry-health-check.service
echo "  ✓ Enabled rasqberry-health-check.service"

# Enable update poller timer (runs every 30 seconds)
systemctl enable rasqberry-update-poller.timer
echo "  ✓ Enabled rasqberry-update-poller.timer"

# Create state directories
echo "Creating state directories..."
mkdir -p /var/lib/rasqberry-update-poller
mkdir -p /var/tmp/rasqberry-updates
echo "  ✓ Created state directories"

# Create log files
echo "Creating log files..."
touch /var/log/rasqberry-health-check.log
touch /var/log/rasqberry-update-poller.log
touch /var/log/rasqberry-update-slot.log
chmod 644 /var/log/rasqberry-*.log
echo "  ✓ Created log files"

echo "RasQberry A/B Boot Support installation complete"
echo ""
echo "NOTE: A/B boot requires manual partition setup using:"
echo "  sudo /home/rasqberry/RasQberry-Two/tools/setup-ab-boot.sh"
echo ""
echo "After partition setup, the system will:"
echo "  - Run health checks on every boot"
echo "  - Poll GitHub every 30 seconds for new dev* releases"
echo "  - Automatically download and install updates"
echo "  - Reboot into new images and validate them"
echo "  - Rollback automatically if validation fails"
