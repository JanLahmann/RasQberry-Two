# RasQberry: offer the one-time LED-layout verify on the FIRST interactive login.
# Installed to /etc/profile.d/. Heavily guarded so it NEVER fires for
# non-interactive sessions (scp, rsync, `ssh host <cmd>`, cron, scripts) - only
# a real interactive login shell with a controlling terminal. Self-disables once
# LED_LAYOUT_VERIFIED=true (checked inside rq_led_verify_prompt.sh).

# Interactive shells only.
case $- in
    *i*) : ;;
    *)   return 0 2>/dev/null || exit 0 ;;
esac

# Real terminal on both ends, once per shell, tool present.
# (The "is anyone actually looking?" test lives in rq_led_verify_prompt.sh, so
# that it covers this hook and the .bashrc one from a single place.)
if [ -t 0 ] && [ -t 1 ] && [ -z "${_RQ_LED_VERIFY_DONE:-}" ] && [ -x /usr/bin/rq_led_verify_prompt.sh ]; then
    export _RQ_LED_VERIFY_DONE=1
    /usr/bin/rq_led_verify_prompt.sh </dev/tty >/dev/tty 2>&1 || true
fi
