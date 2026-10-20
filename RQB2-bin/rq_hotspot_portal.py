#!/usr/bin/env python3
"""
RasQberry hotspot landing page: what this Pi offers to phones and laptops.

Runs while the Wi-Fi hotspot is on (rasqberry-hotspot-portal.service, started
and stopped by rq_hotspot.sh) at http://10.42.0.1/. It lists every web page a
demo serves on the network right now - found by its listening port, named by
the page's own <title> - so a new demo shows up without a list to keep.

Without internet on the hotspot, DNS answers every name with 10.42.0.1
(rq_hotspot.sh), and the phones' connectivity checks (Apple's
hotspot-detect.html, Android's generate_204, Windows' connecttest.txt) get a
redirect here: the phone opens this page by itself on joining. The page says
whether this Wi-Fi reaches the internet (RQ_HOTSPOT_INTERNET from
rq_hotspot.sh, and a way out of the Pi right now).

Usage: rq_hotspot_portal.py [--address 10.42.0.1] [--port 80]
"""

import argparse
import html
import http.server
import logging
import os
import re
import socket
import ssl
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Ports that are not demos: SSH, rpcbind, DNS, DHCP, VNC, CUPS, this page
SKIP_PORTS = {22, 53, 67, 80, 111, 631, 5353, 5900}
TITLE_RE = re.compile(rb"<title[^>]*>(.*?)</title>", re.I | re.S)


def listening_ports(tcp_files=("/proc/net/tcp", "/proc/net/tcp6")):
    """
    TCP ports listening on every address (or on the hotspot's), not only on
    localhost - the ones a phone can reach.

    Args:
        tcp_files (tuple): the kernel's socket tables

    Returns:
        list: sorted port numbers
    """
    ports = set()
    for path in tcp_files:
        try:
            with open(path) as f:
                next(f)
                for line in f:
                    parts = line.split()
                    local, state = parts[1], parts[3]
                    if state != "0A":           # LISTEN
                        continue
                    addr, port = local.rsplit(":", 1)
                    if set(addr) == {"0"} or addr.endswith("01002A0A"):
                        # any address (0.0.0.0 / ::), or 10.42.0.1
                        ports.add(int(port, 16))
        except (OSError, StopIteration, ValueError, IndexError):
            continue
    return sorted(p for p in ports if p not in SKIP_PORTS)


def page_title(port, timeout=1.5):
    """
    Look at what a port serves: (scheme, title), or None when it is no web page.

    Args:
        port (int): the port on this Pi
        timeout (float): seconds per try

    Returns:
        tuple: ("http" or "https", title or "") or None
    """
    insecure = ssl.create_default_context()
    insecure.check_hostname = False
    insecure.verify_mode = ssl.CERT_NONE
    for scheme in ("http", "https"):
        try:
            req = urllib.request.Request(f"{scheme}://127.0.0.1:{port}/",
                                         headers={"User-Agent": "RasQberry-hotspot"})
            with urllib.request.urlopen(req, timeout=timeout,
                                        context=insecure if scheme == "https" else None) as r:
                body = r.read(65536)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):            # a page with a login is still a page
                return scheme, ""
            continue
        except (OSError, ValueError, ssl.SSLError):
            continue
        m = TITLE_RE.search(body)
        title = html.unescape(m.group(1).decode("utf-8", "replace")).strip() if m else ""
        return scheme, " ".join(title.split())[:80]
    return None


def has_uplink(hotspot_iface="", route_file="/proc/net/route"):
    """
    Does the Pi have a way out: a default route over another interface than
    the hotspot's (a network cable, a USB Wi-Fi adapter)?

    Args:
        hotspot_iface (str): the hotspot's interface (its routes do not count)
        route_file (str): the kernel's IPv4 routing table

    Returns:
        bool: True with such a route
    """
    try:
        with open(route_file) as f:
            next(f)
            for line in f:
                parts = line.split()
                if len(parts) < 8 or parts[0] == hotspot_iface:
                    continue
                # destination and mask 0.0.0.0, flag RTF_UP
                if parts[1] == "00000000" and parts[7] == "00000000" and int(parts[3], 16) & 1:
                    return True
    except (OSError, StopIteration, ValueError):
        return False
    return False


