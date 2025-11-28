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

# =============================================================================
# Wheel Cache Setup
# =============================================================================
# Use cached wheels for instant installation (no download needed)
# Wheels are stored in /tmp/wheels during pi-gen build

WHEEL_DIR="/tmp/wheels"

if [ -d "$WHEEL_DIR" ] && [ -n "$(ls -A $WHEEL_DIR/*.whl 2>/dev/null)" ]; then
    WHEEL_COUNT=$(find "$WHEEL_DIR" -name "*.whl" | wc -l)
    echo "Found $WHEEL_COUNT cached wheels in $WHEEL_DIR"
    CACHE_HIT=true
else
    echo "No wheel cache found - will download wheels first"
    CACHE_HIT=false
    mkdir -p "$WHEEL_DIR"
fi

# =============================================================================
# Download wheels (cache miss only)
# =============================================================================
# On first build, download all wheels to cache directory
# This is faster than pip wheel (no compilation) and creates reusable cache

if [ "$CACHE_HIT" = false ] && [ "${PIGEN:-false}" == "true" ]; then
    echo ""
    echo "Downloading wheels to cache (first build)..."

    # Download all wheels including dependencies
    # Use --no-cache-dir to force pip to write files to dest (cached files aren't copied)
    if [ -f "$REQUIREMENTS_FILE" ]; then
        pip download --no-cache-dir --dest="$WHEEL_DIR" --prefer-binary \
            "$QISKIT_SPEC" -r "$REQUIREMENTS_FILE" || true
    else
        pip download --no-cache-dir --dest="$WHEEL_DIR" --prefer-binary \
            "$QISKIT_SPEC" qiskit-ibm-runtime qiskit-aer || true
    fi

    WHEEL_COUNT=$(find "$WHEEL_DIR" -name "*.whl" 2>/dev/null | wc -l)
    echo "Downloaded $WHEEL_COUNT wheels to cache"
fi

# =============================================================================
# Installation
# =============================================================================

# Pre-install packages that need --use-pep517 (legacy setup.py)
echo "Pre-installing hardware dependencies with PEP 517..."
pip install --use-pep517 --prefer-binary --find-links="$WHEEL_DIR" \
    sysv_ipc RPi.GPIO rpi_ws281x || true

# Install everything from wheel cache (or download if not cached)
echo "Installing $QISKIT_SPEC and additional packages..."
if [ -f "$REQUIREMENTS_FILE" ]; then
    pip install --prefer-binary --find-links="$WHEEL_DIR" \
        "$QISKIT_SPEC" -r "$REQUIREMENTS_FILE"
else
    echo "WARNING: Requirements file not found: $REQUIREMENTS_FILE"
    pip install --prefer-binary --find-links="$WHEEL_DIR" \
        "$QISKIT_SPEC" qiskit-ibm-runtime qiskit-aer
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
