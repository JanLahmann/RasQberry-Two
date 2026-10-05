#!/usr/bin/env python3
"""
RasQberry rig test: check that a web or Jupyter demo actually works.

Runs ON the Pi as the desktop user, with the RasQberry venv python (it needs
websocket-client). "Started" and "the URL answers" are not enough: a page can
answer 200 and still be blank, throw on load, or a notebook's kernel can fail.

    webcheck.py browser-debug        restart the desktop Chromium with remote
                                     debugging (127.0.0.1 only), same profile
    webcheck.py browser-restore      restart it as the session starts it
    webcheck.py tabs FILE            save the open tabs' ids
    webcheck.py close-new FILE       close the tabs opened since `tabs FILE`
    webcheck.py check TYPE BEFORE [URL] [HINT-JSON]
                                     check the demo's tab (one opened since
                                     BEFORE, else URL in a new tab)

The desktop's own Chromium is used, so the check sees the very tab the demo
opened (as a person would), and the test can close the demo's tabs afterwards
(a full run used to leave dozens open). Remote debugging only listens on
127.0.0.1 and ends with browser-restore.

check prints one line, "web=<ok|info|warn|fail> <detail>":
  - every page: it loads (load event, title or text, no failed document),
    uncaught JavaScript errors while it loads are reported;
  - web pages: the title has HINT {"title": text}, a key element (HINT
    {"wait": selector}) is there and a key control responds when clicked
    (HINT {"click": selector}; else the first visible button) - the page
    changes or navigates, no new error;
  - Jupyter: the notebook renders, and its first safe code cell runs in a
    fresh kernel of the same server without an error. The kernel gets its own
    session, so nothing is saved into the notebook. Safe: no pip/conda
    installs, and nothing that touches the IBM Quantum account - notebooks
    named like credentials/accounts/tokens and cells that save, delete or read
    accounts, set a token or API key, or touch ~/.qiskit are never run (the
    check once ran 00-Save-Credentials.ipynb and replaced the saved API key).
    No notebook at all, or none with a safe cell: info.
All steps are time-bounded.
"""

import http.cookiejar
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid

import websocket

PORT = int(os.environ.get("RIG_CDP_PORT", "9222"))
CDP = f"http://127.0.0.1:{PORT}"
STATE = os.path.join(os.environ.get("RIG_OUT", "/tmp/rigtest"), "browser.state")
HOMEPAGE = "https://rasqberry.org"
SESSION_ENV = {"DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-0",
               "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}"}
JUPYTER_PATH = re.compile(r"/(lab|tree|notebooks|doc|voila)(/|$|\?)")
# never run code that can change the saved IBM Quantum account
CREDENTIAL_NOTEBOOK = re.compile(r"credential|account|token|api[-_ ]?key|password|secret", re.I)
CREDENTIAL_CODE = re.compile(
    r"save_account|delete_account|saved_accounts|enable_account|token\s*=(?!=)|api[-_]?key"
    r"|QISKIT_IBM_TOKEN|qiskit-ibm\.json|(^|[\s\"'~/(])\.qiskit\b", re.I | re.M)
VERDICTS = ("ok", "info", "warn", "fail")


def worst(*verdicts):
    """The most serious of the verdicts (ok < info < warn < fail)."""
    return max(verdicts, key=VERDICTS.index)


