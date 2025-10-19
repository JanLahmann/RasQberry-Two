#!/bin/sh
#set -eu # this causes terminal misbehaviour, as this file is sourced in bashrc

# Determine non-root user home directory
if [ -n "${SUDO_USER-}" ] && [ "${SUDO_USER}" != "root" ]; then
  USER_HOME="$(eval echo ~${SUDO_USER})"
else
  USER_HOME="${HOME}"
fi

# Default configuration directory
RQB2_CONFDIR="${RQB2_CONFDIR:-.local/config}"

# Path to environment file
ENV_FILE="${USER_HOME}/${RQB2_CONFDIR}/rasqberry_environment.env"

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