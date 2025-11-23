#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: Boot Configuration Loader
# ============================================================================
# Description: Loads boot-time configuration from /boot/firmware/rasqberry_boot.env
#              and merges it with /usr/config/rasqberry_environment.env
# Usage: Called automatically by systemd at boot (rasqberry-boot-config.service)

BOOT_CONFIG="/boot/firmware/rasqberry_boot.env"
GLOBAL_ENV="/usr/config/rasqberry_environment.env"
TEMP_ENV="/tmp/rasqberry_env_merged.tmp"

# Logging function (outputs to stderr to avoid pollution of redirected stdout)
log() {
    echo "[rasqberry-boot-config] $*" | systemd-cat -t rasqberry-boot-config -p info
    echo "[rasqberry-boot-config] $*" >&2
}

error() {
    echo "[rasqberry-boot-config] ERROR: $*" | systemd-cat -t rasqberry-boot-config -p err
    echo "[rasqberry-boot-config] ERROR: $*" >&2
}

# Parse boot config file and extract valid LED configuration
parse_boot_config() {
    local config_file="$1"

    if [ ! -f "$config_file" ]; then
        return 0
    fi

    # Extract valid key=value pairs (LED and matrix config only)
    # Ignore comments (#), empty lines, and non-LED variables
    grep -E '^[[:space:]]*(LED_|RASQ_LED_)' "$config_file" 2>/dev/null | \
        grep -v '^[[:space:]]*#' | \
        sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | \
        while IFS='=' read -r key value; do
            # Remove quotes and extra whitespace from value
            value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | tr -d '"' | tr -d "'")

            # Skip empty values
            if [ -n "$value" ]; then
                echo "${key}=${value}"
            fi
        done
}

# Validate LED configuration values
validate_led_config() {
    local key="$1"
    local value="$2"

    case "$key" in
        LED_COUNT)
            if ! [[ "$value" =~ ^[0-9]+$ ]] || [ "$value" -lt 1 ]; then
                error "Invalid LED_COUNT: $value (must be positive integer)"
                return 1
            fi
            ;;
        LED_GPIO_PIN)
            if ! [[ "$value" =~ ^[0-9]+$ ]] || [ "$value" -gt 27 ]; then
                error "Invalid LED_GPIO_PIN: $value (must be 0-27)"
                return 1
            fi
            ;;
        LED_PIXEL_ORDER)
            if ! [[ "$value" =~ ^(RGB|GRB|RGBW|GRBW)$ ]]; then
                error "Invalid LED_PIXEL_ORDER: $value (must be RGB, GRB, RGBW, or GRBW)"
                return 1
            fi
            ;;
        LED_DEFAULT_BRIGHTNESS)
            if ! [[ "$value" =~ ^0?\.[0-9]+$|^1\.0$|^[01]$ ]]; then
                error "Invalid LED_DEFAULT_BRIGHTNESS: $value (must be 0.0-1.0)"
                return 1
            fi
            ;;
        LED_MATRIX_LAYOUT)
            if ! [[ "$value" =~ ^(single|quad)$ ]]; then
                error "Invalid LED_MATRIX_LAYOUT: $value (must be 'single' or 'quad')"
                return 1
            fi
            ;;
        LED_MATRIX_WIDTH|LED_MATRIX_HEIGHT|LED_MATRIX_PANEL_WIDTH|LED_MATRIX_PANEL_HEIGHT)
            if ! [[ "$value" =~ ^[0-9]+$ ]] || [ "$value" -lt 1 ]; then
                error "Invalid $key: $value (must be positive integer)"
                return 1
            fi
            ;;
        LED_MATRIX_Y_FLIP|LED_INVERT)
            if ! [[ "$value" =~ ^(true|false)$ ]]; then
                error "Invalid $key: $value (must be 'true' or 'false')"
                return 1
            fi
            ;;
        LED_FREQ_HZ|LED_DMA|LED_CHANNEL|LED_CHUNK_SIZE|LED_CHUNK_DELAY_MS|RASQ_LED_DISPLAY_TIMEOUT)
            if ! [[ "$value" =~ ^[0-9]+$ ]]; then
                error "Invalid $key: $value (must be integer)"
                return 1
            fi
            ;;
    esac

    return 0
}

# Merge boot config with global environment
merge_configs() {
    declare -A config_map
    local boot_overrides=0

    # Load defaults from global environment file
    if [ -f "$GLOBAL_ENV" ]; then
        while IFS='=' read -r key value; do
            # Only store LED-related configuration
            if [[ "$key" =~ ^(LED_|RASQ_LED_) ]]; then
                config_map["$key"]="$value"
            fi
        done < "$GLOBAL_ENV"
    else
        error "Global environment file not found: $GLOBAL_ENV"
        return 1
    fi

    # Override with boot config (with validation)
    if [ -f "$BOOT_CONFIG" ]; then
        log "Found boot configuration file: $BOOT_CONFIG"

        while IFS='=' read -r key value; do
            if validate_led_config "$key" "$value"; then
                if [ "${config_map[$key]:-}" != "$value" ]; then
                    log "  Override: $key=$value (was: ${config_map[$key]:-<unset>})"
                    config_map["$key"]="$value"
                    ((boot_overrides++))
                fi
            else
                log "  Skipping invalid config: $key=$value"
            fi
        done < <(parse_boot_config "$BOOT_CONFIG")

        if [ $boot_overrides -gt 0 ]; then
            log "Applied $boot_overrides boot configuration overrides"
        else
            log "No valid boot configuration overrides found"
        fi
    else
        log "No boot configuration file found, using defaults"
    fi

    # Read global env again and apply overrides
    if [ -f "$GLOBAL_ENV" ]; then
        while IFS='=' read -r line; do
            # Skip comments and empty lines
            [[ "$line" =~ ^[[:space:]]*# ]] && echo "$line" && continue
            [[ -z "$line" ]] && echo "$line" && continue

            # Extract key
            key=$(echo "$line" | cut -d'=' -f1)

            # If we have an override for this LED key, use it
            if [[ "$key" =~ ^(LED_|RASQ_LED_) ]] && [ -n "${config_map[$key]:-}" ]; then
                echo "${key}=${config_map[$key]}"
            else
                # Keep original line (preserves non-LED config and comments)
                echo "$line"
            fi
        done < "$GLOBAL_ENV"
    fi
}

# Main execution
main() {
    log "Starting boot configuration loader"

    # Check if global environment file exists
    if [ ! -f "$GLOBAL_ENV" ]; then
        error "Global environment file not found: $GLOBAL_ENV"
        exit 1
    fi

    # Backup original global environment
    if [ ! -f "${GLOBAL_ENV}.original" ]; then
        log "Creating original backup: ${GLOBAL_ENV}.original"
        cp "$GLOBAL_ENV" "${GLOBAL_ENV}.original"
    fi

    # Merge configurations
    if merge_configs > "$TEMP_ENV"; then
        # Replace global environment with merged config
        mv "$TEMP_ENV" "$GLOBAL_ENV"
        chmod 644 "$GLOBAL_ENV"
        log "Boot configuration loaded successfully"
    else
        error "Failed to merge configurations"
        rm -f "$TEMP_ENV"
        exit 1
    fi

    log "Boot configuration loader completed"
}

# Run main function
main