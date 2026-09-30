#!/bin/sh
#set -eu # this causes terminal misbehaviour, as this file is sourced in bashrc

# Determine non-root user home directory
if [ -n "${SUDO_USER-}" ] && [ "${SUDO_USER}" != "root" ]; then
  USER_HOME="$(eval echo ~${SUDO_USER})"
elif [ -n "${HOME-}" ]; then
  USER_HOME="${HOME}"
else
  # No HOME at all: systemd units and cron jobs run this way. Fall back to the
  # primary desktop user (uid 1000) so per-user config such as the external
  # demo manifests still resolves, then to /root. Without this, callers that
  # run under `set -u` (rasqberry-demo-cache.service) died on "HOME: unbound".
  USER_HOME="$(getent passwd 1000 2>/dev/null | cut -d: -f6)"
  [ -n "${USER_HOME}" ] || USER_HOME="/root"
fi

# Path to global system-wide environment file
ENV_FILE="/usr/config/rasqberry_environment.env"

# Load environment variables from env file
if [ -f "${ENV_FILE}" ]; then
  set -a
  . "${ENV_FILE}"
  set +a
else
  echo >&2 "ERROR: Missing config file at ${ENV_FILE}"
  # Return non-zero instead of exit when sourced to prevent killing parent shell
  return 1 2>/dev/null || exit 1
fi

# Set BIN_DIR to system-wide bin directory (all RasQberry scripts are in /usr/bin)
BIN_DIR="/usr/bin"
export BIN_DIR