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
