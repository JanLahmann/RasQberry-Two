#!/bin/bash -e

echo "Installing desktop bookmarks"

# Source the configuration file
if [ -f "/tmp/stage-config" ]; then
    . /tmp/stage-config
    rm -f /tmp/stage-config
    
    # Map the RQB_ prefixed variables to local names
    REPO="${RQB_REPO}"
    FIRST_USER_NAME="${RQB_FIRST_USER_NAME:-rasqberry}"
    
    echo "Configuration loaded successfully"
else
    echo "ERROR: config file not found"
    exit 1
fi

export CLONE_DIR="/tmp/${REPO}"

echo "Installing desktop bookmarks for user: ${FIRST_USER_NAME}"

# Create icon directory
mkdir -p /usr/share/icons/rasqberry

# Copy all icons from desktop-icons directory
if [ -d "${CLONE_DIR}/desktop-icons" ]; then
    for icon_file in "${CLONE_DIR}/desktop-icons"/*.png; do
        if [ -f "$icon_file" ]; then
            cp "$icon_file" /usr/share/icons/rasqberry/
            chmod 644 "/usr/share/icons/rasqberry/$(basename "$icon_file")"
            echo "Installed icon: $(basename "$icon_file")"
        fi
    done
else
    echo "WARNING: Desktop icons directory not found"
fi

# Install desktop files to system applications menu
mkdir -p /usr/share/applications

# Copy desktop bookmark files
if [ -d "${CLONE_DIR}/RQB2-config/desktop-bookmarks" ]; then
    for desktop_file in "${CLONE_DIR}/RQB2-config/desktop-bookmarks"/*.desktop; do
        if [ -f "$desktop_file" ]; then
            cp "$desktop_file" /usr/share/applications/
            chmod 644 "/usr/share/applications/$(basename "$desktop_file")"
            echo "Installed: $(basename "$desktop_file")"
        fi
    done
else
    echo "WARNING: Desktop bookmarks directory not found"
fi

# Install to new user template (so new users get desktop shortcuts)
mkdir -p /etc/skel/Desktop

# Copy desktop files to skel for new users
for desktop_file in /usr/share/applications/*.desktop; do
    if [ -f "$desktop_file" ] && [[ "$(basename "$desktop_file")" =~ ^(composer|grok-bloch|grok-bloch-web)\.desktop$ ]]; then
        cp "$desktop_file" /etc/skel/Desktop/
        chmod 644 "/etc/skel/Desktop/$(basename "$desktop_file")"
        echo "Added to new user template: $(basename "$desktop_file")"
    fi
done

# Install to current user desktop
if [ -n "${FIRST_USER_NAME}" ] && [ "${FIRST_USER_NAME}" != "root" ]; then
    USER_DESKTOP="/home/${FIRST_USER_NAME}/Desktop"
    mkdir -p "$USER_DESKTOP"
    
    for desktop_file in /usr/share/applications/*.desktop; do
        if [ -f "$desktop_file" ] && [[ "$(basename "$desktop_file")" =~ ^(composer|grok-bloch|grok-bloch-web)\.desktop$ ]]; then
            cp "$desktop_file" "$USER_DESKTOP/"
            chown "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$USER_DESKTOP/$(basename "$desktop_file")"
            chmod 644 "$USER_DESKTOP/$(basename "$desktop_file")"
            echo "Added to ${FIRST_USER_NAME} desktop: $(basename "$desktop_file")"
        fi
    done
    
    # Ensure desktop directory ownership
    chown "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$USER_DESKTOP"
fi

echo "Desktop bookmarks installation completed"