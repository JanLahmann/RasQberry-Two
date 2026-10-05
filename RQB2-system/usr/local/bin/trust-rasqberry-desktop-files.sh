#!/bin/bash
# Configure RasQberry desktop on first login
# - Configure GNOME Keyring to avoid password prompts
# - Verify libfm quick_exec setting
# This runs once and then removes itself

LOG_FILE="$HOME/.rasqberry-desktop-trust.log"

echo "$(date): Running RasQberry first-login setup..." >> "$LOG_FILE"

# Wait for desktop environment to be ready
sleep 3

# Configure GNOME Keyring with blank password to avoid Chromium password prompts
echo "$(date): Configuring GNOME Keyring..." >> "$LOG_FILE"
if command -v python3 >/dev/null 2>&1; then
    # Create default keyring directory if it doesn't exist
    mkdir -p "$HOME/.local/share/keyrings" 2>> "$LOG_FILE"

    # Create 'Default' keyring with blank password using Python
    # This prevents the "Enter password to unlock keyring" dialog in Chromium
    python3 - 2>> "$LOG_FILE" << 'PYEOF' || true
import os
keyring_dir = os.path.expanduser("~/.local/share/keyrings")
default_keyring = os.path.join(keyring_dir, "Default.keyring")

# Only create if it doesn't exist
if not os.path.exists(default_keyring):
    try:
        # Create a minimal keyring file with no password
        keyring_content = """[keyring]
display-name=Default
ctime=0
mtime=0
lock-on-idle=false
lock-timeout=0
"""
        os.makedirs(keyring_dir, exist_ok=True)
        with open(default_keyring, 'w') as f:
            f.write(keyring_content)
        os.chmod(default_keyring, 0o600)
        print(f"Created default keyring at {default_keyring}")
    except Exception as e:
        print(f"Failed to create keyring: {e}")
PYEOF
    echo "$(date): GNOME Keyring configured" >> "$LOG_FILE"
fi

# Configure libfm to skip executable file dialog (Bookworm security feature)
echo "$(date): Configuring libfm quick_exec..." >> "$LOG_FILE"
LIBFM_CONFIG="$HOME/.config/libfm/libfm.conf"
if [ -f "$LIBFM_CONFIG" ]; then
    # Check if quick_exec is already set to 1
    if ! grep -q "^quick_exec=1" "$LIBFM_CONFIG"; then
        # Try to update existing quick_exec line
        if grep -q "^quick_exec=" "$LIBFM_CONFIG"; then
            sed -i 's/^quick_exec=.*/quick_exec=1/' "$LIBFM_CONFIG" 2>> "$LOG_FILE" && \
                echo "$(date): Updated quick_exec=1 in libfm.conf" >> "$LOG_FILE" || \
                echo "$(date): Failed to update quick_exec in libfm.conf" >> "$LOG_FILE"
        else
            # Add quick_exec=1 to [config] section
            sed -i '/^\[config\]/a quick_exec=1' "$LIBFM_CONFIG" 2>> "$LOG_FILE" && \
                echo "$(date): Added quick_exec=1 to libfm.conf" >> "$LOG_FILE" || \
                echo "$(date): Failed to add quick_exec to libfm.conf" >> "$LOG_FILE"
        fi
    else
        echo "$(date): quick_exec=1 already set in libfm.conf" >> "$LOG_FILE"
    fi
else
    echo "$(date): libfm config not found at $LIBFM_CONFIG" >> "$LOG_FILE"
fi

# Restart PCManFM desktop to pick up trusted icon and libfm settings
# Without this, desktop icons won't respond to clicks until reboot
echo "$(date): Restarting PCManFM desktop to apply settings..." >> "$LOG_FILE"
pcmanfm --desktop-off 2>> "$LOG_FILE" || true
sleep 1
pcmanfm --desktop 2>> "$LOG_FILE" &
echo "$(date): PCManFM desktop restarted" >> "$LOG_FILE"

# Chromium opens maximised (#15; /etc/chromium.d/rasqberry adds
# --start-maximized). The saved placement says so too, for a start without
# the flag; its size is what "restore" goes back to.
echo "$(date): Configuring Chromium window position..." >> "$LOG_FILE"
CHROMIUM_PREFS_DIR="$HOME/.config/chromium/Default"
CHROMIUM_PREFS="$CHROMIUM_PREFS_DIR/Preferences"
mkdir -p "$CHROMIUM_PREFS_DIR" 2>> "$LOG_FILE"
python3 - "$CHROMIUM_PREFS" 2>> "$LOG_FILE" << 'CHROMEPY' || true
import sys, json, os
prefs_file = sys.argv[1]
if os.path.exists(prefs_file):
    with open(prefs_file, 'r') as f:
        prefs = json.load(f)
else:
    prefs = {}
prefs.setdefault('browser', {})['window_placement'] = {
    'left': 480, 'top': 45, 'right': 1550, 'bottom': 1050,
    'maximized': True,
    'work_area_left': 0, 'work_area_top': 36,
    'work_area_right': 1920, 'work_area_bottom': 1080
}
with open(prefs_file, 'w') as f:
    json.dump(prefs, f)
print("Configured Chromium window: maximised")
CHROMEPY
echo "$(date): Chromium window configured" >> "$LOG_FILE"

echo "$(date): First-login setup completed" >> "$LOG_FILE"

# Remove autostart entry so this doesn't run again
rm -f "$HOME/.config/autostart/trust-rasqberry-desktop.desktop"
