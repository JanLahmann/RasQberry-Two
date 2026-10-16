"""
The Wi-Fi hotspot (rq_hotspot.sh): settings, the boot-partition file, the
join QR code, and what the NetworkManager profile asks of the radio.
"""

import os
import subprocess

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCRIPT = os.path.join(_ROOT, "RQB2-bin", "rq_hotspot.sh")


def _bash(code, env=None):
    full = dict(os.environ, **(env or {}))
    return subprocess.run(["bash", "-c", f'. "{_SCRIPT}"; {code}'],
                          capture_output=True, text=True, env=full)


def test_settings_are_checked():
    cases = {
        "HOTSPOT_BAND a": 0, "HOTSPOT_BAND bg": 0, "HOTSPOT_BAND ac": 1,
        "HOTSPOT_SHARE_INTERNET yes": 0, "HOTSPOT_SHARE_INTERNET maybe": 1,
        "HOTSPOT_AT_BOOT no": 0,
        "HOTSPOT_PASSWORD short": 1, "HOTSPOT_PASSWORD 'long enough'": 0,
        "HOTSPOT_SSID " + "x" * 33: 1, "HOTSPOT_SSID 'Booth 1'": 0,
        "HOTSPOT_INTERFACE auto": 0, "HOTSPOT_INTERFACE wlan1": 0,
        "HOTSPOT_INTERFACE 'wlan0;rm'": 1, "LED_COUNT 192": 1,
    }
    for args, rc in cases.items():
        assert _bash(f"valid_setting {args}").returncode == rc, args


def test_invalid_setting_falls_back_to_default():
    out = _bash("setting HOTSPOT_BAND a", {"HOTSPOT_BAND": "ac"}).stdout.strip()
    assert out == "a"
    assert _bash("setting HOTSPOT_BAND a", {"HOTSPOT_BAND": "bg"}).stdout.strip() == "bg"


def test_join_qr_escapes_special_characters():
    out = _bash("qr_text 'Booth;1' 'pa:ss,w\"d'").stdout
    assert out == r'WIFI:T:WPA;S:Booth\;1;P:pa\:ss\,w\"d;;'


def test_boot_file_is_applied_once_without_the_password(tmp_path):
    boot = tmp_path / "rasqberry-hotspot.txt"
    boot.write_text("# booth\r\nHOTSPOT_AT_BOOT=yes\r\nHOTSPOT_PASSWORD=\"secret-pass\"\r\n"
                    "HOTSPOT_BAND=ac\r\nHOTSPOT_FOO=1\r\n")
    saved = tmp_path / "saved"
    code = (f'update_env_var() {{ echo "$1=$2" >> "{saved}"; }}; load_rqb2_env() {{ :; }}; '
            "apply_boot_file")
    r = _bash(code, {"RQ_HOTSPOT_BOOT_FILE": str(boot)})
    assert r.returncode == 0, r.stderr
    assert saved.read_text().splitlines() == ["HOTSPOT_AT_BOOT=yes", "HOTSPOT_PASSWORD=secret-pass"]
    assert not boot.exists()
    applied = (tmp_path / "rasqberry-hotspot.applied.txt").read_text()
    assert "secret-pass" not in applied and "HOTSPOT_AT_BOOT=yes" in applied
    assert "HOTSPOT_BAND" in r.stderr + r.stdout and "HOTSPOT_FOO" in r.stderr + r.stdout


def test_profile_fits_the_onboard_radio_and_trixie():
    sh = open(_SCRIPT).read()
    # WPA2 only (the onboard chip has no WPA3 hotspot), PMF off (trixie-feedback#29)
    for part in ("wifi-sec.key-mgmt wpa-psk", "wifi-sec.proto rsn", "wifi-sec.pmf 1",
                 "802-11-wireless.mode ap", "ipv4.method shared", "connection.autoconnect no"):
        assert part in sh, part
    assert "sae" not in sh.lower().replace("passphrase", "")
    # 5 GHz on channel 36 (no radar channels), 2.4 GHz on 6
    assert 'channel=36' in sh and 'channel=6' in sh


def test_settings_have_defaults_and_survive_updates():
    env = open(os.path.join(_ROOT, "RQB2-config", "rasqberry_environment.env")).read()
    for line in ("HOTSPOT_BAND=a", "HOTSPOT_INTERFACE=auto", "HOTSPOT_SHARE_INTERNET=yes",
                 "HOTSPOT_AT_BOOT=no", "HOTSPOT_SSID=", "HOTSPOT_PASSWORD="):
        assert "\n" + line + "\n" in env, line
    ds = open(os.path.join(_ROOT, "RQB2-bin", "rq_device_settings.sh")).read()
    assert "HOTSPOT_[A-Z_]*" in ds
    common = open(os.path.join(_ROOT, "RQB2-bin", "rq_common.sh")).read()
    assert "RQ_AUDIO_DELAY_MS|HOTSPOT_*)" in common


