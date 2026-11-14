#!/bin/bash
# ============================================================================
# Common Library Usage Validator
# ============================================================================
# Detects reimplemented functionality that should use rq_common.sh instead
#
# This test catches:
# 1. Duplicate implementations of common functions
# 2. Manual implementations of what the library provides
# 3. Anti-patterns that violate coding standards
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BIN_DIR="$PROJECT_ROOT/RQB2-bin"

ERRORS=0
WARNINGS=0

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

error() {
    echo -e "${RED}❌ ERROR: $*${NC}" >&2
    ERRORS=$((ERRORS + 1))
}

warn() {
    echo -e "${YELLOW}⚠️  WARNING: $*${NC}" >&2
    WARNINGS=$((WARNINGS + 1))
}

info() {
    echo -e "${GREEN}✓ $*${NC}"
}

echo "=== Common Library Usage Validation ==="
echo

# ============================================================================
# CHECK 1: Duplicate Environment Loading
# ============================================================================
echo "1. Checking for duplicate environment loading implementations..."

for script in "$BIN_DIR"/*.sh; do
    [ -f "$script" ] || continue
    script_name=$(basename "$script")

    # Skip the common library itself
    [ "$script_name" = "rq_common.sh" ] && continue

    # If script uses rq_common.sh, check for manual env loading
    if grep -q "rq_common.sh" "$script"; then
        # Check for old-style environment loading
        if grep -q 'if \[ -f "/usr/config/rasqberry_env-config.sh" \]' "$script"; then
            error "$script_name: Reimplements environment loading (should use load_rqb2_env)"
            echo "  Found: if [ -f \"/usr/config/rasqberry_env-config.sh\" ]"
            echo "  Use:   load_rqb2_env"
        fi

        # Check for direct sourcing of env-config
        if grep -q '\. "/usr/config/rasqberry_env-config.sh"' "$script"; then
            if ! grep -q "load_rqb2_env" "$script"; then
                error "$script_name: Sources env-config directly (should use load_rqb2_env)"
            fi
        fi
    fi
done

# ============================================================================
# CHECK 2: Duplicate Virtual Environment Activation
# ============================================================================
echo
echo "2. Checking for duplicate venv activation implementations..."

for script in "$BIN_DIR"/*.sh; do
    [ -f "$script" ] || continue
    script_name=$(basename "$script")

    [ "$script_name" = "rq_common.sh" ] && continue

    if grep -q "rq_common.sh" "$script"; then
        # Check for manual venv activation with multiple location checks
        if grep -q 'if \[ -f .*venv.*bin/activate.*\]; then' "$script"; then
            # Check if it's a simple pattern that could use activate_venv
            venv_checks=$(grep -c 'if \[ -f .*venv.*bin/activate' "$script" || echo 0)
            if [ "$venv_checks" -gt 1 ]; then
                warn "$script_name: Multiple venv location checks (should use activate_venv)"
                echo "  Found: $venv_checks venv checks"
                echo "  Use:   activate_venv || warn \"Venv not available\""
            fi
        fi

        # Check for manual VENV_PATHS array pattern
        if grep -q "VENV_PATHS=(" "$script"; then
            warn "$script_name: Defines VENV_PATHS array (activate_venv handles this)"
        fi

        # Check for direct source of activate
        if grep -q 'source.*bin/activate' "$script"; then
            if ! grep -q "activate_venv" "$script"; then
                warn "$script_name: Direct venv activation (should use activate_venv)"
            fi
        fi
    fi
done

# ============================================================================
# CHECK 3: Duplicate User Detection Logic
# ============================================================================
echo
echo "3. Checking for duplicate user detection implementations..."

for script in "$BIN_DIR"/*.sh; do
    [ -f "$script" ] || continue
    script_name=$(basename "$script")

    [ "$script_name" = "rq_common.sh" ] && continue

    if grep -q "rq_common.sh" "$script"; then
        # Check for manual USER_NAME/USER_HOME detection
        if grep -q 'if \[ -n "\${SUDO_USER}" \].*then' "$script"; then
            if grep -q 'USER_NAME=.*SUDO_USER' "$script"; then
                error "$script_name: Reimplements user detection (NEVER redefine USER_HOME)"
                echo "  Found: Manual SUDO_USER detection"
                echo "  Use:   SUDO_USER_NAME variable from env-config"
            fi
        fi
    fi
done

# ============================================================================
# CHECK 4: Duplicate LED Control
# ============================================================================
echo
echo "4. Checking for duplicate LED control implementations..."

for script in "$BIN_DIR"/*.sh; do
    [ -f "$script" ] || continue
    script_name=$(basename "$script")

    [ "$script_name" = "rq_common.sh" ] && [ "$script_name" != "rq_clear_leds.sh" ] && continue

    if grep -q "rq_common.sh" "$script"; then
        # Check for manual LED script finding
        if grep -q "turn_off_LEDs.py" "$script"; then
            if grep -q 'for location in.*turn_off_LEDs.py' "$script"; then
                warn "$script_name: Manual LED script search (should use clear_leds)"
            fi
        fi

        # Check for manual pkill LED processes
        if grep -q 'pkill.*python' "$script"; then
            if ! grep -q "cleanup_demo_processes" "$script"; then
                warn "$script_name: Manual process cleanup (consider cleanup_demo_processes)"
            fi
        fi
    fi
done

# ============================================================================
# CHECK 5: Duplicate Error Handling
# ============================================================================
echo
echo "5. Checking for duplicate error handling implementations..."

for script in "$BIN_DIR"/*.sh; do
    [ -f "$script" ] || continue
    script_name=$(basename "$script")

    [ "$script_name" = "rq_common.sh" ] && continue

    if grep -q "rq_common.sh" "$script"; then
        # Check for custom die/warn/info functions
        if grep -q '^die()' "$script"; then
            error "$script_name: Redefines die() function (use from rq_common.sh)"
        fi

        if grep -q '^warn()' "$script"; then
            error "$script_name: Redefines warn() function (use from rq_common.sh)"
        fi

        # Check for echo ERROR pattern instead of die
        if grep -q 'echo "Error:' "$script"; then
            if grep -q 'exit 1' "$script"; then
                warn "$script_name: Uses echo + exit instead of die function"
                echo "  Pattern: echo \"Error:...\" && exit 1"
                echo "  Use:     die \"Error message\""
            fi
        fi
    fi
done

# ============================================================================
# CHECK 6: Duplicate Whiptail Dialog Code
# ============================================================================
echo
echo "6. Checking for duplicate whiptail dialog implementations..."

for script in "$BIN_DIR"/*.sh; do
    [ -f "$script" ] || continue
    script_name=$(basename "$script")

    [ "$script_name" = "rq_common.sh" ] && continue

    if grep -q "rq_common.sh" "$script"; then
        # Count raw whiptail calls
        yesno_count=$(grep -c "whiptail --yesno" "$script" 2>/dev/null || echo "0")
        msgbox_count=$(grep -c "whiptail --msgbox" "$script" 2>/dev/null || echo "0")

        # Check if show_* wrappers are used
        uses_show_yesno=$(grep -c "show_yesno" "$script" 2>/dev/null || echo "0")
        uses_show_msgbox=$(grep -c "show_msgbox" "$script" 2>/dev/null || echo "0")

        # Clean up any whitespace/newlines
        yesno_count=$(echo "$yesno_count" | tr -d '\n' | tr -d ' ')
        msgbox_count=$(echo "$msgbox_count" | tr -d '\n' | tr -d ' ')
        uses_show_yesno=$(echo "$uses_show_yesno" | tr -d '\n' | tr -d ' ')
        uses_show_msgbox=$(echo "$uses_show_msgbox" | tr -d '\n' | tr -d ' ')

        if [ "${yesno_count:-0}" -gt 0 ] 2>/dev/null && [ "${uses_show_yesno:-0}" -eq 0 ] 2>/dev/null; then
            warn "$script_name: Uses raw whiptail --yesno ($yesno_count times) instead of show_yesno"
        fi

        if [ "${msgbox_count:-0}" -gt 0 ] 2>/dev/null && [ "${uses_show_msgbox:-0}" -eq 0 ] 2>/dev/null; then
            warn "$script_name: Uses raw whiptail --msgbox ($msgbox_count times) instead of show_msgbox"
        fi
    fi
done

# ============================================================================
# CHECK 7: Duplicate Git Operations
# ============================================================================
echo
echo "7. Checking for duplicate git clone implementations..."

for script in "$BIN_DIR"/*.sh; do
    [ -f "$script" ] || continue
    script_name=$(basename "$script")

    [ "$script_name" = "rq_common.sh" ] && continue

    if grep -q "rq_common.sh" "$script"; then
        # Check for git clone followed by ownership fixing
        if grep -q "git clone" "$script"; then
            if grep -q "chown.*SUDO_USER\|chown.*USER_NAME" "$script"; then
                warn "$script_name: Manual git clone + ownership fix (should use clone_demo)"
                echo "  Use: clone_demo \"\$GIT_URL\" \"\$DEMO_DIR\""
            fi
        fi
    fi
done

# ============================================================================
# CHECK 8: Duplicate Cleanup Trap Logic
# ============================================================================
echo
echo "8. Checking for duplicate cleanup trap implementations..."

for script in "$BIN_DIR"/*.sh; do
    [ -f "$script" ] || continue
    script_name=$(basename "$script")

    [ "$script_name" = "rq_common.sh" ] && continue

    if grep -q "rq_common.sh" "$script"; then
        # Check for manual trap setup
        if grep -q "trap.*cleanup.*SIGINT\|trap.*cleanup.*INT" "$script"; then
            if ! grep -q "setup_cleanup_trap" "$script"; then
                warn "$script_name: Manual trap setup (should use setup_cleanup_trap)"
                echo "  Found: trap cleanup SIGINT SIGTERM"
                echo "  Use:   setup_cleanup_trap cleanup"
            fi
        fi
    fi
done

# ============================================================================
# CHECK 9: Semantic Duplication Detection (Advanced)
# ============================================================================
echo
echo "9. Checking for semantic duplication patterns..."

# Function signature patterns that indicate reimplementation
# Note: Using simple variables instead of associative array for compatibility
PATTERN_NAMES=("environment_loading" "venv_activation" "user_detection" "LED_clearing" "process_cleanup")
PATTERN_environment_loading='if.*\[ -f.*rasqberry_env-config.*\].*then'
PATTERN_venv_activation='for.*in.*venv.*STD_VENV.*bin/activate'
PATTERN_user_detection='SUDO_USER.*!=.*root.*USER_HOME=/home'
PATTERN_LED_clearing='python3.*turn_off_LEDs\.py'
PATTERN_process_cleanup='pkill -f.*python.*LED'

for script in "$BIN_DIR"/*.sh; do
    [ -f "$script" ] || continue
    script_name=$(basename "$script")

    [ "$script_name" = "rq_common.sh" ] && continue

    if grep -q "rq_common.sh" "$script"; then
        for pattern_name in "${PATTERN_NAMES[@]}"; do
            # Get pattern value using variable indirection
            pattern_var="PATTERN_${pattern_name}"
            pattern="${!pattern_var}"

            if grep -E -q "$pattern" "$script"; then
                # Additional check: make sure they're not using the library function
                case "$pattern_name" in
                    "environment_loading")
                        if ! grep -q "load_rqb2_env" "$script"; then
                            warn "$script_name: Detected environment loading pattern"
                        fi
                        ;;
                    "venv_activation")
                        if ! grep -q "activate_venv" "$script"; then
                            warn "$script_name: Detected venv activation pattern"
                        fi
                        ;;
                    "user_detection")
                        error "$script_name: Detected user detection pattern (CRITICAL)"
                        ;;
                esac
            fi
        done
    fi
done

# ============================================================================
# CHECK 10: Function Complexity Analysis
# ============================================================================
echo
echo "10. Checking for overly complex functions (candidates for extraction)..."

for script in "$BIN_DIR"/*.sh; do
    [ -f "$script" ] || continue
    script_name=$(basename "$script")

    [ "$script_name" = "rq_common.sh" ] && [ "$script_name" != "_TEMPLATE.sh" ] && continue

    # Find function definitions and count lines until closing brace
    awk '
    /^[a-z_]+\(\).*{/ {
        fname = $1
        gsub(/\(\).*/, "", fname)
        count = 0
        in_func = 1
        braces = 1
        next
    }
    in_func {
        count++
        braces += gsub(/{/, "&")
        braces -= gsub(/}/, "&")
        if (braces == 0) {
            if (count > 50) {
                print FILENAME ":" fname "(): " count " lines (consider extracting to rq_common.sh)"
            }
            in_func = 0
        }
    }
    ' "$script" | while read -r line; do
        warn "Complex function: $line"
    done
