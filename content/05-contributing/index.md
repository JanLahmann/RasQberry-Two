# Contributing to RasQberry

Welcome to the RasQberry community! We're excited that you're interested in contributing to this quantum computing education project.

## Why Contribute?

RasQberry makes quantum computing accessible through hands-on demonstrations. By contributing, you help:

- **Educate:** Make quantum computing concepts tangible for students and enthusiasts
- **Innovate:** Create new ways to visualize quantum phenomena
- **Inspire:** Show the world that quantum computing can be fun and approachable
- **Connect:** Join a global community of educators, developers, and quantum enthusiasts

## What Can You Contribute?

### 🎮 Quantum Computing Demos

Create new interactive demonstrations that teach quantum concepts:
- Games and puzzles using quantum algorithms
- Visualizations of quantum states and gates
- Artistic applications of quantum computing
- Practical quantum computing examples

**Perfect for:** Python developers, Qiskit users, educators, quantum enthusiasts

### 📚 Documentation

Help others learn and use RasQberry:
- Tutorial improvements
- Demo usage guides
- Hardware setup instructions
- Troubleshooting tips
- Translations

**Perfect for:** Technical writers, educators, experienced RasQberry users

### 🐛 Bug Reports & Fixes

Improve stability and reliability:
- Report issues you encounter
- Fix bugs in existing code
- Improve error messages
- Enhance hardware compatibility

**Perfect for:** Users, testers, developers

### 💡 Feature Suggestions

Share your ideas for improvements:
- New demo concepts
- User experience enhancements
- Hardware integration ideas
- Educational features

**Perfect for:** Everyone!

### 🌟 Share Your Projects

Inspire others by sharing:
- Your RasQberry setup photos/videos
- Classroom experiences
- Custom modifications
- Demo showcases

**Perfect for:** Educators, makers, quantum computing enthusiasts

## Getting Started

### For Demo Developers

