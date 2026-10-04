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
