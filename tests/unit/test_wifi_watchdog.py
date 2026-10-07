"""
Tests for rq_wifi_watchdog.sh: Wi-Fi that NetworkManager gave up on.

On the rig (2026-10-04) the router rejected the first association attempts of
a new card; NetworkManager put wlan0 into need-auth (it asks a secret agent
for a "new" password), nobody answered, and the Pi stayed offline with the
right password stored until `nmcli connection up preconfigured`.

A fake nmcli plays NetworkManager from a JSON scenario and records its calls.
"""

import json
import os
import shutil
import stat
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_SCRIPT = os.path.join(_ROOT, "RQB2-bin", "rq_wifi_watchdog.sh")
_UNITS = os.path.join(_ROOT, "RQB2-system", "etc", "systemd", "system")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")

NM_DIR = "/etc/NetworkManager/system-connections/"

# The fake nmcli: just the calls rq_wifi_watchdog.sh makes, in nmcli 1.42's
# terse formats ("KEY:value" lines for show, ":"-separated escaped rows for
# lists, "NUM (text)" for device state and reason).
_FAKE_NMCLI = r'''#!/usr/bin/env python3
import json, os, sys

path = os.environ["FAKE_NM"]
nm = json.load(open(path))
with open(os.environ["FAKE_NM_LOG"], "a") as log:
    log.write(" ".join(sys.argv[1:]) + "\n")

opts, args, argv = {}, [], sys.argv[1:]
while argv:
    a = argv.pop(0)
    if a in ("-t", "-s"):
        opts[a] = True
    elif a in ("-f", "-g", "-e", "--wait"):
        opts[a] = argv.pop(0)
    else:
        args.append(a)
fields = (opts.get("-f") or opts.get("-g") or "").split(",")

def esc(v):
    return str(v).replace("\\", "\\\\").replace(":", "\\:")

def profile(uuid):
    for p in nm["profiles"]:
        if p["uuid"] == uuid:
            return p
    sys.exit(10)

if args == ["networking"]:
    print(nm.get("networking", "enabled"))
elif args == ["radio", "wifi"]:
    print(nm.get("radio", "enabled"))
elif args == ["device"]:
    for name, d in nm["devices"].items():
        print(f"{name}:{d['type']}")
elif args[:2] == ["device", "show"]:
    d = nm["devices"][args[2]]
    values = {"GENERAL.STATE": f"{d['state']} (state)", "GENERAL.REASON": f"{d.get('reason', 0)} (reason)",
              "GENERAL.AUTOCONNECT": d.get("autoconnect", "yes"), "GENERAL.CON-UUID": d.get("con", "")}
    for f in fields:
        print(f"{f}:{values[f]}")
elif args[:3] == ["device", "wifi", "list"]:
    for ssid in nm.get("scan", {}).get(args[args.index("ifname") + 1], []):
        print(ssid)
elif args == ["connection", "show"]:
    for p in nm["profiles"]:
        row = {"TYPE": p.get("type", "802-11-wireless"), "UUID": p["uuid"],
               "AUTOCONNECT": p.get("autoconnect", "yes"), "AUTOCONNECT-PRIORITY": p.get("priority", 0),
               "TIMESTAMP": p.get("timestamp", 0), "ACTIVE": p.get("active", "no"),
               "FILENAME": p.get("file", "")}
        print(":".join(esc(row[f]) for f in fields))
elif args[:3] == ["connection", "show", "uuid"]:
    p = profile(args[3])
    if "-g" in opts:                      # the password only
        if "-s" in opts and p.get("psk"):
            print(p["psk"])
        sys.exit(0)
    values = {"connection.id": p.get("id", "x"), "connection.autoconnect": p.get("autoconnect", "yes"),
              "connection.interface-name": p.get("iface", ""),
              "connection.autoconnect-retries": p.get("retries", -1),
              "802-11-wireless.mode": p.get("mode", "infrastructure"),
              "802-11-wireless.ssid": p.get("ssid", "HomeNet"),
              "802-11-wireless.hidden": p.get("hidden", "no")}
    if p.get("key_mgmt"):
        values["802-11-wireless-security.key-mgmt"] = p["key_mgmt"]
        values["802-11-wireless-security.psk-flags"] = p.get("psk_flags", 0)
    for f in fields:
        if f in values:
            print(f"{f}:{values[f]}")
elif args[:3] == ["connection", "modify", "uuid"]:
    p = profile(args[3])
    if args[4] == "connection.autoconnect-retries":
        p["retries"] = int(args[5])
    json.dump(nm, open(path, "w"))
elif args[:3] == ["connection", "up", "uuid"]:
    sys.exit(nm.get("up_rc", 0))
else:
    sys.exit(2)
'''


