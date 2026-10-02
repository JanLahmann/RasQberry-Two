#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: Boot Configuration Loader
# ============================================================================
# Description: Loads boot-time configuration from /boot/firmware/rasqberry_boot.env
#              and merges it with /usr/config/rasqberry_environment.env
# Usage: Called automatically by systemd at boot (rasqberry-boot-config.service)

# (RQ_BOOT_CONFIG, RQ_ENV_FILE, RQ_BOOT_TEMP_ENV: test overrides)
BOOT_CONFIG="${RQ_BOOT_CONFIG:-/boot/firmware/rasqberry_boot.env}"
GLOBAL_ENV="${RQ_ENV_FILE:-/usr/config/rasqberry_environment.env}"
TEMP_ENV="${RQ_BOOT_TEMP_ENV:-/tmp/rasqberry_env_merged.tmp}"

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
        LED_LAYOUT_VERIFIED)
            if ! [[ "$value" =~ ^(true|false|skipped)$ ]]; then
                error "Invalid LED_LAYOUT_VERIFIED: $value (must be 'true', 'false' or 'skipped')"
                return 1
            fi
            ;;
        LED_LAYOUT)
            # Names an entry in led-layouts.json. Accept a conservative
            # identifier charset; unknown names fall back safely in code.
            if ! [[ "$value" =~ ^[A-Za-z0-9_-]+$ ]]; then
                error "Invalid LED_LAYOUT: $value (must be a layout name)"
                return 1
            fi
            ;;
        LED_PHYSICAL|LED_VIRTUAL|LED_WEB|LED_VIRTUAL_MIRROR)
            if ! [[ "$value" =~ ^(true|false)$ ]]; then
                error "Invalid $key: $value (must be 'true' or 'false')"
                return 1
            fi
            ;;
        LED_RENDER_MODE)
            if ! [[ "$value" =~ ^(direct|service)$ ]]; then
                error "Invalid LED_RENDER_MODE: $value (must be 'direct' or 'service')"
                return 1
            fi
            ;;
        LED_INVERT)
            if ! [[ "$value" =~ ^(true|false)$ ]]; then
                error "Invalid $key: $value (must be 'true' or 'false')"
                return 1
            fi
            ;;
        LED_FREQ_HZ|LED_DMA|LED_CHANNEL|RASQ_LED_DISPLAY_TIMEOUT)
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
    BOOT_OVERRIDES=0

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
    local -a boot_keys=()
    local matrix_layout="" boot_layout=false
    if [ -f "$BOOT_CONFIG" ]; then
        log "Found boot configuration file: $BOOT_CONFIG"

        while IFS='=' read -r key value; do
            # The old LED_MATRIX_* keys are retired (Q22): LED_LAYOUT is the one
            # layout setting. A card prepared with an older template still
            # means a panel kit by LED_MATRIX_LAYOUT, so carry that over.
            case "$key" in
                LED_MATRIX_LAYOUT)
                    case "$value" in
                        single) matrix_layout="single-24x8" ;;
                        quad)   matrix_layout="quad-4x12" ;;
                        *)      log "  Skipping invalid config: $key=$value" ;;
                    esac
                    continue ;;
                LED_MATRIX_*)
                    log "  Ignoring retired setting $key (LED_LAYOUT sets the layout)"
                    continue ;;
                LED_LAYOUT) boot_layout=true ;;
            esac
            if validate_led_config "$key" "$value"; then
                boot_keys+=("$key")
                if [ "${config_map[$key]:-}" != "$value" ]; then
                    log "  Override: $key=$value (was: ${config_map[$key]:-<unset>})"
                    config_map["$key"]="$value"
                    ((BOOT_OVERRIDES++)) || true
                fi
            else
                log "  Skipping invalid config: $key=$value"
            fi
        done < <(parse_boot_config "$BOOT_CONFIG")

        if [ -n "$matrix_layout" ] && [ "$boot_layout" = false ]; then
            boot_keys+=("LED_LAYOUT")
            if [ "${config_map[LED_LAYOUT]:-}" != "$matrix_layout" ]; then
                log "  Override: LED_LAYOUT=$matrix_layout (from the retired LED_MATRIX_LAYOUT)"
                config_map["LED_LAYOUT"]="$matrix_layout"
                ((BOOT_OVERRIDES++)) || true
            fi
        fi

        if [ "$BOOT_OVERRIDES" -gt 0 ]; then
            log "Applied $BOOT_OVERRIDES boot configuration overrides"
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

        # A boot setting the environment file does not have yet (an older
        # file) used to be dropped here without a word: append it.
        for key in ${boot_keys[@]+"${boot_keys[@]}"}; do
            if ! grep -q "^${key}=" "$GLOBAL_ENV"; then
                echo "${key}=${config_map[$key]}"
            fi
        done
    fi
}

BOOT_OVERRIDES=0

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

    # A freshly flashed A/B slot starts with the shipped defaults: put back
    # the LED settings saved on the shared /data partition (#290). The boot
    # partition's rasqberry_boot.env below still overrides them.
    if [ -x /usr/bin/rq_device_settings.sh ]; then
        /usr/bin/rq_device_settings.sh restore || error "device settings restore failed"
    fi

    # Merge configurations
    # Create temp file first to ensure it exists
    touch "$TEMP_ENV"
    if merge_configs > "$TEMP_ENV" && [ -s "$TEMP_ENV" ]; then
        # Replace global environment with merged config
        mv "$TEMP_ENV" "$GLOBAL_ENV"
        chmod 644 "$GLOBAL_ENV"
        log "Boot configuration loaded successfully"
        # Keep what the boot file set across A/B updates too: the next slot
        # gets its LED settings from /data, not from this boot partition
        # (R-062). Does nothing on the standard image.
        if [ "${BOOT_OVERRIDES:-0}" -gt 0 ] && [ -x /usr/bin/rq_device_settings.sh ]; then
            /usr/bin/rq_device_settings.sh save || error "device settings save failed"
        fi
    else
        # No valid output or merge failed - keep original configuration
        log "No configuration changes needed, keeping original"
        rm -f "$TEMP_ENV"
    fi

    log "Boot configuration loader completed"
}

# Run main function
main