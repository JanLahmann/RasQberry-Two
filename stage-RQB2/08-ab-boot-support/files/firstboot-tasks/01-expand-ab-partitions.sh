#!/bin/bash
# RasQberry A/B Boot: Expand both slots to use available SD card space
# This runs on first boot to resize both Slot A and Slot B partitions

set -e

LOG_FILE="/var/log/rasqberry-ab-expansion.log"

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log_message "=== A/B Partition Expansion Starting ==="

# Get root device info
ROOT_PART=$(findmnt / -o source -n)
ROOT_DEV=$(lsblk -no pkname "$ROOT_PART")
DEVICE="/dev/$ROOT_DEV"

log_message "Root device: $DEVICE"
log_message "Root partition: $ROOT_PART"

# Check if we're on Slot A (p2)
if [ "$ROOT_PART" != "/dev/${ROOT_DEV}p2" ]; then
    log_message "Not running from Slot A, skipping expansion"
    exit 0
fi

# Check if already expanded (marker file)
EXPANSION_MARKER="/var/lib/rasqberry-firstboot/ab-partitions-expanded.done"
if [ -f "$EXPANSION_MARKER" ]; then
    log_message "A/B partitions already expanded"
    exit 0
fi

# Get total device size
DEVICE_SIZE_SECTORS=$(sudo blockdev --getsz "$DEVICE")
DEVICE_SIZE_GB=$((DEVICE_SIZE_SECTORS * 512 / 1024 / 1024 / 1024))
log_message "SD card size: ${DEVICE_SIZE_GB}GB ($DEVICE_SIZE_SECTORS sectors)"

# Get boot partition end
P1_END=$(sudo parted "$DEVICE" unit s print | grep "^ 1" | awk '{print $3}' | sed 's/s//')
log_message "Boot partition ends at sector: $P1_END"

# Calculate available space for slots (device - boot - alignment overhead)
ALIGNMENT_OVERHEAD_SECTORS=8192  # ~4MB for alignment
AVAILABLE_SECTORS=$((DEVICE_SIZE_SECTORS - P1_END - ALIGNMENT_OVERHEAD_SECTORS))
AVAILABLE_GB=$((AVAILABLE_SECTORS * 512 / 1024 / 1024 / 1024))

log_message "Available space for slots: ${AVAILABLE_GB}GB ($AVAILABLE_SECTORS sectors)"

# Each slot gets half the available space
SLOT_SIZE_SECTORS=$((AVAILABLE_SECTORS / 2))
SLOT_SIZE_GB=$((SLOT_SIZE_SECTORS * 512 / 1024 / 1024 / 1024))

log_message "Target size per slot: ${SLOT_SIZE_GB}GB ($SLOT_SIZE_SECTORS sectors)"

# Get current partition 2 info
P2_START=$(sudo parted "$DEVICE" unit s print | grep "^ 2" | awk '{print $2}' | sed 's/s//')
P2_CURRENT_END=$(sudo parted "$DEVICE" unit s print | grep "^ 2" | awk '{print $3}' | sed 's/s//')

log_message "Slot A current: start=$P2_START, end=$P2_CURRENT_END"

# Calculate new end for partition 2 (Slot A)
P2_NEW_END=$((P2_START + SLOT_SIZE_SECTORS - 1))

log_message "Expanding Slot A to sector $P2_NEW_END..."
sudo parted "$DEVICE" resizepart 2 ${P2_NEW_END}s

# Expand filesystem on Slot A
log_message "Expanding Slot A filesystem..."
sudo resize2fs "$ROOT_PART"

# Get current partition 3 info
if sudo parted "$DEVICE" print | grep -q "^ 3"; then
    P3_CURRENT_START=$(sudo parted "$DEVICE" unit s print | grep "^ 3" | awk '{print $2}' | sed 's/s//')
    P3_CURRENT_END=$(sudo parted "$DEVICE" unit s print | grep "^ 3" | awk '{print $3}' | sed 's/s//')

    log_message "Slot B current: start=$P3_CURRENT_START, end=$P3_CURRENT_END"

    # Calculate new position for partition 3 (Slot B)
    P3_NEW_START=$((P2_NEW_END + 2048))  # 1MB gap
    P3_NEW_END=$((P3_NEW_START + SLOT_SIZE_SECTORS - 1))

    # Check if Slot B needs to be moved (if Slot A grew into its space)
    if [ $P3_CURRENT_START -le $P2_NEW_END ]; then
        log_message "Slot B overlaps with expanded Slot A, need to move it"

        # Delete and recreate partition 3
        log_message "Recreating Slot B at sectors $P3_NEW_START to $P3_NEW_END..."
        sudo parted "$DEVICE" rm 3
        sudo parted "$DEVICE" mkpart primary ext4 ${P3_NEW_START}s ${P3_NEW_END}s

        # Reload partition table
        sudo partprobe "$DEVICE"
        sleep 2

        # Format Slot B (it was just recreated)
        log_message "Formatting Slot B..."
        sudo mkfs.ext4 -F -L "rootfs_b" "/dev/${ROOT_DEV}p3"
    else
        # Just resize Slot B in place
        log_message "Expanding Slot B to sector $P3_NEW_END..."
        sudo parted "$DEVICE" resizepart 3 ${P3_NEW_END}s

        # Reload partition table
        sudo partprobe "$DEVICE"
        sleep 2

        # Expand filesystem on Slot B (if it has one)
        if sudo blkid "/dev/${ROOT_DEV}p3" | grep -q ext4; then
            log_message "Expanding Slot B filesystem..."
            sudo e2fsck -f -y "/dev/${ROOT_DEV}p3" || true
            sudo resize2fs "/dev/${ROOT_DEV}p3" || true
        fi
    fi
else
    log_message "Slot B (partition 3) not found, skipping"
fi

# Mark expansion as complete
sudo mkdir -p "$(dirname "$EXPANSION_MARKER")"
sudo touch "$EXPANSION_MARKER"

log_message "=== A/B Partition Expansion Complete ==="
log_message "Slot A: ${SLOT_SIZE_GB}GB"
log_message "Slot B: ${SLOT_SIZE_GB}GB"