#!/bin/bash
#
# RasQberry: Auto-installing IBM Quantum Tutorials Launcher
# Automatically installs demo if missing, then launches it
#
# Content licensed under CC BY-SA 4.0 by IBM/Qiskit
# Source: https://github.com/Qiskit/documentation
#

set -euo pipefail

# Load common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load and verify environment
load_rqb2_env
verify_env_vars REPO USER_HOME BIN_DIR MARKER_IBM_TUTORIALS

# Demo configuration
DEMO_NAME="ibm-quantum-learning"
DEMO_DIR="$USER_HOME/$REPO/demos/$DEMO_NAME"

# Check if demo is installed, auto-install if missing
if [ ! -f "$DEMO_DIR/$MARKER_IBM_TUTORIALS" ]; then
    info "IBM Quantum Tutorials not found. Installing..."
    install_demo_raspiconfig do_ibm_tutorials_install || die "Installation failed"
fi

# Launch the demo using the existing launcher
exec "$BIN_DIR/rq_ibm_tutorials.sh"
