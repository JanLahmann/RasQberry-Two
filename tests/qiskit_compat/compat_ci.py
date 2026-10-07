#!/usr/bin/env python3
"""
CI helpers for the Qiskit compatibility workflow (.github/workflows/qiskit-compat.yml).

The image installs the LATEST Qiskit at build time (RQB2-bin/rq_install_qiskit.sh:
"qiskit[all]" + RQB2-config/qiskit-requirements.txt), so a new Qiskit release
reaches the next image without any change on our side. These helpers let CI
reproduce that install off-Pi and check it:

    compat_ci.py requirements OUT   write the requirements file minus the Pi-only
                                    hardware packages (see PI_ONLY) to OUT
    compat_ci.py check-latest       fail unless the installed qiskit major.minor is
                                    PyPI's latest (an add-on capping Qiskit makes
                                    pip resolve an older one silently)
    compat_ci.py versions           print a markdown version table
    compat_ci.py wheels             check cp313 manylinux aarch64 wheels exist for
                                    the installed versions (the image is aarch64)

Each command appends its markdown to $GITHUB_STEP_SUMMARY and to
$QISKIT_COMPAT_REPORT (the file that goes into the release checklist issue)
when those are set.
"""

import importlib.metadata
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))
REQUIREMENTS = os.path.join(REPO_ROOT, "RQB2-config", "qiskit-requirements.txt")

# Requirements that only make sense on a Raspberry Pi. They are left out of the
# off-Pi install: none of them depends on Qiskit, and the demo tests stub the
# hardware they drive (board/neopixel) instead.
PI_ONLY = {
    # board/neopixel need Pi GPIO/PIO at import; Blinka also pulls sysv_ipc
    # (source build) on Linux. The image pre-installs the low-level drivers
    # (rpi_ws281x, lgpio, ...) separately in rq_install_qiskit.sh.
    "adafruit-blinka": "Pi GPIO/PIO (board module)",
    "adafruit-circuitpython-neopixel": "drives the LED strip via Blinka",
    # sense_hat imports RTIMU (Debian package python3-rtimulib) - Pi only.
    "sense-hat": "Sense HAT hardware (RTIMU from apt)",
    # The emulator GUI needs GTK/pygobject from the system; Quantum Raspberry
    # Tie is tested with its bundled no-GUI sense_faux instead.
    "sense-emu": "GTK emulator GUI (system pygobject)",
    # No wheels at all (source-only); the image installs it in its own pip call
    # for the IP display service, not for anything Qiskit-related.
    "netifaces": "source-only, IP display service, installed separately by the image",
}

# Packages whose aarch64 wheel availability matters. A missing wheel for one of
# REQUIRED_WHEELS breaks the image build (qemu cannot reasonably compile them).
REQUIRED_WHEELS = ["qiskit", "qiskit-aer"]
OTHER_WHEELS = ["qiskit-ibm-runtime", "rustworkx", "qiskit-algorithms",
                "qiskit-optimization", "qiskit-machine-learning", "qiskit-nature",
                "qiskit-finance", "qiskit-experiments"]
# The image's Python: Raspberry Pi OS trixie ships 3.13 (bookworm: 3.11), as
# TARGET_PYTHON_VERSION in pi-gen-config.
TARGET_PYTHON = "3.13"
TARGET_CP = "cp" + TARGET_PYTHON.replace(".", "")
# Raspberry Pi OS trixie ships glibc 2.41, so any manylinux_2_x up to that works.
AARCH64_PLATFORMS = ["manylinux2014_aarch64", "manylinux_2_28_aarch64",
                     "manylinux_2_31_aarch64", "manylinux_2_34_aarch64",
                     "manylinux_2_35_aarch64", "manylinux_2_36_aarch64",
                     "manylinux_2_38_aarch64", "manylinux_2_39_aarch64",
                     "manylinux_2_41_aarch64"]
VERSION_PACKAGES = ["qiskit", "qiskit-aer", "qiskit-ibm-runtime", "rustworkx",
                    "qiskit-algorithms", "qiskit-optimization", "qiskit-machine-learning",
                    "qiskit-nature", "qiskit-finance", "qiskit-experiments",
                    "numpy", "scipy", "matplotlib"]


