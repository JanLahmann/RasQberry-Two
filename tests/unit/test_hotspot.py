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
                    "HOTSPOT_SSID='Jan's Booth (Hall 3)'\r\nHOTSPOT_BAND=ac\r\nHOTSPOT_FOO=1\r\n")
    saved = tmp_path / "saved"
    secrets = tmp_path / "hotspot.conf"
    code = (f'update_env_var() {{ echo "$1=$2" >> "{saved}"; }}; load_rqb2_env() {{ :; }}; '
            "apply_boot_file")
    r = _bash(code, {"RQ_HOTSPOT_BOOT_FILE": str(boot), "RQ_HOTSPOT_SECRETS": str(secrets)})
    assert r.returncode == 0, r.stderr
    # name and password go to their own file, never into the env file (review D1)
    assert saved.read_text().splitlines() == ["HOTSPOT_AT_BOOT=yes"]
    assert _secret(secrets, "HOTSPOT_PASSWORD") == "secret-pass"
    assert _secret(secrets, "HOTSPOT_SSID") == "Jan's Booth (Hall 3)"
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
                 "HOTSPOT_AT_BOOT=no"):
        assert "\n" + line + "\n" in env, line
    # name and password: not in this file, which is loaded as shell code (review D1)
    assert "\nHOTSPOT_SSID=" not in env and "\nHOTSPOT_PASSWORD=" not in env
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
    for item in ("STATE", "SHOW", "NAME", "BOOT", "SHARE", "BAND", "ADMIN"):
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
    stubs = "systemctl() { :; }; forward_ok() { :; }; nat_ready() { [ \"$1\" = wlan0 ]; }; "
    assert _bash(stubs + "portal on Booth wlan0", e).returncode == 0
    assert env_file.read_text() == 'RQ_HOTSPOT_SSID="Booth"\nRQ_HOTSPOT_INTERNET=yes\nRQ_HOTSPOT_IFACE=wlan0\n'
    _bash(stubs + "portal on 'a\\b\"c`d$e' wlan0", e)          # systemd's EnvironmentFile quoting
    assert env_file.read_text().startswith('RQ_HOTSPOT_SSID="a\\\\b\\"c\\`d\\$e"\n')
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


# --- review D1/D5: name and password in a root-only file, never run as shell code

def _secret(path, key):
    value = None
    for line in path.read_text().splitlines():
        if line.startswith(key + "="):
            value = line.split("=", 1)[1]
    return value


_NASTY_NAMES = ["Booth (Hall 3)", "Jan's Booth", "Physics Lab", "Quantum$$Fun", 'a"b`c`$(id);x',
                "back\\slash\\t", "Grüße 2026", "  spaced  ", "x" * 32]
_NASTY_PASSWORDS = ["Quantum$$Fun", "pa ss'w\"o(r)d$x;", "\\t\\\\x12345", "`reboot` $(id)", "a" * 63]


def _env_copy(tmp_path):
    env = tmp_path / "rasqberry_environment.env"
    env.write_text(open(os.path.join(_ROOT, "RQB2-config", "rasqberry_environment.env")).read())
    return env


def _loads_cleanly(env):
    """The env file loads in dash (raspi-config) and bash without an error."""
    for sh in ("dash", "bash"):
        r = subprocess.run([sh, "-c", f'. "{env}"; echo "LOADED $HOTSPOT_AT_BOOT $OS_VERSION"'],
                           capture_output=True, text=True)
        assert r.returncode == 0 and "LOADED no none" in r.stdout and not r.stderr, (sh, r.stderr)


def test_nasty_names_and_passwords_round_trip(tmp_path):
    env = _env_copy(tmp_path)
    before = env.read_text()
    secrets = tmp_path / "data" / "hotspot.conf"
    e = {"RQ_HOTSPOT_SECRETS": str(secrets), "RQ_ENV_FILE": str(env)}
    for name, pw in zip(_NASTY_NAMES, _NASTY_PASSWORDS * 2):
        r = subprocess.run(["bash", "-c", f'. "{_SCRIPT}"; cmd_set HOTSPOT_SSID HOTSPOT_PASSWORD'],
                           input=f"{name}\n{pw}\n", capture_output=True, text=True,
                           env=dict(os.environ, **e))
        assert r.returncode == 0, (name, r.stderr)
        got = _bash("secret_get HOTSPOT_SSID; echo '|'; setting HOTSPOT_PASSWORD x", e).stdout
        assert got == f"{name}|\n{pw}\n", (name, pw, got)
        assert secrets.stat().st_mode & 0o777 == 0o600
    assert env.read_text() == before                    # the env file is not touched
    _loads_cleanly(env)


