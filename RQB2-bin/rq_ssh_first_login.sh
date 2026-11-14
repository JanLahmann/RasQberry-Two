#!/bin/bash
# ============================================================================
# RasQberry: SSH first login with the published demo password
# ============================================================================
# sshd's ForceCommand for the desktop user while that account still has the
# published demo password (rq_ssh_window.sh writes the drop-in, and removes it
# once the password is changed). A login with an SSH key goes straight
# through; a login with the password sets a new password first, then gets its
# shell or command. Runs as the user who logged in.

run_original() {
    if [ -n "${SSH_ORIGINAL_COMMAND:-}" ]; then
        exec "${SHELL:-/bin/bash}" -c "$SSH_ORIGINAL_COMMAND"
    fi
    exec "${SHELL:-/bin/bash}" -l
}

# ExposeAuthInfo: SSH_USER_AUTH lists how this session logged in
if [ -n "${SSH_USER_AUTH:-}" ] && grep -q '^publickey ' "$SSH_USER_AUTH" 2>/dev/null; then
    run_original
fi

if [ ! -t 0 ]; then
    echo "This RasQberry still has the published password. Log in in a terminal (ssh -t) and set a new one first." >&2
    exit 1
fi

cat <<'EOF'

This RasQberry still has the published password: anyone on your network could
log in with it. Set your own password now (first the current one, Qiskit1!,
then the new one twice). It is also the password for VNC and sudo.

EOF
if passwd; then
    echo
    echo "Done: from now on, log in with your new password."
    run_original
fi
echo "The password was not changed: log in again to retry." >&2
exit 1