def test_boot_service_is_enabled():
    units = open(os.path.join(_ROOT, "RQB2-system", "enabled-units.txt")).read()
    assert "\nrasqberry-hotspot.service\n" in units
    unit = open(os.path.join(_ROOT, "RQB2-system", "etc", "systemd", "system",
                             "rasqberry-hotspot.service")).read()
    assert "ExecStart=/usr/bin/rq_hotspot.sh boot" in unit


def test_menu_has_the_hotspot():
    menu = open(os.path.join(_ROOT, "RQB2-config", "RQB2_menu.sh")).read()
    main = menu[menu.index("do_rasqberry_menu() {"):]
    assert 'HOTSPOT "Wi-Fi Hotspot (booths and classrooms)"' in main
    assert "HOTSPOT) do_hotspot_menu" in main
    hs = menu[menu.index("do_hotspot_menu() {"):]
    hs = hs[:hs.index("\n}\n")]
    for item in ("STATE", "SHOW", "NAME", "BOOT", "SHARE", "BAND"):
        assert f"\n            {item} " in hs, item
    # settings go to /data like the LED ones
    assert "LED_*|RASQ_LED_*|RQ_AUDIO_DELAY_MS|HOTSPOT_*)" in menu


def test_entangible_gets_the_hotspot_address_and_loses_it_again(tmp_path):
    env = tmp_path / "entangible"
    env.write_text("QAMPOSER_SOURCE=cv2:0\n# QAMPOSER_ADVERTISE_HOST=10.42.0.1\n")
    e = {"RQ_HOTSPOT_ENTANGIBLE_ENV": str(env), "PATH": "/usr/bin:/bin"}
    assert _bash("advertise on; advertise on", e).returncode == 0
    lines = env.read_text().splitlines()
    assert lines.count("QAMPOSER_ADVERTISE_HOST=10.42.0.1") == 1     # once, however often
    assert _bash("advertise off", e).returncode == 0
    assert env.read_text() == "QAMPOSER_SOURCE=cv2:0\n# QAMPOSER_ADVERTISE_HOST=10.42.0.1\n"


def test_an_address_the_user_set_for_entangible_stays(tmp_path):
    env = tmp_path / "entangible"
    env.write_text("QAMPOSER_ADVERTISE_HOST=booth.local\n")
    e = {"RQ_HOTSPOT_ENTANGIBLE_ENV": str(env), "PATH": "/usr/bin:/bin"}
    _bash("advertise on", e)
    assert env.read_text() == "QAMPOSER_ADVERTISE_HOST=booth.local\n"
    _bash("advertise off", e)
    assert env.read_text() == "QAMPOSER_ADVERTISE_HOST=booth.local\n"