def _profile(**kw):
    """Imager's profile: WPA-PSK, password stored in the file."""
    p = {"uuid": "u-pre", "id": "preconfigured", "autoconnect": "yes", "priority": 0,
         "timestamp": 0, "active": "no", "file": NM_DIR + "preconfigured.nmconnection",
         "mode": "infrastructure", "ssid": "HomeNet", "hidden": "no", "key_mgmt": "wpa-psk",
         "psk_flags": 0, "psk": "a" * 64, "retries": 0}
    p.update(kw)
    return p


def _wlan(state, **kw):
    d = {"type": "wifi", "state": state, "reason": 0, "autoconnect": "yes", "con": ""}
    d.update(kw)
    return d


class Rig:
    def __init__(self, tmp_path):
        self.tmp = tmp_path
        stubs = tmp_path / "stubs"
        stubs.mkdir()
        nmcli = stubs / "nmcli"
        nmcli.write_text(_FAKE_NMCLI)
        nmcli.chmod(nmcli.stat().st_mode | stat.S_IXUSR)
        self.path = f"{stubs}:{os.environ['PATH']}"
        self.scenario = tmp_path / "nm.json"
        self.calls_file = tmp_path / "calls.log"
        self.log_file = tmp_path / "journal.log"
        self.state_dir = tmp_path / "run"
        self.now = 1_000_000

    def set(self, devices, profiles, scan=None, **extra):
        nm = {"devices": devices, "profiles": profiles, "scan": scan or {"wlan0": ["HomeNet"]}}
        nm.update(extra)
        self.scenario.write_text(json.dumps(nm))

    def nm(self):
        return json.loads(self.scenario.read_text())

    def run(self, after=60):
        """One timer run, AFTER seconds after the previous one."""
        self.now += after
        if self.calls_file.exists():
            self.calls_file.unlink()
        env = dict(os.environ, PATH=self.path, FAKE_NM=str(self.scenario),
                   FAKE_NM_LOG=str(self.calls_file), RQ_WIFI_STATE_DIR=str(self.state_dir),
                   RQ_WIFI_LOG=str(self.log_file), RQ_WIFI_NOW=str(self.now))
        proc = subprocess.run(["bash", _SCRIPT], env=env, capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        return self

    @property
    def calls(self):
        return self.calls_file.read_text().splitlines() if self.calls_file.exists() else []

    @property
    def ups(self):
        return [c for c in self.calls if c.startswith("--wait 60 connection up")]

    @property
    def modifies(self):
        return [c for c in self.calls if c.startswith("connection modify")]

    @property
    def journal(self):
        return self.log_file.read_text().splitlines() if self.log_file.exists() else []


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path)


# --- the cases of the rig ----------------------------------------------------

def test_connected_wifi_is_left_alone(rig):
    rig.set({"wlan0": _wlan(100, con="u-pre")}, [_profile(active="yes")])
    for _ in range(3):
        rig.run()
        assert rig.ups == [] and rig.modifies == []
    assert rig.journal == []


