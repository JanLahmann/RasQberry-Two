#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: A/B Boot Partition Setup
# ============================================================================
# Description: One-time setup to configure SD card for A/B boot testing
# Usage: sudo ./setup-ab-boot.sh
#
# WARNING: This script will repartition your SD card!
# - Backup all data before running
# - This process cannot be easily undone
# - Requires a large SD card (32GB+ recommended)
#
# This script:
#   1. Checks prerequisites
#   2. Backs up current system to Slot A
#   3. Creates Slot B partition
#   4. Configures tryboot mechanism
#   5. Installs slot manager and update tools
#
# Partition layout after setup:
#   p1: /boot/firmware (512MB) - Boot partition
#   p2: /          (12GB)  - Slot A (rootfs_a)
#   p3: <new>      (12GB)  - Slot B (rootfs_b)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Load common library from RQB2-bin directory
. "${SCRIPT_DIR}/../RQB2-bin/rq_common.sh"

# ============================================================================
# Helper Functions
# ============================================================================

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        die "This script must be run as root (use sudo)"
    fi
}

confirm_action() {
    local prompt="$1"
    warn "$prompt"
    read -p "Type 'yes' to continue: " response
    if [ "$response" != "yes" ]; then
        info "Aborted by user"
        exit 0
    fi
}

# ============================================================================
# Prerequisite Checks
# ============================================================================

check_prerequisites() {
    info "=== Checking Prerequisites ==="

    # Check if running on Raspberry Pi
    if [ ! -f /proc/device-tree/model ]; then
        die "This script must be run on a Raspberry Pi"
    fi

    local model
    model=$(cat /proc/device-tree/model 2>/dev/null || echo "Unknown")
    info "Detected: $model"

    # Check for Pi 4 or 5 (required for tryboot)
    if [[ "$model" != *"Pi 4"* ]] && [[ "$model" != *"Pi 5"* ]]; then
        die "A/B boot requires Raspberry Pi 4 or 5 (tryboot feature)"
    fi

    # Check available disk space
    local root_part
    root_part=$(findmnt / -o source -n)
    local root_dev
    root_dev=$(lsblk -no pkname "$root_part")

    info "Root device: /dev/$root_dev"
    info "Root partition: $root_part"

    # Get device size
    local dev_size_bytes
    dev_size_bytes=$(lsblk -bno size "/dev/$root_dev")
    local dev_size_gb=$((dev_size_bytes / 1024 / 1024 / 1024))

    info "SD card size: ${dev_size_gb}GB"

    if [ "$dev_size_gb" -lt 32 ]; then
        warn "SD card is smaller than 32GB"
        warn "Recommended: 32GB or larger for A/B boot"
        confirm_action "Continue anyway?"
    fi

    # Check if already configured
    if [ -b "/dev/${root_dev}p3" ]; then
        warn "Partition 3 already exists!"
        warn "This system may already be configured for A/B boot"
        confirm_action "Continue and reconfigure?"
    fi

    # Check required tools
    local required_tools=("parted" "rsync" "partprobe" "resize2fs")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            die "Required tool not found: $tool"
        fi
    done

    info "All prerequisites met"
}

# ============================================================================
# Partition Management
# ============================================================================

create_slot_b_partition() {
    info "=== Creating Slot B Partition ==="

    local root_part
    root_part=$(findmnt / -o source -n)
    local root_dev
    root_dev=$(lsblk -no pkname "$root_part")
    local device="/dev/$root_dev"

    # Get current partition layout
    info "Current partition table:"
    parted "$device" print

    confirm_action "This will create a new partition for Slot B. Continue?"

    # Get the end of partition 2 (Slot A)
    local p2_end
    p2_end=$(parted "$device" unit s print | grep "^ 2" | awk '{print $3}' | sed 's/s//')

    # Calculate partition 3 start (1MB after p2 end for alignment)
    local p3_start=$((p2_end + 2048))

    # Calculate partition 3 end (12GB size = 25165824 sectors of 512 bytes)
    local p3_size=25165824
    local p3_end=$((p3_start + p3_size))

    info "Creating partition 3:"
    info "  Start: sector $p3_start"
    info "  End: sector $p3_end"
    info "  Size: ~12GB"

    # Create partition
    parted "$device" mkpart primary ext4 "${p3_start}s" "${p3_end}s" || die "Failed to create partition"

    # Reload partition table
    partprobe "$device"
    sleep 2

    # Format partition
    local p3_part="/dev/${root_dev}p3"
    info "Formatting partition: $p3_part"

    mkfs.ext4 -F -L "rootfs_b" "$p3_part" || die "Failed to format partition"

    info "Slot B partition created: $p3_part"
}

# ============================================================================
# Tryboot Configuration
# ============================================================================

