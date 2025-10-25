#!/bin/bash
#
# RasQberry: Auto-installing Grok Bloch Sphere Demo Launcher
# Automatically installs demo if missing, then launches it
#

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Load common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load and verify environment
load_rqb2_env
verify_env_vars REPO USER_HOME BIN_DIR

# Demo configuration
DEMO_NAME="grok-bloch"
DEMO_DIR=$(get_demo_dir "$DEMO_NAME")

# Check if demo is installed, auto-install if missing
if [ ! -f "$DEMO_DIR/index.html" ]; then
    info "Grok Bloch demo not found. Installing..."
    install_demo_raspiconfig do_grok_bloch_install || die "Installation failed"
fi

# Launch the demo using the existing launcher
exec "$BIN_DIR/rq_grok_bloch.sh"
