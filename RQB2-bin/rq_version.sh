#!/bin/bash
#
# Display RasQberry version information
#

VERSION_FILE="/etc/rasqberry-version"

if [ -f "$VERSION_FILE" ]; then
  echo "RasQberry Version: $(cat $VERSION_FILE)"
else
  echo "RasQberry Version: Unknown (version file not found)"
  exit 1
fi
