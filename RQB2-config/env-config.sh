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
  exit 1
fi