def test_a_rejected_value_saves_neither(tmp_path):
    secrets = tmp_path / "hotspot.conf"
    e = dict(os.environ, RQ_HOTSPOT_SECRETS=str(secrets))
    for name, pw, rule in (("New name", "Grüße-2026", "without accents"),     # review A11
                           ("New name", "short", "8 to 63"),
                           ("x" * 33, "long enough", "32 characters")):
        r = subprocess.run(["bash", "-c", f'. "{_SCRIPT}"; cmd_set HOTSPOT_SSID HOTSPOT_PASSWORD'],
                           input=f"{name}\n{pw}\n", capture_output=True, text=True, env=e)
        assert r.returncode == 1 and rule in r.stderr, r.stderr
        assert not secrets.exists()
    assert _bash("valid_setting HOTSPOT_SSID $'a\\nb'").returncode == 1        # no control characters
    assert _bash("valid_setting HOTSPOT_PASSWORD $'abcdefgh\\nxyz'").returncode == 1


def test_old_env_lines_move_to_their_own_file(tmp_path):
    # written unquoted by the previous version: dash stopped at "(" (raspi-config died),
    # the apostrophe swallowed the lines after it
    for name in ("Booth (Hall 3)", "Jan's Booth"):
        env = _env_copy(tmp_path)
        env.write_text(env.read_text().replace(
            "HOTSPOT_BAND=a\n", f"HOTSPOT_SSID={name}\nHOTSPOT_PASSWORD=Quantum$$Fun\nHOTSPOT_BAND=a\n"))
        secrets = tmp_path / f"hotspot-{len(name)}.conf"
        r = _bash("migrate_secrets", {"RQ_HOTSPOT_SECRETS": str(secrets), "RQ_ENV_FILE": str(env)})
        assert r.returncode == 0, r.stderr
        assert _secret(secrets, "HOTSPOT_SSID") == name
        assert _secret(secrets, "HOTSPOT_PASSWORD") == "Quantum$$Fun"
        assert "\nHOTSPOT_SSID=" not in env.read_text() and "HOTSPOT_PASSWORD=" not in env.read_text()
        assert "\nHOTSPOT_BAND=a\n" in env.read_text()
        _loads_cleanly(env)


def test_a_fresh_slot_takes_them_from_an_older_store_once(tmp_path):
    env = _env_copy(tmp_path)
    store = tmp_path / "store"
    store.mkdir()
    (store / "device-settings.env").write_text("HOTSPOT_SSID=Old Booth\nHOTSPOT_PASSWORD=old-password\n")
    secrets = tmp_path / "hotspot.conf"
    e = {"RQ_HOTSPOT_SECRETS": str(secrets), "RQ_ENV_FILE": str(env), "RQ_SETTINGS_DIR": str(store)}
    assert _bash("migrate_secrets", e).returncode == 0
    assert _secret(secrets, "HOTSPOT_SSID") == "Old Booth"
    # the user then picks the default name: the store's old one does not come back
    assert _bash("printf 'x\\n' >/dev/null; secret_set HOTSPOT_SSID ''; migrate_secrets", e).returncode == 0
    assert _secret(secrets, "HOTSPOT_SSID") is None
    assert _secret(secrets, "HOTSPOT_PASSWORD") == "old-password"


