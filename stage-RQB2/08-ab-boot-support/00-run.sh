#!/bin/sh -e
#
# Install A/B boot support files and systemd services
# This runs OUTSIDE chroot and copies files directly to ROOTFS_DIR
#

echo "=> Installing A/B Boot Support files"

# Copy scripts to /usr/local/bin in the target filesystem
echo "=> Installing A/B boot scripts to /usr/local/bin"
install -v -m 755 "$(dirname "$0")/../../RQB2-bin/rq_health_check.py" \
  "$ROOTFS_DIR/usr/local/bin/rq_health_check.py"

install -v -m 755 "$(dirname "$0")/../../RQB2-bin/rq_slot_manager.sh" \
  "$ROOTFS_DIR/usr/local/bin/rq_slot_manager.sh"

install -v -m 755 "$(dirname "$0")/../../RQB2-bin/rq_update_poller.py" \
  "$ROOTFS_DIR/usr/local/bin/rq_update_poller.py"

install -v -m 755 "$(dirname "$0")/../../RQB2-bin/rq_update_slot.sh" \
  "$ROOTFS_DIR/usr/local/bin/rq_update_slot.sh"

install -v -m 755 "$(dirname "$0")/../../RQB2-bin/rq_common.sh" \
  "$ROOTFS_DIR/usr/local/bin/rq_common.sh"

# Copy systemd service files
echo "=> Installing systemd service files"
install -v -m 644 "$(dirname "$0")/files/systemd/rasqberry-health-check.service" \
  "$ROOTFS_DIR/etc/systemd/system/rasqberry-health-check.service"

install -v -m 644 "$(dirname "$0")/files/systemd/rasqberry-update-poller.service" \
  "$ROOTFS_DIR/etc/systemd/system/rasqberry-update-poller.service"

install -v -m 644 "$(dirname "$0")/files/systemd/rasqberry-update-poller.timer" \
  "$ROOTFS_DIR/etc/systemd/system/rasqberry-update-poller.timer"

# Create state directories
echo "=> Creating state directories"
mkdir -p "$ROOTFS_DIR/var/lib/rasqberry-update-poller"
mkdir -p "$ROOTFS_DIR/var/tmp/rasqberry-updates"

# Create log files
echo "=> Creating log files"
touch "$ROOTFS_DIR/var/log/rasqberry-health-check.log"
touch "$ROOTFS_DIR/var/log/rasqberry-update-poller.log"
touch "$ROOTFS_DIR/var/log/rasqberry-update-slot.log"
chmod 644 "$ROOTFS_DIR"/var/log/rasqberry-*.log

echo "=> A/B boot files installed (services will be enabled in chroot)"