# ----------------------------------------------------------------------------
# Chromium and its tabs
# ----------------------------------------------------------------------------
def cdp_json(path, method="GET", timeout=5):
    """GET/PUT one of Chromium's /json endpoints."""
    req = urllib.request.Request(CDP + path, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode()
    return json.loads(body) if body.strip().startswith(("{", "[")) else body


def cdp_up():
    """True if the debugging endpoint answers."""
    try:
        cdp_json("/json/version", timeout=2)
        return True
    except OSError:
        return False


def pages():
    """The open tabs (page targets)."""
    return [t for t in cdp_json("/json/list") if t.get("type") == "page"]


def chromium_main():
    """PID and command line of the user's main Chromium process, or (None, [])."""
    uid = os.getuid()
    for pid in sorted(int(p) for p in os.listdir("/proc") if p.isdigit()):
        try:
            if os.stat(f"/proc/{pid}").st_uid != uid:
                continue
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                args = [a.decode(errors="replace") for a in fh.read().split(b"\0") if a]
        except OSError:
            continue
        if len(args) == 1:   # Chromium rewrites its title: one space-joined string
            args = args[0].split()
        if args and args[0].endswith("/chromium") and not any(a.startswith("--type=") for a in args):
            return pid, args
    return None, []


def stop_chromium():
    """Close the user's Chromium gracefully (all windows), wait for it to end."""
    if cdp_up():
        try:
            ws = websocket.create_connection(cdp_json("/json/version")["webSocketDebuggerUrl"],
                                             timeout=10, suppress_origin=True)
            ws.send(json.dumps({"id": 1, "method": "Browser.close"}))
            ws.close()
        except (OSError, websocket.WebSocketException, KeyError):
            pass
    pid, _ = chromium_main()
    if pid and not cdp_up():
        os.kill(pid, signal.SIGTERM)
    for _ in range(150):
        if not chromium_main()[0]:
            return
        time.sleep(0.1)
    pid, _ = chromium_main()
    if pid:
        os.kill(pid, signal.SIGKILL)
        time.sleep(1)


def start_chromium(url, debug):
    """Start Chromium as the desktop session does (rq_desktop_session.py)."""
    cmd = ["/usr/bin/chromium"]
    if debug:
        cmd.append(f"--remote-debugging-port={PORT}")
    cmd.append(url)
    subprocess.Popen(cmd, env={**os.environ, **SESSION_ENV}, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def browser_debug():
    """Restart the desktop Chromium with remote debugging; remember its page."""
    if cdp_up():
        print("browser: debugging already on")
        return 0
    pid, args = chromium_main()
    url = next((a for a in reversed(args[1:]) if re.match(r"(https?|file)://", a)), None)
    with open(STATE, "w") as fh:
        json.dump({"was_running": bool(pid), "url": url or HOMEPAGE}, fh)
    if pid:
        stop_chromium()
    start_chromium(url or HOMEPAGE, debug=True)
    for _ in range(60):
        if cdp_up():
            print(f"browser: debugging on 127.0.0.1:{PORT} ({len(pages())} tab)")
            return 0
        time.sleep(0.5)
    print("browser: debugging did not come up")
    return 1


def browser_restore():
    """Restart the desktop Chromium without debugging, on the page it showed."""
    try:
        with open(STATE) as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        state = {"was_running": True, "url": HOMEPAGE}
    stop_chromium()
    if state.get("was_running"):
        start_chromium(state.get("url") or HOMEPAGE, debug=False)
    try:
        os.remove(STATE)
    except OSError:
        pass
    print(f"browser: restored ({'reopened ' + state.get('url', '') if state.get('was_running') else 'closed'})")
    return 0


def save_tabs(path):
    """Write the ids of the open tabs (nothing if debugging is off)."""
    ids = [t["id"] for t in pages()] if cdp_up() else []
    with open(path, "w") as fh:
        json.dump(ids, fh)
    return 0


def new_tabs(before_file):
    """Tabs opened since save_tabs(before_file), newest first."""
    try:
        with open(before_file) as fh:
            before = set(json.load(fh))
    except (OSError, ValueError):
        before = set()
    return [t for t in pages() if t["id"] not in before]


def close_new(before_file):
    """Close the tabs opened since save_tabs(before_file)."""
    if not cdp_up():
        return 0
    fresh = new_tabs(before_file)
    if fresh and len(fresh) == len(pages()):
        # closing the last window would end Chromium (and its debugging)
        cdp_json("/json/new?" + urllib.parse.quote(HOMEPAGE, safe=":/"), method="PUT")
    for t in fresh:
        cdp_json(f"/json/close/{t['id']}")
    print(f"tabs: closed {len(fresh)}")
    return 0


class Tab:
    """A minimal DevTools protocol client for one tab."""

    def __init__(self, target):
        self.ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=20,
                                              suppress_origin=True)
        self.n = 0
        self.events = []

    def call(self, method, timeout=20, **params):
        """Send a command and wait for its answer; keep events."""
        self.n += 1
        my = self.n
        self.ws.send(json.dumps({"id": my, "method": method, "params": params}))
        end = time.time() + timeout
        while time.time() < end:
            self.ws.settimeout(max(0.2, end - time.time()))
            try:
                msg = json.loads(self.ws.recv())
            except websocket.WebSocketTimeoutException:
                break
            if msg.get("id") == my:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error'].get('message')}")
                return msg.get("result", {})
            if "method" in msg:
                self.events.append(msg)
        raise TimeoutError(method)

    def pump(self, seconds):
        """Collect events for a while."""
        end = time.time() + seconds
        while time.time() < end:
            self.ws.settimeout(max(0.1, end - time.time()))
            try:
                msg = json.loads(self.ws.recv())
            except websocket.WebSocketTimeoutException:
                return
            if "method" in msg:
                self.events.append(msg)

    def ev(self, expr, timeout=20):
        """Evaluate JavaScript in the page; return its value."""
        r = self.call("Runtime.evaluate", timeout=timeout, expression=expr,
                      awaitPromise=True, returnByValue=True)
        return r.get("result", {}).get("value")

    def errors(self):
        """Uncaught exceptions seen so far (short texts)."""
        out = []
        for e in self.events:
            if e["method"] == "Runtime.exceptionThrown":
                d = e["params"]["exceptionDetails"]
                out.append((d.get("exception", {}).get("description") or d.get("text", "")).split("\n")[0][:80])
        return out

    def close(self):
        """Disconnect (the tab stays open)."""
        self.ws.close()


# ----------------------------------------------------------------------------
# page checks
# ----------------------------------------------------------------------------
def load_page(tab, deadline):
    """
    Reload the tab with error reporting on and wait until it has rendered.

    Returns:
        dict: title, url, text length, failed documents.
    """
    tab.call("Runtime.enable")
    tab.call("Page.enable")
    tab.call("Network.enable")
    tab.events.clear()
    tab.call("Page.reload")
    loaded = False
    while time.time() < deadline and not loaded:
        tab.pump(0.5)
        loaded = any(e["method"] == "Page.loadEventFired" for e in tab.events)
    # single-page apps draw after the load event
    info = {}
    for _ in range(20):
        info = tab.ev("({title: document.title, url: location.href, ready: document.readyState,"
                      " text: (document.body && document.body.innerText || '').trim().length})") or {}
        if info.get("text") or time.time() > deadline:
            break
        time.sleep(0.5)
    failed_ids = {e["params"]["requestId"] for e in tab.events
                  if e["method"] == "Network.loadingFailed" and e["params"].get("type") == "Document"
                  and not e["params"].get("canceled")}
    info["loaded"] = loaded
    info["failed_document"] = bool(failed_ids)
    return info


def wait_for(tab, selector, deadline):
    """True once `selector` matches something in the page."""
    while time.time() < deadline:
        if tab.ev(f"!!document.querySelector({json.dumps(selector)})"):
            return True
        time.sleep(0.5)
    return False


CONTROL_JS = r"""
(sel => {
  const bad = /delete|remove|shut ?down|log ?out|sign ?out|quit|reset|clear all/i;
  const local = a => !a.href || new URL(a.href, location.href).origin === location.origin;
  const cands = sel ? [...document.querySelectorAll(sel)] :
    [...document.querySelectorAll('button, [role=button], input[type=button], input[type=submit], ' +
      '[role=tab], [role=slider], [role=checkbox], input[type=range], input[type=checkbox], select, a[href]')]
      .filter(el => el.tagName !== 'A' || local(el));
  for (const el of cands) {
    const r = el.getBoundingClientRect();
    const label = (el.innerText || el.value || el.getAttribute('aria-label') || el.title || '').trim();
    if (r.width < 4 || r.height < 4 || r.bottom < 0 || r.top > innerHeight || el.disabled) continue;
    if (!sel && bad.test(label)) continue;
    window.__rigMut = 0;
    new MutationObserver(m => { window.__rigMut += m.length; })
      .observe(document, {subtree: true, childList: true, attributes: true, characterData: true});
    window.__rigUrl = location.href;
    return {x: r.left + r.width / 2, y: r.top + r.height / 2, label: label.slice(0, 30)};
  }
  return null;
})(%s)
"""


def mouse_click(tab, x, y):
    """A real left click (move, press, release) at viewport pixel (x, y)."""
    for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
        tab.call("Input.dispatchMouseEvent", type=kind, x=x, y=y,
                 button="left" if kind != "mouseMoved" else "none", clickCount=1)


def screenshot(tab):
    """The tab's pixels (PNG, base64) - to see a canvas change."""
    return tab.call("Page.captureScreenshot", format="png", timeout=20)["data"]


def click_at(tab, where):
    """
    Click a point of a canvas app (no DOM controls); did the picture change?

    Args:
        where (list): [x, y] viewport pixels; negative counts from the
            right/bottom edge (controls anchored there).

    Returns:
        tuple: (label, responded bool, or None if the page animates anyway)
    """
    w, h = tab.ev("[innerWidth, innerHeight]")
    x = where[0] if where[0] >= 0 else w + where[0]
    y = where[1] if where[1] >= 0 else h + where[1]
    before = screenshot(tab)
    time.sleep(1)
    if screenshot(tab) != before:
        return f"@{x},{y}", None
    mouse_click(tab, x, y)
    tab.pump(2.5)
    return f"@{x},{y}", screenshot(tab) != before


def click_control(tab, selector):
    """
    Click a key control with real mouse events; did the page respond?

    Returns:
        tuple: (label or None, responded bool)
    """
    target = tab.ev(CONTROL_JS % json.dumps(selector))
    if not target:
        return None, False
    mouse_click(tab, target["x"], target["y"])
    tab.pump(1.5)
    try:
        state = tab.ev("({m: window.__rigMut || 0, moved: location.href !== window.__rigUrl})", timeout=5) or {}
    except (RuntimeError, TimeoutError, websocket.WebSocketException):
        state = {"moved": True}   # the page navigated away: that is a response
    return target["label"] or "?", bool(state.get("m") or state.get("moved"))


# ----------------------------------------------------------------------------
# Jupyter
# ----------------------------------------------------------------------------
class Jupyter:
    """REST client for a running Jupyter server (token and/or cookies)."""

    def __init__(self, url, cookies):
        u = urllib.parse.urlsplit(url)
        self.origin = f"{u.scheme}://{u.netloc}"
        m = JUPYTER_PATH.search(u.path)
        self.base = u.path[:m.start() + 1] if m else "/"
        self.token = urllib.parse.parse_qs(u.query).get("token", [""])[0]
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.cookies = dict(cookies)
        self.seen, self.skipped = 0, []   # set by runnable_notebook
        self.notebook = urllib.parse.unquote(u.path[m.end() - 1:].lstrip("/")) if m else ""
        if m and m.group(1) == "lab":   # /lab/tree/x or /lab/workspaces/<name>/tree/x
            self.notebook = re.sub(r"^(workspaces/[^/]+/)?tree/", "", self.notebook)
        if not self.notebook.endswith(".ipynb"):
            self.notebook = ""
        try:   # an _xsrf cookie for POST/DELETE, as the page gets one
            self.request("GET", self.base + "api/status")
            self.request("GET", self.base + ("lab" if not m else m.group(1)), raw=True)
        except OSError:
            pass

    def headers(self):
        """Auth headers: token, the browser's cookies, XSRF."""
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"token {self.token}"
        jar = {c.name: c.value for c in self.jar}
        cookies = {**self.cookies, **jar}
        if cookies:
            h["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
        if cookies.get("_xsrf"):
            h["X-XSRFToken"] = cookies["_xsrf"]
        return h

    def request(self, method, path, body=None, raw=False, timeout=20):
        """One API call; returns parsed JSON (or text with raw)."""
        req = urllib.request.Request(self.origin + path, method=method, headers=self.headers(),
                                     data=json.dumps(body).encode() if body is not None else None)
        with self.opener.open(req, timeout=timeout) as resp:
            data = resp.read().decode(errors="replace")
        return data if raw else (json.loads(data) if data.strip() else {})

    def find_notebook(self):
        """The notebook the demo shows: from its URL, its session, or the folder."""
        if self.notebook:
            return self.notebook
        for s in self.request("GET", self.base + "api/sessions"):
            if s.get("path", "").endswith(".ipynb") and ".rigtest-" not in s["path"]:
                return s["path"]
        for item in self.request("GET", self.base + "api/contents").get("content", []):
            if item.get("type") == "notebook":
                return item["path"]
        return ""

    def contents(self, path):
        """A notebook's JSON."""
        return self.request("GET", self.base + "api/contents/" + urllib.parse.quote(path) + "?content=1")["content"]

    def runnable_notebook(self, shown, deadline, limit=40):
        """
        The notebook whose first safe code cell is run: the one the demo shows,
        or - a welcome page without code, a credentials notebook, or none
        shown - the first one with a safe code cell in its folder (then two
        levels of subfolders). Sets self.seen (notebooks looked at) and
        self.skipped (what was passed over as credential code).

        Returns:
            tuple: (path, notebook JSON) or ("", None)
        """
        self.seen, self.skipped = 0, []

        def usable(path):
            name = os.path.basename(path)
            self.seen += 1
            if CREDENTIAL_NOTEBOOK.search(name):
                self.skipped.append(name)
                return None
            nb = self.contents(path)
            index, _, unsafe = first_code_cell(nb)
            if unsafe:
                self.skipped.append(f"{unsafe} cell{'s' if unsafe > 1 else ''} of {name}")
            return nb if index is not None else None

        nb = usable(shown) if shown else None
        if nb is not None:
            return shown, nb
        queue, looked = [(os.path.dirname(shown), 0)], 0
        while queue and looked < limit and time.time() < deadline:
            folder, depth = queue.pop(0)
            items = self.request("GET", self.base + "api/contents/" + urllib.parse.quote(folder))
            items = sorted(items.get("content") or [], key=lambda i: i["path"].lower())
            for item in items:
                if item["type"] == "notebook" and item["path"] != shown and ".rigtest-" not in item["path"]:
                    looked += 1
                    nb = usable(item["path"])
                    if nb is not None:
                        return item["path"], nb
                elif item["type"] == "directory" and depth < 2 and not item["name"].startswith("."):
                    queue.append((item["path"], depth + 1))
        return "", None


def first_code_cell(nb):
    """
    The first code cell that is safe to run: it installs nothing and touches no
    IBM Quantum credentials (CREDENTIAL_CODE).

    Returns:
        tuple: (index, source, credential cells passed over) - (None, '', n)
            if there is none.
    """
    unsafe = 0
    for i, cell in enumerate(nb.get("cells", [])):
        src = cell.get("source", "")
        src = "".join(src) if isinstance(src, list) else src
        if cell.get("cell_type") != "code" or not src.strip():
            continue
        if re.search(r"\b(pip|conda|mamba|apt(-get)?)\s+install\b", src):
            continue
        if CREDENTIAL_CODE.search(src):
            unsafe += 1
            continue
        return i, src, unsafe
    return None, "", unsafe


def run_cell(jup, nb_path, nb, deadline):
    """
    Run the notebook's first code cell in a fresh kernel; return a detail string
    and whether it worked.
    """
    index, src, _ = first_code_cell(nb)
    if index is None:
        return "cell=none", True
    if CREDENTIAL_CODE.search(src):   # last line of defence: never run credential code
        return f"cell={index} not run (credential code)", True
    specs = jup.request("GET", jup.base + "api/kernelspecs")
    kname = nb.get("metadata", {}).get("kernelspec", {}).get("name")
    if kname not in specs.get("kernelspecs", {}):
        kname = specs.get("default")
    folder = os.path.dirname(nb_path)
    session = jup.request("POST", jup.base + "api/sessions", {
        "path": (folder + "/" if folder else "") + f".rigtest-{os.getpid()}.ipynb",
        "name": "rigtest", "type": "notebook", "kernel": {"name": kname}})
    try:
        kid = session["kernel"]["id"]
        ws_url = (jup.origin.replace("http", "ws", 1) + jup.base + f"api/kernels/{kid}/channels"
                  + f"?session_id={uuid.uuid4().hex}" + (f"&token={jup.token}" if jup.token else ""))
        h = jup.headers()
        ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True,
                                         header=[f"{k}: {v}" for k, v in h.items() if k in ("Authorization", "Cookie")])
        try:
            return _execute(ws, index, src, deadline)
        finally:
            ws.close()
    finally:
        try:
            jup.request("DELETE", jup.base + f"api/sessions/{session['id']}")
        except (OSError, KeyError):
            pass


def _execute(ws, index, src, deadline):
    """Send kernel_info (wait for the kernel), then execute; collect the result."""
    sid = uuid.uuid4().hex

    def send(msg_type, content):
        mid = uuid.uuid4().hex
        ws.send(json.dumps({"header": {"msg_id": mid, "username": "rigtest", "session": sid,
                                       "msg_type": msg_type, "version": "5.3"},
                            "parent_header": {}, "metadata": {}, "content": content,
                            "channel": "shell", "buffers": []}))
        return mid

    def replies(mid):
        while time.time() < deadline:
            ws.settimeout(max(0.5, deadline - time.time()))
            try:
                msg = json.loads(ws.recv())
            except websocket.WebSocketTimeoutException:
                return
            if msg.get("parent_header", {}).get("msg_id") == mid:
                yield msg

    info = send("kernel_info_request", {})
    if not any(m["msg_type"] == "kernel_info_reply" for m in replies(info)):
        return f"cell={index} kernel did not answer", False
    run = send("execute_request", {"code": src, "silent": False, "store_history": True,
                                   "user_expressions": {}, "allow_stdin": False, "stop_on_error": True})
    out, error, done = "", None, False
    for m in replies(run):
        t, c = m["msg_type"], m["content"]
        if t == "stream":
            out += c.get("text", "")
        elif t in ("execute_result", "display_data"):
            out += c.get("data", {}).get("text/plain", "[" + ",".join(c.get("data", {})) + "]") + " "
        elif t == "error":
            error = f"{c.get('ename')}: {c.get('evalue', '')}"[:100]
        elif t == "status" and c.get("execution_state") == "idle":
            done = True
            break
    if error:
        return f"cell={index} error={error}", False
    if not done:
        return f"cell={index} did not finish in time", False
    out = " ".join(out.split())[:50]
    return f"cell={index} ok" + (f" out='{out}'" if out else " (no output)"), True


# ----------------------------------------------------------------------------
def check(kind, before_file, url, hint):
    """Check the demo's page; print 'web=<ok|warn|fail> <detail>'."""
    deadline = time.time() + float(hint.get("timeout", 240 if kind == "jupyter" else 90))
    if not cdp_up():
        print("web=warn browser debugging off: page not checked")
        return 0
    fresh = new_tabs(before_file)
    port = urllib.parse.urlsplit(url).port if url else None
    mine = [t for t in fresh if port and urllib.parse.urlsplit(t["url"]).port == port] or fresh
    notes, verdict = [], "ok"
    if mine:
        target = mine[0]
        notes.append("tab=demo")
    elif url:
        # a person would see nothing open: for a browser demo that is the
        # failure (seen: a launcher that exits at once loses its browser call
        # when its window closes); still check the page itself
        target = cdp_json("/json/new?" + urllib.parse.quote(url, safe=":/?=&%"), method="PUT")
        notes.append("tab=test (the demo opened none)")
        verdict = "fail" if kind in ("browser", "web-static", "script") else "warn"
    else:
        print("web=fail the demo opened no tab and printed no URL")
        return 0
    tab = Tab(target)
    worked = False   # a cell ran or a control responded
    try:
        page = load_page(tab, min(deadline, time.time() + 45))
        title = (page.get("title") or "").strip()
        notes.insert(0, f"title='{title[:40]}'")
        if not page.get("loaded") or page.get("failed_document") or not (title or page.get("text")):
            print(f"web=fail page did not load ({'document failed' if page.get('failed_document') else 'blank'})"
                  f" {' '.join(notes)} url={page.get('url', target.get('url', ''))[:80]}")
            return 0
        jupyter = kind == "jupyter" or bool(JUPYTER_PATH.search(urllib.parse.urlsplit(page.get("url", "")).path))
        if jupyter:
            ok = wait_for(tab, ".jp-Notebook .jp-Cell, #notebook-container .cell, .jp-NotebookPanel, "
                               ".jp-LabShell, #notebook_list", min(deadline, time.time() + 40))
            if not ok:
                verdict = "fail"
                notes.append("jupyter UI did not render")
            else:
                cookies = {c["name"]: c["value"] for c in tab.call("Network.getCookies").get("cookies", [])
                           if c.get("domain") in (urllib.parse.urlsplit(page["url"]).hostname, "localhost", "127.0.0.1")}
                jup = Jupyter(url if url and urllib.parse.urlsplit(url).port == urllib.parse.urlsplit(page["url"]).port
                              else page["url"], cookies)
                if not jup.notebook:   # the tab's own URL names the notebook (the log's may not)
                    jup.notebook = Jupyter(page["url"], cookies).notebook
                shown = jup.find_notebook()
                nb_path, nb = jup.runnable_notebook(shown, deadline)
                skipped = f" (not run, credentials: {', '.join(jup.skipped)[:80]})" if jup.skipped else ""
                if nb_path:
                    detail, ok = run_cell(jup, nb_path, nb, deadline)
                    notes.append(f"nb={nb_path} {detail}{skipped}")
                    verdict = verdict if ok else "fail"
                    worked = ok
                elif not jup.seen:
                    # an empty workspace (JupyterLab with no notebooks) is fine
                    notes.append("empty workspace, no notebook to run")
                    verdict = worst(verdict, "info")
                elif jup.skipped:
                    notes.append(f"no safe cell to run{skipped}")
                    verdict = worst(verdict, "info")
                else:
                    notes.append(f"no notebook with code to run (shown: {shown or 'none'})")
                    verdict = worst(verdict, "warn")
        else:
            if hint.get("title") and hint["title"].lower() not in title.lower():
                verdict = "fail"
                notes.append(f"title lacks '{hint['title']}'")
            if hint.get("wait") and not wait_for(tab, hint["wait"], min(deadline, time.time() + 30)):
                verdict = "fail"
                notes.append(f"missing {hint['wait']}")
            if hint.get("click_at"):
                label, responded = click_at(tab, hint["click_at"])
                if responded is None:
                    notes.append(f"click='{label}' not judged (the page animates)")
                    label = ""
            else:
                label, responded = click_control(tab, hint.get("click"))
            if label == "":
                pass
            elif label is None:
                notes.append("no control to click")
                verdict = "fail" if hint.get("click") else verdict
            else:
                notes.append(f"click='{label}' " + ("responded" if responded else "NO RESPONSE"))
                worked = bool(responded)
                if not responded:
                    verdict = "fail" if (hint.get("click") or hint.get("click_at")) else "warn"
        errs = tab.errors()
        if errs:
            # reported; a warning only when nothing showed the page working
            notes.append(f"js-errors={len(errs)} ({errs[0]})")
            if verdict in ("ok", "info") and not worked:
                verdict = "warn"
    except (OSError, RuntimeError, TimeoutError, websocket.WebSocketException, ValueError, KeyError) as exc:
        verdict = "fail"
        notes.append(f"check error: {type(exc).__name__}: {str(exc)[:80]}")
    finally:
        tab.close()
    print(f"web={verdict} " + " ".join(notes))
    return 0


def main(argv):
    """Dispatch the sub-commands (see the module docstring)."""
    cmd = argv[0] if argv else ""
    if cmd == "browser-debug":
        return browser_debug()
    if cmd == "browser-restore":
        return browser_restore()
    if cmd == "tabs" and len(argv) == 2:
        return save_tabs(argv[1])
    if cmd == "close-new" and len(argv) == 2:
        return close_new(argv[1])
    if cmd == "check" and len(argv) >= 3:
        hint = json.loads(argv[4]) if len(argv) > 4 and argv[4] else {}
        return check(argv[1], argv[2], argv[3] if len(argv) > 3 else "", hint)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
