#!/usr/bin/env bash
# =============================================================================
# RasQberry Qiskit Installation Script
# =============================================================================
# Consolidated script for installing Qiskit (replaces multiple version scripts)
#
# Usage: rq_install_qiskit.sh [VERSION]
#   VERSION: latest (default), 1.0, 1.1
#
# Related issues: #32, #127, #149
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

VERSION="${1:-latest}"

# =============================================================================
# Environment Setup
# =============================================================================

# Check if running in pi-gen build environment
if [ "${PIGEN:-false}" == "true" ]; then
    # Running in pi-gen: use build-time paths
    echo "Running in pi-gen build environment"
    . /home/"${FIRST_USER_NAME}"/$REPO/venv/$STD_VENV/bin/activate
    REQUIREMENTS_FILE="/usr/config/qiskit-requirements.txt"
else
    # Running on live system: load environment variables
    . /usr/config/rasqberry_env-config.sh
    . "$HOME/$REPO/venv/$STD_VENV/bin/activate"
    REQUIREMENTS_FILE="/usr/config/qiskit-requirements.txt"
fi

# =============================================================================
# Installation
# =============================================================================

export STARTDATE=$(date)
echo
echo "=========================================="
echo "Installing Qiskit (version: $VERSION)"
echo "=========================================="
echo

# Determine qiskit version constraint
case "$VERSION" in
    latest)
        QISKIT_SPEC="qiskit[all]"
        ;;
    1.0)
        QISKIT_SPEC="qiskit[all]==1.0.*"
        ;;
    1.1)
        QISKIT_SPEC="qiskit[all]==1.1.*"
        ;;
    *)
        echo "ERROR: Unknown version: $VERSION"
        echo "Supported versions: latest, 1.0, 1.1"
        exit 1
        ;;
esac

# Pre-install packages that need --use-pep517 (legacy setup.py)
# These are dependencies of hardware packages (adafruit-blinka, etc.)
# Installing them first with --use-pep517 avoids deprecation warnings
echo "Pre-installing hardware dependencies with PEP 517..."
pip install --use-pep517 --prefer-binary sysv_ipc RPi.GPIO rpi_ws281x || true

# Install everything in one pip call for proper version resolution
# This ensures qiskit version constraint is respected by all packages
echo "Installing $QISKIT_SPEC and additional packages..."
if [ -f "$REQUIREMENTS_FILE" ]; then
    # Combine qiskit spec with requirements file
    pip install --prefer-binary "$QISKIT_SPEC" -r "$REQUIREMENTS_FILE"
else
    echo "WARNING: Requirements file not found: $REQUIREMENTS_FILE"
    echo "Installing minimal packages..."
    pip install --prefer-binary "$QISKIT_SPEC" qiskit-ibm-runtime qiskit-aer
fi

# =============================================================================
# Verification
# =============================================================================

echo
echo "Installed Qiskit packages:"
pip3 list | grep -i qiskit || echo "No qiskit packages found"

echo
echo "Start Qiskit install: $STARTDATE"
echo "End   Qiskit install: $(date)"
