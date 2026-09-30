#!/usr/bin/env python3
"""
RasQberry Virtual LED Web Emulator (LED_WEB, Phase C).

The browser analog of rq_led_virtual_gui.py: a tiny stdlib-only HTTP server that
reads the SAME shared-memory frame bus (transport v2, /tmp/rasqberry_virtual_led2.mmap)
written by VirtualNeoPixel, and serves a self-contained canvas page. Anyone on
the network can open it in a browser to watch the LED matrix - useful in a
classroom or for users with no physical strip.

Geometry (width/height/count) comes from the self-describing mmap header, and the
(x, y) -> chain-index mapping is the shared rq_led_utils.map_xy_to_pixel, so the
web view can never disagree with the physical strip or the Tk GUI.

No third-party dependencies (http.server + struct + mmap file read), so it runs
on a bare image and is developable on a laptop.

Usage:
    python3 rq_led_web.py            # serves on http://0.0.0.0:8098
    LED_WEB_PORT=9000 python3 rq_led_web.py

    # Then, with a virtual/web target enabled, run any LED demo and open the page.

Environment:
    LED_WEB_HOST   Bind host (default 0.0.0.0 - reachable from other devices).
    LED_WEB_PORT   Bind port (default 8098).
    RQB2_LED_MMAP_PATH  Override the frame-bus path (matches rq_led_virtual.py).
"""

import json
import os
import struct
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Shared mapper + config (both live in RQB2-bin; /usr/bin when installed).
try:
    from rq_led_utils import map_xy_to_pixel, get_led_config
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from rq_led_utils import map_xy_to_pixel, get_led_config

# mmap transport v2 constants (must match rq_led_virtual.py)
MMAP_MAGIC = b'RQL1'
MMAP_HEADER_SIZE = 16
MMAP_PIXEL_OFFSET = 17  # header (16) + dirty flag (1)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8098


def mmap_path():
    """Frame-bus path; honours RQB2_LED_MMAP_PATH like rq_led_virtual.py."""
    return os.environ.get("RQB2_LED_MMAP_PATH", "/tmp/rasqberry_virtual_led2.mmap")


def _layout_name():
    """Configured layout name for the shared mapper (geometry comes from header)."""
    try:
        return get_led_config().get('led_layout', 'single-24x8')
    except Exception:
        return 'single-24x8'


def _resolve_port():
    """Bind port: LED_WEB_PORT env override first, then the env file, then default.

    get_led_config() reads the env file directly, so the configured port is
    honoured even when it was not exported into this process's environment.
    """
    env = os.environ.get("LED_WEB_PORT")
    if env:
        try:
            return int(env)
        except ValueError:
            pass
    try:
        return int(get_led_config().get('led_web_port', DEFAULT_PORT))
    except Exception:
        return DEFAULT_PORT


# Cache the (x, y) -> chain-index grid, keyed by (width, height, layout), so we
# don't recompute the mapping on every poll. The map only changes when the writer
# switches layout/geometry, which we detect from the header.
_grid_cache = {}
_grid_cache_key = None


def _xy_grid(width, height, layout):
    """Return a height x width list of chain indices (or None) for this geometry."""
    global _grid_cache, _grid_cache_key
    key = (width, height, layout)
    if _grid_cache_key == key:
        return _grid_cache
    grid = [[map_xy_to_pixel(x, y, layout=layout) for x in range(width)]
            for y in range(height)]
    _grid_cache = grid
    _grid_cache_key = key
    return grid


