#!/bin/bash
# ============================================================================
# RasQberry rig test: system checks, run ON the Pi (issue #234)
# ============================================================================
# Prints one line per check: "<PASS|FAIL|WARN|INFO> <name> | <detail>".
# Copied to the Pi and run by tests/rig/rig_test.py; also usable by hand:
#   bash checks.sh

E=/usr/config/rasqberry_environment.env
VENV_PY="$HOME/RasQberry-Two/venv/RQB2/bin/python"
AB=false
lsblk -no LABEL /dev/mmcblk0p1 2>/dev/null | grep -qiE '^config$' && AB=true

say() { printf '%s %s | %s\n' "$1" "$2" "$3"; }
check() {  # check <name> <detail> <command...>: PASS if the command succeeds
    local name="$1" detail="$2"; shift 2
    if "$@" >/dev/null 2>&1; then say PASS "$name" "$detail"; else say FAIL "$name" "$detail"; fi
}

# --- Level 1: boot and access
say INFO version "$(cat /etc/rasqberry-version 2>/dev/null) root=$(findmnt -no SOURCE /) ab=$AB"
check network "default route and DNS" getent hosts github.com
if $AB; then
    st=$(sudo rq_slot_manager.sh status 2>&1 | sed -n 's/.*Slot Status: //p')
    case "$st" in CONFIRMED*) say PASS slot "$st" ;; *) say FAIL slot "${st:-unknown}" ;; esac
fi
failed=$(systemctl --failed --no-legend 2>/dev/null | awk '{print $2}' | tr '\n' ' ')
[ -z "$failed" ] && say PASS failed-units "none" || say FAIL failed-units "$failed"

# --- Level 2: environment
check venv "$VENV_PY" test -x "$VENV_PY"
qv=$("$VENV_PY" -c 'import qiskit, qiskit_aer; print(qiskit.__version__, qiskit_aer.__version__)' 2>/dev/null)
[ -n "$qv" ] && say PASS qiskit "qiskit/aer $qv" || say FAIL qiskit "import failed"
check aer-run "3-qubit GHZ on AerSimulator" "$VENV_PY" -c '
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
qc = QuantumCircuit(3); qc.h(0); qc.cx(0, 1); qc.cx(1, 2); qc.measure_all()
sim = AerSimulator(); c = sim.run(transpile(qc, sim), shots=200).result().get_counts()
assert set(c) <= {"000", "111"}, c'
check build-json "/etc/rasqberry-build.json" jq -e .version /etc/rasqberry-build.json
check menu-cache "valid, no syntax errors this boot" sh -c \
    'sh -n /usr/config/demo-menu-cache.sh && ! journalctl -b --no-pager | grep -q "demo-menu-cache.sh: Syntax"'
check led-config "LED_LAYOUT set" grep -q '^LED_LAYOUT=' "$E"
grep -q '^LED_LAYOUT_VERIFIED=true' "$E" && say PASS led-verified "$(sed -n 's/^LED_LAYOUT=//p' "$E")" \
    || say WARN led-verified "layout not verified yet (first-login wizard pending)"

# --- System files and services (#294, #288, #139)
while IFS= read -r u; do
    u="${u%%#*}"; u="${u//[[:space:]]/}"; [ -n "$u" ] || continue
    systemctl is-enabled "$u" >/dev/null 2>&1 && say PASS "unit:$u" enabled || say FAIL "unit:$u" "not enabled"
done < <(printf '%s\n' rasqberry-firstboot.service rasqberry-boot-config.service rasqberry-demo-cache.service \
    rasqberry-health-check.service rasqberry-tryboot-retry.service rasqberry-ip-display.service rasqberry-update-check.timer)
for u in rasqberry-led-renderer.service rasqberry-update-poller.timer; do
    systemctl is-enabled "$u" 2>/dev/null | grep -q '^enabled' && say FAIL "unit:$u" "enabled (should ship disabled)" \
        || say PASS "unit:$u" "disabled on purpose"
done
vnc=$(sudo raspi-config nonint get_vnc 2>/dev/null)
[ "$vnc" = 0 ] && say PASS vnc "wayvnc $(systemctl is-active wayvnc)" || say FAIL vnc "get_vnc=$vnc"
ls /boot/firmware/initramfs* >/dev/null 2>&1 && say FAIL initramfs "present (none expected)" || say PASS initramfs "none"
uc=$(rq_update_check.sh 2>&1 | tail -1)
[ -n "$uc" ] && say INFO update-check "$uc" || say WARN update-check "no answer"
exit 0