done

# ============================================================================
# SUMMARY
# ============================================================================
echo
echo "=== Validation Summary ==="
echo

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}❌ FAILED: $ERRORS errors found${NC}"
    echo "   These are critical issues that violate coding standards"
    echo
fi

if [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  WARNINGS: $WARNINGS issues found${NC}"
    echo "   These are opportunities to use rq_common.sh functions"
    echo
fi

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed! Excellent common library usage.${NC}"
    echo
fi

# Report statistics
echo "Library Usage Statistics:"
cd "$BIN_DIR"
echo "  Scripts using rq_common.sh:    $(grep -l 'rq_common.sh' *.sh 2>/dev/null | grep -v '^rq_common.sh$' | wc -l)"
echo "  Scripts using load_rqb2_env:   $(grep -l 'load_rqb2_env' *.sh 2>/dev/null | wc -l)"
echo "  Scripts using activate_venv:   $(grep -l 'activate_venv' *.sh 2>/dev/null | wc -l)"
echo "  Scripts using die function:    $(grep -l ' die ' *.sh 2>/dev/null | wc -l)"
echo "  Scripts using show_* dialogs:  $(grep -lE 'show_yesno|show_msgbox' *.sh 2>/dev/null | wc -l)"
echo "  Scripts using clone_demo:      $(grep -l 'clone_demo' *.sh 2>/dev/null | wc -l)"
echo

# Exit with error if critical issues found
if [ $ERRORS -gt 0 ]; then
    exit 1
fi

# Warnings don't fail the build
exit 0
