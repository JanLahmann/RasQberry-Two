#!/bin/bash
#
# rq_demo_validate.sh - Validate RasQberry demo manifest files
#
# Usage:
#   rq_demo_validate.sh                     # Validate all manifests
#   rq_demo_validate.sh <manifest.json>     # Validate specific file
#   rq_demo_validate.sh --check-files       # Also check referenced files exist
#
# Requires: jq
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Find script directory and manifest directory
# When installed: /usr/bin → /usr/config/...
# When in repo: RQB2-bin → RQB2-config/...
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Soft-load the environment so USER_HOME resolves for the user manifest dir.
# Degrades silently in dev/CI where the installed config is absent -> the
# manifest search path falls back to the shipped directory only.
if [ -f "$RQ_CONFIG_FILE" ]; then
    load_rqb2_env
fi

if [ "$SCRIPT_DIR" = "/usr/bin" ]; then
    # Installed system: config is at /usr/config (see issue #246 for global vars)
    MANIFEST_DIR="/usr/config/demo-manifests"
    PATCHES_DIR="/usr/config/demo-patches"
else
    # Development: relative to repo structure
    REPO_DIR="$(dirname "$SCRIPT_DIR")"
    MANIFEST_DIR="$REPO_DIR/RQB2-config/demo-manifests"
    PATCHES_DIR="$REPO_DIR/RQB2-config/demo-patches"
fi

# Counters
TOTAL=0
PASSED=0
FAILED=0
WARNINGS=0

# Options
CHECK_FILES=false
EXTERNAL=false   # --external: apply the hardened external-demo constraints

# Required fields for validation
REQUIRED_FIELDS='["id", "name", "category", "description", "entrypoint"]'
VALID_CATEGORIES='["game", "visualization", "education", "jupyter", "led-demo", "tool"]'
VALID_ENTRYPOINT_TYPES='["python", "jupyter", "docker", "browser", "web-static"]'
# Entrypoint types an external demo may declare (no legacy "script").
EXTERNAL_ENTRYPOINT_TYPES='["python", "jupyter", "docker", "browser", "web-static"]'
VALID_DISPLAY_VALUES='["none", "optional", "required"]'
VALID_TOKEN_VALUES='["none", "prefer", "required"]'

# Print functions
print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_info() {
    echo -e "       $1"
}

# Check if jq is available
check_jq() {
    if ! command -v jq &> /dev/null; then
        echo "Error: jq is required but not installed."
        echo "Install with: sudo apt-get install jq"
        exit 1
    fi
}