def test_env_writers_quote_what_the_shell_would_run(tmp_path):
    # defence in depth: any value written by update_env_var loads as written
    env = _env_copy(tmp_path)
    conf = tmp_path / "env-config.sh"
    conf.write_text("REPO=RasQberry-Two USER_HOME=/nonexistent\n")
    for value in _NASTY_NAMES + ["https://example.org/a&b.git", "plain-1.2", ""]:
        r = _bash('update_env_var RQ_TEST_KEY "$V" >/dev/null', {
            "RQ_ENV_FILE": str(env), "RQ_CONFIG_FILE": str(conf), "V": value,
            "PATH": f"{_stub_dir(tmp_path)}:{os.environ['PATH']}"})
        assert r.returncode == 0, r.stderr
        for sh in ("dash", "bash"):
            got = subprocess.run([sh, "-c", f'. "{env}"; printf %s "$RQ_TEST_KEY"'],
                                 capture_output=True, text=True)
            assert got.stdout == value and not got.stderr, (sh, value, got.stderr)
    assert "\nRQ_TEST_KEY=\n" in env.read_text()             # plain values stay unquoted


def _stub_dir(tmp_path):
    """sudo runs the command as this user (the test is not root)."""
    stubs = tmp_path / "stubs"
    if not stubs.exists():
        stubs.mkdir()
        (stubs / "sudo").write_text('#!/bin/sh\nexec "$@"\n')
        (stubs / "sudo").chmod(0o755)
    return stubs


def test_menu_hands_name_and_password_over_on_stdin():
    menu = open(os.path.join(_ROOT, "RQB2-config", "RQB2_menu.sh")).read()
    fn = menu[menu.index("do_hotspot_name() {"):]
    fn = fn[:fn.index("\n}\n")]
    assert 'rq_hotspot.sh" set HOTSPOT_SSID HOTSPOT_PASSWORD' in fn and "printf '%s\\n%s\\n'" in fn
    assert "_rq_hs_set HOTSPOT_SSID" not in menu and "_rq_hs_set HOTSPOT_PASSWORD" not in menu
    assert "${HOTSPOT_PASSWORD" not in menu
    # raspi-config moves old lines out before it loads the file
    load = menu[menu.index("_rq_load_env() {"):]
    load = load[:load.index("\n}\n")]
    assert load.index("rq_hotspot.sh migrate") < load.index('. "$ENV_CONFIG_FILE"')


# --- review A2-A4: the hotspot's firewall ---------------------------------------

def _rules(tmp_path, env=None, iptables_s=""):
    """share_rules wlan0 with nft and iptables stubbed: (nft ruleset, iptables calls)."""
    nft_in = tmp_path / "nft.in"
    ipt = tmp_path / "ipt.log"
    for f in (nft_in, ipt):
        if f.exists():
            f.unlink()
    stubs = tmp_path / "fwstubs"
    stubs.mkdir(exist_ok=True)
    (stubs / "nft").write_text(f'#!/bin/sh\n[ "$1" = -f ] && cat > "{nft_in}"\nexit 0\n')
    (stubs / "iptables").write_text(
        f'#!/bin/sh\necho "$*" >> "{ipt}"\n'
        f'[ "$1 $2" = "-S DOCKER-USER" ] && printf "%b" "{iptables_s}"\nexit 0\n')
    for f in ("nft", "iptables"):
        (stubs / f).chmod(0o755)
    e = dict(env or {}, PATH=f"{stubs}:{os.environ['PATH']}")
    r = _bash("share_rules wlan0", e)
    assert r.returncode == 0, r.stderr
    return (nft_in.read_text() if nft_in.exists() else "",
            ipt.read_text().splitlines() if ipt.exists() else [])


def test_ssh_and_vnc_from_the_hotspot_are_blocked_by_default(tmp_path):
    ruleset, _ = _rules(tmp_path)
    assert 'iifname "wlan0" tcp dport { 22, 5900 } drop' in ruleset
    assert "hook input" in ruleset
    ruleset, _ = _rules(tmp_path, {"HOTSPOT_ALLOW_ADMIN": "yes"})
    assert "dport" not in ruleset


def test_no_sharing_still_lets_phones_reach_docker_demos(tmp_path):
    ruleset, _ = _rules(tmp_path, {"HOTSPOT_SHARE_INTERNET": "no"})
    fwd = ruleset[ruleset.index("chain forward"):]
    # replies and DNAT'ed demo ports first, then the drops (review A3)
    assert fwd.index("ct status dnat accept") < fwd.index('iifname "wlan0" drop')
    assert fwd.index("ct state established,related accept") < fwd.index('oifname "wlan0" drop')
    ruleset, _ = _rules(tmp_path, {"HOTSPOT_SHARE_INTERNET": "yes"})
    assert "chain forward" not in ruleset


