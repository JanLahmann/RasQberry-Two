#!/bin/bash -e

echo "Installing RasQberry modular firstboot service"

# Create directories
mkdir -p /usr/local/lib/rasqberry-firstboot.d
mkdir -p /var/lib/rasqberry-firstboot

# Create main firstboot runner script
# /usr/local/bin/rasqberry-firstboot.sh is installed from RQB2-system/ by 01-deploy-files (#294)


# Create filesystem expansion task
# /usr/local/lib/rasqberry-firstboot.d/01-expand-filesystem.sh is installed from RQB2-system/ by 01-deploy-files (#294)


# Note: A/B partition expansion is handled manually via raspi-config
# (RasQberry menu -> Expand A/B Partitions) to allow user confirmation
# and control over partition sizing on 64GB+ SD cards

# Create VNC enablement script that runs on every desktop login
# Using raspi-config which is idempotent (safe to run multiple times)
# /usr/local/bin/rasqberry-enable-vnc.sh is installed from RQB2-system/ by 01-deploy-files (#294)


# Create autostart desktop entry that runs on every graphical login
# /etc/xdg/autostart/rasqberry-enable-vnc.desktop is installed from RQB2-system/ by 01-deploy-files (#294)

# Create systemd service
# /etc/systemd/system/rasqberry-firstboot.service is installed from RQB2-system/ by 01-deploy-files (#294)

# Enable the service
# rasqberry-firstboot.service is enabled by 01-deploy-files (RQB2-system/enabled-units.txt)

echo "RasQberry modular firstboot service installed and enabled"
echo "Tasks will run from: /usr/local/lib/rasqberry-firstboot.d/"
echo "  - 01-expand-filesystem.sh: Expand root filesystem to fill SD card (standard images)"
echo "  Note: A/B partition expansion requires manual trigger via raspi-config menu"
echo "VNC will be enabled on first desktop login via /etc/xdg/autostart/"
echo "Completion markers stored in: /var/lib/rasqberry-firstboot/"
