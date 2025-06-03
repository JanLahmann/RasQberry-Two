#!/bin/bash -e

echo "Installing desktop bookmarks"

# Source the configuration file
if [ -f "/tmp/stage-config" ]; then
    . /tmp/stage-config
    rm -f /tmp/stage-config
    
    # Map the RQB_ prefixed variables to local names
    REPO="${RQB_REPO}"
    GIT_USER="${RQB_GIT_USER}"
    GIT_BRANCH="${RQB_GIT_BRANCH}"
    GIT_REPO="${RQB_GIT_REPO}"
    # Use FIRST_USER_NAME from pi-gen config, with fallback to rasqberry
    FIRST_USER_NAME="${FIRST_USER_NAME:-rasqberry}"
    
    echo "Configuration loaded successfully"
else
    echo "ERROR: config file not found"
    exit 1
fi

export CLONE_DIR="/tmp/${REPO}"

# Clone the Git repository for bookmark installation
if [ ! -d "${CLONE_DIR}" ]; then
    echo "Cloning repository ${GIT_REPO} (branch: ${GIT_BRANCH}) to ${CLONE_DIR}"
    git clone --branch ${GIT_BRANCH} ${GIT_REPO} ${CLONE_DIR}
else
    echo "Repository already exists at ${CLONE_DIR}"
fi

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

# Install custom category definition
mkdir -p /usr/share/desktop-directories
if [ -d "${CLONE_DIR}/RQB2-config/desktop-categories" ]; then
    for category_file in "${CLONE_DIR}/RQB2-config/desktop-categories"/*.directory; do
        if [ -f "$category_file" ]; then
            cp "$category_file" /usr/share/desktop-directories/
            chmod 644 "/usr/share/desktop-directories/$(basename "$category_file")"
            echo "Installed category: $(basename "$category_file")"
        fi
    done
else
    echo "WARNING: Desktop categories directory not found"
fi

# Copy desktop bookmark files
if [ -d "${CLONE_DIR}/RQB2-config/desktop-bookmarks" ]; then
    for desktop_file in "${CLONE_DIR}/RQB2-config/desktop-bookmarks"/*.desktop; do
        if [ -f "$desktop_file" ]; then
            cp "$desktop_file" /usr/share/applications/
            chmod 755 "/usr/share/applications/$(basename "$desktop_file")"
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
    if [ -f "$desktop_file" ] && [[ "$(basename "$desktop_file")" =~ ^(composer|grok-bloch|grok-bloch-web|quantum-fractals|quantum-lights-out|quantum-raspberry-tie|led-ibm-demo)\.desktop$ ]]; then
        cp "$desktop_file" /etc/skel/Desktop/
        chmod 755 "/etc/skel/Desktop/$(basename "$desktop_file")"
        echo "Added to new user template: $(basename "$desktop_file")"
    fi
done

# Install to current user desktop
if [ -n "${FIRST_USER_NAME}" ] && [ "${FIRST_USER_NAME}" != "root" ]; then
    USER_DESKTOP="/home/${FIRST_USER_NAME}/Desktop"
    mkdir -p "$USER_DESKTOP"
    
    for desktop_file in /usr/share/applications/*.desktop; do
        if [ -f "$desktop_file" ] && [[ "$(basename "$desktop_file")" =~ ^(composer|grok-bloch|grok-bloch-web|quantum-fractals|quantum-lights-out|quantum-raspberry-tie|led-ibm-demo)\.desktop$ ]]; then
            cp "$desktop_file" "$USER_DESKTOP/"
            chown "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$USER_DESKTOP/$(basename "$desktop_file")"
            chmod 755 "$USER_DESKTOP/$(basename "$desktop_file")"
            echo "Added to ${FIRST_USER_NAME} desktop: $(basename "$desktop_file")"
        fi
    done
    
    # Ensure desktop directory ownership
    chown "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$USER_DESKTOP"
fi

# Update desktop database to recognize custom categories
echo "Updating desktop database..."
update-desktop-database /usr/share/applications || echo "Warning: Failed to update desktop database"

# Clean up cloned repository to save space
if [ -d "${CLONE_DIR}" ]; then
    echo "Cleaning up cloned repository..."
    rm -rf "${CLONE_DIR}"
fi

echo "Desktop bookmarks installation completed"