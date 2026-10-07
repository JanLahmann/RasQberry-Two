# RasQberry-Two Test Suite

This directory contains automated validation scripts for maintaining code quality, consistency, and best practices across the RasQberry-Two codebase.

## Overview

The test suite implements a comprehensive 3-phase validation approach:

1. **Basic Validation** - Fundamental syntax and safety checks
2. **Advanced Pattern Detection** - Semantic analysis and anti-pattern detection
3. **Static Analysis** - ShellCheck linting (advisory)

## Test Scripts

### test_basic_validation.sh

Performs fundamental code quality checks on shell and Python scripts.

**Checks performed:**
1. Shell script syntax validation (`bash -n`)
2. Python script syntax validation (`py_compile`)
3. Safety flags coverage (`set -euo pipefail`)
4. USER_HOME redefinition detection (CRITICAL)
5. rq_common.sh library validation
6. SCRIPT_DIR pattern validation
7. Documentation files check
8. Code quality metrics reporting

**Usage:**
```bash
./tests/test_basic_validation.sh
```

**Exit codes:**
- `0` - All checks passed (warnings allowed)
- `1` - One or more errors detected

**Targets:**
- Safety flag coverage: ≥90% (minimum 80%)
- USER_HOME violations: 0 (CRITICAL)
- All scripts must pass syntax validation

### test_common_library_usage.sh

Advanced validator that detects duplicate functionality, reimplemented patterns, and opportunities for code consolidation.

**Checks performed:**
1. Function existence validation
2. Anti-pattern detection (manual implementations)
3. Semantic duplication analysis
4. Complexity analysis
5. Environment loading patterns
6. Virtual environment activation patterns
7. Error handling patterns
8. User detection patterns
9. Whiptail dialog patterns
10. Cleanup pattern analysis

**Usage:**
```bash
./tests/test_common_library_usage.sh
```

**Exit codes:**
- `0` - All checks passed (warnings allowed)
- `1` - One or more errors detected

**Targets:**
- Function violations: 0 (use common library)
- Anti-patterns: ≤5 across entire codebase
- Duplication score: ≤10% of scripts

### paradoxes/ (Quantum Paradoxes regression, #181)

Fetches maria-violaris/quantum-paradoxes at the manifest's pinned ref, patches
it with `RQB2-bin/setup_quantum_paradoxes.py`, runs every notebook headless and
compares the exact outcome probabilities of every simulated circuit with
`paradoxes/reference_probabilities.json` (recorded from the original notebooks).
It needs a Qiskit 2.x venv (qiskit, qiskit-aer, qiskit-ibm-runtime, nbclient,
ipykernel, matplotlib, pylatexenc) and takes about 3-5 minutes. It skips itself
when that stack is missing, so it is not part of the fast `tests/unit` run:

```bash
python3 -m pytest -q tests/paradoxes          # PARADOXES_SRC=<checkout> avoids the git fetch
```

### qiskit_compat/ (our Qiskit code under the installed Qiskit)

Headless runs, without LEDs or a display, of everything in the image that uses
Qiskit besides the paradox notebooks:

| Test | What runs |
|---|---|
| `test_rasq_led.py` | every RasQ-LED entanglement pattern (checks entangled blocks agree) + one cycle through the `RasQ-LED-display.py` functions (in-process) |
| `test_fractals.py` | fractal statevectors, Julia sets, Bloch plot, then `fractals.py` for 3 frames (Agg backend, fake browser) |
| `test_ibm_token.py` | `rq_set_qiskit_ibm_token.py` saves a dummy token with the installed qiskit-ibm-runtime (temp HOME, network blocked) |
| `test_lights_out.py` | Quantum Lights Out at the pinned ref + our patch: the Grover solver must solve all 18 built-in puzzles |
| `test_raspberry_tie.py` | Quantum Raspberry Tie at the pinned ref + our patch, until its first result on Aer, Aer MPS (16 qubits) and FakeManilaV2 |
| `test_ci_requirements.py` | the CI install leaves out only the Pi-only packages (runs without Qiskit) |

LEDs go to a temp mmap file (`LED_RENDER_MODE=service`, `RQB2_LED_MMAP_PATH`);
`board`/`neopixel` are stubbed where a demo imports them. Not covered: the real
IBM backend paths (need an account and the network) and anything that needs the
Sense HAT or GTK emulator GUI (Raspberry Tie runs with its bundled `sense_faux`).
Demo patches are applied the way `rq_demo_run.sh` applies them, so a patch that
no longer applies fails here too.

Needs the image's Qiskit stack (`qiskit[all]` + `RQB2-config/qiskit-requirements.txt`
minus the Pi-only packages, see `compat_ci.py requirements`), git and network
access for the pinned demo repos (or `QLO_SRC`/`QRT_SRC` checkouts); about 2
minutes. Tests skip themselves when their modules are missing. Deprecation
warnings never fail a test; with `QISKIT_COMPAT_REPORT=<file>` they are written
there as markdown:

```bash
python3 tests/qiskit_compat/compat_ci.py requirements /tmp/req.txt
pip install "qiskit[all]" -r /tmp/req.txt pytest
python3 -m pytest -q -W default::DeprecationWarning tests/qiskit_compat
```

`compat_ci.py` also holds the install checks of the CI workflow
(`check-latest`, `versions`, `wheels` for cp313 manylinux aarch64).

