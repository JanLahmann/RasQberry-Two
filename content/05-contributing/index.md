---
description: "How to contribute to RasQberry Two, the open-source quantum computing project: test and report issues, share ideas, improve the docs, create demos."
---
# Contributing to RasQberry

RasQberry Two is open source and grows with its community: test it, report what
you find, improve the docs, or add a demo.

## How to Contribute

### 1. Test & Report Issues

The most valuable contribution is testing and reporting bugs:
- [Ask to become a tester](/testing/): missions for your hardware, with Ket as your helper
- Try out RasQberry on your hardware
- [Report issues](https://github.com/JanLahmann/RasQberry-Two/issues) with clear steps to reproduce
- Include error messages, screenshots, and hardware details
- Attach the report from `rq_info.sh --report` (saved in your home folder): version, Pi model, A/B slot, disk space and recent logs

### 2. Share Ideas & Feature Requests

Have ideas for improvements?
- Open a [GitHub Discussion](https://github.com/JanLahmann/RasQberry-Two/discussions) or issue
- Suggest new demos, UX improvements, or educational features

### 3. Improve Documentation

Help make RasQberry easier to use:
- Fix typos or unclear instructions
- Add troubleshooting tips
- Use the "Edit this page" link at the bottom of any page

### 4. Create Quantum Demos

Your demo lives in your own public GitHub repository; you don't build an image.
The full guide is [CONTRIBUTING.md](https://github.com/JanLahmann/RasQberry-Two/blob/development/CONTRIBUTING.md):

1. **Your repository:** a licence, exact package versions (`package==1.2.3`), and an `rqb-demo.json`
   manifest at its root that says how the demo runs (`python`, `jupyter`, `browser`,
   `web-static` or `docker`). LED demos draw through `rq_led_utils`, without
   root ([LEDs](https://github.com/JanLahmann/RasQberry-Two/blob/development/CONTRIBUTING.md#2-leds)).
2. **Test it on your Pi:** clone it into `~/RasQberry-Two/demos/`, check it with
   `rq_demo_validate.sh --external rqb-demo.json`, and start it with `rq_demo_run.sh`
   ([steps](https://github.com/JanLahmann/RasQberry-Two/blob/development/CONTRIBUTING.md#4-test-it-on-your-pi)).
3. **Into the catalogue:** [open an issue](https://github.com/JanLahmann/RasQberry-Two/issues)
   with the repository link and the commit to use. We test the demo on a Pi 4 and a Pi 5
   and add it to the catalogue.
4. Users then install it from **Quantum Demos** → **Manage demos** → **Add demo from catalogue**.

**Example demos for inspiration:**
- [Quantum Lights Out](../03-quantum-computing-demos/quantum-lights-out) - Puzzle game with quantum algorithms
- [Raspberry Tie](../03-quantum-computing-demos/raspberry-tie) - LED visualization of quantum circuits
- [Bloch Sphere](../03-quantum-computing-demos/bloch-sphere) - Interactive qubit state visualization

## Quick Links

| Resource | Link |
|----------|------|
| Report Issues | [GitHub Issues](https://github.com/JanLahmann/RasQberry-Two/issues) |
| Discussions | [GitHub Discussions](https://github.com/JanLahmann/RasQberry-Two/discussions) |
| Existing Demos | [Demo List](../03-quantum-computing-demos/01-demo-list) |
| Project Repository | [RasQberry-Two](https://github.com/JanLahmann/RasQberry-Two) |

## Resources

**Learning Qiskit:**
- [IBM Quantum Learning](https://quantum.cloud.ibm.com/learning)
- [Qiskit Documentation](https://quantum.cloud.ibm.com/docs/)

**Development:**
- The Python and Qiskit versions on the image (`rq_info.sh`), Raspberry Pi 4 or 5
- RasQberry OS image from [releases](/latest/)
