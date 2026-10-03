"""
pytest hooks and fixtures for the Qiskit compatibility tests (tests/qiskit_compat).

Every deprecation-type warning seen while the tests run - in-process (pytest's
warning capture) and in demo subprocesses (parsed from their stderr) - is
collected and written as markdown to the file named by $QISKIT_COMPAT_REPORT.
Deprecations never fail a test: they predict what breaks with the NEXT Qiskit
major, so CI only reports them. Errors fail.
"""

import os
import types

import pytest

import compat_helpers as h


def pytest_warning_recorded(warning_message, when, nodeid, location):
    """Collect deprecation-type warnings raised in-process by the tests."""
    category = warning_message.category.__name__
    if not category.endswith(h.DEPRECATION_CATEGORIES):
        return
    source = nodeid.split("::")[0].rsplit("/", 1)[-1] if nodeid else when
    h.record_warning(source, category, warning_message.message,
                     f"{warning_message.filename}:{warning_message.lineno}")


def _is_qiskit(key):
    return "qiskit" in (key[1] + key[2]).lower()


def pytest_sessionfinish(session, exitstatus):
    """Write the deprecation report (markdown) for the CI job summary."""
    path = os.environ.get("QISKIT_COMPAT_REPORT")
    if not path:
        return
    qiskit = [k for k in h.COLLECTED if _is_qiskit(k)]
    other = [k for k in h.COLLECTED if not _is_qiskit(k)]
    lines = ["### Deprecation warnings in our Qiskit code and demos", "",
             f"{len(qiskit)} Qiskit-related, {len(other)} other. They do not fail the job; "
             "they predict breakage in the next major release.", ""]
    for title, entries in (("Qiskit-related", qiskit), ("Other", other)):
        if not entries:
            continue
        lines += [f"**{title}**", "", "| category | where | message | seen in |",
                  "|---|---|---|---|"]
        for cat, msg, loc in entries:
            seen = ", ".join(h.COLLECTED[(cat, msg, loc)])
            lines.append(f"| {cat} | `{loc}` | {msg.replace('|', '/')} | {seen} |")
        lines.append("")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


@pytest.fixture
def led_env(tmp_path, monkeypatch):
    """A virtual-only LED setup: no GPIO, frames go to a temp mmap file.

    LED_RENDER_MODE=service makes rq_led_utils.create_neopixel_strip() return
    the VirtualNeoPixel mmap writer and never touch board/neopixel;
    RQB2_LED_MMAP_PATH keeps the frame file out of /dev/shm. Both are plain
    environment overrides rq_led_utils honours, so they reach demo subprocesses
    too. In-process, rq_led_utils.ENV_FILE points at a copy of the shipped
    environment file with the physical/virtual/web targets off.
    """
    mmap = tmp_path / "leds.mmap"
    monkeypatch.setenv("LED_RENDER_MODE", "service")
    monkeypatch.setenv("RQB2_LED_MMAP_PATH", str(mmap))
    monkeypatch.setenv("MPLBACKEND", "Agg")
    monkeypatch.syspath_prepend(h.BIN_DIR)

    overrides = {"LED_PHYSICAL": "false", "LED_VIRTUAL": "false", "LED_WEB": "false",
                 "LED_RENDER_MODE": "service"}
    with open(os.path.join(h.CONFIG_DIR, "rasqberry_environment.env"), encoding="utf-8") as fh:
        lines = [ln for ln in fh.read().splitlines()
                 if ln.split("=", 1)[0].strip() not in overrides]
    env_file = tmp_path / "rasqberry_environment.env"
    env_file.write_text("\n".join(lines + [f"{k}={v}" for k, v in overrides.items()]) + "\n")

    import rq_led_utils
    monkeypatch.setattr(rq_led_utils, "ENV_FILE", str(env_file))
    monkeypatch.setattr(rq_led_utils, "_pixels_singleton", None)
    return types.SimpleNamespace(env_file=env_file, mmap=mmap, config=rq_led_utils.get_led_config())
