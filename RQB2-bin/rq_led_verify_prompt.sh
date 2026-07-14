#!/bin/bash
# ============================================================================
# RasQberry: one-time LED layout verify trigger
# ============================================================================
# Shared entry point for the "is this your LED panel?" first-run check. Called
# from three places so the user meets it however they arrive:
#   - the raspi-config LED menu (do_select_led_option)
#   - an interactive first login (/etc/profile.d/rasqberry-led-verify.sh)
#   - desktop autostart on first boot (/etc/xdg/autostart/)
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
