#!/bin/bash
set -euo pipefail

################################################################################
# qoffee-setup.sh - RasQberry Qoffee-Maker Setup
#
# Description:
#   Sets up Qoffee-Maker demo (Docker + repository + configuration)
#   Calls docker-setup.sh for Docker installation/permissions
#   Clones repository and creates configuration file
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

echo
echo "=== Qoffee-Maker Setup ==="
echo

# Load environment and verify required variables
load_rqb2_env
verify_env_vars USER_HOME REPO BIN_DIR GIT_REPO_DEMO_QOFFEE

DEMO_DIR="$USER_HOME/$REPO/demos/Qoffee-Maker"

################################################################################
# Docker setup (install, permissions, networking)
################################################################################

# Run generic Docker setup
"${SCRIPT_DIR}/docker-setup.sh" || exit 1

################################################################################
# Clone Qoffee-Maker repository
################################################################################

# Clone Qoffee-Maker repository if needed
# Check for marker file (qoffee.ipynb) to verify successful installation
if [ ! -f "$DEMO_DIR/qoffee.ipynb" ]; then
    echo
    info "Cloning Qoffee-Maker repository..."

    if ! clone_demo "$GIT_REPO_DEMO_QOFFEE" "$DEMO_DIR"; then
        # Clean up incomplete directory and show error
        rm -rf "$DEMO_DIR"
        show_msgbox "Clone Error" "Failed to clone Qoffee-Maker repository.\n\nPlease check your internet connection."
        die "Failed to clone Qoffee-Maker repository"
    fi
    info "Qoffee-Maker repository cloned"
else
    info "Qoffee-Maker repository already exists"

    # Update repository
    info "Updating Qoffee-Maker repository..."
    cd "$DEMO_DIR" && git pull --quiet origin main 2>/dev/null || true
    cd "$USER_HOME" || die "Failed to return to home directory"
fi

################################################################################
# Create configuration file
################################################################################

# Create .env configuration file if needed
ENV_FILE="$DEMO_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo
    info "Creating configuration file..."

    # Check if env-template exists
    if [ -f "$DEMO_DIR/env-template" ]; then
        cp "$DEMO_DIR/env-template" "$ENV_FILE"
    else
        # Create default .env if template missing
        cat > "$ENV_FILE" << 'ENVEOF'
# Home Connect API Configuration
# Register at: https://developer.home-connect.com/
HOMECONNECT_API_URL=https://simulator.home-connect.com/
HOMECONNECT_CLIENT_ID=your_client_id_here
HOMECONNECT_CLIENT_SECRET=your_client_secret_here
HOMECONNECT_REDIRECT_URL=http://localhost:8887/auth/callback
DEVICE_HA_ID=

# IBM Quantum API Key
# Get your key at: https://quantum-computing.ibm.com/account
IBMQ_API_KEY=your_ibmq_api_key_here

# Jupyter Token (change for security)
JUPYTER_TOKEN=super-secret-token
ENVEOF
    fi

    # Fix ownership to user (not root)
    USER_NAME=$(get_user_name)
    sudo chown "$USER_NAME":"$USER_NAME" "$ENV_FILE"

    info "Configuration file created: $ENV_FILE"
    echo
    warn "CONFIGURATION REQUIRED!"
    echo
    echo "Before using Qoffee-Maker, you must configure:"
    echo "  1. Home Connect Developer Account"
    echo "     → https://developer.home-connect.com/"
    echo "  2. IBM Quantum Account"
    echo "     → https://quantum-computing.ibm.com/account"
    echo
    echo "Edit: $ENV_FILE"
    echo

    # Skip interactive dialog in auto-install mode
    if [ "${RQ_AUTO_INSTALL:-0}" != "1" ]; then
        if show_yesno "Edit Configuration?" \
            "Configuration file created at:\n$ENV_FILE\n\nYou need to add your API credentials:\n• Home Connect Client ID & Secret\n• IBM Quantum API Key\n\nWould you like to edit it now?"; then
            ${EDITOR:-nano} "$ENV_FILE"
        fi
    else
        info "Skipping credentials setup (auto-install mode)"
    fi
else
    info "Configuration file exists: $ENV_FILE"
fi

################################################################################
# Complete setup
################################################################################

echo
echo "=== Setup Complete ==="
echo
echo "Qoffee-Maker is ready to use!"
echo "You can now run it from:"
echo "  • RasQberry menu → Quantum Demos → Qoffee-Maker"
echo "  • Desktop shortcut"
echo "  • Command line: $BIN_DIR/qoffee-maker.sh"
echo

# Update environment variable
update_env_var "QOFFEE_MAKER_INSTALLED" "true"

exit 0
