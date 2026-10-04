# Contributing to RasQberry

We welcome contributions to this quantum computing education project!

## How to Contribute

### 1. Test & Report Issues

The most valuable contribution is testing and reporting bugs:
- Try out RasQberry on your hardware
- [Report issues](https://github.com/JanLahmann/RasQberry-Two/issues) with clear steps to reproduce
- Include error messages, screenshots, and hardware details
- Paste the output of `rq_info.sh --json`: RasQberry version, build origin, A/B slot and Pi model

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

Build new interactive demonstrations:
1. Create your demo using Python and Qiskit, in its own GitHub repository with `requirements.txt` and `README.md`
2. Add an `rqb-demo.json` manifest at the repository root that says how the demo runs (`python`, `jupyter`, `browser` or `docker`); the format is described in [EXTERNAL_DEMOS.md](https://github.com/JanLahmann/RasQberry-Two/blob/development/RQB2-config/demo-manifests/EXTERNAL_DEMOS.md)
3. Open a pull request that adds your repository, pinned to a commit, to `RQB2-config/known-demos.json`
4. Once merged, users install it from **Quantum Demos** → **Add demo from catalogue** (`rq_demo_add_external.sh <id>`)

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
- Python 3.11+, Raspberry Pi 4 or 5
- RasQberry OS image from [releases](/latest/)
