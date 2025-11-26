# Stage: 00-install-extras

## Purpose

Install additional system packages and Python libraries required for RasQberry quantum computing demos and LED control functionality.

## What This Stage Does

This stage installs essential packages in two categories:

### 1. System Packages (via apt-get)

**Development Tools:**
- `git` - Version control for cloning demo repositories
- `build-essential` - C/C++ compilers and build tools

**Python Development:**
- `python3-pip` - Python package installer
- `python3-venv` - Virtual environment support
- `python3-dev` - Python development headers

**System Libraries:**
- `libatlas-base-dev` - Linear algebra library (BLAS/LAPACK)
- `libopenblas-dev` - Optimized BLAS library
- `gfortran` - Fortran compiler (required by some scientific packages)

**Graphics and Display:**
- `chromium-browser` - Web browser for web-based quantum demos
- `libgl1-mesa-glx` - OpenGL libraries for graphics

**Hardware Access:**
- `i2c-tools` - I2C bus debugging and management
- `python3-smbus` - Python I2C/SMBus library

### 2. Python Packages (via pip3, system-wide)

**LED Control:**
- `rpi_ws281x` - NeoPixel LED strip control library

**Serial Communication:**
- `pyserial` - Serial port access library

**HTTP and Web:**
- `requests` - HTTP library for Python

## Files Modified

- System package database (apt)
- Python system site-packages (`/usr/lib/python3.*/site-packages/`)
- Package manager caches

## Configuration Variables

No configuration variables required. Package list is hardcoded.

## Scripts

- `00-run-chroot.sh`: Installs all packages using apt-get and pip3

## Package Details

### libatlas-base-dev vs libopenblas-dev

Both libraries provide BLAS (Basic Linear Algebra Subprograms):
- **ATLAS**: Automatically Tuned Linear Algebra Software
- **OpenBLAS**: Open-source optimized BLAS library
- **Why both?**: Provides fallback options and compatibility
- **Used by**: NumPy, SciPy, and Qiskit for matrix operations

### rpi_ws281x

Critical library for NeoPixel LED control:
- Supports WS2811/WS2812/WS2812B/SK6812 LED strips
- Uses PWM or SPI for precise timing
- Requires root access or proper permissions
- **RasQberry use**: Visualizing quantum states on LED matrix

### System-wide vs Virtual Environment

This stage installs packages system-wide intentionally:
- **System packages**: Available to all users and virtual environments
- **Virtual environment**: Created in stage 03-install-qiskit with `--system-site-packages`
- **Rationale**: Base hardware libraries (rpi_ws281x, pyserial) benefit from system installation

### APT vs pip Package Strategy

To avoid duplicate package warnings, Python packages are split:

**APT-only packages (cannot be pip-installed or need system integration):**
- `python3-gi` - GTK bindings with system typelibs
- `sense-emu-tools` - Desktop menu shortcuts (pulls in python3-sense-emu)

**pip-only packages (in qiskit-requirements.txt):**
- `numpy`, `pillow`, `python-dotenv` - Scientific/utility packages
- `sense-hat`, `sense-emu` - Hardware libraries

This avoids "Can't uninstall" warnings during venv pip installs.

## Execution Context

- **Execution**: Inside chroot environment
- **User**: root
- **Order**: Early (00-prefix) to provide dependencies for later stages
- **Network**: Requires internet access for package downloads

## Installation Order

1. `apt-get update` - Refresh package lists
2. `apt-get install -y` - Install system packages
3. `pip3 install` - Install Python packages system-wide

## Disk Space Impact

Approximate sizes:
- Build tools: ~200MB
- Python libraries: ~50MB
- Graphics libraries: ~100MB
- Total: ~350MB

## Dependencies

**Required by:**
- [03-install-qiskit](../03-install-qiskit/README.md) - Qiskit installation needs NumPy, dev tools
- [06-desktop-integration](../06-desktop-integration/README.md) - Chromium for web demos
- All LED control scripts - rpi_ws281x library
- All Python demos - requests, pyserial, etc.

## Special Considerations

### ARM-Specific Packages

- OpenBLAS optimized for ARM architecture
- ATLAS auto-tunes for specific CPU
- Performance-critical for quantum simulations

### Root Privileges

rpi_ws281x requires root for GPIO access:
- LED control scripts must run as root OR
- User must be in gpio group with proper udev rules

### Build Dependencies

build-essential, python3-dev, and gfortran are needed for:
- Compiling Python packages with C extensions
- Building scientific libraries from source
- pip install operations that require compilation

## Troubleshooting

**Issue**: Package installation fails with "Unable to locate package"
- **Cause**: Package repositories not accessible or outdated
- **Resolution**: Check network connectivity, verify apt sources
- **Command**: `apt-get update` should complete successfully

**Issue**: pip3 install fails for rpi_ws281x
- **Cause**: Missing build dependencies or wrong architecture
- **Resolution**: Ensure build-essential and python3-dev installed first
- **Platform**: Only works on Raspberry Pi with GPIO hardware

**Issue**: ImportError for numpy or scientific packages
- **Cause**: BLAS libraries not properly linked
- **Resolution**: Reinstall libatlas-base-dev and libopenblas-dev
- **Verify**: `python3 -c "import numpy; numpy.show_config()"`

**Issue**: Chromium won't start in demos
- **Cause**: Missing graphics libraries or X11 not available
- **Resolution**: Ensure libgl1-mesa-glx installed, X11 session running
- **Test**: `chromium-browser --version`

## Related Stages

- Provides dependencies for [03-install-qiskit](../03-install-qiskit/README.md)
- Enables LED control in all demo stages
- Chromium used by [06-desktop-integration](../06-desktop-integration/README.md) demos

## Version Considerations

- Packages installed from Debian Bookworm repositories
- Python packages use latest available from PyPI
- No version pinning (uses whatever is current at build time)
- For reproducible builds, consider pinning versions in future

## Alternative Approaches

### Virtual Environment Installation

Could install Python packages in venv instead of system-wide:
- **Pro**: Isolated from system Python
- **Con**: Must activate venv for all scripts
- **Current choice**: System-wide for convenience

### Minimal Installation

Could defer some packages to runtime installation:
- **Pro**: Smaller base image
- **Con**: First-run requires network and takes longer
- **Current choice**: Pre-install everything for offline use