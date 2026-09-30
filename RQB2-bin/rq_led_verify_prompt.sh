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

# Is anyone actually looking?
#
# "Interactive shell with a controlling terminal" does not mean a person is
# there. The image logs itself in on tty1 at boot (/bin/login -f) and that shell
# is interactive with a real tty, so it passed every guard our callers apply:
# the dialog fired on tty1 at EVERY boot, underneath the desktop where nobody
# could see it, and sat unanswered for the whole session. While it waits it
# holds the LED renderer, so every LED demo the user then starts dies on "GPIO
# busy" against a dark panel - which is what made LED demos look broken.
#
# A person arrives over ssh, or opens a terminal on the desktop: both are pts.
# The boot console is a VT (/dev/tty1). Only ask where an answer can come back.
# (This check is here, not in the callers, so the profile.d hook and the .bashrc
# hook are both covered by one rule.) The LED menu calls the wizard directly and
# is unaffected.
case "$(tty 2>/dev/null)" in
    /dev/pts/*) : ;;
    *)          exit 0 ;;
esac

WIZARD="/usr/bin/rq_led_setup_wizard.sh"
[ -x "$WIZARD" ] || exit 0

exec "$WIZARD" --verify
