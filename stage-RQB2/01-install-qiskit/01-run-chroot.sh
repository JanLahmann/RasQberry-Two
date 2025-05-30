#!/bin/bash -e

echo "Starting qiskit Installation"

# Use configuration variables from pi-gen-config (exported via stage-RQB2/config)
# These can be overridden in pi-gen-config for different builds
export REPO="${RQB_REPO:-RasQberry-Two}"
export GIT_USER="${RQB_GIT_USER:-JanLahmann}"
export GIT_BRANCH="${RQB_GIT_BRANCH:-main}"
export GIT_REPO="${RQB_GIT_REPO:-https://github.com/${GIT_USER}/${REPO}.git}"
export CLONE_DIR="/tmp/${REPO}"
export STD_VENV="${RQB_STD_VENV:-RQB2}"
export RQB2_CONFDIR="${RQB_CONFDIR:-.local/config}"
export PIGEN="${RQB_PIGEN:-true}"

# Display configuration for logging
echo "Configuration:"
echo "  REPO: $REPO"
echo "  GIT_USER: $GIT_USER"
echo "  GIT_BRANCH: $GIT_BRANCH"
echo "  GIT_REPO: $GIT_REPO"
echo "  CLONE_DIR: $CLONE_DIR"
echo "  STD_VENV: $STD_VENV"
echo "  RQB2_CONFDIR: $RQB2_CONFDIR"
echo "  PIGEN: $PIGEN"
echo "  FIRST_USER_NAME: ${FIRST_USER_NAME}"

# Clone the Git repository
if [ ! -d "${CLONE_DIR}" ]; then
    git clone --branch ${GIT_BRANCH} ${GIT_REPO} ${CLONE_DIR}
fi
chmod 755 ${CLONE_DIR}

# Create necessary directories
[ ! -d /home/${FIRST_USER_NAME}/.local/bin ] && mkdir -p /home/${FIRST_USER_NAME}/.local/bin
[ ! -d /home/${FIRST_USER_NAME}/${RQB2_CONFDIR} ] && mkdir -p /home/${FIRST_USER_NAME}/${RQB2_CONFDIR}
[ ! -d /usr/config ] && mkdir -p /usr/config
[ ! -d /usr/venv ] && mkdir -p /usr/venv

# Set permissions
chmod -R 755 ${CLONE_DIR}/RQB2-bin 
chmod -R 755 ${CLONE_DIR}/RQB2-config

# Copy files to user directories
cp ${CLONE_DIR}/RQB2-bin/* /home/${FIRST_USER_NAME}/.local/bin/
cp -r ${CLONE_DIR}/RQB2-config/* /home/${FIRST_USER_NAME}/${RQB2_CONFDIR}/

# Copy files to system directories
cp ${CLONE_DIR}/RQB2-bin/* /usr/bin
cp -r ${CLONE_DIR}/RQB2-config/* /usr/config

# Set permissions on target directories
chmod 755 /home/${FIRST_USER_NAME}/.local/bin 
chmod 755 /home/${FIRST_USER_NAME}/${RQB2_CONFDIR}

# Apply RQB2 patch to /usr/bin/raspi-config at boot time
# Adding patch script to root-crontab 
bash -c 'CRON="@reboot sleep 2; /usr/bin/rq_patch_raspiconfig.sh"; \
  crontab -l 2>/dev/null | grep -Fqx "$CRON" || \
  ( crontab -l 2>/dev/null; printf "%s\n" "$CRON" ) | crontab -'

# Install Qiskit using pip
echo "Installing qiskit for ${FIRST_USER_NAME} user"
mkdir -p /home/${FIRST_USER_NAME}/$REPO/venv/$STD_VENV

# Create virtual environment
python3 -m venv /home/${FIRST_USER_NAME}/$REPO/venv/$STD_VENV --system-site-packages
source /home/${FIRST_USER_NAME}/$REPO/venv/$STD_VENV/bin/activate

# Install Qiskit
. /home/"${FIRST_USER_NAME}"/.local/bin/rq_install_Qiskit_latest.sh
deactivate

# Copy venv to system location for new users
cp -r /home/${FIRST_USER_NAME}/$REPO /usr/venv

# Add setup script to bashrc
export LINE=". /usr/config/setup_qiskit_env.sh"
echo "$LINE" >> /etc/skel/.bashrc
echo "$LINE" >> /home/${FIRST_USER_NAME}/.bashrc

echo "Qiskit installation completed for ${FIRST_USER_NAME}"

# Clean up
rm -rf $CLONE_DIR

echo "End qiskit Installation"