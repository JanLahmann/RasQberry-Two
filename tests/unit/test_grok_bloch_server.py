"""
The local Grok Bloch server (rq_grok_bloch.sh) answers while a browser holds
an idle connection open.

The rig test of 2026-10-04 timed out on it in one run of three (http=000)
while the page worked: the server was single-threaded, and a connection
without a request - Chromium opens spare ones - kept it waiting.
"""

import http.client
import os
import re
import socket
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_LAUNCHER = os.path.join(_HERE, "..", "..", "RQB2-bin", "rq_grok_bloch.sh")


def _server_code():
    text = open(_LAUNCHER, encoding="utf-8").read()
    return re.search(r"cat > /tmp/grok_server\.py << 'EOF'\n(.*?)\nEOF\n", text, re.S).group(1)


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_server_keeps_its_bind_address():
    # every interface, as before (the browser on the Pi uses localhost)
    assert 'ReusableTCPServer(("", port), QuietHTTPRequestHandler)' in _server_code()


def test_server_answers_while_a_connection_is_idle(tmp_path):
    (tmp_path / "index.html").write_text("<html>bloch</html>")
    server = tmp_path / "grok_server.py"
    # bound to 127.0.0.1 here only, so a developer machine's firewall stays quiet
    server.write_text(_server_code().replace('("", port)', '("127.0.0.1", port)'))
    port = _free_port()
    proc = subprocess.Popen([sys.executable, str(server), str(port)], cwd=tmp_path,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    idle = []
    try:
        end = time.time() + 10
        while True:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                assert time.time() < end, "the server did not start"
                time.sleep(0.1)
        # connections without a request, accepted before the real one
        idle = [socket.create_connection(("127.0.0.1", port)) for _ in range(2)]
        time.sleep(0.3)
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/index.html")
        r = conn.getresponse()
        assert r.status == 200
        assert b"bloch" in r.read()
        conn.close()
    finally:
        for s in idle:
            s.close()
        proc.terminate()
        proc.wait(timeout=10)


def test_over_ssh_it_prints_a_tunnel_instead_of_refusing(tmp_path):
    # #17/#31: over SSH it said "needs a screen", although it is a web page
    # the notebook demos offer through ssh -L
    import json
    import shutil
    import stat
    if shutil.which("bash") is None:
        return
    root = os.path.join(_HERE, "..", "..")
    manifest = json.load(open(os.path.join(root, "RQB2-config", "demo-manifests", "rq_demo_grok-bloch.json")))
    assert manifest["needs_hw"]["display"] == "optional"
    web = [v for v in manifest["variants"] if v["id"] == "web"][0]
    assert web["needs_hw"]["display"] == "required"        # the online page: a browser here
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    # the server: alive long enough for the start check, then gone
    py = stubs / "python3"
    py.write_text("#!/bin/sh\nsleep 3\n")
    py.chmod(py.stat().st_mode | stat.S_IXUSR)
    host = stubs / "hostname"
    host.write_text("#!/bin/sh\necho rasqberry\n")
    host.chmod(host.stat().st_mode | stat.S_IXUSR)
    home = tmp_path / "home"
    (home / "RasQberry-Two" / "demos" / "grok-bloch").mkdir(parents=True)
    (home / "RasQberry-Two" / "demos" / "grok-bloch" / "index.html").write_text("bloch")
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(f'USER_HOME="{home}"\nREPO=RasQberry-Two\nMARKER_GROK_BLOCH=index.html\n')
    env = {"PATH": f"{stubs}:{os.environ['PATH']}", "HOME": str(home), "USER": "rasqberry",
           "RQ_CONFIG_FILE": str(env_config)}
    log = "/tmp/grok_server.log"            # the launcher's own (it writes there on the Pi)
    had_log = os.path.exists(log)
    try:
        proc = subprocess.run(["bash", _LAUNCHER], capture_output=True, text=True, env=env, timeout=60,
                              stdin=subprocess.DEVNULL)
    finally:
        if not had_log and os.path.exists(log):
            os.remove(log)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "needs a screen" not in proc.stdout + proc.stderr
    assert re.search(r"ssh -N -L (80\d\d):127\.0\.0\.1:\1 rasqberry@rasqberry\.local", proc.stdout), proc.stdout
    assert "http://localhost:80" in proc.stdout
