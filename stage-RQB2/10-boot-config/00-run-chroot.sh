#!/bin/bash -e
#
# Install boot configuration loader and systemd service
#

echo "=== Installing RasQberry boot configuration system ==="

# Clone repository if not already cloned
export CLONE_DIR="/tmp/${REPO}"
if [ ! -d "${CLONE_DIR}" ]; then
    echo "Cloning repository to ${CLONE_DIR}"
    git clone --depth 1 --branch "${GIT_BRANCH:-main}" "${GIT_REPO}" "${CLONE_DIR}"
fi

# Install boot config loader script
echo "=> Installing boot config loader script"
install -v -m 755 "${CLONE_DIR}/RQB2-bin/rasqberry-load-boot-config.sh" \
  /usr/local/bin/rasqberry-load-boot-config.sh

# Install systemd service
echo "=> Installing systemd service"
install -v -m 644 files/systemd/rasqberry-boot-config.service \
  /etc/systemd/system/rasqberry-boot-config.service

# Enable the service
echo "=> Enabling boot configuration service"
systemctl enable rasqberry-boot-config.service

echo "Boot configuration system installed and enabled"