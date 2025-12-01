#!/bin/bash
#
# RasQberry: Auto-installing Fun-with-Quantum Demo Launcher
# Automatically installs demo if missing, then launches it
#

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Load common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load and verify environment
load_rqb2_env
verify_env_vars REPO USER_HOME BIN_DIR MARKER_FWQ

# Demo configuration
DEMO_NAME="fun-with-quantum"
DEMO_DIR=$(get_demo_dir "$DEMO_NAME")

# Check if demo is installed, auto-install if missing
if [ ! -f "$DEMO_DIR/$MARKER_FWQ" ]; then
    info "Fun-with-Quantum not found. Installing..."
    install_demo_raspiconfig do_fwq_install || die "Installation failed"
fi

# Launch the demo using the existing launcher
exec "$BIN_DIR/rq_fun_with_quantum.sh"
