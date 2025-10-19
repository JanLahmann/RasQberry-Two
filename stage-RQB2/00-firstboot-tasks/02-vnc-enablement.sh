#!/bin/bash -e

echo "Adding VNC enablement to firstboot tasks"

# Create VNC enablement task
cat > /usr/local/lib/rasqberry-firstboot.d/02-enable-vnc.sh << 'EOF'
#!/bin/bash
# RasQberry Firstboot Task: Enable VNC Server
# Enables and starts RealVNC server for remote desktop access

echo "Enabling VNC server..."

# Enable VNC using raspi-config
if raspi-config nonint do_vnc 0; then
    echo "VNC server enabled successfully"
    exit 0
else
    echo "WARNING: Failed to enable VNC server"
    # Don't fail the boot, just warn
    exit 0
fi
EOF

chmod +x /usr/local/lib/rasqberry-firstboot.d/02-enable-vnc.sh

echo "VNC firstboot task added"
