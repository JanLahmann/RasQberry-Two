#!/bin/bash -e

echo "=> Installing and Enabling RasQberry A/B Boot Support"

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

# Copy scripts to /usr/local/bin
echo "=> Installing A/B boot scripts to /usr/local/bin"
install -v -m 755 "${CLONE_DIR}/RQB2-bin/rq_health_check.py" /usr/local/bin/
install -v -m 755 "${CLONE_DIR}/RQB2-bin/rq_slot_manager.sh" /usr/local/bin/
install -v -m 755 "${CLONE_DIR}/RQB2-bin/rq_update_poller.py" /usr/local/bin/
install -v -m 755 "${CLONE_DIR}/RQB2-bin/rq_update_slot.sh" /usr/local/bin/
install -v -m 755 "${CLONE_DIR}/RQB2-bin/rq_common.sh" /usr/local/bin/

# Note: systemd service files are already installed by 00-run.sh

# Install firstboot task for A/B partition expansion
echo "=> Installing A/B partition expansion firstboot task"
install -v -m 755 "${CLONE_DIR}/stage-RQB2/08-ab-boot-support/files/firstboot-tasks/01-expand-ab-partitions.sh" \
  "/usr/local/lib/rasqberry-firstboot.d/01-expand-ab-partitions.sh"

# Enable health check (runs once on boot)
echo "=> Enabling rasqberry-health-check.service"
systemctl enable rasqberry-health-check.service

# Enable update poller timer (runs every 30 seconds)
echo "=> Enabling rasqberry-update-poller.timer"
systemctl enable rasqberry-update-poller.timer

echo "=> RasQberry A/B Boot Support installed and enabled"
echo ""
echo "NOTE: A/B boot requires manual partition setup:"
echo "  1. Boot the Pi"
echo "  2. Run: sudo /home/rasqberry/RasQberry-Two/tools/setup-ab-boot.sh"
echo ""
echo "After partition setup, the system will:"
echo "  - Run health checks on every boot"
echo "  - Poll GitHub every 30 seconds for new dev* releases"
echo "  - Automatically download and install updates to Slot B"
echo "  - Reboot into new images and validate them"
echo "  - Rollback automatically to Slot A if validation fails"
echo ""
echo "Slot A: STABLE (protected, manual updates only)"
echo "Slot B: TESTING (auto-updated from dev* releases)"