configure_tryboot() {
    info "=== Configuring Tryboot ==="

    local boot_dir="/boot/firmware"

    # Create tryboot.txt
    cat > "$boot_dir/tryboot.txt" << 'EOF'
# RasQberry A/B Boot Tryboot Configuration
# This file enables tryboot feature for automatic rollback
[all]
os_prefix=slot_b/
EOF

    info "Created: $boot_dir/tryboot.txt"

    # Create autoboot.txt (initially disabled)
    cat > "$boot_dir/autoboot.txt" << 'EOF'
# RasQberry A/B Boot Autoboot Configuration
# tryboot_a_b=1 enables tryboot mode
# Remove this line to boot normally (confirmed slot)
EOF

    info "Created: $boot_dir/autoboot.txt"

    # Create current-slot marker
    echo "A" > "$boot_dir/current-slot"
    info "Created: $boot_dir/current-slot"

    info "Tryboot configured"
}

# ============================================================================
# Install Tools
# ============================================================================

install_ab_boot_tools() {
    info "=== Installing A/B Boot Tools ==="

    local repo_dir
    # Try to find RasQberry-Two repository
    for dir in "/home/rasqberry/RasQberry-Two" "/home/*/RasQberry-Two" "$SCRIPT_DIR/.."; do
        if [ -d "$dir/RQB2-bin" ]; then
            repo_dir="$dir"
            break
        fi
    done

    if [ -z "$repo_dir" ]; then
        warn "RasQberry-Two repository not found, skipping tool installation"
        return
    fi

    info "Found repository: $repo_dir"

    # Copy slot manager to /usr/local/bin
    if [ -f "$repo_dir/RQB2-bin/rq_slot_manager.sh" ]; then
        cp "$repo_dir/RQB2-bin/rq_slot_manager.sh" /usr/local/bin/
        chmod +x /usr/local/bin/rq_slot_manager.sh
        info "Installed: rq_slot_manager.sh"
    else
        warn "Slot manager not found, skipping"
    fi

    # Copy update tools
    if [ -f "$repo_dir/RQB2-bin/rq_update_slot.sh" ]; then
        cp "$repo_dir/RQB2-bin/rq_update_slot.sh" /usr/local/bin/
        chmod +x /usr/local/bin/rq_update_slot.sh
        info "Installed: rq_update_slot.sh"
    else
        warn "Update slot script not found, skipping"
    fi

    if [ -f "$repo_dir/RQB2-bin/rq_update_poller.py" ]; then
        cp "$repo_dir/RQB2-bin/rq_update_poller.py" /usr/local/bin/
        chmod +x /usr/local/bin/rq_update_poller.py
        info "Installed: rq_update_poller.py"
    else
        warn "Update poller not found, skipping"
    fi

    if [ -f "$repo_dir/RQB2-bin/rq_health_check.py" ]; then
        cp "$repo_dir/RQB2-bin/rq_health_check.py" /usr/local/bin/
        chmod +x /usr/local/bin/rq_health_check.py
        info "Installed: rq_health_check.py"
    else
        warn "Health check not found, skipping"
    fi

    # Copy common library (needed by scripts)
    if [ -f "$repo_dir/RQB2-bin/rq_common.sh" ]; then
        cp "$repo_dir/RQB2-bin/rq_common.sh" /usr/local/bin/
        chmod +x /usr/local/bin/rq_common.sh
        info "Installed: rq_common.sh"
    else
        warn "Common library not found, skipping"
    fi

    info "A/B boot tools installed"
}

# ============================================================================
# Main
# ============================================================================

main() {
    check_root

    echo ""
    warn "╔════════════════════════════════════════════════════════════╗"
    warn "║                                                            ║"
    warn "║       RasQberry A/B Boot Partition Setup                   ║"
    warn "║                                                            ║"
    warn "║  WARNING: This will repartition your SD card!              ║"
    warn "║  Backup all data before proceeding!                        ║"
    warn "║                                                            ║"
    warn "╚════════════════════════════════════════════════════════════╝"
    echo ""

    confirm_action "Do you want to continue with A/B boot setup?"

    # Run setup steps
    check_prerequisites
    create_slot_b_partition
    configure_tryboot
    install_ab_boot_tools

    echo ""
    info "╔════════════════════════════════════════════════════════════╗"
    info "║                                                            ║"
    info "║  A/B Boot Setup Complete!                                  ║"
    info "║                                                            ║"
    info "╚════════════════════════════════════════════════════════════╝"
    echo ""

    info "Next steps:"
    info "1. Verify setup: sudo rq_slot_manager.sh status"
    info "2. Test slot switching: sudo rq_slot_manager.sh switch"
    info "3. Enable update poller systemd service (if installed)"
    echo ""
}

main "$@"
