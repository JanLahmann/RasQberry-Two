#!/bin/bash -e
#
# Install boot configuration file to boot partition
#

STAGE_DIR="$(dirname "$0")"

echo "=== Installing RasQberry boot configuration file ==="

# Copy boot configuration template to boot partition
install -v -m 644 "${STAGE_DIR}/../../RQB2-config/rasqberry_boot.env" \
  "${ROOTFS_DIR}/boot/firmware/rasqberry_boot.env"

echo "=> Boot configuration file installed"