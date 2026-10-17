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
    assert main.index("HOTSPOT_AT_BOOT") < main.index('[ ! -e "$SEEN" ] || exit 0') \
        < main.index("wait_for_network")
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


# --- review A1: only a real way out counts as a network -----------------------

def _net(devices, routes):
    """network_up with nmcli's device list and the devices that have a default route."""
    stubs = (f"nmcli() {{ printf '%b' '{devices}'; }}; "
             f"ip() {{ case \" $* \" in *' default dev '*) for d in {routes}; do "
             "case \" $* \" in *\" dev $d \"*) echo \"default via 192.168.1.1 dev $d\" ;; esac; done ;; esac; }; ")
    return _bash(stubs + "network_up").returncode == 0


_DOCKER = r"docker0:bridge:connected (externally)\nlo:loopback:connected (externally)\n"


def test_docker_bridge_is_no_network():
    # NetworkManager says "connected (local only)" for docker0 alone: the setup
    # Wi-Fi never opened on a RasQberry image
    assert not _net(r"eth0:ethernet:unavailable\nwlan0:wifi:disconnected\n" + _DOCKER, "")
    assert not _net(r"eth0:ethernet:unavailable\nwlan0:wifi:disconnected\n" + _DOCKER, "docker0")


def test_an_access_point_is_no_network():
    # the setup Wi-Fi itself, or the booth hotspot: "connected", without a default route
    assert not _net(r"wlan0:wifi:connected\n" + _DOCKER, "")


def test_cable_or_wifi_with_a_way_out_is_a_network():
    assert _net(r"eth0:ethernet:connected\nwlan0:wifi:disconnected\n" + _DOCKER, "eth0")
    assert _net(r"eth0:ethernet:unavailable\nwlan0:wifi:connected\n" + _DOCKER, "wlan0")
    assert _net(r"wlan1:wifi:connected\nwlan0:wifi:connected\n", "wlan1")   # a USB adapter
    # a cable to a laptop without a gateway: no way out
    assert not _net(r"eth0:ethernet:connected\n", "")


# --- review A5: the setup Wi-Fi ends ----------------------------------------------

def _watch(tmp_path, stations="0", network="false", known="false", alive=True, joins=0):
    """Run watch_portal with a clock that moves a minute per check; print REASON and minutes."""
    clock = tmp_path / "clock"
    clock.write_text("0")
    code = (
        f'now() {{ local t; t=$(cat "{clock}"); echo $((t + 60)) > "{clock}"; echo "$t"; }}; '
        f"stations() {{ echo {stations}; }}; network_up() {{ {network}; }}; "
        f"known_in_range() {{ {known}; }}; ap_up() {{ true; }}; "
        f"POLL=0; START=0; JOINS={joins}; "
        + ('sleep 1000 & WC_PID=$!; ' if alive else 'true & WC_PID=$!; wait; ')
        + f'watch_portal wlan0; echo "$REASON $(( $(cat "{clock}") / 60 ))"; kill $WC_PID 2>/dev/null || true')
    r = _bash(code)
    assert r.returncode == 0, r.stderr
    return r.stdout.split()


def test_setup_wifi_ends_when_a_network_comes(tmp_path):
    assert _watch(tmp_path, stations="1", network="true")[0] == "network"


def test_setup_wifi_ends_after_30_minutes_without_anyone_even_after_a_visit(tmp_path):
    # wifi-connect's --activity-timeout never fires once the page was opened
    reason, minutes = _watch(tmp_path, stations="0")
    assert reason == "idle" and 30 <= int(minutes) <= 32


def test_setup_wifi_ends_after_an_hour_with_someone_on_it(tmp_path):
    reason, minutes = _watch(tmp_path, stations="1")
    assert reason == "limit" and 60 <= int(minutes) <= 62


def test_setup_wifi_gives_way_to_a_known_wifi(tmp_path):
    reason, minutes = _watch(tmp_path, stations="0", known="true")
    assert reason == "known" and int(minutes) <= 4
    # after three tries it no longer looks
    assert _watch(tmp_path, stations="0", known="true", joins=3)[0] == "idle"


def test_wifi_connect_exiting_ends_the_watch(tmp_path):
    assert _watch(tmp_path, alive=False)[0] == "exited"


def test_wifi_connect_is_stopped_and_its_access_point_removed():
    sh = open(_SCRIPT).read()
    stop = sh[sh.index("stop_portal() {"):]
    stop = stop[:stop.index("\n}\n")]
    assert "kill -TERM" in stop and "kill -KILL" in stop and "nmcli connection delete uuid" in stop
    unit = open(os.path.join(_ROOT, "RQB2-system", "etc", "systemd", "system",
                             "rasqberry-setup-hotspot.service")).read()
    assert "TimeoutStopSec=30" in unit


