# RasQberry: offer any pending setup steps on the first interactive login.
# Installed to /etc/profile.d/, and sourced from .bashrc too (desktop terminals
# are non-login interactive shells and skip /etc/profile.d).
#
# Heavily guarded so it NEVER fires for non-interactive sessions (scp, rsync,
# `ssh host <cmd>`, cron, scripts). The "is anyone actually looking?" test - and
# the list of steps - live in rq_firstlogin.sh, so this hook and the .bashrc one
# share one rule. It says nothing when nothing is pending, and self-disables once
# the steps are done or dismissed.

# Interactive shells only.
case $- in
    *i*) : ;;
    *)   return 0 2>/dev/null || exit 0 ;;
esac

# Real terminal on both ends, once per shell, tool present.
if [ -t 0 ] && [ -t 1 ] && [ -z "${_RQ_FIRSTLOGIN_DONE:-}" ] && [ -x /usr/bin/rq_firstlogin.sh ]; then
    export _RQ_FIRSTLOGIN_DONE=1
    /usr/bin/rq_firstlogin.sh </dev/tty >/dev/tty 2>&1 || true
fi
