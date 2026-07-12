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
# One pip call per package: a single failing package must not abort the rest
# of the list (a combined call with || true shipped an image without any LED
# backend). Failures are reported here and enforced by the verification below.
echo "Pre-installing hardware dependencies with PEP 517..."
# Array, not a space-separated string: this script sets IFS to newline+tab,
# so an unquoted string expansion does NOT split on spaces (caused the
# 2026-07-12 build failure: all five names reached pip as one requirement,
# which the post-install verification correctly caught).
HW_PACKAGES=(sysv_ipc RPi.GPIO rpi_ws281x lgpio Adafruit-Blinka-Raspberry-Pi5-Neopixel)
for pkg in "${HW_PACKAGES[@]}"; do
    if ! pip install --use-pep517 --prefer-binary --find-links="$WHEEL_DIR" "$pkg"; then
        echo "WARNING: failed to install hardware dependency: $pkg"
    fi
done

# Pre-install source-only packages that are dependencies of cached packages
# These need PyPI access and must be installed before --no-index install
echo "Pre-installing source-only dependencies..."
pip install --prefer-binary docplex netifaces || true

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

# Note: source-only packages (docplex, netifaces) are pre-installed above

# =============================================================================
# Verification
# =============================================================================

echo
echo "Installed Qiskit packages:"
pip3 list | grep -i qiskit || echo "No qiskit packages found"

# Verify the LED/hardware backends are actually importable. find_spec checks
# installation without executing module code (imports that probe hardware
# would fail in the qemu chroot). A missing backend means broken LED demos
# on the finished image, so this is a hard build failure.
echo
echo "Verifying LED/hardware backend modules..."
MISSING_MODULES=""
for mod in rpi_ws281x lgpio adafruit_raspberry_pi5_neopixel_write neopixel board; do
    if python3 -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$mod') else 1)"; then
        echo "  OK: $mod"
    else
        echo "  MISSING: $mod"
        MISSING_MODULES="$MISSING_MODULES $mod"
    fi
done
if [ -n "$MISSING_MODULES" ]; then
    echo "ERROR: required hardware modules missing from venv:$MISSING_MODULES"
    exit 1
fi

echo
echo "Start Qiskit install: $STARTDATE"
echo "End   Qiskit install: $(date)"