def _portal():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "rq_hotspot_portal", os.path.join(_ROOT, "RQB2-bin", "rq_hotspot_portal.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_landing_page_finds_ports_open_to_phones(tmp_path):
    tcp = tmp_path / "tcp"
    head = "  sl  local_address rem_address   st\n"
    tcp.write_text(head +
                   "   0: 00000000:1F90 00000000:0000 0A\n"     # 0.0.0.0:8080 listening
                   "   1: 0100007F:22B8 00000000:0000 0A\n"     # 127.0.0.1:8888 - localhost only
                   "   2: 01002A0A:20FB 00000000:0000 0A\n"     # 10.42.0.1:8443
                   "   3: 00000000:0016 00000000:0000 0A\n"     # :22 SSH - not a demo
                   "   4: 00000000:1F91 0100007F:1234 01\n")    # established, not listening
    assert _portal().listening_ports((str(tcp),)) == [8080, 8443]


def test_landing_page_escapes_titles():
    page = _portal().render("10.42.0.1", "Booth <1>", [("<b>x</b>", "http://10.42.0.1:8080/")])
    assert "&lt;b&gt;x&lt;/b&gt;" in page and "Booth &lt;1&gt;" in page and "<b>x" not in page


def test_landing_page_runs_only_with_the_hotspot():
    units = open(os.path.join(_ROOT, "RQB2-system", "enabled-units.txt")).read()
    assert "rasqberry-hotspot-portal" not in units          # started by rq_hotspot.sh
    unit = open(os.path.join(_ROOT, "RQB2-system", "etc", "systemd", "system",
                             "rasqberry-hotspot-portal.service")).read()
    assert "DynamicUser=yes" in unit and "AmbientCapabilities=CAP_NET_BIND_SERVICE" in unit
    sh = open(_SCRIPT).read()
    assert 'portal on "$ssid"' in sh and "portal off" in sh and "address=/#/" in sh


def test_join_card_escapes_and_has_both_codes(tmp_path):
    import shutil
    import pytest
    if not shutil.which("qrencode"):
        pytest.skip("qrencode not installed")
    out = tmp_path / "card.html"
    r = _bash(f"write_card 'Booth <1>' 'pa&ss word' '{out}'")
    assert r.returncode == 0, r.stderr
    card = out.read_text()
    assert card.count("<svg") == 2
    assert "Booth &lt;1&gt;" in card and "pa&amp;ss word" in card and "Booth <1>" not in card
    assert "http://10.42.0.1" in card and "@page { size: A6" in card


# Rig mission 2026-10-16: the page always said "This Wi-Fi has no internet",
# also with sharing on and a cable in the Pi
_ROUTES_HEAD = "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"


def _routes(tmp_path, *lines):
    f = tmp_path / "route"
    f.write_text(_ROUTES_HEAD + "".join(lines))
    return str(f)


def test_landing_page_says_whether_the_wifi_reaches_the_internet():
    portal = _portal()
    off = portal.render("10.42.0.1", "Booth", [])
    assert "This Wi-Fi has no internet" in off and "reaches the internet" not in off
    on = portal.render("10.42.0.1", "Booth", [], internet=True)
    assert "This Wi-Fi also reaches the internet" in on and "has no internet" not in on
    assert '<a href="https://rasqberry.org/">rasqberry.org</a>' in on


def test_internet_needs_sharing_and_a_way_out(tmp_path):
    portal = _portal()
    cable = _routes(tmp_path, "eth0\t00000000\t01B2A8C0\t0003\t0\t0\t100\t00000000\t0\t0\t0\n",
                    "wlan0\t002A0A00\t00000000\t0001\t0\t0\t600\t00FFFFFF\t0\t0\t0\n")
    shared = {"RQ_HOTSPOT_INTERNET": "yes", "RQ_HOTSPOT_IFACE": "wlan0"}
    assert portal.reaches_internet(shared, cable)
    assert not portal.reaches_internet({"RQ_HOTSPOT_INTERNET": "no", "RQ_HOTSPOT_IFACE": "wlan0"}, cable)
    assert not portal.reaches_internet({}, cable)
    # the cable is out: only the hotspot's own routes are left
    hotspot_only = _routes(tmp_path, "wlan0\t00000000\t00000000\t0001\t0\t0\t600\t00000000\t0\t0\t0\n")
    assert not portal.reaches_internet(shared, hotspot_only)
    assert not portal.reaches_internet(shared, _routes(tmp_path))
    assert not portal.reaches_internet(shared, str(tmp_path / "missing"))


def test_hotspot_tells_the_page_whether_it_shares_internet(tmp_path):
    env_file = tmp_path / "portal.env"
    captive = tmp_path / "captive.conf"
    e = {"RQ_HOTSPOT_PORTAL_ENV": str(env_file), "RQ_HOTSPOT_CAPTIVE_CONF": str(captive)}
    stubs = "systemctl() { :; }; nat_ready() { [ \"$1\" = wlan0 ]; }; "
    assert _bash(stubs + "portal on Booth wlan0", e).returncode == 0
    assert env_file.read_text() == "RQ_HOTSPOT_SSID=Booth\nRQ_HOTSPOT_INTERNET=yes\nRQ_HOTSPOT_IFACE=wlan0\n"
    captive.write_text("address=/#/10.42.0.1\n")      # no way out: every name leads to the page
    _bash(stubs + "portal on Booth wlan0", e)
    assert "RQ_HOTSPOT_INTERNET=no\n" in env_file.read_text()
    captive.unlink()
    _bash(stubs + "portal on Booth wlan1", e)             # no NAT for the hotspot
    assert "RQ_HOTSPOT_INTERNET=no\n" in env_file.read_text()
    _bash(stubs + "portal off", e)
    assert not env_file.exists()
    sh = open(_SCRIPT).read()
    on = sh[sh.index("cmd_on() {"):]
    on = on[:on.index("\n}\n")]
    assert on.index("nat_ready") < on.index('portal on "$ssid" "$iface"')
