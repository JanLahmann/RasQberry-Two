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