def test_sharing_gets_past_dockers_forward_drop(tmp_path):
    _, calls = _rules(tmp_path, {"HOTSPOT_SHARE_INTERNET": "yes"})
    inserts = [c for c in calls if c.startswith("-I DOCKER-USER")]
    assert "-N DOCKER-USER" in calls
    assert len(inserts) == 4 and all("--comment rasqberry-hotspot" in c for c in inserts)
    # the last insert is checked first: Docker's bridges stay under Docker's rules
    assert "-o docker+" in inserts[-1] and "-j RETURN" in inserts[-1]
    assert "-o br-+" in inserts[-2] and "-j RETURN" in inserts[-2]
    assert "-i wlan0" in inserts[-3] and inserts[-3].endswith("-j ACCEPT")
    assert "-o wlan0 -m conntrack --ctstate RELATED,ESTABLISHED" in inserts[0]
    # sharing off: only the old rules go
    _, calls = _rules(tmp_path, {"HOTSPOT_SHARE_INTERNET": "no"},
                      iptables_s=r"-N DOCKER-USER\n-A DOCKER-USER -i wlan0 -m comment --comment rasqberry-hotspot -j ACCEPT\n-A DOCKER-USER -j RETURN\n")
    assert not [c for c in calls if c.startswith("-I")]
    assert "-D DOCKER-USER -i wlan0 -m comment --comment rasqberry-hotspot -j ACCEPT" in calls
    assert "-D DOCKER-USER -j RETURN" not in calls                 # not ours


def test_page_says_no_internet_while_the_firewall_drops_it(tmp_path):
    env_file = tmp_path / "portal.env"
    e = {"RQ_HOTSPOT_PORTAL_ENV": str(env_file), "RQ_HOTSPOT_CAPTIVE_CONF": str(tmp_path / "none")}
    stubs = "systemctl() { :; }; nat_ready() { :; }; "
    _bash(stubs + "forward_ok() { false; }; portal on Booth wlan0", e)
    assert "RQ_HOTSPOT_INTERNET=no\n" in env_file.read_text()
    _bash(stubs + "forward_ok() { :; }; portal on Booth wlan0", e)
    assert "RQ_HOTSPOT_INTERNET=yes\n" in env_file.read_text()


def test_forward_ok_reads_dockers_policy(tmp_path):
    def ok(policy, accept):
        stub = (f"iptables() {{ case \"$1 $2\" in '-S FORWARD') echo '-P FORWARD {policy}' ;; "
                f"'-C DOCKER-USER') {accept} ;; esac; }}; ")
        return _bash(stub + "forward_ok wlan0").returncode == 0
    assert ok("ACCEPT", "false")                  # no Docker
    assert not ok("DROP", "false")                # Docker, no accept for the hotspot
    assert ok("DROP", "true")


def test_admin_setting_is_kept_and_in_the_menu():
    env = open(os.path.join(_ROOT, "RQB2-config", "rasqberry_environment.env")).read()
    assert "\nHOTSPOT_ALLOW_ADMIN=no\n" in env
    assert _bash("valid_setting HOTSPOT_ALLOW_ADMIN yes").returncode == 0
    assert _bash("valid_setting HOTSPOT_ALLOW_ADMIN maybe").returncode == 1
    menu = open(os.path.join(_ROOT, "RQB2-config", "RQB2_menu.sh")).read()
    assert "ADMIN) do_hotspot_admin" in menu
    fn = menu[menu.index("do_hotspot_admin() {"):]
    assert "--defaultno --yesno" in fn[:fn.index("\n}\n")]


# --- review C1, A7: what goes with the hotspot follows its real state --------------