def _summary(text):
    """Print markdown and append it to the job summary / report file if set."""
    print(text)
    for var in ("GITHUB_STEP_SUMMARY", "QISKIT_COMPAT_REPORT"):
        path = os.environ.get(var)
        if path:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(text + "\n")


def requirement_name(line):
    """Return the normalized project name of a requirements line, or None."""
    line = line.split("#", 1)[0].strip()
    if not line or line.startswith("-"):
        return None
    match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", line)
    return match.group(0).lower().replace("_", "-") if match else None


def filtered_requirements(path=REQUIREMENTS):
    """Return (kept_lines, excluded_names) for the requirements file."""
    kept, excluded = [], []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            name = requirement_name(line)
            if name in PI_ONLY:
                excluded.append(name)
            elif name:
                kept.append(line.split("#", 1)[0].strip())
    return kept, excluded


def installed(name):
    """Installed version of a distribution, or None."""
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def cmd_requirements(out):
    kept, excluded = filtered_requirements()
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(kept) + "\n")
    print(f"wrote {len(kept)} requirements to {out}")
    for name in excluded:
        print(f"  left out (Pi-only): {name} - {PI_ONLY[name]}")
    return 0


def cmd_check_latest():
    data = json.load(urllib.request.urlopen("https://pypi.org/pypi/qiskit/json", timeout=60))
    latest = data["info"]["version"]
    have = installed("qiskit")
    ok = have is not None and have.split(".")[:2] == latest.split(".")[:2]
    _summary(f"**Qiskit on PyPI:** {latest} - **installed:** {have} - "
             f"{'OK' if ok else 'MISMATCH'}\n")
    if not ok:
        print(f"::error::pip installed qiskit {have} but PyPI's latest is {latest}: "
              "a package in qiskit[all] or qiskit-requirements.txt caps Qiskit, so "
              "the image would ship the older version. Find the cap with "
              "'pip install qiskit[all]==<latest> -r <requirements>'.")
        return 1
    return 0


def cmd_versions():
    rows = ["| package | version |", "|---|---|",
            f"| python | {sys.version.split()[0]} |"]
    rows += [f"| {name} | {installed(name) or '-'} |" for name in VERSION_PACKAGES]
    _summary("\n".join(rows) + "\n")
    return 0


def _has_aarch64_wheel(name, version, dest):
    """True if pip finds a TARGET_CP manylinux aarch64 (or pure) wheel for name==version."""
    cmd = [sys.executable, "-m", "pip", "download", "--quiet", "--no-deps",
           "--only-binary", ":all:", "--python-version", TARGET_PYTHON,
           "--implementation", "cp", "--dest", dest]
    for plat in AARCH64_PLATFORMS:
        cmd += ["--platform", plat]
    cmd.append(f"{name}=={version}" if version else name)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode == 0, proc.stderr.strip().splitlines()[-1:] or [""]


def cmd_wheels():
    failed = False
    rows = [f"| package | version | {TARGET_CP} aarch64 wheel |", "|---|---|---|"]
    with tempfile.TemporaryDirectory() as dest:
        for name in REQUIRED_WHEELS + OTHER_WHEELS:
            version = installed(name)
            ok, err = _has_aarch64_wheel(name, version, dest)
            required = name in REQUIRED_WHEELS
            status = "yes" if ok else ("**MISSING (required)**" if required else "missing (warning)")
            rows.append(f"| {name} | {version or 'latest'} | {status} |")
            if not ok:
                level = "error" if required else "warning"
                print(f"::{level}::no {TARGET_CP} manylinux aarch64 wheel for {name}=={version}: {err[0]}")
                failed = failed or required
    _summary("\n".join(rows) + "\n")
    return 1 if failed else 0


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd == "requirements" and len(args) == 1:
        return cmd_requirements(args[0])
    if cmd == "check-latest":
        return cmd_check_latest()
    if cmd == "versions":
        return cmd_versions()
    if cmd == "wheels":
        return cmd_wheels()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
