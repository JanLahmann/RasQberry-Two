# RasQberry: offer any pending setup steps on the first interactive login.
# Installed to /etc/profile.d/, and sourced from .bashrc too (desktop terminals
# are non-login interactive shells and skip /etc/profile.d).
#
# Heavily guarded so it NEVER fires for non-interactive sessions (scp, rsync,
# `ssh host <cmd>`, cron, scripts). The "is anyone actually looking?" test - and
# the list of steps - live in rq_firstlogin.sh, so this hook and the .bashrc one
# share one rule. The checklist opens by itself only once per user (Q12): here
# for an SSH or console login, in its own window for the desktop
# (/etc/xdg/autostart/rasqberry-setup-checklist.desktop); a desktop terminal
# leaves it to that window. After that it exits at once.

# Interactive shells only.
case $- in
    *i*) : ;;
    *)   return 0 2>/dev/null || exit 0 ;;
esac

# Real terminal on both ends, once per shell, tool present.
# One line when the daily check (rasqberry-update-check.timer) found a newer
# release for this Pi (#139, #242): rq_release_notice.py writes it with the
# rules of the desktop notice (grace period, staged rollout, withdrawn
# releases, both slots); silent otherwise.
if [ -t 1 ] && [ -z "${_RQ_FIRSTLOGIN_DONE:-}" ] && [ -s /var/lib/rasqberry/update-notice ]; then
    head -n 1 /var/lib/rasqberry/update-notice 2>/dev/null || true
fi

if [ -t 0 ] && [ -t 1 ] && [ -z "${_RQ_FIRSTLOGIN_DONE:-}" ] && [ -x /usr/bin/rq_firstlogin.sh ]; then
    export _RQ_FIRSTLOGIN_DONE=1
    /usr/bin/rq_firstlogin.sh </dev/tty >/dev/tty 2>&1 || true
fi
