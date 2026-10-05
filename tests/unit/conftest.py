"""
Shared test settings.

No test may send a real Umami event: everything the tests start (the demo
engine, learning paths, the health check ...) inherits RQ_UMAMI=0. Tests of
the sender itself switch it on again against a local test server.
"""
import os

os.environ["RQ_UMAMI"] = "0"
# and if a test switches it on without its own server: a dead local port,
# never cloud.umami.is
os.environ["RQ_UMAMI_URL"] = "http://127.0.0.1:9/no-real-umami-in-tests"

# No test may touch a real browser's tabs: the demo-tab helper
# (rq_browser_tab.py) talks to a dead local port and gives up at once.
# Tests of the helper itself use a browser they start.
os.environ["RQ_BROWSER_CDP_PORT"] = "9"
os.environ["RQ_BROWSER_FIND_WAIT"] = "1"
