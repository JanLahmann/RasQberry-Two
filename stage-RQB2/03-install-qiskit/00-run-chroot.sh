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

# Create virtual environment (isolated, without --system-site-packages)
# This avoids "Can't uninstall" warnings from pip when system packages conflict
python3 -m venv /home/${FIRST_USER_NAME}/$REPO/venv/$STD_VENV

# Symlink GTK/Cairo bindings into venv (can't be pip-installed, need system versions)
VENV_SITE=$("/home/${FIRST_USER_NAME}/$REPO/venv/$STD_VENV/bin/python3" -c "import site; print(site.getsitepackages()[0])")
echo "Symlinking GTK bindings into venv..."
ln -sf /usr/lib/python3/dist-packages/gi "$VENV_SITE/"
ln -sf /usr/lib/python3/dist-packages/cairo "$VENV_SITE/"
# Include egg-info for proper package detection
for egg in /usr/lib/python3/dist-packages/PyGObject-*.egg-info; do
    [ -e "$egg" ] && ln -sf "$egg" "$VENV_SITE/"
done
for egg in /usr/lib/python3/dist-packages/pycairo-*.egg-info; do
    [ -e "$egg" ] && ln -sf "$egg" "$VENV_SITE/"
done

# Qt for GUI demos (LED Painter, matplotlib's Qt backend): the system PyQt5.
# PySide6/PyQt wheels from pip bundle a Qt that crashes with a bus error on the
# Pi 5 kernel (16 KB pages), #302.
ln -sfn /usr/lib/python3/dist-packages/PyQt5 "$VENV_SITE/PyQt5"
for meta in /usr/lib/python3/dist-packages/PyQt5-*.dist-info /usr/lib/python3/dist-packages/PyQt5_sip-*.egg-info; do
    [ -e "$meta" ] && ln -sf "$meta" "$VENV_SITE/"
done

# Install Qiskit using consolidated script (scripts are now in /usr/bin)
# The script handles venv activation based on PIGEN environment variable
. /usr/bin/rq_install_qiskit.sh latest
deactivate

# Pip cache will be saved by 01-run.sh and cleaned by 02-run.sh
# No action needed here - cache remains in place for now
echo "Pip cache will be managed by post-install scripts"
echo "Pip cache location: /root/.cache/pip"
echo "Pip cache size: $(du -sh /root/.cache/pip 2>/dev/null | cut -f1 || echo 'N/A')"

# Venv extras for learners' own programs (B10): 00-rasqberry.pth makes the
# RasQberry Python modules in /usr/bin (rq_led_utils, ...) importable and keeps
# root runs from writing bytecode into the venv; a Jupyter setting stops
# `jupyter notebook` from loading the JupyterLab extension it cannot run.
# Installed before the copy below, so a venv recreated from the template
# (setup_qiskit_env.sh) has them too.
/usr/bin/rq_learner_setup.sh --venv-only "/home/${FIRST_USER_NAME}/$REPO/venv/$STD_VENV"

# Copy venv to system location for new users
cp -r /home/${FIRST_USER_NAME}/$REPO /usr/venv

# Add setup script to bashrc
export LINE=". /usr/config/setup_qiskit_env.sh"
grep -qxF "$LINE" /etc/skel/.bashrc || echo "$LINE" >> /etc/skel/.bashrc
grep -qxF "$LINE" /home/${FIRST_USER_NAME}/.bashrc || echo "$LINE" >> /home/${FIRST_USER_NAME}/.bashrc

# Fix ownership of venv and bashrc created/modified as root
chown -R ${FIRST_USER_NAME}:${FIRST_USER_NAME} /home/${FIRST_USER_NAME}/$REPO
chown ${FIRST_USER_NAME}:${FIRST_USER_NAME} /home/${FIRST_USER_NAME}/.bashrc

# First user's learner setup (B10): Thonny and Geany run programs with the venv,
# ~/My-Quantum-Programs gets the starter programs. Run as that user, so the
# files are theirs. Not needed for the image to work: on failure the build
# goes on, and the autostart entry rasqberry-learner-setup.desktop repeats the
# setup at the first desktop login.
runuser -u "${FIRST_USER_NAME}" -- env HOME="/home/${FIRST_USER_NAME}" /usr/bin/rq_learner_setup.sh \
    || echo "WARNING: learner setup for ${FIRST_USER_NAME} failed; it runs again at the first desktop login"

echo "Qiskit installation completed for ${FIRST_USER_NAME}"