# --- review A6: a booth hotspot that did not start leaves a way in ------------------

def _main(tmp_path, booth, seen=True, net="true"):
    seen_file = tmp_path / "network-seen"
    if seen:
        seen_file.write_text("")
    wc = tmp_path / "wifi-connect"
    wc.write_text("#!/bin/sh\nexit 0\n")
    wc.chmod(0o755)
    code = (f"ensure_root() {{ :; }}; load_rqb2_env() {{ :; }}; booth_running() {{ {booth}; }}; "
            f"network_up() {{ {net}; }}; WIFI_CONNECT={wc}; main")
    return _bash(code, {"HOTSPOT_AT_BOOT": "yes", "RQ_NETWORK_SEEN": str(seen_file),
                        "RQ_SETUP_WAIT": "0", "RQ_SETUP_POLL": "0"})


def test_running_booth_hotspot_means_no_setup_wifi(tmp_path):
    r = _main(tmp_path, booth="true")
    assert r.returncode == 0 and "did not start" not in r.stderr


def test_failed_booth_hotspot_falls_back_to_the_setup_wifi(tmp_path):
    # also on a Pi that had a network before (network-seen): it waits for one
    r = _main(tmp_path, booth="false", seen=True, net="true")
    assert r.returncode == 0 and "did not start" in r.stderr


# --- review A9, A10, A12 ---------------------------------------------------------

def test_no_venv_does_not_stop_the_setup_wifi():
    # find_venv failing ended the script under set -e before wifi-connect
    sh = open(os.path.join(_ROOT, "RQB2-bin", "rq_common.sh")).read()
    fn = sh[sh.index("rq_wifi_scroll() {"):]
    fn = fn[:fn.index("\n}\n")]
    assert 'py="$(find_venv 2>/dev/null || true)/bin/python3"' in fn


def test_led_scroll_runs_in_its_own_unit(tmp_path):
    log = tmp_path / "log"
    run = tmp_path / "run"
    common = os.path.join(_ROOT, "RQB2-bin", "rq_common.sh")
    code = (f'. "{common}"; led_holders() {{ :; }}; find_venv() {{ return 1; }}; '
            f'systemctl() {{ echo "systemctl $*" >> "{log}"; }}; '
            f'systemd-run() {{ echo "systemd-run $*" >> "{log}"; }}; '
            'rq_wifi_scroll rasqberry-setup-scroll 3600 "Wi-Fi X  ***  password secret-pw"')
    r = subprocess.run(["bash", "-c", code], capture_output=True, text=True,
                       env=dict(os.environ, RQ_RUN_DIR=str(run)))
    assert r.returncode == 0, r.stderr
    calls = log.read_text()
    assert "systemctl stop rasqberry-ip-display.service" in calls        # the address scroll gives way
    assert "--unit=rasqberry-setup-scroll" in calls and "--text-file" in calls
    assert "secret-pw" not in calls                                       # not in a command line
    text = run / "rasqberry-setup-scroll.txt"
    assert text.read_text().endswith("secret-pw") and text.stat().st_mode & 0o777 == 0o600
    # "Stop It" names it, and stops its unit - not the setup Wi-Fi
    label = subprocess.run(["bash", "-c", f'. "{common}"; _rq_led_holder_label '
                            '"python3 /usr/bin/rq_display_ip.py --text-file /run/rasqberry/x.txt"'],
                           capture_output=True, text=True).stdout.strip()
    assert label == "the Wi-Fi name and password scroll"
    # a demo on the panel keeps it
    log.unlink()
    code2 = code.replace("led_holders() { :; }", 'led_holders() { echo "12 Quantum Lights Out"; }')
    r = subprocess.run(["bash", "-c", code2], capture_output=True, text=True,
                       env=dict(os.environ, RQ_RUN_DIR=str(run)))
    assert r.returncode == 1 and not log.exists()


