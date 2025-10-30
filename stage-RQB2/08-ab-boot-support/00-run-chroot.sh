#!/bin/bash -e

echo "=> Installing RasQberry A/B Boot Support (Health Check Only)"

# Source the configuration file
if [ -f "/tmp/stage-config" ]; then
    . /tmp/stage-config

    # Map the RQB_ prefixed variables to local names
    REPO="${RQB_REPO}"
    GIT_USER="${RQB_GIT_USER}"
    GIT_BRANCH="${RQB_GIT_BRANCH}"
    GIT_REPO="${RQB_GIT_REPO}"

    echo "Configuration loaded successfully"
else
    echo "WARNING: stage config file not found, using defaults"
    REPO="RasQberry-Two"
    GIT_BRANCH="main"
    GIT_REPO="https://github.com/JanLahmann/RasQberry-Two.git"
fi

export CLONE_DIR="/tmp/${REPO}"

# Clone the repository if not already cloned
if [ ! -d "${CLONE_DIR}" ]; then
    echo "Cloning repository ${GIT_REPO} (branch: ${GIT_BRANCH}) to ${CLONE_DIR}"
    git clone --depth 1 --branch ${GIT_BRANCH} ${GIT_REPO} ${CLONE_DIR}
else
    echo "Repository already exists at ${CLONE_DIR}"
fi

# Verify required files exist
if [ ! -f "${CLONE_DIR}/RQB2-bin/rq_health_check.py" ]; then
    echo "ERROR: Required A/B boot files not found in ${CLONE_DIR}/RQB2-bin"
    exit 1
fi

# Copy A/B boot scripts to /usr/local/bin
echo "=> Installing A/B boot scripts to /usr/local/bin"
install -v -m 755 "${CLONE_DIR}/RQB2-bin/rq_health_check.py" /usr/local/bin/
install -v -m 755 "${CLONE_DIR}/RQB2-bin/rq_slot_manager.sh" /usr/local/bin/
install -v -m 755 "${CLONE_DIR}/RQB2-bin/rq_common.sh" /usr/local/bin/
install -v -m 755 "${CLONE_DIR}/RQB2-bin/setup-ab-boot.sh" /usr/local/bin/
install -v -m 755 "${CLONE_DIR}/RQB2-bin/reboot-to-slot-b.sh" /usr/local/bin/

# Note: systemd service files are already installed by 00-run.sh

# Enable health check (runs once on boot to validate tryboot)
echo "=> Enabling rasqberry-health-check.service"
systemctl enable rasqberry-health-check.service

echo "=> RasQberry A/B Boot Support installed"
echo ""
echo "A/B boot health check is enabled and will run on every boot."
echo "This allows the tryboot mechanism to validate new images."
echo ""
echo "To set up A/B boot partitioning (optional for testing):"
echo "  1. Disable filesystem expansion before first boot:"
echo "     sudo touch /path/to/sdcard/var/lib/rasqberry-firstboot/01-expand-filesystem.sh.done"
echo "  2. Boot the Pi normally"
echo "  3. Run: sudo setup-ab-boot.sh"
echo ""
echo "After A/B setup, you can manually test new images in Slot B:"
echo "  1. Download image to Slot B:"
echo "     wget <image-url> && sudo bash -c 'xz -dc image.img.xz | dd of=/dev/mmcblk0p3 bs=4M'"
echo "  2. Reboot to Slot B: sudo reboot-to-slot-b"
echo "  3. Health check validates (60 seconds)"
echo "  4. If successful: Slot B becomes default"
echo "     If failed: System rolls back to Slot A"
echo ""
echo "Note: Update polling is NOT included - updates are manual only"