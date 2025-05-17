#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Determine non-root user home directory
if [ -n "${SUDO_USER-}" ] && [ "${SUDO_USER}" != "root" ]; then
  USER_HOME="$(eval echo ~${SUDO_USER})"
else
  USER_HOME="${HOME}"
fi

# Default configuration directory
RQB2_CONFDIR="${RQB2_CONFDIR:-.local/config}"

# Path to environment file
CONFIG_FILE="${USER_HOME}/${RQB2_CONFDIR}/rasqberry_environment.env"

# Load environment variables from env file
if [ -f "${CONFIG_FILE}" ]; then
  set -a
  source "${CONFIG_FILE}"
  set +a
else
  echo >&2 "ERROR: Missing config file at ${CONFIG_FILE}"
  exit 1
fi