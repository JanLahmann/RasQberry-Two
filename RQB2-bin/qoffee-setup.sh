#!/bin/bash
set -euo pipefail

################################################################################
# qoffee-setup.sh - RasQberry Qoffee-Maker Setup
#
# Description:
#   Sets up Qoffee-Maker demo (repository + configuration)
#   Fetches the notebooks at the pinned commit and creates the settings file
#   Docker is installed and configured at image build time
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

echo
echo "=== Qoffee-Maker Setup ==="
echo

# Load environment and verify required variables
load_rqb2_env
verify_env_vars USER_HOME REPO BIN_DIR

DEMO_DIR="$USER_HOME/$REPO/demos/Qoffee-Maker"
SRC_URL="$(rq_demo_repo qoffee-maker)"
SRC_REF="$(rq_demo_ref qoffee-maker)"
[ -n "$SRC_URL" ] && [ -n "$SRC_REF" ] \
    || die "The Qoffee-Maker demo description (manifest) names no pinned source."

################################################################################
# The Qoffee-Maker notebooks, at the commit pinned for this release (Q32)
################################################################################
if [ ! -f "$DEMO_DIR/qoffee.ipynb" ]; then
    info "Downloading the Qoffee-Maker notebooks (commit ${SRC_REF:0:7})..."
    rq_remove_tree "$DEMO_DIR" || die "An earlier, incomplete download is in the way: $DEMO_DIR"
    fetch_pinned_repo "$SRC_URL" "$SRC_REF" "$DEMO_DIR" \
        || die "Could not download the Qoffee-Maker notebooks from $SRC_URL"
else
    info "Qoffee-Maker notebooks are there"
fi

################################################################################
# Settings file (.env). The credentials are optional (R-037).
################################################################################
ENV_FILE="$DEMO_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$DEMO_DIR/env-template" ]; then
        cp "$DEMO_DIR/env-template" "$ENV_FILE"
    else
        cat > "$ENV_FILE" << 'ENVEOF'
HOMECONNECT_API_URL=https://simulator.home-connect.com/
HOMECONNECT_CLIENT_ID=your_client_id_here
HOMECONNECT_CLIENT_SECRET=your_client_secret_here
HOMECONNECT_REDIRECT_URL=http://localhost:8887/auth/callback
DEVICE_HA_ID=
IBMQ_API_KEY=your_ibmq_api_key_here
JUPYTER_TOKEN=super-secret-token
ENVEOF
    fi
    fix_root_ownership "$ENV_FILE" >/dev/null 2>&1 || true
    info "Settings file created: $ENV_FILE"
    echo
    echo "Qoffee-Maker opens without any accounts. To brew with a real coffee"
    echo "machine, add your Home Connect credentials (developer.home-connect.com)"
    echo "to $ENV_FILE"
    echo
    if [ "${RQ_AUTO_INSTALL:-0}" != "1" ] && [ -t 0 ]; then
        if whiptail --title "Qoffee-Maker settings" --defaultno --yesno \
            "Qoffee-Maker opens without any accounts.\n\nTo brew with a real coffee machine it needs your Home Connect credentials (developer.home-connect.com) in:\n$ENV_FILE\n\nEdit the settings file now?" 14 70; then
            ${EDITOR:-nano} "$ENV_FILE"
        fi
    fi
fi

update_env_var "QOFFEE_MAKER_INSTALLED" "true"
exit 0
