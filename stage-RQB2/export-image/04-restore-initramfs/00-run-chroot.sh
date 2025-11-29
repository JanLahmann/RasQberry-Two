#!/bin/bash -e
# ============================================================================
# RasQberry: Restore Initramfs Tools (Export Stage)
# ============================================================================
# Description: Restore real update-initramfs before pi-gen's finalise stage
#
# This runs in export-image stage, just before pi-gen's 05-finalise/01-run.sh
# which regenerates initramfs. By restoring the diversion here, we let pi-gen
# do the generation ONCE at the very end, avoiding redundant generations.
#
# Build optimization:
# - Stage 0: Divert update-initramfs to no-op (prevents 6+ redundant generations)
# - Stage 99: Keep diversion active (no generation in our stages)
# - Export 04: Restore real update-initramfs HERE
# - Export 05: Pi-gen's finalise generates initramfs ONCE
#
# Time savings: ~12 minutes (6 redundant generations prevented)
# Space savings: ~36MB (avoid duplicate initramfs files)
# ============================================================================

echo "=== Restoring Initramfs Tools ==="

# Check if we should skip initramfs entirely
if [ "${SKIP_INITRAMFS:-0}" = "1" ]; then
    echo "SKIP_INITRAMFS=1: Leaving initramfs diverted (no generation)"
    echo "Image will have NO initramfs"
    exit 0
fi

echo "SKIP_INITRAMFS=0: Restoring real update-initramfs for pi-gen's finalise stage"
echo ""

# Restore the real update-initramfs and mkinitramfs commands
if [ -f /usr/sbin/update-initramfs.real ]; then
    dpkg-divert --remove --rename /usr/sbin/update-initramfs
    echo "✓ update-initramfs restored"
else
    echo "⚠ update-initramfs.real not found (may not be diverted)"
fi

if [ -f /usr/sbin/mkinitramfs.real ]; then
    dpkg-divert --remove --rename /usr/sbin/mkinitramfs
    echo "✓ mkinitramfs restored"
else
    echo "⚠ mkinitramfs.real not found (may not be diverted)"
fi

echo ""
echo "Configuring initramfs for MMC device detection..."

# The MMC drivers (mmc_core, mmc_block, sdhci, sdhci-brcmstb) are built into
# the Raspberry Pi kernel, not loadable modules. They initialize automatically
# but AFTER initramfs starts looking for the root device.
#
# Solution: Add a local-block script to wait for MMC device to appear

echo "Installing MMC wait script for initramfs..."
mkdir -p /etc/initramfs-tools/scripts/local-block

if [ -f /files/wait-for-mmc ]; then
    cp /files/wait-for-mmc /etc/initramfs-tools/scripts/local-block/
    chmod +x /etc/initramfs-tools/scripts/local-block/wait-for-mmc
    echo "✓ Installed wait-for-mmc script in local-block phase"
    echo "  This script waits for /dev/mmcblk0 to appear before mounting root"
else
    echo "WARNING: wait-for-mmc script not found at /files/wait-for-mmc"
fi

echo ""
echo "Initramfs tools restored. Pi-gen's finalise stage will now generate initramfs."