def read_frame():
    """
    Read the current frame from the mmap and return a JSON-able dict.

    Returns a dict with either {"waiting": true} when no valid frame bus exists
    yet, or {"w", "h", "layout", "rows"} where rows is a height-length list of
    width-length lists of [r, g, b] (already brightness-applied by the writer).

    We deliberately ignore the dirty flag and always return the current pixels,
    so the web view never fights the Tk GUI over clearing that flag.
    """
    path = mmap_path()
    try:
        with open(path, 'rb') as f:
            blob = f.read()
    except OSError:
        return {"waiting": True}

    if len(blob) < MMAP_PIXEL_OFFSET or blob[:4] != MMAP_MAGIC:
        return {"waiting": True}

    width, height, count = struct.unpack('<HHH', blob[4:10])
    if width == 0 or height == 0 or count == 0:
        return {"waiting": True}

    pixels = blob[MMAP_PIXEL_OFFSET:MMAP_PIXEL_OFFSET + count * 3]
    if len(pixels) < count * 3:
        return {"waiting": True}

    layout = _layout_name()
    grid = _xy_grid(width, height, layout)

    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            idx = grid[y][x]
            if idx is None or idx < 0 or (idx * 3 + 2) >= len(pixels):
                row.append([0, 0, 0])
            else:
                o = idx * 3
                row.append([pixels[o], pixels[o + 1], pixels[o + 2]])
        rows.append(row)

    return {"w": width, "h": height, "layout": layout, "rows": rows}


# Self-contained page: a canvas that polls /frame and draws the matrix. No
# external assets, so it works with no internet and behind the strict image.
INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RasQberry Virtual LED Matrix</title>
<style>
  html, body { margin: 0; height: 100%; background: #1a1a1a; color: #888;
    font-family: "Courier New", monospace; }
  #wrap { display: flex; flex-direction: column; align-items: center;
    justify-content: center; height: 100%; gap: 10px; }
  #status { font-size: 13px; }
  canvas { max-width: 96vw; max-height: 80vh; background: #1a1a1a; }
</style>
</head>
<body>
<div id="wrap">
  <canvas id="c" width="600" height="200"></canvas>
  <div id="status">Connecting...</div>
</div>
<script>
  var canvas = document.getElementById('c');
  var ctx = canvas.getContext('2d');
  var status = document.getElementById('status');
  var OFF = '#2a2a2a';

  function draw(frame) {
    var w = frame.w, h = frame.h, rows = frame.rows;
    var cell = 26, gap = 4, pad = 12;
    canvas.width = pad * 2 + w * cell - gap;
    canvas.height = pad * 2 + h * cell - gap;
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    var r = (cell - gap) / 2;
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        var p = rows[y][x];
        var isOff = (p[0] === 0 && p[1] === 0 && p[2] === 0);
        ctx.beginPath();
        ctx.arc(pad + x * cell + r, pad + y * cell + r, r, 0, 2 * Math.PI);
        ctx.fillStyle = isOff ? OFF : 'rgb(' + p[0] + ',' + p[1] + ',' + p[2] + ')';
        ctx.fill();
      }
    }
    status.textContent = w + '\\u00d7' + h + '  \\u00b7  ' + frame.layout;
  }

  function poll() {
    fetch('/frame', { cache: 'no-store' })
      .then(function (res) { return res.json(); })
      .then(function (frame) {
        if (frame.waiting) { status.textContent = 'Waiting for LED data...'; }
        else { draw(frame); }
      })
      .catch(function () { status.textContent = 'Disconnected - retrying...'; });
  }

  setInterval(poll, 100);
  poll();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    """Serves the canvas page at / and the current frame as JSON at /frame."""

    def _send(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/' or path == '/index.html':
            self._send(200, INDEX_HTML.encode('utf-8'), "text/html; charset=utf-8")
        elif path == '/frame':
            body = json.dumps(read_frame()).encode('utf-8')
            self._send(200, body, "application/json")
        else:
            self._send(404, b'not found', "text/plain")

    def log_message(self, *args):
        """Silence the default per-request stderr logging."""
        return


def main():
    host = os.environ.get("LED_WEB_HOST", DEFAULT_HOST)
    port = _resolve_port()

    try:
        server = ThreadingHTTPServer((host, port), Handler)
    except OSError as e:
        # Another instance already owns the port (singleton launch raced, or the
        # user started one by hand). Nothing to do - exit quietly and cleanly.
        print(f"LED web emulator: port {port} already in use ({e}); not starting.")
        return

    print(f"RasQberry LED web emulator on http://{host}:{port}  "
          f"(frame bus: {mmap_path()})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
