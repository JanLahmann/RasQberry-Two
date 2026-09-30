#!/bin/bash -e
#
# Install boot configuration loader and systemd service
#

echo "=== Installing RasQberry boot configuration system ==="

# Load configuration from stage config file
if [ -f "/tmp/stage-config" ]; then
    . /tmp/stage-config
    # Map RQB_ prefixed variables to local names
    REPO="${RQB_REPO}"
    GIT_REPO="${RQB_GIT_REPO}"
    GIT_BRANCH="${RQB_GIT_BRANCH:-main}"
    rm -f /tmp/stage-config
    echo "Configuration loaded: REPO=$REPO"
else
    # Fallback defaults if config file not found
    REPO="RasQberry-Two"
    GIT_REPO="https://github.com/JanLahmann/RasQberry-Two.git"
    GIT_BRANCH="main"
    echo "WARNING: stage config not found, using defaults"
fi

# Clone repository if not already cloned
export CLONE_DIR="/tmp/${REPO}"
if [ ! -d "${CLONE_DIR}" ]; then
    echo "Cloning repository ${GIT_REPO} (branch: ${GIT_BRANCH}) to ${CLONE_DIR}"
    git clone --depth 1 --branch ${GIT_BRANCH} ${GIT_REPO} ${CLONE_DIR}
else
    echo "Repository already exists at ${CLONE_DIR}"
fi

# The boot config loader (/usr/local/bin/rasqberry-load-boot-config.sh) and the
# units are installed, and enabled per RQB2-system/enabled-units.txt, by
# 01-deploy-files (#294). rasqberry-led-renderer.service ships disabled on
# purpose (LED_RENDER_MODE defaults to 'direct').

echo "Boot configuration system installed and enabled"