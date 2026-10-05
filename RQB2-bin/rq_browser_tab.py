#!/usr/bin/env python3
"""
RasQberry: the browser tab of a demo, through Chromium's DevTools port.

The desktop Chromium listens for the DevTools protocol on 127.0.0.1 only
(/etc/chromium.d/rasqberry). A demo served on this Pi opens in a window of
its own (rq_open_browser in rq_common.sh), and this helper looks after it:

- watch: finds the demo's tab, makes its window maximised (or full screen,
  Qoffee-Maker), and closes the tab once the demo's server has stopped. The
  tab used to stay behind with "Dead kernel" or "Connection failed", and
  closing it asked "Leave site?" (#9, #15). A tab closed through the
  protocol does not ask.
- close: closes a demo's tabs at once, before its server stops.
- save: saves the open notebooks of a JupyterLab tab before it stops (#12).

Usage:
    rq_browser_tab.py ids                      ids of the open tabs (comma-separated)
    rq_browser_tab.py watch [--before IDS] [--window-state STATE] URL
    rq_browser_tab.py close URL                close the tabs on URL's server
    rq_browser_tab.py save URL                 save the notebooks open there

Exit status of save: 0 saved (or nothing open), 1 a tab could not save,
2 no DevTools port (nothing known). Without the port everything else does
nothing. Python standard library only.
"""

import argparse
import base64
import json
import logging
import os
import socket
import struct
import sys
import time
import urllib.parse
import urllib.request

logging.basicConfig(level=logging.WARNING, format="rq_browser_tab: %(message)s")
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("RQ_BROWSER_CDP_PORT", "9222"))
# How long watch looks for the new tab (a Chromium it had to start first)
FIND_WAIT = float(os.environ.get("RQ_BROWSER_FIND_WAIT", "30"))
# Seconds between two looks at the demo's server
POLL = float(os.environ.get("RQ_BROWSER_POLL", "1"))

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


# --------------------------------------------------------------------------
# DevTools HTTP endpoints
# --------------------------------------------------------------------------
def origin(url):
    """
    Return scheme://host:port of a URL; localhost counts as 127.0.0.1.

    Args:
        url (str): Address.

    Returns:
        str: The origin, or "" for an address without a host.
    """
    try:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https"):
            return ""
        host = parts.hostname or ""
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        return ""
    if not host:
        return ""
    if host == "localhost":
        host = "127.0.0.1"
    return "%s://%s:%d" % (parts.scheme, host, port)


def cdp(path, method="GET", timeout=2.0):
    """
    Call a DevTools HTTP endpoint.

    Args:
        path (str): e.g. /json/list
        method (str): HTTP method (/json/new needs PUT).
        timeout (float): Seconds.

    Returns:
        str: The body.
    """
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (PORT, path), method=method)
    with _OPENER.open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def pages(timeout=2.0):
    """
    List the open tabs.

    Args:
        timeout (float): Seconds.

    Returns:
        list: Page targets (dicts with id, url, webSocketDebuggerUrl), or None
        without the DevTools port.
    """
    try:
        return [t for t in json.loads(cdp("/json/list", timeout=timeout)) if t.get("type") == "page"]
    except (OSError, ValueError):
        return None


def tabs_on(org, tabs):
    """The tabs whose address is on the origin ORG."""
    return [t for t in tabs or [] if origin(t.get("url", "")) == org]


def close(url):
    """
    Close every tab on URL's server, without the "Leave site?" question.

    Args:
        url (str): An address on the demo's server.

    Returns:
        int: Number of tabs closed.
    """
    org = origin(url)
    closed = 0
    for tab in tabs_on(org, pages()):
        try:
            cdp("/json/close/%s" % tab["id"])
            closed += 1
        except OSError as exc:
            logger.debug("close %s: %s", tab.get("id"), exc)
    return closed


def server_up(org, timeout=1.0):
    """
    Tell whether the demo's server still accepts connections.

    Args:
        org (str): Its origin.
        timeout (float): Seconds; a server too busy to answer counts as up.

    Returns:
        bool: False only when the connection is refused (nothing listens).
    """
    parts = urllib.parse.urlsplit(org)
    try:
        socket.create_connection((parts.hostname, parts.port), timeout=timeout).close()
        return True
    except ConnectionRefusedError:
        return False
    except OSError:
        return True


