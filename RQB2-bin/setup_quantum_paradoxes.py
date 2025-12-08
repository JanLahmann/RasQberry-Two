#!/usr/bin/env python3
"""
Setup script for quantum-paradoxes repository.

This script performs post-clone setup:
1. Fixes Qiskit 2.x compatibility issues in notebooks
2. Creates a WELCOME.ipynb with links to videos and blogs
3. Adds header cells to each notebook with navigation links
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote


# ============================================================================
# CONFIGURATION
# ============================================================================

WEBSITE_URL = "https://www.mariaviolaris.com/quantum-paradoxes/"
YOUTUBE_PLAYLIST = "https://www.youtube.com/playlist?list=PLOFEBzvs-VvoQP-EVyd5Di3UrPPc2YKIc"
TRAILER_VIDEO_ID = "Pz829XZIxXg"

# Paradox metadata: filename -> (title, blog_url, video_id)
# video_id should be the YouTube video ID (e.g., "sBtAe8BsOhA" for https://youtu.be/sBtAe8BsOhA)
PARADOXES = {
    "schrodingers-cat.ipynb": (
        "Schrödinger's Cat",
        "https://medium.com/qiskit/schr%C3%B6dingers-cat-meets-qiskit-why-do-we-never-see-cats-that-are-both-dead-and-alive-6e9adf7a09e0",
        "sBtAe8BsOhA"
    ),
    "quantum-zeno-effect.ipynb": (
        "Quantum Zeno Effect",
        "https://medium.com/qiskit/the-quantum-zeno-effect-from-motionless-arrows-to-entangled-freezers-e93beb7d52ae",
        "vfUn8cR-eXw"
    ),
    "A quantum lie detector for Hardy's paradox.ipynb": (
        "Hardy's Paradox",
        "https://medium.com/qiskit/how-to-build-a-quantum-lie-detector-with-quantum-computers-464d6456c5ec",
        "kLdvDDHLvOA"
    ),
    "double-slit.ipynb": (
        "Double-Slit Experiment",
        None,  # Coming soon
        "CI41yWg38Oo"
    ),
    "EPR-paradox.ipynb": (
        "EPR Paradox",
        None,  # Coming soon
        "eoPX4WJlOM8"
    ),
    "many-worlds.ipynb": (
        "Many-Worlds",
        None,  # Coming soon
        "-YEmRhogaSQ"
    ),
    "Pigeonhole_paradox-notebook.ipynb": (
        "Pigeonhole Paradox",
        "https://medium.com/qiskit/how-to-count-pigeons-using-a-quantum-computer-without-breaking-math-32404fd2abc4",
        None  # Video ID not in notebook
    ),
    "quantum-eraser.ipynb": (
        "Quantum Eraser",
        None,  # Coming soon
        "Bb0hAo9Kp3w"
    ),
    "quantum-maxwells-demon.ipynb": (
        "Maxwell's Demon",
        "https://medium.com/qiskit/quantum-maxwells-demon-trick-or-treat-2a3052d94f53",
        "YX5VxYvDfxM"
    ),
    "quantum-minesweeper-code.ipynb": (
        "Quantum Bomb Tester",
        "https://medium.com/qiskit/building-quantum-bomb-testers-and-other-thought-experiments-with-quantum-computers-c160060fdde4",
        "fus1nJ6JaTk"
    ),
    "teleportation.ipynb": (
        "Quantum Teleportation",
        None,  # Coming soon
        "KsvNsY4cVvE"
    ),
    "time-loops.ipynb": (
        "Time Loops",
        "https://medium.com/qiskit/a-christmas-closed-timelike-curve-could-the-story-of-scrooge-actually-happen-in-a-quantum-universe-cb22cdf8c9a7",
        "jcC1Ck45Ykw"
    ),
    "wigner-friend-friend-friend.ipynb": (
        "Frauchiger-Renner",
        None,  # Coming soon
        "kM1EwKBWXPs"
    ),
    "wigners-friend.ipynb": (
        "Wigner's Friend",
        "https://www.ibm.com/quantum/blog/wigners-friend-qiskit",
        "TMBK88Mpg5U"
    ),
}

# Qiskit 2.x compatibility fixes
QISKIT_IMPORT_FIXES = [
    # qiskit.providers.aer moved to qiskit_aer
    ("from qiskit.providers.aer import QasmSimulator", "from qiskit_aer import AerSimulator; from qiskit import transpile"),
    ("from qiskit.providers.aer import AerSimulator", "from qiskit_aer import AerSimulator; from qiskit import transpile"),
    ("from qiskit.providers.aer import Aer", "from qiskit_aer import Aer, AerSimulator; from qiskit import transpile"),
    ("from qiskit import Aer", "from qiskit_aer import Aer, AerSimulator; from qiskit import transpile"),
    ("from qiskit_aer import AerSimulator", "from qiskit_aer import AerSimulator; from qiskit import transpile"),
    # qiskit.providers.aer.noise moved to qiskit_aer.noise
    ("from qiskit.providers.aer.noise import NoiseModel", "from qiskit_aer.noise import NoiseModel"),
    ("from qiskit.providers.aer.noise import depolarizing_error", "from qiskit_aer.noise import depolarizing_error"),
    # qiskit.tools.visualization moved to qiskit.visualization
    ("from qiskit.tools.visualization import plot_histogram", "from qiskit.visualization import plot_histogram"),
    # c_if chaining removed in Qiskit 2.x - need gate classes for append
    ("from qiskit import QuantumRegister, ClassicalRegister, QuantumCircuit",
     "from qiskit import QuantumRegister, ClassicalRegister, QuantumCircuit, transpile\nfrom qiskit.circuit.library import XGate, ZGate  # For c_if compatibility"),
    ("from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister",
     "from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile\nfrom qiskit.circuit.library import XGate, ZGate  # For c_if compatibility"),
    # qiskit.test.mock moved to qiskit_ibm_runtime.fake_provider
    ("from qiskit.test.mock import FakeParis", "from qiskit_ibm_runtime.fake_provider import FakeParisV2 as FakeParis"),
    ("from qiskit.test.mock import FakeVigo", "from qiskit_ibm_runtime.fake_provider import FakeVigoV2 as FakeVigo"),
    # IBMQ was removed in Qiskit 2.x - use fake backend with noise model + execute shim
    ("from qiskit import IBMQ, execute", "from qiskit_ibm_runtime.fake_provider import FakeManilaV2; from qiskit import transpile\ndef execute(circuit, backend, shots=1024): return backend.run(transpile(circuit, backend), shots=shots)  # Qiskit 2.x shim"),
    ("from qiskit import IBMQ", "from qiskit_ibm_runtime.fake_provider import FakeManilaV2; from qiskit import transpile  # IBMQ removed in Qiskit 2.x"),
    # execute() was removed in Qiskit 2.x - provide shim
    ("from qiskit import execute", "from qiskit import transpile\ndef execute(circuit, backend, shots=1024): return backend.run(transpile(circuit, backend), shots=shots)  # Qiskit 2.x shim"),
]

QISKIT_CODE_FIXES = [
    ("QasmSimulator()", "AerSimulator()"),
    ("simulator = QasmSimulator", "simulator = AerSimulator"),
    ("backend = QasmSimulator", "backend = AerSimulator"),
    # Replace IBMQ cloud connection with fake noisy backend
    ("IBMQ.load_account()", "pass  # IBMQ.load_account() - using fake backend"),
    ("provider = IBMQ.get_provider", "backend = FakeManilaV2()  # Noisy simulator: provider = IBMQ.get_provider"),
    ("provider.get_backend", "backend  # Noisy simulator: provider.get_backend"),
    # cnot() renamed to cx() in Qiskit 2.x
    (".cnot(", ".cx("),
    # c_if completely removed in Qiskit 2.x - use if_test context manager instead
    # Teleportation notebook specific fixes - convert to if_test
    ("qc.x(bob_q[0]).c_if(alice_c2, 1)", "with qc.if_test((alice_c2, 1)):\n    qc.x(bob_q[0])"),
    ("qc.z(bob_q[0]).c_if(alice_c1, 1)", "with qc.if_test((alice_c1, 1)):\n    qc.z(bob_q[0])"),
    ("qc.append(XGate().to_mutable().c_if(alice_c2, 1), [bob_q[0]])", "with qc.if_test((alice_c2, 1)):\n    qc.x(bob_q[0])"),
    ("qc.append(ZGate().to_mutable().c_if(alice_c1, 1), [bob_q[0]])", "with qc.if_test((alice_c1, 1)):\n    qc.z(bob_q[0])"),
    ("qc.append(XGate().c_if(alice_c2, 1), [bob_q[0]])", "with qc.if_test((alice_c2, 1)):\n    qc.x(bob_q[0])"),
    ("qc.append(ZGate().c_if(alice_c1, 1), [bob_q[0]])", "with qc.if_test((alice_c1, 1)):\n    qc.z(bob_q[0])"),
    # EPR-paradox notebook specific fixes - convert to if_test
    ("qc.x(qr_Check_qubit).c_if(cr_Alice_outcome, 1)", "with qc.if_test((cr_Alice_outcome, 1)):\n    qc.x(qr_Check_qubit)"),
    ("qc.x(qr_Check_qubit).c_if(cr_Bob_outcome, 1)", "with qc.if_test((cr_Bob_outcome, 1)):\n    qc.x(qr_Check_qubit)"),
    ("qc.append(XGate().to_mutable().c_if(cr_Alice_outcome, 1), [qr_Check_qubit])", "with qc.if_test((cr_Alice_outcome, 1)):\n    qc.x(qr_Check_qubit)"),
    ("qc.append(XGate().to_mutable().c_if(cr_Bob_outcome, 1), [qr_Check_qubit])", "with qc.if_test((cr_Bob_outcome, 1)):\n    qc.x(qr_Check_qubit)"),
    ("qc.append(XGate().c_if(cr_Alice_outcome, 1), [qr_Check_qubit])", "with qc.if_test((cr_Alice_outcome, 1)):\n    qc.x(qr_Check_qubit)"),
    ("qc.append(XGate().c_if(cr_Bob_outcome, 1), [qr_Check_qubit])", "with qc.if_test((cr_Bob_outcome, 1)):\n    qc.x(qr_Check_qubit)"),
    # Qiskit 2.x requires transpile before run on noisy simulator
    ("sim_noise.run(engine)", "sim_noise.run(transpile(engine, sim_noise))"),
    ("sim_noise.run(reset_circ)", "sim_noise.run(transpile(reset_circ, sim_noise))"),
    # AerSimulator.from_backend() restricts basis gates - use plain AerSimulator with noise_model
    ("sim_noise = AerSimulator.from_backend(device_backend, noise_model = noise_model)",
     "sim_noise = AerSimulator(noise_model=noise_model)  # Use plain simulator with noise"),
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def youtube_thumbnail(video_id: str, size: str = "default") -> str:
    """Get YouTube thumbnail URL for a video.

    Sizes: default (120x90), mqdefault (320x180), hqdefault (480x360),
           sddefault (640x480), maxresdefault (1280x720), 0.jpg (480x360)
    """
    return f"https://img.youtube.com/vi/{video_id}/{size}.jpg"


# ============================================================================
# NOTEBOOK UTILITIES
# ============================================================================

def load_notebook(filepath: Path) -> Dict:
    """Load a Jupyter notebook from disk."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_notebook(filepath: Path, notebook: Dict) -> None:
    """Save a Jupyter notebook to disk."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)
    print(f"  Saved: {filepath.name}")


def create_markdown_cell(source: str) -> Dict:
    """Create a Jupyter markdown cell."""
    if isinstance(source, str):
        source = source.split('\n')
        source = [line + '\n' for line in source[:-1]] + [source[-1]]

    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source
    }


def create_code_cell(source: str, hidden: bool = False, outputs: List = None) -> Dict:
    """Create a Jupyter code cell."""
    if isinstance(source, str):
        source = source.split('\n')
        source = [line + '\n' for line in source[:-1]] + [source[-1]]

    cell = {
        "cell_type": "code",
        "execution_count": 1 if outputs else None,
        "metadata": {},
        "outputs": outputs or [],
        "source": source
    }
    if hidden:
        cell["metadata"]["jupyter"] = {"source_hidden": True}
    return cell


def create_youtube_output(video_id: str, width: int = 560, height: int = 315) -> List:
    """Create pre-rendered YouTube video output."""
    return [{
        "data": {
            "text/html": f'<iframe width="{width}" height="{height}" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>',
            "text/plain": f"<IPython.lib.display.YouTubeVideo at 0x0>"
        },
        "execution_count": 1,
        "metadata": {},
        "output_type": "execute_result"
    }]


# ============================================================================
# QISKIT COMPATIBILITY FIXES
# ============================================================================

def fix_qiskit_imports(notebook: Dict) -> Tuple[Dict, int]:
    """Fix Qiskit 2.x compatibility issues in a notebook."""
    fixes_count = 0

    for cell in notebook.get('cells', []):
        if cell.get('cell_type') != 'code':
            continue

        source = cell.get('source', [])
        if isinstance(source, str):
            source = [source]

        modified = False
        new_source = []

        for line in source:
            new_line = line

            for old_import, new_import in QISKIT_IMPORT_FIXES:
                if old_import in new_line:
                    new_line = new_line.replace(old_import, new_import)
                    modified = True
                    fixes_count += 1

            for old_code, new_code in QISKIT_CODE_FIXES:
                if old_code in new_line:
                    new_line = new_line.replace(old_code, new_code)
                    modified = True
                    fixes_count += 1

            new_source.append(new_line)

        if modified:
            cell['source'] = new_source

    return notebook, fixes_count


# ============================================================================
# HEADER CELLS
# ============================================================================

def create_header_cell(
    paradox_title: str,
    blog_url: Optional[str] = None,
    video_id: Optional[str] = None
) -> Dict:
    """Create a header cell with navigation links and embedded video."""
    lines = [
        f"# {paradox_title}\n",
        "\n",
        "---\n",
        "\n",
    ]

    links = []
    links.append("[← Back to Welcome](WELCOME.ipynb)")

    if blog_url:
        links.append(f"[Read Blog]({blog_url})")

    links.append(f"[Website]({WEBSITE_URL})")
    links.append(f"[All Videos]({YOUTUBE_PLAYLIST})")

    lines.append(" | ".join(links) + "\n")
    lines.append("\n")

    # Embed YouTube video if available
    if video_id:
        lines.append(f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" ')
        lines.append('frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; ')
        lines.append('gyroscope; picture-in-picture" allowfullscreen></iframe>\n')
        lines.append("\n")

    lines.append("---\n")

    return create_markdown_cell(lines)


def has_header_cell(notebook: Dict) -> bool:
    """Check if notebook already has a header cell added by this script."""
    cells = notebook.get('cells', [])
    for cell in cells[:3]:  # Check first 3 cells
        if cell.get('cell_type') == 'markdown':
            source = cell.get('source', [])
            if isinstance(source, list):
                source = ''.join(source)
            if '← Back to Welcome' in source:
                return True
    return False


def remove_header_cells(notebook: Dict) -> Dict:
    """Remove any existing header cells added by this script."""
    cells = notebook.get('cells', [])
    # Remove cells from the beginning that contain our header marker
    while cells:
        cell = cells[0]
        if cell.get('cell_type') == 'markdown':
            source = cell.get('source', [])
            if isinstance(source, list):
                source = ''.join(source)
            if '← Back to Welcome' in source:
                cells.pop(0)
                continue
        break
    notebook['cells'] = cells
    return notebook


def add_header_to_notebook(
    notebook: Dict,
    paradox_title: str,
    blog_url: Optional[str] = None,
    video_url: Optional[str] = None
) -> Dict:
    """Add a header cell to the beginning of a notebook."""
    # Remove any existing headers first
    notebook = remove_header_cells(notebook)
    header_cell = create_header_cell(paradox_title, blog_url, video_url)
    cells = notebook.get('cells', [])
    cells.insert(0, header_cell)
    notebook['cells'] = cells
    return notebook


# ============================================================================
# WELCOME NOTEBOOK
# ============================================================================

def create_welcome_notebook(paradoxes: Dict[str, Tuple[str, str, Optional[str]]]) -> Dict:
    """Create a WELCOME.ipynb notebook with links to all paradoxes."""
    cells = []

    # Title and introduction
    title_cell = create_markdown_cell(
        "# Welcome to Quantum Paradoxes!\n"
        "\n"
        "Interactive Jupyter notebooks exploring quantum mechanics paradoxes.\n"
        "\n"
        f"**Created by Maria Violaris** - [Visit Website]({WEBSITE_URL})\n"
        "\n"
        "---\n"
    )
    cells.append(title_cell)

    # Video Series with embedded trailer
    video_section = create_markdown_cell(
        "## Video Series\n"
        "\n"
        f"[![Quantum Paradoxes Trailer](https://img.youtube.com/vi/{TRAILER_VIDEO_ID}/0.jpg)](https://www.youtube.com/watch?v={TRAILER_VIDEO_ID})\n"
        "\n"
        "*Click thumbnail to watch the trailer*\n"
        "\n"
        f"[![YouTube Playlist](https://img.shields.io/badge/YouTube-Full_Playlist-red?style=for-the-badge&logo=youtube)]({YOUTUBE_PLAYLIST})\n"
        "\n"
        "---\n"
    )
    cells.append(video_section)

    # Table of paradoxes with thumbnails
    table_lines = (
        "## Quantum Paradoxes\n"
        "\n"
        "| | Paradox | Notebook | Blog |\n"
        "|:---:|---------|----------|------|\n"
    )

    for filename, (title, blog_url, video_id) in sorted(paradoxes.items()):
        # Small thumbnail (default.jpg is 120x90)
        if video_id:
            thumbnail = f"[![]({youtube_thumbnail(video_id, 'default')})](https://youtu.be/{video_id})"
        else:
            thumbnail = f"[![]({youtube_thumbnail(TRAILER_VIDEO_ID, 'default')})]({YOUTUBE_PLAYLIST})"
        # URL-encode filename to handle spaces and special characters
        encoded_filename = quote(filename)
        notebook_link = f"[Open]({encoded_filename})"
        blog_link = f"[Read]({blog_url})" if blog_url else "—"
        table_lines += f"| {thumbnail} | **{title}** | {notebook_link} | {blog_link} |\n"

    table_lines += "\n---\n"
    cells.append(create_markdown_cell(table_lines))

    # Getting started section
    getting_started = create_markdown_cell(
        "## Getting Started\n"
        "\n"
        "1. Click on any notebook link in the table above\n"
        "2. Run the cells sequentially (Shift + Enter)\n"
        "3. Experiment with the quantum circuits!\n"
        "\n"
        "### Qiskit 2.x Compatibility\n"
        "\n"
        "These notebooks have been updated for Qiskit 2.x:\n"
        "- `QasmSimulator` replaced with `AerSimulator`\n"
        "- Imports updated to use `qiskit_aer` package\n"
        "\n"
        "---\n"
    )
    cells.append(getting_started)

    # Footer
    footer = create_markdown_cell(
        "## Learn More\n"
        "\n"
        "- [Qiskit Documentation](https://docs.quantum.ibm.com/)\n"
        f"- [Maria Violaris - Quantum Paradoxes]({WEBSITE_URL})\n"
    )
    cells.append(footer)

    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.9.0"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }


# ============================================================================
# MAIN SETUP FUNCTION
# ============================================================================

def setup_quantum_paradoxes(repo_path: Optional[Path] = None) -> None:
    """Main setup function for quantum-paradoxes repository."""
    if repo_path is None:
        repo_path = Path.cwd()
    else:
        repo_path = Path(repo_path)

    if not repo_path.exists():
        print(f"Error: Repository path does not exist: {repo_path}")
        sys.exit(1)

    print(f"Setting up quantum-paradoxes at: {repo_path}")
    print("=" * 60)

    total_fixes = 0
    processed = []

    for filename, (title, blog_url, video_url) in PARADOXES.items():
        notebook_path = repo_path / filename

        if not notebook_path.exists():
            print(f"Warning: Notebook not found: {filename}")
            continue

        print(f"\nProcessing: {filename}")

        try:
            notebook = load_notebook(notebook_path)

            notebook, fixes_count = fix_qiskit_imports(notebook)
            if fixes_count > 0:
                print(f"  Applied {fixes_count} Qiskit 2.x fix(es)")
                total_fixes += fixes_count

            notebook = add_header_to_notebook(notebook, title, blog_url, video_url)
            print(f"  Added header cell")

            save_notebook(notebook_path, notebook)
            processed.append(filename)

        except Exception as e:
            print(f"Error processing {filename}: {e}")

    # Create WELCOME.ipynb
    print("\n" + "=" * 60)
    print("Creating WELCOME.ipynb")

    welcome_notebook = create_welcome_notebook(PARADOXES)
    save_notebook(repo_path / "WELCOME.ipynb", welcome_notebook)

    # Summary
    print("\n" + "=" * 60)
    print("SETUP COMPLETE!")
    print(f"Processed: {len(processed)}/{len(PARADOXES)} notebooks")
    print(f"Qiskit fixes: {total_fixes}")
    print("Created: WELCOME.ipynb")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Setup quantum-paradoxes repository")
    parser.add_argument('--path', type=str, help='Path to repository', default=None)
    args = parser.parse_args()

    setup_quantum_paradoxes(Path(args.path) if args.path else None)


if __name__ == '__main__':
    main()