def test_need_auth_with_a_stored_password_is_brought_up_once(rig):
    # the rig: stuck in need-auth on Imager's profile, nobody answers
    rig.set({"wlan0": _wlan(60, con="u-pre")}, [_profile(active="yes")])
    rig.run()
    assert rig.ups == []                        # first sighting: only noted
    rig.run()
    assert rig.ups == ["--wait 60 connection up uuid u-pre ifname wlan0"]
    assert len(rig.journal) == 1
    assert "wlan0" in rig.journal[0] and "'preconfigured'" in rig.journal[0]
    assert "try 1" in rig.journal[0] and "connected" in rig.journal[0]


def test_no_stored_password_is_left_alone(rig):
    # agent-owned (desktop keyring), asked every time, or no password at all
    for prof in (_profile(psk_flags=1, psk=""), _profile(psk_flags=2, psk=""),
                 _profile(psk=""), _profile(key_mgmt="", psk="")):
        rig.set({"wlan0": _wlan(60, con="u-pre")}, [prof])
        rig.run().run()
        assert rig.ups == [], prof
    assert rig.journal == []


def test_wifi_switched_off_is_left_alone(rig):
    rig.set({"wlan0": _wlan(20)}, [_profile(retries=-1)], radio="disabled")
    rig.run().run()
    assert rig.ups == [] and rig.modifies == []
    assert rig.calls == ["networking", "radio wifi"]
    rig.set({"wlan0": _wlan(20)}, [_profile(retries=-1)], networking="disabled")
    rig.run()
    assert rig.calls == ["networking"]


def test_profiles_with_autoconnect_no_are_left_alone(rig):
    rig.set({"wlan0": _wlan(30)}, [_profile(autoconnect="no", retries=-1)])
    rig.run().run().run()
    assert rig.ups == [] and rig.modifies == []
    # also when it is the one stuck in need-auth (the user started it)
    rig.set({"wlan0": _wlan(60, con="u-pre")}, [_profile(autoconnect="no", active="yes")])
    rig.run().run()
    assert rig.ups == []
    assert rig.journal == []


# --- respecting the user -----------------------------------------------------

def test_a_wifi_the_user_disconnected_stays_disconnected(rig):
    # nmcli connection down / the desktop: reason 39; nmcli device disconnect:
    # the device's autoconnect is off
    for dev in (_wlan(30, reason=39), _wlan(30, autoconnect="no"), _wlan(60, con="u-pre", autoconnect="no")):
        rig.set({"wlan0": dev}, [_profile()])
        rig.run().run()
        assert rig.ups == [], dev


def test_need_auth_on_a_profile_without_password_does_not_switch_profiles(rig):
    # someone may be typing the password of "Cafe" into a dialog
    cafe = _profile(uuid="u-cafe", id="Cafe", ssid="Cafe", psk_flags=1, psk="", active="yes")
    rig.set({"wlan0": _wlan(60, con="u-cafe")}, [cafe, _profile()], scan={"wlan0": ["Cafe", "HomeNet"]})
    rig.run().run().run()
    assert rig.ups == []


def test_busy_unavailable_and_unmanaged_devices_are_left_alone(rig):
    for state in (10, 20, 50, 110):           # unmanaged, unavailable, config, deactivating
        rig.set({"wlan0": _wlan(state, con="u-pre")}, [_profile()])
        rig.run().run()
        assert rig.ups == [], state


# --- disconnected after a failure --------------------------------------------

def test_disconnected_after_a_failure_brings_up_a_profile_in_range(rig):
    # after "no secrets" NetworkManager blocks the profile; the device ends
    # up disconnected (reason 0)
    home = _profile(timestamp=100)
    office = _profile(uuid="u-off", id="Office", ssid="Office", timestamp=200)
    hotspot = _profile(uuid="u-ap", id="Hotspot", ssid="RasQ-AP", mode="ap", priority=10)
    rig.set({"wlan0": _wlan(30), "eth0": {"type": "ethernet", "state": 100}},
            [home, office, hotspot], scan={"wlan0": ["HomeNet", "Neighbour"]})
    rig.run().run()
    # Office is the more recent one, but not in range; the hotspot is no client
    assert rig.ups == ["--wait 60 connection up uuid u-pre ifname wlan0"]
    assert "disconnected after a failure" in rig.journal[0]