# --------------------------------------------------------------------------
# A small WebSocket client (the protocol's commands), standard library only
# --------------------------------------------------------------------------
class DevTools:
    """One WebSocket connection to a DevTools endpoint (no Origin header)."""

    def __init__(self, ws_url, timeout=10.0):
        parts = urllib.parse.urlsplit(ws_url)
        self.sock = socket.create_connection((parts.hostname, parts.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        request = ("GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\n"
                   "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
                   "Sec-WebSocket-Version: 13\r\n\r\n"
                   % (parts.path or "/", parts.hostname, parts.port, key))
        self.sock.sendall(request.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise OSError("DevTools closed the connection")
            head += chunk
        status = head.split(b"\r\n", 1)[0]
        if b" 101 " not in status + b" ":
            raise OSError("DevTools refused the connection: %s" % status.decode("latin-1"))
        self.buf = head.split(b"\r\n\r\n", 1)[1]
        self.next_id = 0

    def close(self):
        """Close the connection."""
        try:
            self.sock.close()
        except OSError:
            pass

    def _recv(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise OSError("DevTools closed the connection")
            self.buf += chunk
        data, self.buf = self.buf[:n], self.buf[n:]
        return data

    def _send_frame(self, opcode, payload):
        mask = os.urandom(4)
        n = len(payload)
        if n < 126:
            header = struct.pack("!BB", 0x80 | opcode, 0x80 | n)
        elif n < 65536:
            header = struct.pack("!BBH", 0x80 | opcode, 0x80 | 126, n)
        else:
            header = struct.pack("!BBQ", 0x80 | opcode, 0x80 | 127, n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(header + mask + masked)

    def _message(self):
        parts = []
        while True:
            b1, b2 = self._recv(2)
            opcode, n = b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._recv(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._recv(8))[0]
            mask = self._recv(4) if b2 & 0x80 else None
            data = self._recv(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 0x8:
                raise OSError("DevTools closed the connection")
            if opcode == 0x9:
                self._send_frame(0xA, data)
                continue
            if opcode in (0x1, 0x2, 0x0):
                parts.append(data)
                if b1 & 0x80:
                    return b"".join(parts).decode("utf-8", "replace")

    def call(self, method, params=None):
        """
        Send one command and wait for its answer (events in between are skipped).

        Args:
            method (str): e.g. Browser.getWindowForTarget
            params (dict): Its parameters.

        Returns:
            dict: The result.

        Raises:
            RuntimeError: The browser answered with an error.
        """
        self.next_id += 1
        self._send_frame(0x1, json.dumps({"id": self.next_id, "method": method,
                                          "params": params or {}}).encode())
        while True:
            msg = json.loads(self._message())
            if msg.get("id") == self.next_id:
                if "error" in msg:
                    raise RuntimeError(msg["error"].get("message", "error"))
                return msg.get("result", {})


def browser_devtools(timeout=10.0):
    """Open the browser-wide DevTools connection."""
    version = json.loads(cdp("/json/version", timeout=timeout))
    return DevTools(version["webSocketDebuggerUrl"], timeout=timeout)


def set_window_state(target_id, state):
    """
    Maximise a tab's window, or make it full screen.

    Args:
        target_id (str): The tab.
        state (str): "maximized" or "fullscreen".

    Returns:
        bool: True if the browser did it.
    """
    try:
        dev = browser_devtools()
    except (OSError, ValueError, KeyError) as exc:
        logger.debug("window state: %s", exc)
        return False
    try:
        window = dev.call("Browser.getWindowForTarget", {"targetId": target_id})["windowId"]
        try:
            dev.call("Browser.setWindowBounds", {"windowId": window, "bounds": {"windowState": state}})
        except RuntimeError:
            # some changes go through the normal state first
            dev.call("Browser.setWindowBounds", {"windowId": window, "bounds": {"windowState": "normal"}})
            dev.call("Browser.setWindowBounds", {"windowId": window, "bounds": {"windowState": state}})
        return True
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        logger.debug("window state: %s", exc)
        return False
    finally:
        dev.close()


# JupyterLab (window.jupyterapp, LabApp.expose_app_in_browser) or the classic
# notebook (window.Jupyter): save what is open and changed
_SAVE_JS = """(async () => {
  const app = window.jupyterapp;
  if (app && app.commands && app.commands.hasCommand('docmanager:save-all')) {
    await app.commands.execute('docmanager:save-all');
    return 'saved';
  }
  const nb = window.Jupyter && window.Jupyter.notebook;
  if (nb && nb.save_notebook) {
    if (nb.dirty) { await nb.save_notebook(); }
    return 'saved';
  }
  return 'no-app';
})()"""


def save(url, timeout=15.0):
    """
    Save the notebooks open in the tabs on URL's server.

    Args:
        url (str): An address on the Jupyter server.
        timeout (float): Seconds per tab.

    Returns:
        int: 0 saved (or nothing open there), 1 a tab could not save,
        2 no DevTools port.
    """
    tabs = pages()
    if tabs is None:
        return 2
    status = 0
    for tab in tabs_on(origin(url), tabs):
        ws_url = tab.get("webSocketDebuggerUrl")
        if not ws_url:     # another DevTools client holds it
            status = 1
            continue
        try:
            dev = DevTools(ws_url, timeout=timeout)
        except OSError as exc:
            logger.debug("save %s: %s", tab.get("id"), exc)
            status = 1
            continue
        try:
            res = dev.call("Runtime.evaluate", {"expression": _SAVE_JS, "awaitPromise": True,
                                                "returnByValue": True})
            if res.get("exceptionDetails") or res.get("result", {}).get("value") != "saved":
                status = 1
        except (OSError, ValueError, RuntimeError) as exc:
            logger.debug("save %s: %s", tab.get("id"), exc)
            status = 1
        finally:
            dev.close()
    return status


# --------------------------------------------------------------------------
# watch
# --------------------------------------------------------------------------
def find_new_tab(org, before, wait=None):
    """
    Wait for the tab a demo has just opened on ORG.

    Args:
        org (str): The demo's origin.
        before (set): Ids of the tabs open before it.
        wait (float): Seconds (default FIND_WAIT).

    Returns:
        dict: The tab, or None.
    """
    end = time.monotonic() + (FIND_WAIT if wait is None else wait)
    while True:
        new = [t for t in tabs_on(org, pages()) if t.get("id") not in before]
        if new:
            return new[0]
        if time.monotonic() >= end:
            return None
        time.sleep(0.5)


def watch(url, before=(), state=""):
    """
    Look after a demo's new tab until the demo's server has stopped.

    Args:
        url (str): The address the demo opened.
        before (iterable): Ids of the tabs open before.
        state (str): Window state to set ("maximized", "fullscreen", "").

    Returns:
        int: 0 (also when there is nothing to do).
    """
    org = origin(url)
    tab = find_new_tab(org, set(before))
    if tab is None:
        return 0
    if state:
        set_window_state(tab["id"], state)
    missed = no_browser = 0
    # A server that has not answered yet is still starting (a busy Pi 4 can
    # open the port after the browser): only one that was up can have stopped
    seen_up = False
    while True:
        time.sleep(POLL)
        tabs = pages()
        if tabs is None:
            no_browser += 1
            if no_browser >= 5:       # the browser has ended
                return 0
            continue
        no_browser = 0
        if not tabs_on(org, tabs):    # closed, or gone elsewhere
            return 0
        if server_up(org):
            seen_up = True
            missed = 0
            continue
        if not seen_up:
            continue
        missed += 1
        if missed >= 2:               # stopped: no dead tab left behind
            close(url)
            return 0


def main(argv=None):
    """
    Run one subcommand.

    Args:
        argv (list): Command-line arguments.

    Returns:
        int: Exit status.
    """
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ids")
    w = sub.add_parser("watch")
    w.add_argument("--before", default="")
    w.add_argument("--window-state", default="", choices=["", "maximized", "fullscreen"])
    w.add_argument("url")
    for name in ("close", "save"):
        sub.add_parser(name).add_argument("url")
    args = ap.parse_args(argv)
    if args.cmd == "ids":
        tabs = pages(timeout=1.0)
        print(",".join(t["id"] for t in tabs or []))
        return 0
    if args.cmd == "watch":
        return watch(args.url, [i for i in args.before.split(",") if i], args.window_state)
    if args.cmd == "close":
        close(args.url)
        return 0
    return save(args.url)


if __name__ == "__main__":
    sys.exit(main())