def _state_env(tmp_path):
    ent = tmp_path / "entangible"
    ent.write_text("QAMPOSER_SOURCE=cv2:0\n# rq_hotspot.sh: phones on the hotspot use its address "
                   "(removed when it stops)\nQAMPOSER_ADVERTISE_HOST=10.42.0.1\n")
    captive = tmp_path / "captive.conf"
    captive.write_text("address=/#/10.42.0.1\n")
    portal_env = tmp_path / "portal.env"
    portal_env.write_text("RQ_HOTSPOT_SSID=\"Booth\"\n")
    e = {"RQ_HOTSPOT_ENTANGIBLE_ENV": str(ent), "RQ_HOTSPOT_CAPTIVE_CONF": str(captive),
         "RQ_HOTSPOT_PORTAL_ENV": str(portal_env), "RQ_HOTSPOT_BOOT_FILE": str(tmp_path / "none.txt"),
         "RQ_HOTSPOT_LOCK": str(tmp_path / "lock")}
    return ent, captive, portal_env, e


def test_boot_without_the_hotspot_clears_what_an_earlier_one_left(tmp_path):
    # an unclean end, then a reboot onto the school Wi-Fi: Entangible still
    # showed phones https://10.42.0.1:8443 and the captive DNS stayed (review C1)
    ent, captive, portal_env, e = _state_env(tmp_path)
    stubs = "nmcli() { :; }; systemctl() { :; }; nft() { :; }; "
    r = _bash(stubs + "cmd_boot", dict(e, HOTSPOT_AT_BOOT="no"))
    assert r.returncode == 0, r.stderr
    assert ent.read_text() == "QAMPOSER_SOURCE=cv2:0\n"
    assert not captive.exists() and not portal_env.exists()


def test_sync_restarts_the_hotspot_when_the_way_out_changed(tmp_path):
    ent, captive, portal_env, e = _state_env(tmp_path)
    log = tmp_path / "log"
    stubs = (f'hotspot_active() {{ :; }}; profile_value() {{ case "$1" in *interface*) echo wlan0 ;; *) echo Booth ;; esac; }}; '
             f'cmd_on() {{ echo "on $*" >> "{log}"; }}; share_rules() {{ echo "rules $*" >> "{log}"; }}; '
             f'portal() {{ echo "portal $*" >> "{log}"; }}; ')
    # a cable came in: sharing on, a default route over eth0, but all names still go to the Pi
    route = 'ip() { echo "default via 192.168.1.1 dev eth0 proto dhcp"; }; '
    assert _bash(stubs + route + "cmd_sync", dict(e, HOTSPOT_SHARE_INTERNET="yes")).returncode == 0
    assert log.read_text() == "on quiet\n"
    # nothing changed: rules, Entangible's address and the page, no restart
    log.unlink()
    ent.write_text("QAMPOSER_SOURCE=cv2:0\n")
    assert _bash(stubs + "ip() { :; }; cmd_sync", dict(e, HOTSPOT_SHARE_INTERNET="yes")).returncode == 0
    assert log.read_text() == "rules wlan0\nportal on Booth wlan0\n"
    assert "QAMPOSER_ADVERTISE_HOST=10.42.0.1" in ent.read_text()


def test_network_changes_bring_a_sync(tmp_path):
    hook = os.path.join(_ROOT, "RQB2-system", "etc", "NetworkManager", "dispatcher.d",
                        "91-rasqberry-hotspot")
    log = tmp_path / "log"
    stubs = tmp_path / "hookstubs"
    stubs.mkdir()
    (stubs / "systemd-run").write_text(f'#!/bin/sh\necho "$*" >> "{log}"\n')
    (stubs / "systemd-run").chmod(0o755)
    fake = tmp_path / "rq_hotspot.sh"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)
    env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", RQ_HOTSPOT_BIN=str(fake))
    for iface, action in (("eth0", "up"), ("wlan0", "down"), ("eth0", "dhcp4-change"),
                          ("veth12", "up"), ("lo", "up")):
        subprocess.run(["bash", hook, iface, action], env=env, capture_output=True, text=True)
    calls = log.read_text().splitlines()
    assert calls == [f"--no-block --quiet --collect {fake} sync"] * 2


def test_on_off_boot_and_sync_take_turns():
    sh = open(_SCRIPT).read()
    assert 'on|off|boot|sync) take_lock "$1"' in sh and "flock -w" in sh
    # rq_entangible.sh sources this script for these names (sync_hotspot_address)
    assert _bash('declare -F advertise >/dev/null && [ "$PROFILE" = rasqberry-hotspot ]').returncode == 0


