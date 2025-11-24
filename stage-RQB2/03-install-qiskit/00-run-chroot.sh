#!/bin/bash -e

echo "Installing Qiskit"

# Source the configuration file
if [ -f "/tmp/stage-config" ]; then
    . /tmp/stage-config
    rm -f /tmp/stage-config

    # Map the RQB_ prefixed variables to local names
    REPO="${RQB_REPO}"
    STD_VENV="${RQB_STD_VENV}"
    PIGEN="${RQB_PIGEN}"

    echo "Configuration loaded successfully"
else
    echo "ERROR: config file not found"
    exit 1
fi

# Display configuration for logging
echo "Configuration:"
echo "  REPO: $REPO"
echo "  STD_VENV: $STD_VENV"
echo "  PIGEN: $PIGEN"
echo "  FIRST_USER_NAME: ${FIRST_USER_NAME}"

# Export variables needed by installation script
export REPO STD_VENV PIGEN FIRST_USER_NAME

# Install Qiskit using pip
echo "Installing qiskit for ${FIRST_USER_NAME} user"
mkdir -p /home/${FIRST_USER_NAME}/$REPO/venv/$STD_VENV

# Create virtual environment
python3 -m venv /home/${FIRST_USER_NAME}/$REPO/venv/$STD_VENV --system-site-packages

# Install Qiskit using consolidated script (scripts are now in /usr/bin)
# The script handles venv activation based on PIGEN environment variable
. /usr/bin/rq_install_qiskit.sh latest
deactivate

# Clean pip cache to reduce image size
echo "Cleaning pip cache..."
pip cache purge 2>/dev/null || true
rm -rf /root/.cache/pip 2>/dev/null || true
rm -rf /home/${FIRST_USER_NAME}/.cache/pip 2>/dev/null || true

# Copy venv to system location for new users
cp -r /home/${FIRST_USER_NAME}/$REPO /usr/venv

# Add setup script to bashrc
export LINE=". /usr/config/setup_qiskit_env.sh"
echo "$LINE" >> /etc/skel/.bashrc
echo "$LINE" >> /home/${FIRST_USER_NAME}/.bashrc

echo "Qiskit installation completed for ${FIRST_USER_NAME}"