# Check a path-like value against the external safety rules:
#   - matches ^[A-Za-z0-9._/-]+$ (no whitespace, no exotic chars)
#   - no leading "/"
#   - no ".." path segment
# An empty value is treated as "field absent" (safe here; presence is checked
# separately). Returns 0 if safe, 1 otherwise.
is_safe_ext_path() {
    local v="$1"
    [ -n "$v" ] || return 0
    echo "$v" | grep -qE '^[A-Za-z0-9._/-]+$' || return 1
    case "$v" in
        /*) return 1 ;;
    esac
    if echo "$v" | grep -qE '(^|/)\.\.(/|$)'; then
        return 1
    fi
    return 0
}

# Apply the hardened external-demo constraints (spec §1 + §5). Prints one
# [FAIL] line per violation and stores the count in the global EXT_ERR_COUNT.
EXT_ERR_COUNT=0
validate_external_constraints() {
    local file="$1"
    local errs=0

    # Forbidden fields: external demos ship no launcher/patch/command
    local launcher patch_file command
    launcher=$(jq -r '.entrypoint.launcher // empty' "$file")
    patch_file=$(jq -r '.install.patch_file // empty' "$file")
    command=$(jq -r '.entrypoint.command // empty' "$file")

    if [ -n "$launcher" ]; then
        print_fail "External demo must not set entrypoint.launcher"
        errs=$((errs + 1))
    fi
    if [ -n "$patch_file" ]; then
        print_fail "External demo must not set install.patch_file"
        errs=$((errs + 1))
    fi
    if [ -n "$command" ]; then
        print_fail "External demo must not set entrypoint.command"
        errs=$((errs + 1))
    fi

    # Entrypoint type must be one of the declarative types (no legacy "script")
    local etype
    etype=$(jq -r '.entrypoint.type // empty' "$file")
    if [ -z "$etype" ]; then
        print_fail "External demo must declare entrypoint.type"
        errs=$((errs + 1))
    elif ! echo "$EXTERNAL_ENTRYPOINT_TYPES" | jq -e "index(\"$etype\")" >/dev/null 2>&1; then
        print_fail "External entrypoint.type invalid: '$etype' (valid: python, jupyter, browser, docker, web-static)"
        errs=$((errs + 1))
    fi

    # id: kebab-case (also path-safe by construction)
    local id
    id=$(jq -r '.id // empty' "$file")
    if [ -z "$id" ]; then
        print_fail "External demo missing id"
        errs=$((errs + 1))
    elif ! echo "$id" | grep -qE '^[a-z0-9-]+$'; then
        print_fail "External id must be kebab-case ^[a-z0-9-]+$ : '$id'"
        errs=$((errs + 1))
    fi

    # marker_file is required for external demos (proves checkout integrity)
    local marker_file
    marker_file=$(jq -r '.install.marker_file // empty' "$file")
    if [ -z "$marker_file" ]; then
        print_fail "External demo must set install.marker_file"
        errs=$((errs + 1))
    fi

    # repo_url must be https://
    local repo_url
    repo_url=$(jq -r '.install.repo_url // empty' "$file")
    if [ -z "$repo_url" ]; then
        print_fail "External demo must set install.repo_url"
        errs=$((errs + 1))
    elif ! echo "$repo_url" | grep -qE '^https://'; then
        print_fail "External install.repo_url must start with https:// : '$repo_url'"
        errs=$((errs + 1))
    fi

    # Path-safe fields: no traversal, no leading slash, no whitespace
    local working_dir script serve_dir
    working_dir=$(jq -r '.entrypoint.working_dir // empty' "$file")
    script=$(jq -r '.entrypoint.script // empty' "$file")
    serve_dir=$(jq -r '.entrypoint.serve_dir // empty' "$file")

    local pair name val
    for pair in "install.marker_file:$marker_file" \
                "entrypoint.working_dir:$working_dir" \
                "entrypoint.script:$script" \
                "entrypoint.serve_dir:$serve_dir"; do
        name="${pair%%:*}"
        val="${pair#*:}"
        if ! is_safe_ext_path "$val"; then
            print_fail "External $name is unsafe (path traversal / leading slash / illegal chars): '$val'"
            errs=$((errs + 1))
        fi
    done

    # working_dir is required for external demos
    if [ -z "$working_dir" ]; then
        print_fail "External demo must set entrypoint.working_dir"
        errs=$((errs + 1))
    fi

    # web-static: serve_dir + integer port in range
    if [ "$etype" = "web-static" ]; then
        if [ -z "$serve_dir" ]; then
            print_fail "External web-static demo must set entrypoint.serve_dir"
            errs=$((errs + 1))
        fi
        local port
        port=$(jq -r '.entrypoint.port // empty' "$file")
        if [ -z "$port" ]; then
            print_fail "External web-static demo must set entrypoint.port"
            errs=$((errs + 1))
        elif ! echo "$port" | grep -qE '^[0-9]+$' || [ "$port" -lt 1024 ] || [ "$port" -gt 65535 ]; then
            print_fail "External web-static entrypoint.port must be an integer 1024-65535: '$port'"
            errs=$((errs + 1))
        fi
    fi

    EXT_ERR_COUNT=$errs
}

# Validate a single manifest file
validate_manifest() {
    local file="$1"
    local filename
    filename=$(basename "$file")
    local errors=0
    local warnings=0

    echo ""
    echo "Validating: $filename"
    echo "----------------------------------------"

    # Check JSON syntax
    if ! jq empty "$file" 2>/dev/null; then
        print_fail "Invalid JSON syntax"
        FAILED=$((FAILED + 1))
        return 1
    fi
    print_pass "Valid JSON syntax"

    # Check required fields
    for field in id name category description entrypoint; do
        if ! jq -e ".$field" "$file" > /dev/null 2>&1; then
            print_fail "Missing required field: $field"
            errors=$((errors + 1))
        fi
    done

    if [ $errors -eq 0 ]; then
        print_pass "All required fields present"
    fi

    # Get values for validation
    local id
    id=$(jq -r '.id // ""' "$file")
    local category
    category=$(jq -r '.category // ""' "$file")
    local entrypoint_type
    entrypoint_type=$(jq -r '.entrypoint.type // ""' "$file")
    local launcher
    launcher=$(jq -r '.entrypoint.launcher // ""' "$file")
    local display
    display=$(jq -r '.needs_hw.display // "none"' "$file")
    local token
    token=$(jq -r '.needs_ibm_token // "none"' "$file")

    # Validate ID matches filename. External manifests are validated inside
    # the demo repo checkout, where the file carries the registry's
    # manifest_path name (conventionally rqb-demo.json); the rq_demo_<id>.json
    # naming is applied by the add-flow when copying into the user manifest
    # dir, so this check does not apply in --external mode.
    if [ "$EXTERNAL" = "true" ]; then
        print_pass "Filename check skipped (external manifest named by registry manifest_path)"
    else
        local expected_filename="rq_demo_${id}.json"
        if [ "$filename" != "$expected_filename" ]; then
            print_fail "ID '$id' doesn't match filename (expected: $expected_filename)"
            errors=$((errors + 1))
        else
            print_pass "ID matches filename"
        fi
    fi

    # Validate ID format (lowercase, hyphens only)
    if ! echo "$id" | grep -qE '^[a-z0-9-]+$'; then
        print_fail "ID must be lowercase alphanumeric with hyphens only: $id"
        errors=$((errors + 1))
    fi

    # Validate category
    if ! echo "$VALID_CATEGORIES" | jq -e "index(\"$category\")" > /dev/null 2>&1; then
        print_fail "Invalid category: $category (valid: game, visualization, education, jupyter, led-demo, tool)"
        errors=$((errors + 1))
    else
        print_pass "Valid category: $category"
    fi

    # Validate entrypoint: either type or launcher must be specified
    if [ -z "$entrypoint_type" ] && [ -z "$launcher" ]; then
        print_fail "entrypoint must have either 'type' or 'launcher'"
        errors=$((errors + 1))
    elif [ -n "$entrypoint_type" ]; then
        # Accept "script" as legacy type (still works, not documented)
        if [ "$entrypoint_type" = "script" ]; then
            print_pass "Valid entrypoint type: $entrypoint_type (legacy, uses launcher)"
        elif ! echo "$VALID_ENTRYPOINT_TYPES" | jq -e "index(\"$entrypoint_type\")" > /dev/null 2>&1; then
            print_fail "Invalid entrypoint type: $entrypoint_type (valid: python, jupyter, docker, browser)"
            errors=$((errors + 1))
        else
            print_pass "Valid entrypoint type: $entrypoint_type"
        fi
    else
        print_pass "Using launcher fallback: $launcher"
    fi

    # Validate display value
    if ! echo "$VALID_DISPLAY_VALUES" | jq -e "index(\"$display\")" > /dev/null 2>&1; then
        print_fail "Invalid display value: $display (valid: none, optional, required)"
        errors=$((errors + 1))
    fi

    # Validate token value
    if ! echo "$VALID_TOKEN_VALUES" | jq -e "index(\"$token\")" > /dev/null 2>&1; then
        print_fail "Invalid needs_ibm_token value: $token (valid: none, prefer, required)"
        errors=$((errors + 1))
    fi

    # Check for duplicate IDs (will be checked globally)

    # Optional: Check referenced files exist
    if $CHECK_FILES; then
        # Check patch file
        local patch_file
        patch_file=$(jq -r '.install.patch_file // ""' "$file")
        if [ -n "$patch_file" ]; then
            if [ -f "$PATCHES_DIR/$patch_file" ]; then
                print_pass "Patch file exists: $patch_file"
            else
                print_warn "Patch file not found: $patch_file"
                warnings=$((warnings + 1))
            fi
        fi

        # Check launcher script
        local launcher
        launcher=$(jq -r '.entrypoint.launcher // ""' "$file")
        if [ -n "$launcher" ]; then
            if [ -f "$SCRIPT_DIR/$launcher" ]; then
                print_pass "Launcher script exists: $launcher"
            else
                print_warn "Launcher script not found: $launcher"
                warnings=$((warnings + 1))
            fi
        fi
    fi

    # External-demo constraints (only in --external mode)
    if $EXTERNAL; then
        validate_external_constraints "$file"
        if [ "$EXT_ERR_COUNT" -eq 0 ]; then
            print_pass "External constraints satisfied"
        fi
        errors=$((errors + EXT_ERR_COUNT))
    fi

    # Summary for this file
    if [ $errors -gt 0 ]; then
        print_fail "Validation failed with $errors error(s)"
        FAILED=$((FAILED + 1))
        return 1
    else
        if [ $warnings -gt 0 ]; then
            print_pass "Validation passed with $warnings warning(s)"
            WARNINGS=$((WARNINGS + warnings))
        else
            print_pass "Validation passed"
        fi
        PASSED=$((PASSED + 1))
        return 0
    fi
}

# Check for duplicate IDs across all manifests
check_duplicate_ids() {
    echo ""
    echo "Checking for duplicate IDs..."
    echo "----------------------------------------"

    local ids
    ids=$(find "$MANIFEST_DIR" -name 'rq_demo_*.json' -exec jq -r '.id // empty' {} \; 2>/dev/null | sort)
    local duplicates
    duplicates=$(echo "$ids" | uniq -d)

    if [ -n "$duplicates" ]; then
        print_fail "Duplicate IDs found:"
        echo "$duplicates" | while read -r dup; do
            print_info "  - $dup"
        done
        return 1
    else
        print_pass "No duplicate IDs found"
        return 0
    fi
}

# Main
main() {
    check_jq

    # Parse arguments
    local files=()
    for arg in "$@"; do
        case "$arg" in
            --check-files)
                CHECK_FILES=true
                ;;
            --external)
                EXTERNAL=true
                ;;
            --help|-h)
                echo "Usage: $0 [options] [manifest.json ...]"
                echo ""
                echo "Options:"
                echo "  --check-files    Also verify referenced files exist"
                echo "  --external       Enforce hardened external-demo constraints"
                echo "                   (rejects launcher/patch_file/command, path"
                echo "                   traversal, non-https repo_url; see EXTERNAL_DEMOS.md)"
                echo "  --help, -h       Show this help"
                echo ""
                echo "If no manifest files specified, validates all in $MANIFEST_DIR"
                exit 0
                ;;
            *)
                files+=("$arg")
                ;;
        esac
    done

    echo "========================================"
    echo "RasQberry Demo Manifest Validator"
    echo "========================================"

    # If no files specified, validate all across the manifest search path
    # (shipped + user; shipped wins on id collision)
    if [ ${#files[@]} -eq 0 ]; then
        while IFS= read -r file; do
            [ -n "$file" ] && files+=("$file")
        done < <(rq_list_manifests "$MANIFEST_DIR")
    fi

    if [ ${#files[@]} -eq 0 ]; then
        echo "No manifest files found in $MANIFEST_DIR"
        exit 1
    fi

    # Validate each file
    for file in "${files[@]}"; do
        TOTAL=$((TOTAL + 1))
        validate_manifest "$file" || true
    done

    # Check for duplicates if validating all
    if [ ${#files[@]} -gt 1 ]; then
        check_duplicate_ids || FAILED=$((FAILED + 1))
    fi

    # Final summary
    echo ""
    echo "========================================"
    echo "Summary"
    echo "========================================"
    echo "Total:    $TOTAL"
    echo -e "Passed:   ${GREEN}$PASSED${NC}"
    echo -e "Failed:   ${RED}$FAILED${NC}"
    echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"
    echo ""

    if [ $FAILED -gt 0 ]; then
        exit 1
    fi
    exit 0
}

main "$@"
