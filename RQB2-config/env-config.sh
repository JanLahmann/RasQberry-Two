#!/bin/sh
#set -eu # this causes terminal misbehaviour, as this file is sourced in bashrc

# Determine non-root user home directory (for BIN_DIR calculation)
if [ -n "${SUDO_USER-}" ] && [ "${SUDO_USER}" != "root" ]; then
  USER_HOME="$(eval echo ~${SUDO_USER})"
else
  USER_HOME="${HOME}"
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

# Set BIN_DIR to user's local bin directory
BIN_DIR="${USER_HOME}/.local/bin"
export BIN_DIR