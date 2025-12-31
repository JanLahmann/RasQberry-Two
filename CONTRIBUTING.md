# Contributing to RasQberry-Two

Thank you for your interest in contributing to RasQberry-Two! This project aims to make quantum computing accessible and engaging through hands-on demonstrations on Raspberry Pi hardware.

We welcome contributions of all kinds: new quantum computing demos, bug fixes, documentation improvements, and more.

## Table of Contents

- [Quick Start](#quick-start)
- [Adding a New Quantum Computing Demo](#adding-a-new-quantum-computing-demo)
- [Project Structure](#project-structure)
- [Coding Standards](#coding-standards)
- [Testing Your Changes](#testing-your-changes)
- [Submitting Pull Requests](#submitting-pull-requests)
- [Getting Help](#getting-help)

---

## Quick Start

### Prerequisites

- Basic knowledge of Bash scripting
- Python 3.11+ programming skills
- Familiarity with Qiskit (for quantum demos)
- Understanding of Git and GitHub workflows

### Development Setup

1. **Fork and Clone**
   ```bash
   git fork https://github.com/JanLahmann/RasQberry-Two.git
   cd RasQberry-Two
   ```

2. **Create a Feature Branch**
   ```bash
   git checkout -b feature/my-new-demo
   ```

3. **Test on Raspberry Pi**
   - Build or download a RasQberry image
   - Test your changes on actual hardware
   - Ensure demos work with LED panels (if applicable)

---

## Adding a New Quantum Computing Demo

This is the most common contribution type. Follow these steps to integrate a new quantum computing demonstration.

### Step 1: Prepare Your Demo Repository

Create a GitHub repository for your demo with:

**Required Files:**
- `main.py` (or your demo's entry point)
- `requirements.txt` (Python dependencies)
- `README.md` (description, usage, educational value)

**Optional Files:**
- `.rasqberry.yml` (metadata for future auto-discovery)
- Screenshots/videos
- Example circuits
- Educational materials

**Example Structure:**
```
my-quantum-demo/
├── main.py                 # Demo entry point
├── requirements.txt        # Dependencies (qiskit, numpy, etc.)
├── README.md              # Documentation
├── assets/                # Images, data files
└── examples/              # Example quantum circuits
```

### Step 2: Add Configuration Variables

Edit `RQB2-config/rasqberry_environment.env` to add your demo's Git URL:

```bash
# Add at the end of the file:
# My Quantum Demo
GIT_REPO_DEMO_MYQUANTUM=https://github.com/your-username/my-quantum-demo.git
MYQUANTUM_INSTALLED=false
```

**Variable Naming Convention:**
- Git URLs: `GIT_REPO_DEMO_<NAME>`
- Installation flags: `<NAME>_INSTALLED`
- Use UPPERCASE with underscores

### Step 3: Create a Launcher Script

Copy the template and customize:

```bash
cp RQB2-bin/_TEMPLATE.sh RQB2-bin/rq_myquantum.sh
```

Edit `rq_myquantum.sh`:

```bash
#!/bin/bash
# ============================================================================
# RasQberry: My Quantum Demo Launcher
# ============================================================================
# Description: Launches my quantum computing demonstration
# Usage: ./rq_myquantum.sh [args]

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# SETUP
# ============================================================================

# Load common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load and verify environment
load_rqb2_env
verify_env_vars REPO USER_HOME STD_VENV

# ============================================================================
# CONFIGURATION
# ============================================================================

# Demo-specific configuration
DEMO_NAME="my-quantum-demo"
DEMO_DIR=$(get_demo_dir "$DEMO_NAME")
GIT_URL="${GIT_REPO_DEMO_MYQUANTUM}"

# ============================================================================
# FUNCTIONS
# ============================================================================

# Cleanup function (called on script exit)
cleanup() {
    info "Cleaning up..."
    clear_leds  # Turn off LEDs when demo ends
}

# Check if demo is installed
check_demo_installed() {
    if ! ensure_demo_dir "$DEMO_NAME" >/dev/null 2>&1; then
        return 1
    fi
    return 0
}

# Install demo if needed
install_demo_if_needed() {
    if ! check_demo_installed; then
        # Ask user to install (with size info)
        ask_demo_install "$DEMO_NAME" "5MB" "10MB" || return 1

        # Clone repository
        clone_demo "$GIT_URL" "$DEMO_DIR"

        # Update environment tracking
        update_env_var "${DEMO_NAME}_INSTALLED" "true"

        info "Demo installed successfully"
    fi
}

# Main demo logic
run_demo() {
    info "Launching $DEMO_NAME..."

    # Activate virtual environment
    activate_venv || die "Virtual environment not found"

    # Change to demo directory
    cd "$DEMO_DIR" || die "Cannot change to demo directory"

    # Run the demo
    exec python3 main.py "$@"
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    # Setup cleanup handler
    setup_cleanup_trap cleanup

    # Check dependencies (uncomment if needed)
    # check_display || die "This demo requires a graphical display"
    # require_command docker "Docker is required for this demo"

    # Install if needed
    install_demo_if_needed || die "Demo installation failed or cancelled"

    # Run demo
    run_demo "$@"
}

# Run main function
main "$@"
```

**Make the script executable:**
```bash
chmod +x RQB2-bin/rq_myquantum.sh
```

### Step 4: Add Menu Entry

Edit `RQB2-config/RQB2_menu.sh` to add your demo to the menu system.

**Add a runner function** (around line 300-400):

```bash
# Run My Quantum Demo
run_myquantum_demo() {
    # Launch the demo using the dedicated launcher script
    "$BIN_DIR/rq_myquantum.sh"
}
```

**Add menu item** in `do_quantum_demo_menu()` function (around line 520):

```bash
do_quantum_demo_menu() {
  while true; do
    FUN=$(show_menu "RasQberry: Quantum Demos" "Select demo category" \
       LED  "Test LEDs" \
       QLO  "Quantum-Lights-Out Demo" \
       QRT  "Quantum Raspberry-Tie" \
       GRB  "Grok Bloch Sphere (Local)" \
       MQD  "My Quantum Demo" \          # <-- Add this line
       # ... other menu items ...
       STOP "Stop last running demo and clear LEDs") || break
    case "$FUN" in
      LED)  do_select_led_option       || { handle_error "Failed to open LED options."; continue; } ;;
      QLO)  do_select_qlo_option       || { handle_error "Failed to open QLO options."; continue; } ;;
      QRT)  do_select_qrt_option       || { handle_error "Failed to open QRT options."; continue; } ;;
      GRB)  run_grok_bloch_demo        || continue ;;
      MQD)  run_myquantum_demo         || { handle_error "Failed to run My Quantum Demo."; continue; } ;;  # <-- Add this line
      # ... other cases ...
    esac
  done
}
```

### Step 5: Create Desktop Launcher (Optional)

If you want users to launch your demo from the desktop, create a `.desktop` file:

**Create:** `stage-RQB2/06-desktop-integration/files/Desktop/MyQuantumDemo.desktop`

```ini
[Desktop Entry]
Type=Application
Name=My Quantum Demo
Comment=Run my quantum computing demonstration
Icon=/usr/share/pixmaps/rasqberry-icon.png
Exec=lxterminal -e /usr/bin/rq_myquantum.sh
Terminal=true
Categories=Education;Science;
```

**Install location:** This will be automatically copied during image build.

### Step 6: Create Demo Manifest (Recommended)

Create a manifest file to register your demo in the manifest system. This enables automatic menu generation and validation.

**Create:** `RQB2-config/demo-manifests/rq_demo_<your-demo-id>.json`

```json
{
  "id": "my-quantum-demo",
  "name": "My Quantum Demo",
  "category": "visualization",
  "description": "Brief description of your demo (max 200 chars)",
  "keywords": ["quantum", "demo", "your-keywords"],

  "entrypoint": {
    "type": "python",
    "script": "main.py",
    "working_dir": "my-quantum-demo",
    "launcher": "rq_myquantum.sh"
  },

  "install": {
    "preinstalled": false,
    "repo_url": "https://github.com/your-username/my-quantum-demo.git",
    "marker_file": "main.py"
  },

  "needs_hw": {
    "leds": true,
    "display": "optional"
  },
  "needs_ibm_token": "none",
  "browser_based": false,
  "loop_ok": true,
  "timeout": 60,

  "menu": {
    "show": true,
    "order": 50
  },

  "desktop": {
    "show": true,
    "terminal": true
  }
}
```

**Key fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique ID (lowercase, hyphens only) |
| `name` | Yes | Display name |
| `category` | Yes | `game`, `visualization`, `education`, `jupyter`, `led-demo`, or `tool` |
| `description` | Yes | Short description (max 200 chars) |
| `entrypoint.type` | Yes | `python`, `script`, `jupyter`, `docker`, or `browser` |
| `entrypoint.launcher` | No | Launcher script in RQB2-bin/ |
| `install.repo_url` | No | Git URL for cloning |
| `install.marker_file` | No | File that indicates demo is installed |
| `install.patch_file` | No | Patch file in demo-patches/ for RasQberry customizations |
| `needs_hw.leds` | No | Requires LED matrix (default: false) |
| `needs_hw.display` | No | `none`, `optional`, or `required` |
| `needs_ibm_token` | No | `none`, `prefer`, or `required` |
| `loop_ok` | No | Safe for demo loop (default: true) |

**Validate your manifest:**

```bash
./RQB2-bin/rq_demo_validate.sh RQB2-config/demo-manifests/rq_demo_my-quantum-demo.json
```

**View generated menu items:**

```bash
./RQB2-bin/rq_demo_generate_menu.sh --list
```

See the [schema file](RQB2-config/demo-manifests/rq_demo_schema.json) for complete field documentation.

### Step 7: Document Your Demo

Add documentation to the website (gh-pages branch):

**Create:** `content/03-quantum-computing-demos/my-quantum-demo.md`

```markdown
---
title: My Quantum Demo
description: Brief description of what your demo does
---

# My Quantum Demo

## Overview

Describe what your demo does and what quantum concepts it demonstrates.

## Educational Value

Explain what users will learn:
- Quantum superposition
- Entanglement
- Measurement
- etc.

## Requirements

**Hardware:**
- Raspberry Pi 5 (or Pi 4)
- LED panels: Required / Not required
- Display: Required / Optional

**Software:**
- Pre-installed in RasQberry
- Additional dependencies: [list if any]

## How to Run

### From RasQberry Menu
1. Open terminal
2. Run `sudo raspi-config`
3. Select "0 RasQberry"
4. Select "Quantum Demos"
5. Select "My Quantum Demo"

### From Desktop
Double-click the "My Quantum Demo" icon on the desktop.

### From Command Line
```bash
/usr/bin/rq_myquantum.sh
```

## How It Works

Explain the demo's operation:
1. Initialize quantum circuit
2. Apply quantum gates
3. Visualize results
4. etc.

### Example Circuit

Show example quantum circuit or code:

```python
from qiskit import QuantumCircuit

qc = QuantumCircuit(3, 3)
qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)
qc.measure(range(3), range(3))
```

## Screenshots

![Demo in action](../assets/my-quantum-demo-screenshot.png)

## Technical Details

**Quantum Concepts:**
- [Concept 1]
- [Concept 2]

**Qiskit Features Used:**
- QuantumCircuit
- AerSimulator
- etc.

## Troubleshooting

### LED panels not working
Check LED connection to GPIO pin 21.

### Import errors
Ensure virtual environment is activated.

## References

- Link to your repository
- Related papers
- Educational resources

## Contributing

Found a bug? Want to improve this demo?
Visit: https://github.com/your-username/my-quantum-demo
```

**Update the demo list** in `content/03-quantum-computing-demos/01-demo-list.md`

---

## Project Structure

Understanding the project layout helps you navigate and contribute effectively.

### Core Directories

```
RasQberry-Two/
├── RQB2-config/              # Configuration & environment
│   ├── rasqberry_environment.env  # Central config file
│   ├── rasqberry_env-config.sh    # Environment loader
│   ├── RQB2_menu.sh              # Main menu system
│   └── setup_qiskit_env.sh       # Qiskit setup
│
├── RQB2-bin/                 # Executable scripts
│   ├── rq_common.sh         # Common shell library ⭐
│   ├── rq_led_utils.py      # LED utilities library ⭐
│   ├── _TEMPLATE.sh         # Template for new scripts ⭐
│   ├── rq_*.sh              # Demo launcher scripts
│   └── *.py                 # Python utilities and demos
│
├── stage-RQB2/               # pi-gen build system
│   ├── 00-*/                # Build stages
│   ├── 01-deploy-files/     # File deployment
│   ├── 03-install-qiskit/   # Qiskit installation
│   └── 06-desktop-integration/  # Desktop files
│
├── content/                  # Website (gh-pages branch)
│   └── 03-quantum-computing-demos/  # Demo documentation
│
├── tests/                    # Validation scripts
│   ├── test_basic_validation.sh
│   └── test_common_library_usage.sh
│
└── .github/workflows/        # CI/CD
    └── code-quality.yml      # Automated testing
```

### Key Files

| File | Purpose |
|------|---------|
| `RQB2-bin/rq_common.sh` | Shell script library with reusable functions |
| `RQB2-bin/rq_led_utils.py` | Python LED control utilities |
| `RQB2-bin/_TEMPLATE.sh` | Template for new demo launchers |
| `RQB2-bin/rq_demo_validate.sh` | Validate demo manifest files |
| `RQB2-bin/rq_demo_generate_menu.sh` | Generate menu entries from manifests |
| `RQB2-config/rasqberry_environment.env` | All configuration variables |
| `RQB2-config/RQB2_menu.sh` | Interactive menu integrated into raspi-config |
| `RQB2-config/demo-manifests/rq_demo_*.json` | Demo manifest files |
| `RQB2-config/demo-manifests/rq_demo_schema.json` | JSON schema for manifest validation |

---

## Coding Standards

Following these standards ensures consistency and maintainability.

### Shell Script Standards

**1. Use the Template**

Start all new shell scripts from `RQB2-bin/_TEMPLATE.sh`:
```bash
cp RQB2-bin/_TEMPLATE.sh RQB2-bin/your_script.sh
```

**2. Include Safety Flags**

Add at the top of every standalone script:
```bash
#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures
```

**Exception:** Scripts sourced by other scripts (like `RQB2_menu.sh`) should NOT use these flags.

**3. Use Common Library Functions**

Always use `rq_common.sh` instead of duplicating code:

```bash
# Load common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load environment
load_rqb2_env
verify_env_vars REPO USER_HOME STD_VENV

# Use library functions
activate_venv
demo_dir=$(get_demo_dir "My-Demo")
ensure_demo_dir "My-Demo" || die "Demo not installed"
clear_leds
```

See `RQB2-bin/RQ_COMMON_README.md` for complete function reference.

**4. Never Redefine USER_HOME**

❌ **Bad:**
```bash
USER_HOME="/home/${SUDO_USER}"  # DON'T DO THIS
```

✅ **Good:**
```bash
load_rqb2_env  # USER_HOME is already set correctly
```

**5. Error Handling**

Use standardized error functions:
```bash
die "Fatal error message"     # Print error and exit
warn "Warning message"         # Print warning, continue
info "Info message"           # Print information
debug "Debug message"         # Print only if RQ_DEBUG=1
```

**6. Naming Conventions**

- Installation functions: `do_<name>_install`
- Runner functions: `run_<name>_demo`
- Utility functions: `<verb>_<noun>`
- Scripts: `rq_<name>.sh`

### Python Script Standards

**1. Module Docstrings**

Every Python module should have a docstring:
```python
#!/usr/bin/env python3
"""
Module Name: Brief Description

Detailed description of what this module does,
its purpose, and how it fits into the project.
"""
```

**2. Function Docstrings**

All functions should document their parameters and return values:
```python
def calculate_quantum_state(qubits: int, entanglement: bool) -> QuantumCircuit:
    """
    Calculate quantum state for given configuration.

    Args:
        qubits (int): Number of qubits in the circuit
        entanglement (bool): Whether to apply entanglement gates

    Returns:
        QuantumCircuit: Configured quantum circuit ready for execution

    Raises:
        ValueError: If qubits < 1

    Example:
        >>> circuit = calculate_quantum_state(3, True)
        >>> print(circuit.depth())
        5
    """
```

Use the format from `RQB2-bin/rq_led_utils.py` as the standard.

**3. Error Handling**

Use try/except blocks with informative messages:
```python
try:
    from qiskit import QuantumCircuit
except ImportError as e:
    print(f"Error: Qiskit not installed: {e}")
    print("Please ensure you're in the RQB2 virtual environment")
    sys.exit(1)
```

**4. Configuration Loading**

Load config from centralized location:
```python
from dotenv import dotenv_values

config = dotenv_values("/usr/config/rasqberry_environment.env")
led_count = int(config.get("LED_COUNT", 192))
```

**5. LED Control**

Use the LED utilities library:
```python
from rq_led_utils import (
    get_led_config,
    create_neopixel_strip,
    chunked_show,
    chunked_clear
)

# Load configuration
config = get_led_config()

# Initialize LEDs
spi = board.SPI()
pixels = create_neopixel_strip(
    spi,
    config['led_count'],
    pixel_order,
    pi_model=config['pi_model']
)

# Update LEDs
pixels[0] = (255, 0, 0)  # Set pixel
chunked_show(pixels)      # Update display

# Turn off when done
chunked_clear(pixels)
```

---

## Testing Your Changes

### Manual Testing

**1. Syntax Check**
```bash
# Shell scripts
bash -n your_script.sh

# Python scripts
python3 -m py_compile your_script.py
```

**2. Test on Raspberry Pi**

Always test on actual hardware:
- Build image or copy files to running RasQberry
- Test demo launch from menu
- Verify LED functionality (if applicable)
- Check error handling (disconnect LEDs, etc.)

**3. Test Different Scenarios**
- First-time installation (demo not cloned yet)
- Subsequent runs (demo already installed)
- Cancellation (user cancels installation)
- Errors (network down, missing dependencies)

### Automated Validation

The project includes automated code quality checks:

```bash
# Run basic validation
./tests/test_basic_validation.sh

# Run advanced pattern detection
./tests/test_common_library_usage.sh
```

**These run automatically on GitHub when you submit a PR.**

### Code Quality Checklist

Before submitting, verify:
- [ ] Shell scripts use `set -euo pipefail` (if standalone)
- [ ] Scripts load environment with `load_rqb2_env`
- [ ] No USER_HOME redefinitions
- [ ] Use common library functions (rq_common.sh)
- [ ] Python functions have docstrings
- [ ] Error handling is present
- [ ] Scripts follow naming conventions
- [ ] Code tested on Raspberry Pi

---

## Submitting Pull Requests

### Workflow

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/my-new-demo
   ```

2. **Make Changes**
   - Follow coding standards
   - Test thoroughly
   - Keep commits focused and atomic

3. **Commit with Clear Messages**
   ```bash
   git add RQB2-bin/rq_myquantum.sh
   git commit -m "Add My Quantum Demo launcher

   - Create launcher script following template
   - Add menu entry in RQB2_menu.sh
   - Add environment configuration
   - Test on Raspberry Pi 5 with LED panels"
   ```

4. **Push to Your Fork**
   ```bash
   git push origin feature/my-new-demo
   ```

5. **Open Pull Request**
   - Go to GitHub and create PR
   - Fill in the PR template
   - Link to any related issues
   - Add screenshots/videos if applicable

### PR Guidelines

**Good PR:**
- Focused on single feature/fix
- Clear description of changes
- Includes testing information
- Follows coding standards
- All CI checks pass

**PR Description Template:**
```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] New quantum demo
- [ ] Bug fix
- [ ] Documentation update
- [ ] Code refactoring

## Testing
- [x] Tested on Raspberry Pi 5
- [x] LED panels working correctly
- [ ] Tested with GUI
- [x] Tested from command line

## Checklist
- [x] Follows coding standards
- [x] Updated documentation
- [x] All tests pass
- [x] No new warnings

## Screenshots
[If applicable, add screenshots]

## Related Issues
Closes #123
```

### Review Process

1. Automated checks run (CI/CD)
2. Maintainers review code
3. Address feedback if needed
4. Approval and merge

---

## Getting Help

### Resources

**Documentation:**
- Project README: [README.md](README.md)
- Website: https://rasqberry.org
- Qiskit docs: https://docs.qiskit.org/

**Common Functions Reference:**
- Shell library: `RQB2-bin/RQ_COMMON_README.md`
- LED utilities: See docstrings in `RQB2-bin/rq_led_utils.py`

**Examples:**
- Template script: `RQB2-bin/_TEMPLATE.sh`
- Existing demos: `RQB2-bin/rq_*.sh`
- Python demos: `RQB2-bin/*.py`

### Questions and Support

**GitHub Issues:**
- Bug reports: [Create an issue](https://github.com/JanLahmann/RasQberry-Two/issues/new)
- Feature requests: [Create an issue](https://github.com/JanLahmann/RasQberry-Two/issues/new)
- Questions: [Check existing issues](https://github.com/JanLahmann/RasQberry-Two/issues)

**Before Opening an Issue:**
1. Search existing issues
2. Check documentation
3. Test on latest version
4. Gather error messages/logs

### Issue Template

```markdown
**Description:**
Clear description of the issue or request.

**Environment:**
- RasQberry version: [e.g., beta-2025-01-26]
- Raspberry Pi model: [e.g., Pi 5]
- LED setup: [e.g., 4x 4x12 panels]

**Steps to Reproduce:**
1. Step one
2. Step two
3. ...

**Expected Behavior:**
What should happen.

**Actual Behavior:**
What actually happens.

**Error Messages:**
```
paste error messages here
```

**Screenshots:**
[If applicable]
```

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inspiring community for all. Please treat everyone with respect.

### Expected Behavior

- Be kind and courteous
- Respect differing viewpoints
- Give and accept constructive feedback gracefully
- Focus on what's best for the community
- Show empathy towards others

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or insulting comments
- Publishing others' private information
- Other conduct inappropriate in a professional setting

### Reporting

Report unacceptable behavior to the project maintainers via GitHub issues (mark as private/confidential if needed).

---

## Recognition

Contributors are recognized in several ways:

- Listed in project contributors
- Mentioned in release notes
- Demo attribution in documentation
- Community showcase (if desired)

We appreciate all contributions, large and small!

---

## License

By contributing to RasQberry-Two, you agree that your contributions will be licensed under the same license as the project.

---

## Thank You!

Thank you for contributing to RasQberry-Two! Your efforts help make quantum computing more accessible to students, educators, and enthusiasts worldwide.

Every contribution, whether it's a new demo, a bug fix, or a documentation improvement, makes a difference.

**Happy Quantum Computing! 🎨🔬✨**