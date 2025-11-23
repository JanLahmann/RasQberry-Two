#!/bin/bash -e

echo "Installing RasQberry modular firstboot service"

# Create directories
mkdir -p /usr/local/lib/rasqberry-firstboot.d
mkdir -p /var/lib/rasqberry-firstboot

# Create main firstboot runner script
cat > /usr/local/bin/rasqberry-firstboot.sh << 'EOF'
#!/bin/bash
# RasQberry First Boot Task Runner
# Runs all tasks in /usr/local/lib/rasqberry-firstboot.d/ in order

TASK_DIR="/usr/local/lib/rasqberry-firstboot.d"
MARKER_DIR="/var/lib/rasqberry-firstboot"
REBOOT_REQUESTED=0

echo "=== RasQberry First Boot Task Runner ==="

# Run each task in order
for task in "$TASK_DIR"/*; do
    [ -f "$task" ] || continue
    [ -x "$task" ] || continue

    task_name=$(basename "$task")
    marker="$MARKER_DIR/${task_name}.done"

    # Skip if already completed
    if [ -f "$marker" ]; then
        echo "Task $task_name: already completed, skipping"
        continue
    fi

    echo "Task $task_name: running..."

    # Run the task
    if "$task"; then
        # Task succeeded
        touch "$marker"
        echo "Task $task_name: completed successfully"
    else
        exit_code=$?
        if [ $exit_code -eq 99 ]; then
            # Task requests reboot
            echo "Task $task_name: completed, reboot requested"
            touch "$marker"
            REBOOT_REQUESTED=1
            break
        else
            # Task failed
            echo "Task $task_name: FAILED with exit code $exit_code"
            exit $exit_code
        fi
    fi
done

# Reboot if requested
if [ $REBOOT_REQUESTED -eq 1 ]; then
    echo "Rebooting as requested by firstboot tasks..."
    sleep 2
    reboot
fi

echo "=== RasQberry First Boot Tasks Completed ==="
EOF

chmod +x /usr/local/bin/rasqberry-firstboot.sh

# Create filesystem expansion task
cat > /usr/local/lib/rasqberry-firstboot.d/01-expand-filesystem.sh << 'EOF'
#!/bin/bash
# RasQberry Firstboot Task: Expand Root Filesystem
# Expands the root filesystem to fill the SD card/device

echo "Expanding root filesystem..."

# Check for skip marker in bootfs (accessible from Mac/Windows)
# This allows users to disable expansion by creating a file on the boot partition
if [ -f /boot/firmware/skip-expansion ]; then
    echo "Expansion disabled: /boot/firmware/skip-expansion marker found"
    echo "This is typically used for A/B boot setup"
    exit 0
fi

# Check if expansion is needed
ROOT_PART=$(findmnt / -o source -n)
ROOT_DEV=$(lsblk -no pkname "$ROOT_PART")
PART_END=$(parted /dev/$ROOT_DEV -ms unit s p | grep "^${ROOT_PART##*/}:" | cut -d: -f3 | sed 's/s$//')
DEV_SIZE=$(cat /sys/block/$ROOT_DEV/size)

if [ "$PART_END" -ge "$((DEV_SIZE - 1))" ]; then
    echo "Root filesystem already at maximum size"
    exit 0
fi

# Run raspi-config expansion
if raspi-config nonint do_expand_rootfs; then
    echo "Filesystem expansion configured successfully"
    # Request reboot (exit code 99)
    exit 99
else
    echo "ERROR: Failed to configure filesystem expansion"
    exit 1
fi
EOF

chmod +x /usr/local/lib/rasqberry-firstboot.d/01-expand-filesystem.sh

# Note: A/B partition expansion is handled manually via raspi-config
# (RasQberry menu -> Expand A/B Partitions) to allow user confirmation
# and control over partition sizing on 64GB+ SD cards

# Create VNC enablement script that runs on every desktop login
# Using raspi-config which is idempotent (safe to run multiple times)
cat > /usr/local/bin/rasqberry-enable-vnc.sh << 'EOF'
#!/bin/bash
# RasQberry Desktop Login: Ensure VNC Server is Enabled
# Runs on every login - raspi-config do_vnc is idempotent

# Enable VNC using raspi-config (idempotent, safe to run every login)
sudo raspi-config nonint do_vnc 0 2>/dev/null
EOF

chmod +x /usr/local/bin/rasqberry-enable-vnc.sh

# Create autostart desktop entry that runs on every graphical login
cat > /etc/xdg/autostart/rasqberry-enable-vnc.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=RasQberry VNC Enablement
Comment=Ensure VNC Server is enabled on each desktop login
Exec=/usr/local/bin/rasqberry-enable-vnc.sh
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF

# Create systemd service
cat > /etc/systemd/system/rasqberry-firstboot.service << 'EOF'
[Unit]
Description=RasQberry First Boot Tasks
After=systemd-remount-fs.service boot-firmware.mount
Requires=boot-firmware.mount
Before=rc-local.service systemd-user-sessions.service
DefaultDependencies=no

[Service]
Type=oneshot
ExecStart=/usr/local/bin/rasqberry-firstboot.sh
RemainAfterExit=yes
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=sysinit.target
EOF

# Enable the service
systemctl enable rasqberry-firstboot.service

echo "RasQberry modular firstboot service installed and enabled"
echo "Tasks will run from: /usr/local/lib/rasqberry-firstboot.d/"
echo "  - 01-expand-filesystem.sh: Expand root filesystem to fill SD card (standard images)"
echo "  Note: A/B partition expansion requires manual trigger via raspi-config menu"
echo "VNC will be enabled on first desktop login via /etc/xdg/autostart/"
echo "Completion markers stored in: /var/lib/rasqberry-firstboot/"
