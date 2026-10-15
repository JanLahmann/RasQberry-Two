"""
The setup hotspot (rq_setup_hotspot.sh): a new Pi without a network opens
RasQberry-Setup-XXXX with balena wifi-connect and RasQberry's own page.
"""

import os
import re
import subprocess

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCRIPT = os.path.join(_ROOT, "RQB2-bin", "rq_setup_hotspot.sh")


def _bash(code, env=None):
    return subprocess.run(["bash", "-c", f'. "{_SCRIPT}"; {code}'], capture_output=True, text=True,
                          env=dict(os.environ, **(env or {})))


def test_wifi_country_comes_from_the_time_zone():
    if not os.path.exists("/usr/share/zoneinfo/zone.tab"):
        import pytest
        pytest.skip("no zone.tab")
    out = _bash("timedatectl() { echo Europe/Berlin; }; wifi_country_from_timezone").stdout.strip()
    assert out == "DE"
    out = _bash("timedatectl() { echo America/Chicago; }; wifi_country_from_timezone").stdout.strip()
    assert out == "US"


def test_only_while_the_pi_never_had_a_network():
    sh = open(_SCRIPT).read()
    main = sh[sh.index("main() {"):]
    # booth hotspot first, then "had a network once", then a wait for one
    assert main.index("HOTSPOT_AT_BOOT") < main.index('[ -e "$SEEN" ] && exit 0') < main.index("network_up")
    assert "/data/rasqberry/network-seen" in sh             # shared by both A/B slots
    assert 'PASSWORD="rasqberry"' in sh and "--activity-timeout" in sh


def test_wifi_connect_is_pinned_and_checked():
    stage = open(os.path.join(_ROOT, "stage-RQB2", "02-system-integration", "00-run-chroot.sh")).read()
    assert re.search(r"WIFI_CONNECT_VERSION=v\d+\.\d+\.\d+", stage)
    assert re.search(r"WIFI_CONNECT_SHA256=[0-9a-f]{64}", stage)
    assert "sha256sum -c -" in stage and "/usr/local/sbin/wifi-connect" in stage


def test_setup_page_uses_the_wifi_connect_api():
    page = open(os.path.join(_ROOT, "RQB2-system", "usr", "share", "rasqberry", "setup-portal",
                             "index.html")).read()
    assert "fetch('/networks')" in page and "fetch('/connect'" in page
    for field in ("ssid", "identity", "passphrase"):
        assert field + ":" in page.replace(" ", "")
    assert "rasqberry" in page                              # the documented setup password


def test_setup_service_is_enabled():
    units = open(os.path.join(_ROOT, "RQB2-system", "enabled-units.txt")).read()
    assert "\nrasqberry-setup-hotspot.service\n" in units
    unit = open(os.path.join(_ROOT, "RQB2-system", "etc", "systemd", "system",
                             "rasqberry-setup-hotspot.service")).read()
    assert "ExecStart=/usr/bin/rq_setup_hotspot.sh" in unit


def test_led_scroller_can_show_any_text():
    py = open(os.path.join(_ROOT, "RQB2-bin", "rq_display_ip.py")).read()
    assert "'--text'" in py and "if not args.once and not args.text:" in py