def test_disconnected_with_nothing_in_range_stays_quiet(rig):
    rig.set({"wlan0": _wlan(30)}, [_profile()], scan={"wlan0": ["Neighbour"]})
    rig.run().run().run()
    assert rig.ups == [] and rig.journal == []


def test_hidden_network_is_tried_without_a_scan(rig):
    rig.set({"wlan0": _wlan(120)}, [_profile(hidden="yes")], scan={"wlan0": []})
    rig.run().run()
    assert len(rig.ups) == 1


def test_profile_bound_to_another_device_or_active_elsewhere_is_skipped(rig):
    rig.set({"wlan0": _wlan(30)}, [_profile(iface="wlan1"), _profile(uuid="u-2", active="yes")])
    rig.run().run()
    assert rig.ups == []


# --- back off ----------------------------------------------------------------

def test_tries_back_off_and_reset_once_connected(rig):
    rig.set({"wlan0": _wlan(60, con="u-pre")}, [_profile(active="yes")], up_rc=4)
    rig.run(); rig.run()
    assert len(rig.ups) == 1                    # try 1
    # then 2, 4, 8, 16 and 30 minutes after the previous try: a check a
    # minute early does nothing, the one on time tries again
    for gap in (2, 4, 8, 16, 30, 30):
        rig.run(60 * (gap - 1))
        assert rig.ups == [], gap
        rig.run(60)
        assert len(rig.ups) == 1, gap
    assert "try 7" in rig.journal[-1] and "trying again later" in rig.journal[-1]
    assert len(rig.journal) == 7
    # connected: the count starts again
    nm = rig.nm()
    nm["devices"]["wlan0"]["state"] = 100
    rig.scenario.write_text(json.dumps(nm))
    rig.run()
    assert not (rig.state_dir / "wifi-watchdog.wlan0").exists()


# --- part 1: retry forever ---------------------------------------------------

def test_stored_password_profiles_retry_forever(rig):
    imager = _profile(retries=-1)
    agent = _profile(uuid="u-agent", id="Keyring", psk_flags=1, psk="", retries=-1)
    own = _profile(uuid="u-own", id="Own choice", retries=3)
    runtime = _profile(uuid="u-run", id="Runtime", retries=-1,
                       file="/run/NetworkManager/system-connections/x.nmconnection")
    rig.set({"wlan0": _wlan(100, con="u-pre")}, [imager, agent, own, runtime])
    rig.run()
    assert rig.modifies == ["connection modify uuid u-pre connection.autoconnect-retries 0"]
    assert rig.journal == ["Wi-Fi profile 'preconfigured' has a stored password: "
                           "it now retries forever (connection.autoconnect-retries 0)"]
    rig.run()
    assert rig.modifies == []                   # done once
    assert [p["retries"] for p in rig.nm()["profiles"]] == [0, -1, 3, -1]


def test_a_colon_in_the_file_name_is_no_problem(rig):
    rig.set({"wlan0": _wlan(100)}, [_profile(retries=-1, file=NM_DIR + "Home:5G.nmconnection")])
    rig.run()
    assert len(rig.modifies) == 1


# --- the units ---------------------------------------------------------------

def test_timer_is_enabled_and_runs_every_minute():
    timer = open(os.path.join(_UNITS, "rasqberry-wifi-watchdog.timer")).read()
    service = open(os.path.join(_UNITS, "rasqberry-wifi-watchdog.service")).read()
    assert "OnBootSec=90s" in timer and "OnUnitActiveSec=1min" in timer
    assert "ExecStart=/usr/bin/rq_wifi_watchdog.sh" in service
    assert "LogLevelMax=notice" in service
    units = [l.split("#", 1)[0].strip() for l in open(os.path.join(_ROOT, "RQB2-system", "enabled-units.txt"))]
    assert "rasqberry-wifi-watchdog.timer" in units
    assert os.access(_SCRIPT, os.X_OK)
