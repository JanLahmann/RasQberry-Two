"""
Feedback batch C3 (2026-10-03):

- item 36: "maturity": "beta" in manifests, variants and the catalogue gives a
  "(beta)" tag in the RasQberry menu and the desktop tooltip, and a feedback
  invitation when the demo starts;
- item 8: the Applications menu - the raspi-config icon named for what it
  opens, one Bloch sphere entry, one name per demo;
- item 11: the Fun with Quantum icon offers every variant, website bundle pin;
- item 29: the Bloch sphere tips and explanation come from our patch on the
  pinned upstream.
"""

import json
import os
import re
import shutil
import subprocess

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_MANIFESTS = os.path.join(_CFG, "demo-manifests")
_BOOKMARKS = os.path.join(_CFG, "desktop-bookmarks")
_COMMON = os.path.join(_BIN, "rq_common.sh")

needs_bash = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required")


def _manifest(demo_id):
    with open(os.path.join(_MANIFESTS, f"rq_demo_{demo_id}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _desktop(name):
    entry = {}
    with open(os.path.join(_BOOKMARKS, name), encoding="utf-8") as fh:
        for line in fh:
            if "=" in line and not line.startswith("#"):
                key, value = line.rstrip("\n").split("=", 1)
                entry.setdefault(key, value)
    return entry


def _bash(script, tmp_path, *args):
    env = dict(os.environ, USER_HOME=str(tmp_path / "home"),
               RQ_CONFIG_FILE=str(tmp_path / "no-such-config.sh"))
    return subprocess.run(["bash", "-c", script, "x", *args], capture_output=True,
                          text=True, env=env)


# --- item 36: beta ---------------------------------------------------------------

def test_the_new_demos_are_beta():
    assert _manifest("doqumentation")["maturity"] == "beta"
    assert _manifest("qiskit-tutorials")["maturity"] == "beta"
    fwq = {v["id"]: v.get("maturity") for v in _manifest("fun-with-quantum")["variants"]}
    assert fwq["website"] == fwq["family"] == "beta" and fwq["coin-game"] is None
    registry = json.load(open(os.path.join(_CFG, "known-demos.json")))["demos"]
    beta = {d["id"] for d in registry if d.get("maturity") == "beta"}
    # the SAP demos are SAP's to call beta: we take them as they are (Jan)
    assert "racetraq" in beta and not beta & {"sap-quantum-learning", "sap-quantum-led"}


@needs_bash
def test_maturity_lookup_and_the_catalogue_fallback(tmp_path):
    # a catalogue demo installed before it was marked: its manifest has no field;
    # and one installed under its earlier name (racetraQ "replaces" traqmania)
    user = tmp_path / "home" / ".local" / "config" / "demo-manifests"
    user.mkdir(parents=True)
    (user / "rq_demo_racetraq.json").write_text(json.dumps({"id": "racetraq", "name": "racetraQ"}))
    (user / "rq_demo_traqmania.json").write_text(json.dumps({"id": "traqmania", "name": "traQmania"}))
    proc = _bash(f'. "{_COMMON}"; '
                 'echo "a=$(rq_demo_maturity doqumentation)"; '
                 'echo "b=$(rq_demo_maturity racetraq)"; '
                 'echo "f=$(rq_demo_maturity traqmania)"; '
                 'echo "c=$(rq_demo_maturity fun-with-quantum "" website)"; '
                 'echo "d=$(rq_demo_maturity fun-with-quantum "" coin-game)"; '
                 'echo "e=$(rq_demo_maturity quantum-lights-out)"; '
                 'rq_beta_notice doqumentation', tmp_path)
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "a=beta\nb=beta\nf=beta\nc=beta\nd=\ne=\n" in out
    assert "This demo is new - please try it and tell us what works and what doesn't." in out
    assert "issues/new?template=demo-feedback.yml&demo=doqumentation" in out


@needs_bash
def test_menu_cache_tags_beta_and_hides_menu_show_false(tmp_path):
    cache = tmp_path / "cache.sh"
    env = dict(os.environ, USER_HOME=str(tmp_path / "home"),
               RQ_CONFIG_FILE=str(tmp_path / "no-such-config.sh"))
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_demo_generate_menu.sh"), "--cache",
                           str(cache)], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    text = cache.read_text()
    assert '"doqumentation" "Workshop & Qiskit Server (beta)"' in text
    assert '"qiskit-tutorials" "Qiskit Tutorials on this Pi (beta)"' in text
    assert '"Fun with Quantum website: games in the browser (beta)"' in text
    assert '"coin-game" "Quantum Coin Game"' in text
    # item 8: one Bloch sphere entry, the online version is its variant
    assert '"grok-bloch-web"' not in text.split("dispatch_demo_by_id")[0]
    assert '"grok-bloch") printf' in text and '"web" "Online version' in text


def test_validator_rejects_an_unknown_maturity(tmp_path):
    if shutil.which("jq") is None:
        pytest.skip("jq required")
    m = _manifest("composer")
    m["maturity"] = "alpha"
    bad = tmp_path / "rq_demo_composer.json"
    bad.write_text(json.dumps(m))
    proc = subprocess.run([os.path.join(_BIN, "rq_demo_validate.sh"), str(bad)],
                          capture_output=True, text=True)
    assert proc.returncode != 0 and "Invalid maturity: alpha" in proc.stdout


def test_beta_icons_say_so_in_their_tooltip():
    for name in sorted(os.listdir(_BOOKMARKS)):
        entry = _desktop(name)
        m = re.fullmatch(r"/usr/bin/rq_hold_on_error\.sh /usr/bin/rq_demo_run\.sh ([a-z0-9-]+)",
                         entry.get("Exec", ""))
        if not m:
            continue
        beta = _manifest(m.group(1)).get("maturity") == "beta"
        assert entry["Comment"].startswith("(beta) ") == beta, name


def test_catalogue_picker_and_desktop_entries_show_beta():
    add = open(os.path.join(_BIN, "rq_demo_add_external.sh")).read()
    assert '[ "$(registry_field "$id" "maturity")" = "beta" ]' in add
    entry = open(os.path.join(_BIN, "rq_demo_desktop_entry.sh")).read()
    assert 'description="(beta) $description"' in entry
    run = open(os.path.join(_BIN, "rq_demo_run.sh")).read()
    assert 'rq_beta_notice "$DEMO_ID"' in run


# --- item 8: Applications menu -----------------------------------------------------

def test_raspi_config_icon_says_what_it_opens():
    # the name was the confusing part (Jan): it is raspi-config
    entry = _desktop("rasqberry-menu.desktop")
    assert entry["Name"] == "RasQberry Configuration (raspi-config)"
    assert entry["NoDisplay"] == "false"
    stage = open(os.path.join(_ROOT, "stage-RQB2", "06-desktop-integration", "00-run-chroot.sh")).read()
    assert "|rasqberry-menu|" in stage


def test_one_bloch_sphere_entry():
    assert not os.path.exists(os.path.join(_BOOKMARKS, "grok-bloch-web.desktop"))
    web = _manifest("grok-bloch-web")
    assert web["menu"]["show"] is False and web["desktop"]["show"] is False
    bloch = _manifest("grok-bloch")
    assert bloch["menu"]["variant_menu"] is True
    web_variant = [v for v in bloch["variants"] if v["id"] == "web"][0]
    assert web_variant["install"]["preinstalled"] is True   # nothing to download


def test_an_icon_has_its_demos_name():
    # docs/STYLE.md: a demo has one name, on the icon, in the menu, on the website
    for name in sorted(os.listdir(_BOOKMARKS)):
        entry = _desktop(name)
        m = re.fullmatch(r"/usr/bin/rq_hold_on_error\.sh (?:-t \"[^\"]+\" )?"
                         r"/usr/bin/rq_demo_(?:run|choose)\.sh ([a-z0-9-]+)", entry.get("Exec", ""))
        if m:
            assert entry["Name"] == _manifest(m.group(1))["name"], name
    assert _desktop("led-ibm-demo.desktop")["Name"] == "IBM LED Demo"
    assert _desktop("quantum-mixer.desktop")["Name"] == "Quantum Mixer"


# --- item 11: Fun with Quantum ------------------------------------------------------

def test_fun_with_quantum_icon_offers_every_variant():
    assert _desktop("fun-with-quantum.desktop")["Exec"] == \
        '/usr/bin/rq_hold_on_error.sh -t "Fun with Quantum" /usr/bin/rq_demo_choose.sh fun-with-quantum'
    chooser = open(os.path.join(_BIN, "rq_demo_choose.sh")).read()
    assert '"$SCRIPT_DIR/rq_demo_run.sh" "$DEMO_ID" "$choice"' in chooser


def test_website_bundle_is_the_workshops_page_build():
    inst = _manifest("fun-with-quantum")["install"]
    assert inst["portal_ref"] == "8724eee6286baa4ee31b6b10e2a3e3c772ae8202"
    assert inst["portal_sha256"] == "5106abe9fd53d0ae307109e9a988843bc98a64ca0f7060cdbfd1b803f93480e1"


# --- item 29: Bloch sphere tips --------------------------------------------------------

def test_bloch_tips_come_from_our_patch():
    assert _manifest("grok-bloch")["install"]["patch_file"] == "grok-bloch-help.patch"
    patch = open(os.path.join(_CFG, "demo-patches", "grok-bloch-help.patch")).read()
    assert "+++ b/rasqberry-help.js" in patch and "new file mode" in patch
    assert '+    <script src="rasqberry-help.js"></script>' in patch
    for words in ("What it shows", "Try this", "What to notice", "Explain the Bloch sphere"):
        assert words in patch
    assert "https://quantum.cloud.ibm.com/learning/en/courses/" in patch
