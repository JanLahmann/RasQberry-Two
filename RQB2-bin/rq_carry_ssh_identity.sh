#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: keep the SSH identity across an A/B slot update (#275)
# ============================================================================
# Description: Each slot has its own root filesystem, so a slot written by
#   rq_update_slot.sh came up with a new SSH host key (clients refuse with
#   "REMOTE HOST IDENTIFICATION HAS CHANGED") and without the user's
#   authorized_keys (key login fails). This copies both from the running slot
#   into the freshly written target root, device to device, at update time.
#   Nothing is baked into the published image: every device still generates
#   its own keys on its first boot.
#
#   Carried over, and nothing else: /etc/ssh/ssh_host_* and the desktop
#   user's ~/.ssh/authorized_keys.
#
#   The stock regenerate_ssh_host_keys.service deletes all host keys on the
#   first boot of a flashed image, unconditionally; it is masked in the target
#   so the copied keys survive. A later package upgrade cannot re-enable a
#   masked unit.
#
# Usage: rq_carry_ssh_identity.sh <mounted-target-root>   (as root)
# Called by rq_update_slot.sh; a failure there is a warning, not an abort.
#
# Environment overrides (tests): RQ_SSH_SOURCE_ROOT (default /),
#   RQ_SSH_USER_HOME (default: home of uid 1000)

target="${1:-}"
[ -n "$target" ] && [ -d "$target/etc" ] || { echo "Usage: $(basename "$0") <mounted-target-root>" >&2; exit 2; }
src="${RQ_SSH_SOURCE_ROOT:-}"
home="${RQ_SSH_USER_HOME:-$(getent passwd 1000 2>/dev/null | cut -d: -f6)}"
carried=""

# Host keys
if compgen -G "$src/etc/ssh/ssh_host_*_key" >/dev/null && [ -d "$target/etc/ssh" ]; then
    rm -f "$target"/etc/ssh/ssh_host_*
    cp -p "$src"/etc/ssh/ssh_host_* "$target/etc/ssh/"
    chmod 600 "$target"/etc/ssh/ssh_host_*_key
    chmod 644 "$target"/etc/ssh/ssh_host_*_key.pub
    mkdir -p "$target/etc/systemd/system"
    ln -sfn /dev/null "$target/etc/systemd/system/regenerate_ssh_host_keys.service"
    rm -f "$target/etc/systemd/system/multi-user.target.wants/regenerate_ssh_host_keys.service"
    carried="host keys"
fi

# The user's authorized_keys
if [ -n "$home" ] && [ -s "$src$home/.ssh/authorized_keys" ] && [ -d "$target$home" ]; then
    mkdir -p "$target$home/.ssh"
    cp "$src$home/.ssh/authorized_keys" "$target$home/.ssh/authorized_keys"
    chmod 700 "$target$home/.ssh"
    chmod 600 "$target$home/.ssh/authorized_keys"
    if [ "$(id -u)" = "0" ]; then
        owner=$(stat -c %u:%g "$target$home")
        chown "$owner" "$target$home/.ssh" "$target$home/.ssh/authorized_keys"
    fi
    carried="${carried:+$carried and }authorized_keys"
fi

echo "SSH identity carried over: ${carried:-nothing (no host keys or authorized_keys found)}"
