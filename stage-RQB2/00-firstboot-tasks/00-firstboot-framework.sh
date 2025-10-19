#!/bin/bash -e

echo "Installing RasQberry modular firstboot framework"

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

# Create systemd service
cat > /etc/systemd/system/rasqberry-firstboot.service << 'EOF'
[Unit]
Description=RasQberry First Boot Tasks
After=systemd-remount-fs.service
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

echo "RasQberry modular firstboot framework installed and enabled"
echo "Task runner: /usr/local/bin/rasqberry-firstboot.sh"
echo "Tasks directory: /usr/local/lib/rasqberry-firstboot.d/"
echo "Markers directory: /var/lib/rasqberry-firstboot/"