def reaches_internet(env=None, route_file="/proc/net/route"):
    """
    Does this Wi-Fi reach the internet: rq_hotspot.sh shares it (sharing on, a
    way out at the start, the NAT there), and the way out is still there.

    Args:
        env (dict): the environment (default: os.environ)
        route_file (str): the kernel's IPv4 routing table

    Returns:
        bool: True if phones on the hotspot reach the internet
    """
    env = os.environ if env is None else env
    if env.get("RQ_HOTSPOT_INTERNET", "no") != "yes":
        return False
    return has_uplink(env.get("RQ_HOTSPOT_IFACE", ""), route_file)


def offers(address):
    """
    The web pages demos serve right now.

    Returns:
        list: (title, url) pairs
    """
    found = []
    for port in listening_ports():
        seen = page_title(port)
        if seen is None:
            continue
        scheme, title = seen
        found.append((title or f"A demo on port {port}", f"{scheme}://{address}:{port}/"))
    return found


def render(address, ssid, items, internet=False):
    """The landing page (HTML); internet: this Wi-Fi reaches the internet."""
    rows = "\n".join(
        f'<li><a href="{html.escape(url)}">{html.escape(title)}</a>'
        f'<span>{html.escape(url)}</span></li>' for title, url in items)
    if not rows:
        rows = ('<li class="none">No demo is open to phones right now. Start one on the '
                "RasQberry, e.g. Entangible or the LED browser view, then reload this page.</li>")
    if internet:
        note = ("This Wi-Fi also reaches the internet, through the RasQberry; the demos run on the "
                'RasQberry itself. More about RasQberry: <a href="https://rasqberry.org/">rasqberry.org</a>')
    else:
        note = ("This Wi-Fi has no internet; the demos run on the RasQberry itself. "
                "More about RasQberry: rasqberry.org")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RasQberry Two</title>
<style>
:root {{ --bg:#fff; --fg:#161616; --muted:#6f6f6f; --accent:#0f62fe; --line:#e0e0e0; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#161616; --fg:#f4f4f4; --muted:#a8a8a8; --accent:#78a9ff; --line:#393939; }} }}
body {{ margin:0; padding:24px 16px; font:17px/1.45 system-ui, sans-serif; background:var(--bg); color:var(--fg); }}
main {{ max-width:560px; margin:0 auto; }}
h1 {{ font-size:24px; margin:0 0 4px; }}
p {{ color:var(--muted); margin:0 0 20px; }}
p a {{ color:var(--accent); }}
ul {{ list-style:none; padding:0; margin:0 0 24px; }}
li {{ border-top:1px solid var(--line); padding:14px 0; }}
li a {{ color:var(--accent); font-weight:600; text-decoration:none; display:block; }}
li span {{ color:var(--muted); font-size:14px; word-break:break-all; }}
li.none {{ color:var(--muted); }}
.reload {{ display:inline-block; padding:10px 16px; border:1px solid var(--line); border-radius:8px; color:var(--fg); text-decoration:none; }}
</style></head>
<body><main>
<h1>RasQberry Two</h1>
<p>You are on the Wi-Fi {html.escape(ssid) if ssid else "of this RasQberry"}. These demos are open to you:</p>
<ul>
{rows}
</ul>
<a class="reload" href="/">Reload</a>
<p style="margin-top:24px">{note}</p>
</main></body></html>"""


def make_handler(address, ssid):
    """A request handler bound to the hotspot's address and name."""

    class Handler(http.server.BaseHTTPRequestHandler):
        """Every name and path but the page itself leads to the page."""

        server_version = "RasQberry"
        sys_version = ""

        def do_GET(self):
            """Serve the page, or redirect to it (connectivity checks, other names)."""
            host = (self.headers.get("Host") or "").split(":")[0]
            if host != address or self.path.split("?")[0] not in ("/", "/index.html"):
                self.send_response(302)
                self.send_header("Location", f"http://{address}/")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = render(address, ssid, offers(address), reaches_internet()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_HEAD = do_GET

        def log_message(self, fmt, *args):
            """No log line per request (phones ask often)."""

    return Handler


def main():
    """Serve the landing page until stopped."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--address", default="10.42.0.1")
    parser.add_argument("--port", type=int, default=80)
    args = parser.parse_args()
    ssid = os.environ.get("RQ_HOTSPOT_SSID", "")
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    server = http.server.ThreadingHTTPServer((args.address, args.port), make_handler(args.address, ssid))
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    logger.info("Landing page on http://%s:%d/", args.address, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
