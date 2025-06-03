#!/bin/bash
# Integration example: Updated get_demo_venv() function

# Enhanced version that uses PYTHONPATH manipulation instead of separate venvs
get_demo_venv() {
    local DEMO_NAME="$1"
    local VENV_VAR="${DEMO_NAME}_VENV"
    local DEMO_QISKIT_VERSION
    local UNIFIED_VENV_PATH
    
    # Get the demo-specific Qiskit version requirement
    eval "DEMO_QISKIT_VERSION=\${${VENV_VAR}:-$DEFAULT_QISKIT_VENV}"
    
    # Use unified virtual environment
    UNIFIED_VENV_PATH="$USER_HOME/$REPO/venv/RQB2-unified/bin/activate"
    
    # Validate that the unified virtual environment exists
    if [ ! -f "$UNIFIED_VENV_PATH" ]; then
        echo "Error: Unified virtual environment not found!" >&2
        return 1
    fi
    
    # Set up version-specific PYTHONPATH before returning
    setup_qiskit_version "$DEMO_QISKIT_VERSION"
    
    echo "$UNIFIED_VENV_PATH"
}

# New function: Set up PYTHONPATH for specific Qiskit version
setup_qiskit_version() {
    local VERSION="$1"
    local LEGACY_BASE="$USER_HOME/$REPO/venv/RQB2-unified/legacy"
    
    # Clean up any existing legacy paths
    export PYTHONPATH=$(echo "$PYTHONPATH" | tr ':' '\n' | grep -v "$LEGACY_BASE" | tr '\n' ':' | sed 's/:$//')
    
    case "$VERSION" in
        "RQB2-v14"|"1.4")
            # Prepend Qiskit 1.4 legacy path
            local QISKIT_14_PATH="$LEGACY_BASE/qiskit-1.4"
            if [ -d "$QISKIT_14_PATH" ]; then
                export PYTHONPATH="$QISKIT_14_PATH:$PYTHONPATH"
                echo "Using Qiskit 1.4 from legacy installation"
            else
                echo "Warning: Qiskit 1.4 legacy path not found, using default"
            fi
            ;;
        "RQB2-v044"|"0.44")
            # Prepend Qiskit 0.44 legacy path
            local QISKIT_044_PATH="$LEGACY_BASE/qiskit-0.44"
            if [ -d "$QISKIT_044_PATH" ]; then
                export PYTHONPATH="$QISKIT_044_PATH:$PYTHONPATH"
                echo "Using Qiskit 0.44 from legacy installation"
            else
                echo "Warning: Qiskit 0.44 legacy path not found, using default"
            fi
            ;;
        "RQB2"|"latest"|*)
            # Use default (latest) Qiskit from standard site-packages
            echo "Using latest Qiskit from standard installation"
            ;;
    esac
}

# Updated run_demo function with version setup
run_demo() {
    # Mode selection: default is pty; allow "bg" as first arg
    MODE="pty"
    if [ "$1" = bg ]; then MODE="bg"; shift; fi
    DEMO_TITLE="$1"; shift
    DEMO_DIR="$1"; shift
    
    # Build the command string from all remaining args
    CMD="$1"
    shift
    for arg in "$@"; do
        CMD="$CMD $arg"
    done
    
    # Get the unified virtual environment path and set up version
    VENV_PATH=$(get_demo_venv "$(basename "$DEMO_DIR")")
    
    if [ -f "$VENV_PATH" ]; then
        # Activate unified venv and preserve PYTHONPATH
        CMD=". \"$VENV_PATH\" && export PYTHONPATH=\"$PYTHONPATH\" && exec $CMD"
    fi
    
    # Rest of the function remains the same...
    # Save current terminal settings
    OLD_STTY=$(stty -g)
    # Reset terminal state before launching
    stty sane
    
    # Launch the demo
    if [ "$MODE" = "pty" ]; then
        ( trap '' INT; cd "$DEMO_DIR" && exec setsid script -qfc "$CMD" /dev/null ) &
    else
        ( trap '' INT; cd "$DEMO_DIR" && exec setsid sh -c "$CMD" ) &
    fi
    
    DEMO_PID=$!
    # ... rest remains the same
}

# Example usage with environment variables:
# QUANTUM_FRACTALS_VENV=RQB2-v14     # Will use Qiskit 1.4
# GROK_BLOCH_VENV=RQB2               # Will use latest Qiskit
# QUANTUM_LIGHTS_OUT_VENV=RQB2       # Will use latest Qiskit