#!/bin/bash
# ============================================================================
# Basic Code Quality Validation
# ============================================================================
# Performs fundamental syntax and safety checks on shell and Python scripts
#
# This test catches:
# 1. Shell script syntax errors
# 2. Python script syntax errors
# 3. Missing safety flags (set -euo pipefail)
# 4. USER_HOME redefinition violations
# 5. Missing SCRIPT_DIR pattern in scripts using rq_common.sh
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BIN_DIR="$PROJECT_ROOT/RQB2-bin"
CONFIG_DIR="$PROJECT_ROOT/RQB2-config"

ERRORS=0
WARNINGS=0

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
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

header() {
    echo -e "${BLUE}=== $* ===${NC}"
}

echo "=== RasQberry-Two Basic Code Quality Validation ==="
echo

# ============================================================================
# CHECK 1: Shell Script Syntax Validation
# ============================================================================
header "1. Shell Script Syntax Check"

SHELL_ERRORS=0
SHELL_CHECKED=0

for script in "$BIN_DIR"/*.sh "$CONFIG_DIR"/*.sh; do
    [ -f "$script" ] || continue

    script_name=$(basename "$script")
    SHELL_CHECKED=$((SHELL_CHECKED + 1))

    if bash -n "$script" 2>/dev/null; then
        echo "  ✓ $script_name"
    else
        error "$script_name: Syntax error detected"
        echo "    Run: bash -n $script"
        SHELL_ERRORS=$((SHELL_ERRORS + 1))
    fi
done

if [ $SHELL_ERRORS -eq 0 ]; then
    info "All $SHELL_CHECKED shell scripts passed syntax check"
else
    error "$SHELL_ERRORS of $SHELL_CHECKED shell scripts have syntax errors"
fi

echo

# ============================================================================
# CHECK 2: Python Script Syntax Validation
# ============================================================================
header "2. Python Script Syntax Check"

if ! command -v python3 >/dev/null 2>&1; then
    warn "Python3 not found - skipping Python validation"
else
    PYTHON_ERRORS=0
    PYTHON_CHECKED=0

    for script in "$BIN_DIR"/*.py; do
        [ -f "$script" ] || continue

        script_name=$(basename "$script")
        PYTHON_CHECKED=$((PYTHON_CHECKED + 1))

        if python3 -m py_compile "$script" 2>/dev/null; then
            echo "  ✓ $script_name"
        else
            error "$script_name: Python syntax error detected"
            echo "    Run: python3 -m py_compile $script"
            PYTHON_ERRORS=$((PYTHON_ERRORS + 1))
        fi
    done

    # Cleanup __pycache__
    find "$BIN_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

    if [ $PYTHON_ERRORS -eq 0 ]; then
        info "All $PYTHON_CHECKED Python scripts passed syntax check"
    else
        error "$PYTHON_ERRORS of $PYTHON_CHECKED Python scripts have syntax errors"
    fi
fi

echo

# ============================================================================
# CHECK 3: Safety Flags Coverage (set -euo pipefail)
# ============================================================================
header "3. Safety Flags Coverage Check"

TOTAL_SCRIPTS=0
WITH_SAFETY=0
WITHOUT_SAFETY=()

for script in "$BIN_DIR"/*.sh; do
    [ -f "$script" ] || continue
    script_name=$(basename "$script")

    # Skip scripts that are intentionally without safety flags
    case "$script_name" in
        # These scripts are sourced, not executed
        "rq_common.sh")
            continue
            ;;
    esac

    TOTAL_SCRIPTS=$((TOTAL_SCRIPTS + 1))

    if grep -q "set -euo pipefail\|set -eo pipefail" "$script" 2>/dev/null; then
        WITH_SAFETY=$((WITH_SAFETY + 1))
    else
        WITHOUT_SAFETY+=("$script_name")
    fi
done

PERCENTAGE=$((WITH_SAFETY * 100 / TOTAL_SCRIPTS))

echo "  Scripts with safety flags: $WITH_SAFETY/$TOTAL_SCRIPTS ($PERCENTAGE%)"

if [ ${#WITHOUT_SAFETY[@]} -gt 0 ]; then
    echo ""
    echo "  Scripts without 'set -euo pipefail':"
    for script in "${WITHOUT_SAFETY[@]}"; do
        echo "    - $script"
    done
fi

if [ $PERCENTAGE -ge 90 ]; then
    info "Safety flag coverage: $PERCENTAGE% (target: ≥90%)"
elif [ $PERCENTAGE -ge 80 ]; then
    warn "Safety flag coverage: $PERCENTAGE% (target: ≥90%)"
else
    error "Safety flag coverage: $PERCENTAGE% (below minimum 80%)"
fi

echo

# ============================================================================
# CHECK 4: USER_HOME Redefinition Check (CRITICAL)
# ============================================================================
header "4. USER_HOME Redefinition Check"

USER_HOME_VIOLATIONS=()

for script in "$BIN_DIR"/*.sh; do
    [ -f "$script" ] || continue
    script_name=$(basename "$script")

    # Skip rq_common.sh (it exports USER_HOME from env-config)
    [ "$script_name" = "rq_common.sh" ] && continue

    # Look for USER_HOME assignments (but not exports or comments)
    if grep -n "USER_HOME=" "$script" 2>/dev/null | grep -v "export USER_HOME" | grep -v "#.*USER_HOME"; then
        USER_HOME_VIOLATIONS+=("$script_name")
        error "$script_name: Redefines USER_HOME (CRITICAL VIOLATION)"
        echo "    USER_HOME should ONLY be set in rasqberry_env-config.sh"
        echo "    Scripts should use: load_rqb2_env"
    fi
done

if [ ${#USER_HOME_VIOLATIONS[@]} -eq 0 ]; then
    info "No USER_HOME redefinitions found (target: 0)"
else
    error "${#USER_HOME_VIOLATIONS[@]} scripts redefine USER_HOME (CRITICAL)"
fi

echo

# ============================================================================
# CHECK 5: rq_common.sh Library Validation
# ============================================================================
header "5. Common Library Validation"

if [ ! -f "$BIN_DIR/rq_common.sh" ]; then
    error "rq_common.sh not found!"
else
    # Test syntax
    if bash -n "$BIN_DIR/rq_common.sh" 2>/dev/null; then
        info "rq_common.sh syntax valid"
    else
        error "rq_common.sh has syntax errors"
    fi

    # Test that it can be sourced
    if ( cd "$BIN_DIR" && . ./rq_common.sh ) 2>/dev/null; then
        info "rq_common.sh can be sourced successfully"
    else
        error "rq_common.sh cannot be sourced"
    fi

    # Check for essential functions
    MISSING_FUNCTIONS=()
    REQUIRED_FUNCTIONS=(
        "die"
        "warn"
        "info"
        "load_rqb2_env"
        "verify_env_vars"
        "activate_venv"
        "show_yesno"
        "show_msgbox"
        "clone_demo"
        "clear_leds"
    )

    for func in "${REQUIRED_FUNCTIONS[@]}"; do
        if ! grep -q "^$func()" "$BIN_DIR/rq_common.sh" 2>/dev/null; then
            MISSING_FUNCTIONS+=("$func")
        fi
    done

    if [ ${#MISSING_FUNCTIONS[@]} -eq 0 ]; then
        info "All ${#REQUIRED_FUNCTIONS[@]} essential functions present"
    else
        error "${#MISSING_FUNCTIONS[@]} essential functions missing: ${MISSING_FUNCTIONS[*]}"
    fi
fi

echo

# ============================================================================
# CHECK 6: SCRIPT_DIR Pattern Validation
# ============================================================================
header "6. SCRIPT_DIR Pattern Check"

SCRIPT_DIR_VIOLATIONS=()

for script in "$BIN_DIR"/*.sh; do
    [ -f "$script" ] || continue
    script_name=$(basename "$script")

    # Only check scripts that source rq_common.sh
    if grep -q "rq_common.sh" "$script" 2>/dev/null; then
        # Check for proper SCRIPT_DIR pattern
        if ! grep -q 'SCRIPT_DIR=.*cd.*dirname.*BASH_SOURCE' "$script" 2>/dev/null; then
            SCRIPT_DIR_VIOLATIONS+=("$script_name")
            warn "$script_name: Missing or incorrect SCRIPT_DIR pattern"
            echo "    Expected: SCRIPT_DIR=\"\$(cd \"\$(dirname \"\${BASH_SOURCE[0]}\")\" && pwd)\""
        fi
    fi
done

if [ ${#SCRIPT_DIR_VIOLATIONS[@]} -eq 0 ]; then
    info "All scripts using rq_common.sh have correct SCRIPT_DIR pattern"
else
    warn "${#SCRIPT_DIR_VIOLATIONS[@]} scripts have SCRIPT_DIR pattern issues"
fi

echo

# ============================================================================
# CHECK 7: Documentation Files Validation
# ============================================================================
header "7. Documentation Files Check"

REQUIRED_DOCS=(
    "$BIN_DIR/RQ_COMMON_README.md:Common library documentation"
    "$BIN_DIR/_TEMPLATE.sh:Script template"
    "$PROJECT_ROOT/.editorconfig:Editor configuration"
)

for doc_spec in "${REQUIRED_DOCS[@]}"; do
    IFS=':' read -r doc_path doc_desc <<< "$doc_spec"

    if [ -f "$doc_path" ]; then
        line_count=$(wc -l < "$doc_path" 2>/dev/null || echo 0)
        echo "  ✓ $doc_desc ($line_count lines)"
    else
        warn "$doc_desc not found: $doc_path"
    fi
done

echo

# ============================================================================
# CHECK 8: Code Quality Metrics
# ============================================================================
header "8. Code Quality Metrics"

cd "$BIN_DIR"

# Count scripts using modern patterns
USING_COMMON=$(grep -l "rq_common.sh" *.sh 2>/dev/null | grep -v "rq_common.sh" | wc -l)
USING_LOAD_ENV=$(grep -l "load_rqb2_env" *.sh 2>/dev/null | wc -l)
USING_DIE=$(grep -l " die " *.sh 2>/dev/null | wc -l)
USING_ACTIVATE_VENV=$(grep -l "activate_venv" *.sh 2>/dev/null | wc -l)

TOTAL=$(ls -1 *.sh 2>/dev/null | wc -l)

echo "  Library Adoption:"
echo "    Scripts using rq_common.sh:  $USING_COMMON/$TOTAL"
echo "    Scripts using load_rqb2_env: $USING_LOAD_ENV"
echo "    Scripts using die function:  $USING_DIE"
echo "    Scripts using activate_venv: $USING_ACTIVATE_VENV"

echo ""
echo "  Safety & Consistency:"
echo "    Safety flags coverage:       $PERCENTAGE%"
echo "    USER_HOME violations:        ${#USER_HOME_VIOLATIONS[@]} (target: 0)"

cd "$PROJECT_ROOT"

echo

# ============================================================================
# SUMMARY
# ============================================================================
header "Validation Summary"

echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED${NC}"
    echo ""
    echo "  All basic validation checks completed successfully!"
    echo "  - Shell scripts: Syntax OK"
    echo "  - Python scripts: Syntax OK"
    echo "  - Safety flags: $PERCENTAGE% coverage"
    echo "  - USER_HOME: No violations"
    echo "  - Common library: Valid"
    echo ""
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠️  PASSED WITH WARNINGS${NC}"
    echo ""
    echo "  No errors found, but $WARNINGS warnings issued"
    echo "  Review warnings above for improvement opportunities"
    echo ""
else
    echo -e "${RED}❌ VALIDATION FAILED${NC}"
    echo ""
    echo "  Errors: $ERRORS"
    echo "  Warnings: $WARNINGS"
    echo ""
    echo "  Please fix the errors above before committing"
    echo ""
fi

# Exit with error if any errors were found
if [ $ERRORS -gt 0 ]; then
    exit 1
fi

exit 0
