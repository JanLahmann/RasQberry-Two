#!/bin/bash -e

echo "=== Cleaning caches and temporary files before export ==="

# Build metadata for support and diagnostics (#233). Written here, in the last
# stage, so the installed kernel, Python and Qiskit versions are final.
echo "Writing /etc/rasqberry-build.json..."
VENV_PY=$(ls /home/*/RasQberry-Two/venv/RQB2/bin/python 2>/dev/null | head -1 || true)
python3 - "$VENV_PY" << 'PYEOF' || echo "WARNING: could not write /etc/rasqberry-build.json"
import json, os, platform, subprocess, sys, datetime

def read(path, default=""):
    try:
        with open(path) as fh:
            return fh.read().strip()
    except OSError:
        return default

def env_value(key):
    for line in read("/usr/config/rasqberry_environment.env").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return ""

os_release = dict(
    l.split("=", 1) for l in read("/etc/os-release").splitlines() if "=" in l
)
modules = sorted(os.listdir("/lib/modules")) if os.path.isdir("/lib/modules") else []

venv_py, qiskit, python = sys.argv[1], "", platform.python_version()
if venv_py:
    try:
        out = subprocess.run(
            [venv_py, "-c", "import platform, qiskit; print(platform.python_version(), qiskit.__version__)"],
            capture_output=True, text=True, timeout=120,
        ).stdout.split()
        if len(out) == 2:
            python, qiskit = out
    except Exception:
        pass

meta = {
    "version": read("/etc/rasqberry-version"),
    "build_timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "git_repo": env_value("RQB_BUILD_REPO"),
    "git_branch": env_value("RQB_BUILD_BRANCH"),
    "git_commit": env_value("RQB_BUILD_COMMIT"),
    "os": os_release.get("PRETTY_NAME", "").strip('"'),
    "debian_version": read("/etc/debian_version"),
    "kernel_versions": modules,
    "python_version": python,
    "qiskit_version": qiskit,
}
with open("/etc/rasqberry-build.json", "w") as fh:
    json.dump(meta, fh, indent=2)
    fh.write("\n")
print(json.dumps(meta, indent=2))
PYEOF
chmod 644 /etc/rasqberry-build.json 2>/dev/null || true

# APT cache cleanup
echo "Cleaning APT cache..."
echo "  Package cache size before: $(du -sh /var/cache/apt/archives 2>/dev/null | cut -f1 || echo '0')"
if [ -f /etc/apt/apt.conf.d/01cache ]; then
    rm -f /etc/apt/apt.conf.d/01cache
fi
apt-get clean
echo "  Package cache size after: $(du -sh /var/cache/apt/archives 2>/dev/null | cut -f1 || echo '0')"

# Python __pycache__ directories
echo "Cleaning Python __pycache__ directories..."
find /usr -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find /home -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Python .pyc compiled files
echo "Cleaning Python .pyc files..."
find /usr -name "*.pyc" -delete 2>/dev/null || true
find /home -name "*.pyc" -delete 2>/dev/null || true

# Temporary directories
echo "Cleaning temporary directories..."
rm -rf /tmp/* /var/tmp/* 2>/dev/null || true

# Bash history
echo "Cleaning bash history..."
rm -f /root/.bash_history 2>/dev/null || true
rm -f /home/*/.bash_history 2>/dev/null || true

echo "=== Cache cleanup completed ==="