**Quick Start:**
1. Review the [full contribution guide](https://github.com/JanLahmann/RasQberry-Two/blob/main/CONTRIBUTING.md)
2. Use our template to create your demo launcher
3. Test on RasQberry hardware
4. Submit a pull request

**Typical Time Investment:**
- Simple demo: 2-3 hours
- Complex demo: 1-2 days
- Documentation: 30 minutes

### For Documentation Writers

**Quick Start:**
1. Find documentation that needs improvement
2. Edit on GitHub (use the "Edit this page" link at bottom of pages)
3. Submit your changes

**Areas Needing Help:**
- Beginner tutorials
- Demo walkthroughs
- Troubleshooting guides
- Assembly instructions

### For Bug Reporters

**How to Report:**
1. Visit [GitHub Issues](https://github.com/JanLahmann/RasQberry-Two/issues)
2. Search for existing reports
3. Create a new issue with:
   - Clear description
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages/screenshots
   - Your hardware setup

## Community Guidelines

### Be Welcoming

RasQberry serves beginners and experts alike. Everyone was a beginner once. Be patient, kind, and encouraging.

### Be Respectful

Treat all community members with respect. Differences in opinion are learning opportunities.

### Be Collaborative

Share knowledge, ask questions, and work together. Great demos come from collaboration.

### Be Educational

Remember that RasQberry is primarily an educational tool. Consider how your contribution helps others learn.

## Adding a New Quantum Demo

Here's a quick overview of adding a new quantum computing demonstration to RasQberry:

### 1. Create Your Demo

Develop your quantum computing demonstration using Python and Qiskit:

```python
from qiskit import QuantumCircuit

# Your quantum demo logic
def my_quantum_demo():
    qc = QuantumCircuit(3, 3)
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(1, 2)
    # ... your demo continues
```

### 2. Package It

Create a GitHub repository with:
- Your demo code
- `requirements.txt` for dependencies
- `README.md` with description and usage
- Educational documentation

### 3. Integrate with RasQberry

- Add configuration to environment file
- Create launcher script using our template
- Add menu entry
- Document your demo

### 4. Submit

- Test thoroughly on Raspberry Pi
- Create pull request
- Respond to feedback

**For detailed step-by-step instructions, see our [comprehensive contribution guide](https://github.com/JanLahmann/RasQberry-Two/blob/main/CONTRIBUTING.md).**

## Examples of Great Contributions

Looking for inspiration? Check out these community contributions:

**Quantum Lights Out** by Luka-D
- Interactive puzzle game using quantum algorithms
- Teaches quantum superposition and measurement
- Visual LED feedback for quantum states

**Quantum Raspberry-Tie** by KPRoche
- Displays quantum circuit results on LED array
- Integrates with IBM Quantum backends
- Great for demonstrating real quantum hardware

**Grok Bloch Sphere** by JavaFXpert
- Interactive visualization of single-qubit states
- Teaches quantum gates intuitively
- Browser-based interface

These demos show how quantum concepts can be made tangible and fun!

## Resources for Contributors

### Documentation

**Getting Started:**
- [Full Contribution Guide](https://github.com/JanLahmann/RasQberry-Two/blob/main/CONTRIBUTING.md) - Detailed step-by-step instructions
- [Project README](https://github.com/JanLahmann/RasQberry-Two) - Project overview
- [Demo Documentation](../03-quantum-computing-demos/00-overview) - Existing demos

**Learning Quantum Computing:**
- [IBM Quantum Learning](https://learning.quantum.ibm.com/) - Free quantum computing courses
- [Qiskit Documentation](https://docs.qiskit.org/) - Qiskit framework documentation
- [Qiskit YouTube](https://www.youtube.com/@qiskit) - Video tutorials

### Tools

**Development:**
- Python 3.11+ for demo development
- Bash scripting for launcher scripts
- Git/GitHub for version control
- Raspberry Pi for testing

**Testing:**
- RasQberry OS image (download from releases)
- Raspberry Pi 4 or 5
- LED panels (optional, for LED demos)

## Recognition

We value all contributions! Contributors are recognized through:

### Attribution
- Your name in project contributors list
- Demo authorship clearly attributed
- Mentions in release notes
- Optional showcase on website

### Community
- Be part of a global quantum education community
- Connect with educators and quantum enthusiasts
- Share your work at conferences and events
- Contribute to quantum computing education worldwide

## Getting Help

### Questions?

**Before asking:**
- Check the [contribution guide](https://github.com/JanLahmann/RasQberry-Two/blob/main/CONTRIBUTING.md)
- Review [existing issues](https://github.com/JanLahmann/RasQberry-Two/issues)
- Look at [demo examples](../03-quantum-computing-demos/00-overview)

**Still need help?**
- Open a [GitHub issue](https://github.com/JanLahmann/RasQberry-Two/issues/new)
- Ask questions respectfully
- Provide context and details
- Be patient waiting for responses

### Found a Bug?

1. Check if it's already reported
2. Gather information (version, hardware, error messages)
3. Create detailed bug report on GitHub
4. Include steps to reproduce

## Quick Links

| Resource | Link |
|----------|------|
| **Contribution Guide** | [CONTRIBUTING.md](https://github.com/JanLahmann/RasQberry-Two/blob/main/CONTRIBUTING.md) |
| **GitHub Repository** | [RasQberry-Two](https://github.com/JanLahmann/RasQberry-Two) |
| **Report Issues** | [GitHub Issues](https://github.com/JanLahmann/RasQberry-Two/issues) |
| **Existing Demos** | [Demo List](../03-quantum-computing-demos/01-demo-list) |
| **Website** | [rasqberry.org](https://rasqberry.org) |

## Your Turn!

Ready to contribute? Here's what to do next:

1. **Read** the [full contribution guide](https://github.com/JanLahmann/RasQberry-Two/blob/main/CONTRIBUTING.md)
2. **Explore** existing [quantum demos](../03-quantum-computing-demos/00-overview) for inspiration
3. **Start** with something small (docs, bug fix, or simple demo)
4. **Share** your work via pull request
5. **Celebrate** making quantum computing more accessible!

## Thank You

Every contribution, no matter how small, makes RasQberry better and helps spread quantum computing education worldwide.

**Your contributions help shape the future of quantum computing education.**

Ready to start? Visit our [detailed contribution guide](https://github.com/JanLahmann/RasQberry-Two/blob/main/CONTRIBUTING.md) and join the quantum revolution!

---

## Contact & Community

**Questions or Ideas?**
- 📧 GitHub Issues: [Report issues or ask questions](https://github.com/JanLahmann/RasQberry-Two/issues)
- 💬 Discussions: [Join conversations](https://github.com/JanLahmann/RasQberry-Two/discussions)
- 🌐 Website: [rasqberry.org](https://rasqberry.org)

**Stay Updated:**
- ⭐ Star the project on [GitHub](https://github.com/JanLahmann/RasQberry-Two)
- 📰 Watch for releases and updates
- 🎉 Celebrate with us when your contribution is merged!

---

*RasQberry is an independent educational project inspiring quantum computing exploration worldwide.*