**Workflow:** `.github/workflows/qiskit-compat.yml` runs `qiskit_compat/` and
`paradoxes/` on pushes that touch our Qiskit code, its patches/pins or these
tests, and - via a weekly PyPI check - when a new Qiskit x.y.0 is released;
then it also opens one "Qiskit X.Y released: compatibility checklist" issue
with the results and the manual follow-ups.

## CI/CD Integration

The validation suite runs automatically on GitHub Actions for:

- Push to: `main`, `beta`, `dev*` branches
- Pull requests to: `main`, `beta`, `dev*` branches

**Workflow:** `.github/workflows/code-quality.yml`

### CI Pipeline Phases

#### Phase 1: Basic Validation (Required)
- Runs `test_basic_validation.sh`
- Must pass for CI to succeed
- Validates syntax, safety flags, critical violations

#### Phase 2: Advanced Pattern Detection (Required)
- Runs `test_common_library_usage.sh`
- Must pass for CI to succeed
- Detects duplicate code and anti-patterns

#### Phase 3: ShellCheck Analysis (Advisory)
- Runs ShellCheck on all scripts
- Does NOT fail the build
- Provides improvement suggestions

### Running Locally

Before pushing code, run the full validation suite:

```bash
# Run all checks
./tests/test_basic_validation.sh && \
./tests/test_common_library_usage.sh && \
echo "✅ All validation checks passed!"

# Run with ShellCheck
./tests/test_basic_validation.sh && \
./tests/test_common_library_usage.sh && \
shellcheck RQB2-bin/*.sh RQB2-config/*.sh
```

## Code Quality Standards

### Required Standards (CI Enforced)

1. **Syntax Validation**
   - All shell scripts must pass `bash -n` check
   - All Python scripts must pass `py_compile` check

2. **Safety Flags**
   - All executable scripts must include `set -euo pipefail`
   - Exception: `rq_common.sh` (sourced library)
   - Target: ≥90% coverage

3. **USER_HOME Consistency (CRITICAL)**
   - **Zero tolerance**: No scripts may redefine USER_HOME
   - USER_HOME is set ONLY in `rasqberry_env-config.sh`
   - Scripts must use `load_rqb2_env` to access USER_HOME

4. **Common Library Usage**
   - Scripts must use `rq_common.sh` functions
   - No reimplementation of existing functions
   - No anti-patterns (manual implementations)

5. **SCRIPT_DIR Pattern**
   - Scripts using `rq_common.sh` must set SCRIPT_DIR correctly:
     ```bash
     SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
     ```

### Advisory Standards (Not CI Enforced)

1. **ShellCheck Compliance**
   - Address ShellCheck suggestions when practical
   - Some warnings may be acceptable (context-dependent)

2. **Code Complexity**
   - Keep functions under 50 lines when possible
   - Extract complex logic to common library

3. **Documentation**
   - Maintain README files for major components
   - Include usage examples in function headers

## Maintenance

### Adding New Checks

To add a new validation check:

1. Determine if it's basic or advanced:
   - **Basic**: Syntax, safety, critical violations → `test_basic_validation.sh`
   - **Advanced**: Patterns, duplication, complexity → `test_common_library_usage.sh`

2. Add the check logic to the appropriate script
3. Update the script's header documentation
4. Update this README
5. Test locally before committing

### Updating Standards

When updating quality standards:

1. Update the validation script thresholds
2. Update this README documentation
3. Announce changes to the team
4. Consider a grace period for existing code

## Current Metrics

As of the latest dev-review01 branch:

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Shell syntax errors | 0 | 0 | ✅ |
| Python syntax errors | 0 | 0 | ✅ |
| Safety flag coverage | 90% (18/20) | ≥90% | ✅ |
| USER_HOME violations | 0 | 0 | ✅ |
| Common library adoption | 82% (14/17) | ≥80% | ✅ |
| Code duplication | Low | ≤10% | ✅ |

**Overall Grade: A- (93/100)**

## Troubleshooting

### Common CI Failures

**"Syntax error detected"**
```bash
# Check syntax locally
bash -n path/to/script.sh
python3 -m py_compile path/to/script.py
```

**"Safety flag coverage below 90%"**
```bash
# Add to top of script (after shebang)
set -euo pipefail
```

**"USER_HOME redefinition detected"**
```bash
# Remove: USER_HOME=/home/$SUDO_USER
# Replace with:
load_rqb2_env
verify_env_vars USER_HOME
```

**"Missing SCRIPT_DIR pattern"**
```bash
# Add near top of script:
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
```

**"Function reimplementation detected"**
```bash
# Instead of implementing your own:
my_custom_error() { echo "Error: $1" >&2; exit 1; }

# Use the common library:
. "${SCRIPT_DIR}/rq_common.sh"
die "Error message"
```

### Getting Help

- Review [RQB2-bin/RQ_COMMON_README.md](../RQB2-bin/RQ_COMMON_README.md) for available functions
- Check [RQB2-bin/_TEMPLATE.sh](../RQB2-bin/_TEMPLATE.sh) for the standard script template
- See `.editorconfig` for formatting standards

## References

- **Common Library**: [RQB2-bin/rq_common.sh](../RQB2-bin/rq_common.sh)
- **Environment Config**: [RQB2-config/rasqberry_env-config.sh](../RQB2-config/rasqberry_env-config.sh)
- **Environment Loader**: [RQB2-config/rasqberry_env-config.sh](../RQB2-config/rasqberry_env-config.sh)
- **Script Template**: [RQB2-bin/_TEMPLATE.sh](../RQB2-bin/_TEMPLATE.sh)
- **CI Workflow**: [.github/workflows/code-quality.yml](../.github/workflows/code-quality.yml)
