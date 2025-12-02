#!/bin/bash -e

echo "Deploying RasQberry files and configuration"

# Source the configuration file
if [ -f "/tmp/stage-config" ]; then
    . /tmp/stage-config
    rm -f /tmp/stage-config
    
    # Map the RQB_ prefixed variables to local names
    REPO="${RQB_REPO}"
    GIT_USER="${RQB_GIT_USER}"
    GIT_BRANCH="${RQB_GIT_BRANCH}"
    GIT_REPO="${RQB_GIT_REPO}"
    STD_VENV="${RQB_STD_VENV}"
    PIGEN="${RQB_PIGEN}"
    
    echo "Configuration loaded successfully"
else
    echo "ERROR: config file not found"
    exit 1
fi

export CLONE_DIR="/tmp/${REPO}"


# Display configuration for logging
echo "Configuration:"
echo "  REPO: $REPO"
echo "  GIT_USER: $GIT_USER"
echo "  GIT_BRANCH: $GIT_BRANCH"
echo "  GIT_REPO: $GIT_REPO"
echo "  CLONE_DIR: $CLONE_DIR"
echo "  STD_VENV: $STD_VENV"
echo "  PIGEN: $PIGEN"
echo "  FIRST_USER_NAME: ${FIRST_USER_NAME}"

# Clone the Git repository
if [ ! -d "${CLONE_DIR}" ]; then
    git clone --branch ${GIT_BRANCH} ${GIT_REPO} ${CLONE_DIR}
fi
chmod 755 ${CLONE_DIR}

# DEBUG: Check what was actually cloned
echo "=== Checking cloned repository structure ==="
echo "Contents of ${CLONE_DIR}:"
ls -la ${CLONE_DIR} || echo "Failed to list ${CLONE_DIR}"
echo ""
echo "Looking for RQB2-bin:"
find ${CLONE_DIR} -name "RQB2-bin" -type d || echo "RQB2-bin directory not found!"
echo ""
echo "Git branch info:"
cd ${CLONE_DIR} && git branch && git log --oneline -n 5
cd /

# Check if expected directories exist
if [ ! -d "${CLONE_DIR}/RQB2-bin" ]; then
    echo "ERROR: RQB2-bin directory not found in cloned repository!"
    echo "This might mean:"
    echo "1. Wrong branch was cloned (expected: beta, got: ${GIT_BRANCH})"
    echo "2. The ${GIT_BRANCH} branch doesn't have the RQB2-bin directory"
    echo "3. The repository structure has changed"
    exit 1
fi

# Create necessary directories
[ ! -d /home/${FIRST_USER_NAME}/${REPO}/demos ] && mkdir -p /home/${FIRST_USER_NAME}/${REPO}/demos
[ ! -d /usr/config ] && mkdir -p /usr/config
[ ! -d /usr/venv ] && mkdir -p /usr/venv

# Set permissions
chmod -R 755 ${CLONE_DIR}/RQB2-bin
chmod -R 755 ${CLONE_DIR}/RQB2-config

# Copy files to system directories (global, not user-specific)
cp -r ${CLONE_DIR}/RQB2-bin/* /usr/bin
cp -r ${CLONE_DIR}/RQB2-config/* /usr/config

# Copy VERSION file to system directory for identification
if [ -f ${CLONE_DIR}/VERSION ]; then
  cp ${CLONE_DIR}/VERSION /etc/rasqberry-version
  chmod 644 /etc/rasqberry-version
  echo "Installed RasQberry version: $(cat /etc/rasqberry-version)"
fi

# Set permissions on system-wide directories (must be world-accessible)
chmod 755 /usr/config   # World-readable/executable so users can access config files
chmod 755 /usr/venv     # World-readable/executable so users can copy venv templates

# Set permissions on system-wide files
chmod 644 /usr/config/rasqberry_environment.env   # World-readable configuration
chmod 755 /usr/config/rasqberry_env-config.sh     # World-executable environment loader
chmod 755 /usr/bin/rq_detect_hardware.sh          # Executable hardware detection script
chmod 644 /usr/bin/rq_led_utils.py                # Python module (not executable)

# Fix ownership of all user directories created as root
# This ensures demos can be installed later without permission issues
# IMPORTANT: Must also fix the home directory itself, not just subdirectories
chown ${FIRST_USER_NAME}:${FIRST_USER_NAME} /home/${FIRST_USER_NAME}
chown -R ${FIRST_USER_NAME}:${FIRST_USER_NAME} /home/${FIRST_USER_NAME}/.local
chown -R ${FIRST_USER_NAME}:${FIRST_USER_NAME} /home/${FIRST_USER_NAME}/${REPO}

# Clean up
rm -rf $CLONE_DIR

echo "RasQberry file deployment completed"