def test_address_hook_leaves_the_setup_wifi_alone(tmp_path):
    hook = os.path.join(_ROOT, "RQB2-system", "etc", "NetworkManager", "dispatcher.d",
                        "90-rasqberry-ip-display")
    shown = tmp_path / "shown"
    shown.write_text("")
    log = tmp_path / "log"
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name, body in (("systemctl", f'echo "systemctl $*" >> "{log}"\n'),
                       ("ip", 'echo "3: wlan0    inet 192.168.42.1/24 scope global wlan0"\n'),
                       ("logger", "exit 0\n")):
        (stubs / name).write_text("#!/bin/sh\n" + body)
        (stubs / name).chmod(0o755)
    env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", RQ_IP_SHOWN=str(shown),
               RQ_CLEAR_LEDS="/nonexistent", CONNECTION_ID="RasQberry-Setup-D6B3")
    subprocess.run(["bash", hook, "wlan0", "up"], env=env, capture_output=True, text=True)
    assert not log.exists() or "restart" not in log.read_text()
    env["CONNECTION_ID"] = "preconfigured"
    subprocess.run(["bash", hook, "wlan0", "up"], env=env, capture_output=True, text=True)
    assert "restart --no-block rasqberry-ip-display.service" in log.read_text()


def test_wifi_country_follows_the_time_zone_while_it_is_the_image_default(tmp_path):
    if not os.path.exists("/usr/share/zoneinfo/zone.tab"):
        import pytest
        pytest.skip("no zone.tab")
    log = tmp_path / "log"

    def country(reg, tz):
        if log.exists():
            log.unlink()
        code = (f'timedatectl() {{ echo {tz}; }}; rfkill() {{ :; }}; '
                f'raspi-config() {{ echo "$*" >> "{log}"; }}; ')
        stub = tmp_path / "iw"
        stub.write_text(f"#!/bin/sh\necho 'country {reg}: DFS-ETSI'\n")
        stub.chmod(0o755)
        sh = open(_SCRIPT).read().replace("/usr/sbin/iw", str(stub))
        script = tmp_path / "setup.sh"
        script.write_text(sh.replace('SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
                                     f'SCRIPT_DIR="{os.path.join(_ROOT, "RQB2-bin")}"'))
        subprocess.run(["bash", "-c", f'. "{script}"; {code} ensure_wifi_country'],
                       capture_output=True, text=True)
        return log.read_text().split()[-1] if log.exists() else None

    assert country("GB", "America/Chicago") == "US"     # the image default, a US time zone
    assert country("GB", "Europe/London") is None       # nothing to change
    assert country("00", "Europe/Berlin") == "DE"
    assert country("DE", "America/Chicago") is None     # a country someone chose stays


def test_wifi_connect_ships_its_licence_and_the_download_retries():
    # Apache-2.0 4a: the licence goes with the binary (review A16)
    doc = open(os.path.join(_ROOT, "RQB2-system", "usr", "share", "doc", "wifi-connect", "copyright")).read()
    stage = open(os.path.join(_ROOT, "stage-RQB2", "02-system-integration", "00-run-chroot.sh")).read()
    version = re.search(r"WIFI_CONNECT_VERSION=(v[\d.]+)", stage).group(1)
    assert f"Version: {version}" in doc and "Apache License" in doc and "END OF TERMS AND CONDITIONS" in doc
    assert re.search(r"WIFI_CONNECT_SHA256=([0-9a-f]{64})", stage).group(1) in doc
    assert "curl -fsSL --retry" in stage


def test_known_wifi_with_accents_or_colons_is_found_in_the_scan(tmp_path):
    # iw prints "Müller WLAN" as M\xc3\xbcller WLAN; nmcli -g escapes ":"
    iw = tmp_path / "iw"
    iw.write_text("#!/bin/sh\nprintf 'BSS 00:11(on wlan0)\\n\\tSSID: M\\\\xc3\\\\xbcller WLAN\\n"
                  "BSS 00:12(on wlan0)\\n\\tSSID: Lab:2\\n'\n")
    iw.chmod(0o755)
    script = tmp_path / "setup.sh"
    script.write_text(open(_SCRIPT).read().replace("/usr/sbin/iw", str(iw)).replace(
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        f'SCRIPT_DIR="{os.path.join(_ROOT, "RQB2-bin")}"'))

    def found(ssid_g):
        nm = (f"nmcli() {{ case \"$*\" in *UUID,TYPE*) echo 'u1:802-11-wireless:yes' ;; "
              f"*mode*) echo infrastructure ;; *ssid*) printf '%s\\n' '{ssid_g}' ;; esac; }}; ")
        r = subprocess.run(["bash", "-c", f'. "{script}"; {nm} known_in_range wlan0'],
                           capture_output=True, text=True)
        return r.returncode == 0
    assert found("Müller WLAN")
    assert found("Lab\\:2")                      # nmcli -g's escaping is undone
    assert not found("Müller")
