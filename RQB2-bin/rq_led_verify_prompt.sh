#!/bin/bash
# ============================================================================
# RasQberry: one-time LED layout verify trigger
# ============================================================================
# Shared entry point for the "is this your LED panel?" first-run check. Called
# at the first INTERACTIVE login so the user meets it however they arrive, but
# NEVER auto-started unattended at desktop boot (that raced ip-display for the
# LED GPIO and left a stuck console dialog - task #35):
#   - the raspi-config LED menu (do_select_led_option)
#   - login shells: /etc/profile.d/rasqberry-led-verify.sh (ssh, console login)
#   - desktop terminals: sourced from .bashrc (non-login interactive shells,
#     which skip /etc/profile.d)
# It self-disables: rq_led_setup_wizard.sh --verify persists
# LED_LAYOUT_VERIFIED=true once the user answers, after which this is a no-op.
# The wizard re-execs itself with sudo for GPIO, so this need not be root.

set +u
ENV_FILE="/usr/config/rasqberry_environment.env"

# Already verified -> nothing to do (self-disable).
if grep -q '^LED_LAYOUT_VERIFIED=true' "$ENV_FILE" 2>/dev/null; then
    exit 0
fi

WIZARD="/usr/bin/rq_led_setup_wizard.sh"
[ -x "$WIZARD" ] || exit 0

exec "$WIZARD" --verify
