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
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
MANIFEST_DIR="$REPO_DIR/RQB2-config/demo-manifests"
PATCHES_DIR="$REPO_DIR/RQB2-config/demo-patches"

# Counters
TOTAL=0
PASSED=0
FAILED=0
WARNINGS=0

# Options
CHECK_FILES=false

# Required fields for validation
REQUIRED_FIELDS='["id", "name", "category", "description", "entrypoint"]'
VALID_CATEGORIES='["game", "visualization", "education", "jupyter", "led-demo", "tool"]'
VALID_ENTRYPOINT_TYPES='["python", "script", "jupyter", "docker", "browser"]'
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
        ((FAILED++))
        return 1
    fi
    print_pass "Valid JSON syntax"

    # Check required fields
    for field in id name category description entrypoint; do
        if ! jq -e ".$field" "$file" > /dev/null 2>&1; then
            print_fail "Missing required field: $field"
            ((errors++))
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
    local display
    display=$(jq -r '.needs_hw.display // "none"' "$file")
    local token
    token=$(jq -r '.needs_ibm_token // "none"' "$file")

    # Validate ID matches filename
    local expected_filename="rq_demo_${id}.json"
    if [ "$filename" != "$expected_filename" ]; then
        print_fail "ID '$id' doesn't match filename (expected: $expected_filename)"
        ((errors++))
    else
        print_pass "ID matches filename"
    fi

    # Validate ID format (lowercase, hyphens only)
    if ! echo "$id" | grep -qE '^[a-z0-9-]+$'; then
        print_fail "ID must be lowercase alphanumeric with hyphens only: $id"
        ((errors++))
    fi

    # Validate category
    if ! echo "$VALID_CATEGORIES" | jq -e "index(\"$category\")" > /dev/null 2>&1; then
        print_fail "Invalid category: $category (valid: game, visualization, education, jupyter, led-demo, tool)"
        ((errors++))
    else
        print_pass "Valid category: $category"
    fi

    # Validate entrypoint type
    if [ -n "$entrypoint_type" ]; then
        if ! echo "$VALID_ENTRYPOINT_TYPES" | jq -e "index(\"$entrypoint_type\")" > /dev/null 2>&1; then
            print_fail "Invalid entrypoint type: $entrypoint_type"
            ((errors++))
        else
            print_pass "Valid entrypoint type: $entrypoint_type"
        fi
    fi

    # Validate display value
    if ! echo "$VALID_DISPLAY_VALUES" | jq -e "index(\"$display\")" > /dev/null 2>&1; then
        print_fail "Invalid display value: $display (valid: none, optional, required)"
        ((errors++))
    fi

    # Validate token value
    if ! echo "$VALID_TOKEN_VALUES" | jq -e "index(\"$token\")" > /dev/null 2>&1; then
        print_fail "Invalid needs_ibm_token value: $token (valid: none, prefer, required)"
        ((errors++))
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
                ((warnings++))
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
                ((warnings++))
            fi
        fi
    fi

    # Summary for this file
    if [ $errors -gt 0 ]; then
        print_fail "Validation failed with $errors error(s)"
        ((FAILED++))
        return 1
    else
        if [ $warnings -gt 0 ]; then
            print_pass "Validation passed with $warnings warning(s)"
            ((WARNINGS += warnings))
        else
            print_pass "Validation passed"
        fi
        ((PASSED++))
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
            --help|-h)
                echo "Usage: $0 [options] [manifest.json ...]"
                echo ""
                echo "Options:"
                echo "  --check-files    Also verify referenced files exist"
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

    # If no files specified, validate all
    if [ ${#files[@]} -eq 0 ]; then
        while IFS= read -r -d '' file; do
            files+=("$file")
        done < <(find "$MANIFEST_DIR" -name 'rq_demo_*.json' -not -name '*schema*' -print0 2>/dev/null | sort -z)
    fi

    if [ ${#files[@]} -eq 0 ]; then
        echo "No manifest files found in $MANIFEST_DIR"
        exit 1
    fi

    # Validate each file
    for file in "${files[@]}"; do
        ((TOTAL++))
        validate_manifest "$file" || true
    done

    # Check for duplicates if validating all
    if [ ${#files[@]} -gt 1 ]; then
        check_duplicate_ids || ((FAILED++))
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
