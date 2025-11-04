#!/bin/bash -e

echo "=== Configuring RasQberry Plymouth splash theme ==="

# Update Plymouth alternatives to use RasQberry theme
if [ -f /usr/share/plymouth/themes/rasqberry/rasqberry.plymouth ]; then
    echo "=> Setting RasQberry as default Plymouth theme"
    plymouth-set-default-theme rasqberry

    # Update initramfs to include the new theme
    echo "=> Updating initramfs with new Plymouth theme"
    update-initramfs -u

    echo "=> Plymouth theme configured successfully"
else
    echo "WARNING: RasQberry Plymouth theme files not found"
    exit 1
fi

echo ""
echo "RasQberry splash screen will be displayed at next boot"