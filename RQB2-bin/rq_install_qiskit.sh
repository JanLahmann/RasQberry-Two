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
    # --no-cache-dir: force pip to write files to dest (cached files aren't copied)
    # --only-binary :all:: skip source packages that need building (e.g., pygobject)
    # Filter out packages without ARM64 wheels (netifaces) - they'll be built from source during install
    if [ -f "$REQUIREMENTS_FILE" ]; then
        grep -v '^netifaces' "$REQUIREMENTS_FILE" > /tmp/requirements-wheels.txt
        pip download --no-cache-dir --dest="$WHEEL_DIR" --only-binary :all: \
            "$QISKIT_SPEC" -r /tmp/requirements-wheels.txt || true
        rm -f /tmp/requirements-wheels.txt
    else
        pip download --no-cache-dir --dest="$WHEEL_DIR" --only-binary :all: \
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

# Use --no-index when cache hit to skip network entirely (instant install)
# This is only used for dev builds; main/beta don't use wheel cache
if [ "$CACHE_HIT" = true ]; then
    echo "Using cached wheels only (--no-index for fast install)..."
    PIP_INDEX_OPTS="--no-index"
else
    echo "No wheel cache - will download from PyPI..."
    PIP_INDEX_OPTS=""
fi

# Filter out packages without wheels (netifaces) - they need PyPI access
if [ -f "$REQUIREMENTS_FILE" ]; then
    grep -v '^netifaces' "$REQUIREMENTS_FILE" > /tmp/requirements-install.txt
    pip install $PIP_INDEX_OPTS --prefer-binary --find-links="$WHEEL_DIR" \
        "$QISKIT_SPEC" -r /tmp/requirements-install.txt
    rm -f /tmp/requirements-install.txt
else
    echo "WARNING: Requirements file not found: $REQUIREMENTS_FILE"
    pip install $PIP_INDEX_OPTS --prefer-binary --find-links="$WHEEL_DIR" \
        "$QISKIT_SPEC" qiskit-ibm-runtime qiskit-aer
fi

# Install source-only packages separately (need PyPI access)
echo "Installing source-only packages (netifaces)..."
pip install --use-pep517 netifaces || true

# =============================================================================
# Verification
# =============================================================================

echo
echo "Installed Qiskit packages:"
pip3 list | grep -i qiskit || echo "No qiskit packages found"

echo
echo "Start Qiskit install: $STARTDATE"
echo "End   Qiskit install: $(date)"