# --- review A6, A8: start at boot ------------------------------------------------

def test_no_wifi_device_gives_the_message_not_a_silent_exit():
    # under set -e, `iface=$(hotspot_interface)` ended the script before the die
    r = _bash("nmcli() { :; }; iface=$(hotspot_interface); echo \"after [$iface]\"")
    assert r.returncode == 0 and "after []" in r.stdout
    r = _bash("nmcli() { :; }; cmd_on quiet")
    assert r.returncode == 1 and "No Wi-Fi device found" in r.stderr


def test_boot_waits_for_the_wifi_and_tries_again(tmp_path):
    _, _, _, e = _state_env(tmp_path)
    tries = tmp_path / "tries"
    checks = tmp_path / "checks"
    # wlan0 is "unavailable" for three checks, then cmd_on fails twice and works
    code = (f'nmcli() {{ case "$*" in *DEVICE,TYPE*) echo wlan0:wifi ;; *DEVICE,STATE*) '
            f'echo x >> "{checks}"; [ "$(wc -l < "{checks}")" -gt 3 ] && echo wlan0:disconnected '
            '|| echo wlan0:unavailable ;; esac; }; sleep() { :; }; '
            f'cmd_on() {{ echo x >> "{tries}"; [ "$(wc -l < "{tries}")" -ge 3 ]; }}; '
            'readlink() { echo /x/brcmfmac; }; cmd_boot')
    r = _bash(code, dict(e, HOTSPOT_AT_BOOT="yes"))
    assert r.returncode == 0, r.stderr
    assert len(checks.read_text().split()) == 4                 # it waited for the device
    assert len(tries.read_text().split()) == 3 and "try 2 of 3" in r.stderr


def test_boot_that_fails_leaves_nothing_behind(tmp_path):
    ent, captive, portal_env, e = _state_env(tmp_path)
    code = ('nmcli() { :; }; sleep() { :; }; systemctl() { :; }; nft() { :; }; '
            'hotspot_interface() { echo wlan0; }; cmd_on() { false; }; cmd_boot')
    r = _bash(code, dict(e, HOTSPOT_AT_BOOT="yes", RQ_HOTSPOT_WIFI_WAIT="0"))
    assert r.returncode == 1 and "setup Wi-Fi" in r.stderr
    assert not captive.exists() and "10.42.0.1" not in ent.read_text()
    unit = open(os.path.join(_ROOT, "RQB2-system", "etc", "systemd", "system",
                             "rasqberry-hotspot.service")).read()
    assert "network-online.target" in unit and "TimeoutStartSec=300" in unit


# --- review A11, A13, A14, A15 ------------------------------------------------------

def _pick(devices, no_ap=""):
    stub = (f"nmcli() {{ printf '%b' '{devices}'; }}; "
            "readlink() { case \"$2\" in */wlan0/*) echo /drivers/brcmfmac ;; *) echo /drivers/mt7921u ;; esac; }; "
            f"ap_capable() {{ [ \"$1\" != '{no_ap}' ]; }}; ")
    return _bash(stub + "hotspot_interface").stdout.strip()


def test_auto_never_takes_the_uplink_adapter_when_another_radio_is_idle():
    # USB adapter idle: it is the hotspot (the onboard Wi-Fi stays the client)
    assert _pick(r"wlan0:wifi:connected:home\nwlan1:wifi:disconnected:\n") == "wlan1"
    # USB adapter is the Pi's Wi-Fi connection, the onboard radio idle (review A13)
    assert _pick(r"wlan0:wifi:disconnected:\nwlan1:wifi:connected:home\n") == "wlan0"
    # one radio only: it, as before (the menu warns)
    assert _pick(r"wlan0:wifi:connected:home\n") == "wlan0"
    # the running hotspot counts as idle: a restart keeps its radio
    assert _pick(r"wlan0:wifi:connected:rasqberry-hotspot\nwlan1:wifi:connected:home\n") == "wlan0"
    # an adapter that cannot be an access point is left out
    assert _pick(r"wlan0:wifi:disconnected:\nwlan1:wifi:disconnected:\n", no_ap="wlan1") == "wlan0"
    assert _pick(r"eth0:ethernet:connected:x\n") == ""


