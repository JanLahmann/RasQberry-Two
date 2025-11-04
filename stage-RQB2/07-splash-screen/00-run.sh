#!/bin/bash -e
#
# Install RasQberry boot splash screen using Plymouth
#

STAGE_DIR="$(dirname "$0")"

echo "=== Installing RasQberry Plymouth splash theme ==="

# Create Plymouth theme directory
THEME_NAME="rasqberry"
PLYMOUTH_DIR="${ROOTFS_DIR}/usr/share/plymouth/themes/${THEME_NAME}"
mkdir -p "${PLYMOUTH_DIR}"

# Copy logo from stage files
echo "=> Copying RasQberry Cube logo for splash screen"
install -v -m 644 "${STAGE_DIR}/files/images/RasQberry Cube Logo 1000x1000.png" \
  "${PLYMOUTH_DIR}/rasqberry-logo.png"

# Copy theme configuration files
echo "=> Copying Plymouth theme files"
install -v -m 644 "${STAGE_DIR}/files/plymouth/rasqberry.plymouth" "${PLYMOUTH_DIR}/"
install -v -m 644 "${STAGE_DIR}/files/plymouth/rasqberry.script" "${PLYMOUTH_DIR}/"

echo "=> RasQberry splash screen files installed"