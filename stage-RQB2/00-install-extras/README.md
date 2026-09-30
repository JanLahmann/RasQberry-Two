# 00-install-extras

Installs the Debian packages the demos and RasQberry tools need, before anything
RasQberry-specific is deployed.

## What it does

pi-gen installs every package listed in `00-packages` (no scripts in this stage):

| Package(s) | Used for |
|---|---|
| `python3-gi`, `gir1.2-gtk-3.0`, `libgirepository1.0-dev`, `libcairo2-dev` | GTK/cairo bindings, linked into the venv by 03-install-qiskit |
| `graphviz` | circuit and graph drawings |
| `python3-pkg-resources` | older Python packages that still import `pkg_resources` |
| `sense-emu-tools` | SenseHAT emulator (Quantum Raspberry Tie); pulls in `python3-sense-emu` |
| `chromium-browser`, `chromium-chromedriver` | browser demos and the start page |
| `libxcb-cursor-dev` | Qt apps under Wayland (LED Painter) |
| `jq`, `curl` | demo manifests, release picker, update check |
| `parted` | A/B partition expansion |

## Notes

- Python packages (Qiskit and the demo requirements) are installed into the venv by
  [03-install-qiskit](../03-install-qiskit/), not here.