def test_join_card_shows_the_running_hotspot(tmp_path):
    code = ('hotspot_active() { :; }; '
            'nmcli() { case "$*" in *psk*) echo "pw-of-the-profile" ;; *ssid*) echo "Booth A" ;; esac; }; '
            'join_details')
    assert _bash(code, {"RQ_HOTSPOT_SECRETS": str(tmp_path / "none")}).stdout == "Booth A\npw-of-the-profile\n"
    sh = open(_SCRIPT).read()
    on = sh[sh.index("cmd_on() {"):]
    assert 'secret_set HOTSPOT_SSID "$ssid"' in on[:on.index("\n}\n")]   # the name is kept


def test_boot_file_on_the_config_partition_is_read(tmp_path):
    cfg = tmp_path / "config" / "rasqberry-hotspot.txt"
    cfg.parent.mkdir()
    cfg.write_text("HOTSPOT_AT_BOOT=yes\n")
    saved = tmp_path / "saved"
    code = f'update_env_var() {{ echo "$1=$2" >> "{saved}"; }}; load_rqb2_env() {{ :; }}; apply_boot_file'
    r = _bash(code, {"RQ_HOTSPOT_BOOT_FILE": str(tmp_path / "fw" / "rasqberry-hotspot.txt"),
                     "RQ_HOTSPOT_CONFIG_FILE": str(cfg), "RQ_HOTSPOT_SECRETS": str(tmp_path / "s")})
    assert r.returncode == 0, r.stderr
    assert saved.read_text() == "HOTSPOT_AT_BOOT=yes\n"
    assert not cfg.exists() and (tmp_path / "config" / "rasqberry-hotspot.applied.txt").exists()


def test_a_refused_password_is_listed_and_shown_at_the_start(tmp_path):
    boot = tmp_path / "rasqberry-hotspot.txt"
    boot.write_text("HOTSPOT_AT_BOOT=yes\nHOTSPOT_PASSWORD=short\n")
    secrets = tmp_path / "hotspot.conf"
    log = tmp_path / "log"
    _, _, _, e = _state_env(tmp_path)
    e.update(RQ_HOTSPOT_BOOT_FILE=str(boot), RQ_HOTSPOT_SECRETS=str(secrets), HOTSPOT_AT_BOOT="yes",
             RQ_HOTSPOT_WIFI_WAIT="0")
    code = ('update_env_var() { :; }; load_rqb2_env() { :; }; wait_for_wifi() { :; }; cmd_on() { :; }; '
            'join_details() { printf "Booth\\nnew-pw-1234\\n"; }; '
            f'rq_wifi_scroll() {{ echo "scroll $*" >> "{log}"; }}; cmd_boot')
    r = _bash(code, e)
    assert r.returncode == 0, r.stderr
    applied = (tmp_path / "rasqberry-hotspot.applied.txt").read_text()
    assert "short" not in applied
    assert "# Not taken: HOTSPOT_PASSWORD. The password needs 8 to 63 characters" in applied
    assert "LED panel scrolls it" in applied
    # nobody knows the password: the LED panel and the journal say it once
    assert "scroll rasqberry-hotspot-scroll 600 Wi-Fi Booth  ***  password new-pw-1234" in log.read_text()
    assert "its password is new-pw-1234" in r.stdout
    # a password that was taken: no scroll
    log.unlink()
    secrets.write_text("HOTSPOT_PASSWORD=known-password\n")
    boot.write_text("HOTSPOT_AT_BOOT=yes\n")
    assert _bash(code, e).returncode == 0 and not log.exists()


def test_join_card_makes_the_cache_folders_the_users(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    code = ('join_details() { printf "Booth\\npw-12345678\\n"; }; write_card() { echo card > "$3"; }; '
            'rq_open_browser() { :; }; cmd_card')
    r = _bash(code, {"USER_HOME": str(home)})
    assert r.returncode == 0, r.stderr
    assert (home / ".cache").stat().st_mode & 0o777 == 0o700
    assert (home / ".cache" / "rasqberry" / "hotspot-card.html").stat().st_mode & 0o777 == 0o600
