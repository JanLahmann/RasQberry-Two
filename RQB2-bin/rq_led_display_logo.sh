#!/bin/bash
# RasQberry LED Logo Display - Interactive launcher
# Allows user to select and display logos from library or custom files

set -euo pipefail

# Load common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load and verify environment
load_rqb2_env
verify_env_vars REPO USER_HOME STD_VENV BIN_DIR

# ============================================================================
# Main function
# ============================================================================

main() {
    info "RasQberry LED Logo Display"

    LOGO_DIR="$USER_HOME/$REPO/RQB2-config/LED-Logos"

    # Check if logo directory exists
    if [ ! -d "$LOGO_DIR" ]; then
        die "Logo directory not found: $LOGO_DIR"
    fi

    # Build menu from available logos
    MENU_ITEMS=()
    while IFS= read -r logo; do
        [ -f "$logo" ] || continue
        BASENAME=$(basename "$logo" .png)
        # Only show 24x8 logos (standard size)
        if [[ "$BASENAME" == *"-24x8" ]]; then
            DISPLAY_NAME="${BASENAME%-24x8}"  # Remove -24x8 suffix for display
            MENU_ITEMS+=("$logo")
            MENU_ITEMS+=("$DISPLAY_NAME")
        fi
    done < <(find "$LOGO_DIR" -name "*.png" -type f | sort)

    # Check if any logos found
    if [ ${#MENU_ITEMS[@]} -eq 0 ]; then
        show_msgbox "No Logos Found" "No logos found in $LOGO_DIR\n\nPlease run:\npython3 $USER_HOME/$REPO/RQB2-config/LED-Logos/create_logos.py"
        exit 1
    fi

    # Add custom option
    MENU_ITEMS+=("custom")
    MENU_ITEMS+=("Browse for custom image...")

    # Show menu
    CHOICE=$(whiptail --menu "Choose logo to display:" 20 70 12 \
             "${MENU_ITEMS[@]}" \
             --title "LED Logo Display" 3>&1 1>&2 2>&3) || {
        info "User cancelled"
        exit 0
    }

    # Handle custom option
    if [ "$CHOICE" = "custom" ]; then
        # Prompt for file path
        CHOICE=$(whiptail --inputbox "Enter path to PNG or JPG image:" 10 70 \
                 --title "Custom Logo" 3>&1 1>&2 2>&3) || {
            info "User cancelled"
            exit 0
        }

        # Expand path
        CHOICE=$(eval echo "$CHOICE")

        # Check if file exists
        if [ ! -f "$CHOICE" ]; then
            show_msgbox "File Not Found" "Image file not found:\n$CHOICE"
            exit 1
        fi
    fi

    # Prompt for duration
    DURATION=$(whiptail --inputbox "Display duration (seconds):" 10 60 \
               "10" --title "Duration" 3>&1 1>&2 2>&3) || {
        info "User cancelled"
        exit 0
    }

    # Validate duration is a number
    if ! [[ "$DURATION" =~ ^[0-9]+$ ]]; then
        die "Duration must be a positive number"
    fi

    # Prompt for effects
    if whiptail --yesno "Enable fade-in and fade-out effects?" 8 60 --title "Effects" --defaultno; then
        FADE_EFFECTS="--fade-in --fade-out"
    else
        FADE_EFFECTS=""
    fi

    # Show summary and confirm
    BASENAME=$(basename "$CHOICE")
    if ! whiptail --yesno "Ready to display:\n\nLogo: $BASENAME\nDuration: ${DURATION}s\nEffects: ${FADE_EFFECTS:-none}\n\nContinue?" 12 60 --title "Confirm"; then
        info "User cancelled"
        exit 0
    fi

    # Activate virtual environment
    activate_venv

    # Create temporary Python script to display logo
    TEMP_SCRIPT=$(mktemp)
    trap "rm -f '$TEMP_SCRIPT'" EXIT

    cat > "$TEMP_SCRIPT" << 'PYTHON_EOF'
#!/usr/bin/env python3
import sys
from rq_led_logo import display_logo

# Parse arguments
image_path = sys.argv[1]
duration = int(sys.argv[2])
fade_in = '--fade-in' in sys.argv
fade_out = '--fade-out' in sys.argv

# Display logo
try:
    display_logo(
        image_path,
        duration=duration,
        brightness=0.5,
        fade_in=fade_in,
        fade_out=fade_out
    )
except KeyboardInterrupt:
    print("\nInterrupted by user")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
PYTHON_EOF

    # Execute display
    info "Displaying logo on LED matrix..."
    python3 "$TEMP_SCRIPT" "$CHOICE" "$DURATION" $FADE_EFFECTS || die "Failed to display logo"

    info "Display complete!"
}

# Run main function
main