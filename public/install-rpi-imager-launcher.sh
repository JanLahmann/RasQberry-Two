#!/bin/bash
#
# RasQberry Pi Imager Launcher Installer for macOS
#
# This script creates a macOS launcher app with the RasQberry icon that opens
# Raspberry Pi Imager with the RasQberry custom image repository pre-loaded.
#
# USAGE:
#
#   OPTION 1 - One-line install (recommended):
#     Run this command in Terminal to download and execute:
#
#       curl -sSL https://rasqberry.org/install-rpi-imager-launcher.sh | bash
#
#   OPTION 2 - Download, inspect, then run:
#     1. Download this script:
#        curl -O https://rasqberry.org/install-rpi-imager-launcher.sh
#
#     2. Make it executable:
#        chmod +x install-rpi-imager-launcher.sh
#
#     3. Run it:
#        ./install-rpi-imager-launcher.sh
#
# The installer will:
#   - Check if Raspberry Pi Imager is installed
#   - Download the RasQberry cube logo icon
#   - Create "Pi Imager for RasQberry" app on your Desktop
#   - Apply the custom icon
#
# You can then move the app to your Applications folder or Dock.
#
# REQUIREMENTS:
#   - macOS (tested on macOS 10.15+)
#   - Raspberry Pi Imager installed in /Applications/
#     Download from: https://www.raspberrypi.com/software/
#

set -e

echo "Installing RasQberry Pi Imager Launcher..."

# Check if Raspberry Pi Imager is installed
if [ ! -d "/Applications/Raspberry Pi Imager.app" ]; then
    echo "Error: Raspberry Pi Imager not found in /Applications/"
    echo "Please install it first from https://www.raspberrypi.com/software/"
    exit 1
fi

# Create temporary directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Download the RasQberry icon
echo "Downloading RasQberry icon..."
curl -sL "https://rasqberry.org/Artwork/RasQberry%202%20Logo%20Cube%2064x64.png" -o rasqberry-icon.png

if [ ! -f rasqberry-icon.png ]; then
    echo "Warning: Could not download icon, using default"
    USE_CUSTOM_ICON=false
else
    USE_CUSTOM_ICON=true
fi

# Create the AppleScript
echo "Creating launcher..."
cat > launcher.scpt << 'EOF'
do shell script "open -a '/Applications/Raspberry Pi Imager.app' --args --repo https://RasQberry.org/RQB-images.json"
EOF

# Compile AppleScript to app
osacompile -o "$HOME/Desktop/Pi Imager for RasQberry.app" launcher.scpt

# Apply custom icon if available
if [ "$USE_CUSTOM_ICON" = true ]; then
    echo "Applying custom icon..."

    # Create iconset with multiple resolutions
    mkdir -p RasQberry-icon.iconset
    sips -z 16 16 rasqberry-icon.png --out RasQberry-icon.iconset/icon_16x16.png >/dev/null 2>&1
    sips -z 32 32 rasqberry-icon.png --out RasQberry-icon.iconset/icon_16x16@2x.png >/dev/null 2>&1
    sips -z 32 32 rasqberry-icon.png --out RasQberry-icon.iconset/icon_32x32.png >/dev/null 2>&1
    sips -z 64 64 rasqberry-icon.png --out RasQberry-icon.iconset/icon_32x32@2x.png >/dev/null 2>&1
    sips -z 128 128 rasqberry-icon.png --out RasQberry-icon.iconset/icon_128x128.png >/dev/null 2>&1
    sips -z 256 256 rasqberry-icon.png --out RasQberry-icon.iconset/icon_128x128@2x.png >/dev/null 2>&1
    sips -z 256 256 rasqberry-icon.png --out RasQberry-icon.iconset/icon_256x256.png >/dev/null 2>&1
    sips -z 512 512 rasqberry-icon.png --out RasQberry-icon.iconset/icon_256x256@2x.png >/dev/null 2>&1
    sips -z 512 512 rasqberry-icon.png --out RasQberry-icon.iconset/icon_512x512.png >/dev/null 2>&1

    # Convert to icns
    iconutil -c icns RasQberry-icon.iconset -o RasQberry.icns

    # Copy icon to app
    cp RasQberry.icns "$HOME/Desktop/Pi Imager for RasQberry.app/Contents/Resources/applet.icns"

    # Update Info.plist
    defaults write "$HOME/Desktop/Pi Imager for RasQberry.app/Contents/Info" CFBundleIconFile "applet.icns"

    # Touch app to refresh
    touch "$HOME/Desktop/Pi Imager for RasQberry.app"
fi

# Cleanup
cd "$HOME"
rm -rf "$TEMP_DIR"

echo ""
echo "✅ Installation complete!"
echo ""
echo "The 'Pi Imager for RasQberry' app has been created on your Desktop."
echo "You can:"
echo "  - Double-click it to launch Raspberry Pi Imager with RasQberry images"
echo "  - Move it to Applications folder"
echo "  - Drag it to your Dock for quick access"
echo ""
echo "Note: The custom icon may take a moment to appear due to macOS icon caching."
echo ""
