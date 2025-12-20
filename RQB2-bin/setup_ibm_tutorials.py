#!/usr/bin/env python3
"""
Setup script for IBM Quantum Tutorials and Courses.

This script generates WELCOME notebooks with navigation links to tutorials and courses
from the Qiskit documentation repository.

Content is licensed under CC BY-SA 4.0 by IBM/Qiskit.
Source: https://github.com/Qiskit/documentation
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ============================================================================
# CONFIGURATION
# ============================================================================

SOURCE_URL = "https://github.com/Qiskit/documentation"
LICENSE_INFO = "CC BY-SA 4.0 | Apache 2.0"

ATTRIBUTION_HEADER = f"""# {{title}}

> **Source:** [Qiskit Documentation]({SOURCE_URL})
> **License:** {LICENSE_INFO}
> See `LICENSE` and `LICENSE-DOCS` files for full license terms.

---

"""


# ============================================================================
# NOTEBOOK UTILITIES
# ============================================================================

def create_notebook(cells: List[Dict]) -> Dict:
    """Create a Jupyter notebook structure."""
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
                "version": "3.11.0"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }


def create_markdown_cell(source: str) -> Dict:
    """Create a markdown cell."""
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source.split('\n') if '\n' in source else [source]
    }


def extract_notebook_title(notebook_path: Path) -> Optional[str]:
    """Extract title from a notebook's first markdown cell or metadata."""
    try:
        with open(notebook_path, 'r', encoding='utf-8') as f:
            nb = json.load(f)

        # Try metadata title first
        if 'title' in nb.get('metadata', {}):
            return nb['metadata']['title']

        # Look for first markdown cell with a heading
        for cell in nb.get('cells', []):
            if cell.get('cell_type') == 'markdown':
                source = ''.join(cell.get('source', []))
                # Match # heading
                match = re.search(r'^#\s+(.+)$', source, re.MULTILINE)
                if match:
                    return match.group(1).strip()

        # Fallback to filename
        return notebook_path.stem.replace('-', ' ').replace('_', ' ').title()
    except Exception:
        return notebook_path.stem.replace('-', ' ').replace('_', ' ').title()


def slugify_to_title(slug: str) -> str:
    """Convert a slug to a readable title."""
    # Handle common abbreviations
    abbreviations = {
        'vqe': 'VQE',
        'qaoa': 'QAOA',
        'chsh': 'CHSH',
        'ai': 'AI',
        'ibm': 'IBM',
        'qec': 'QEC',
        'qml': 'QML',
    }

    words = slug.replace('-', ' ').replace('_', ' ').split()
    result = []
    for word in words:
        if word.lower() in abbreviations:
            result.append(abbreviations[word.lower()])
        else:
            result.append(word.capitalize())

    return ' '.join(result)


# ============================================================================
# TUTORIALS GENERATION
# ============================================================================

def find_tutorials(base_path: Path) -> List[Tuple[str, Path]]:
    """Find all tutorial notebooks and extract their titles."""
    tutorials_dir = base_path / "docs" / "tutorials"

    if not tutorials_dir.exists():
        print(f"Error: Tutorials directory not found: {tutorials_dir}")
        return []

    tutorials = []
    for notebook_path in sorted(tutorials_dir.glob("*.ipynb")):
        title = extract_notebook_title(notebook_path)
        tutorials.append((title, notebook_path))

    return tutorials


def generate_tutorials_welcome(base_path: Path) -> bool:
    """Generate WELCOME-tutorials.ipynb with links to all tutorials."""
    tutorials = find_tutorials(base_path)

    if not tutorials:
        print("No tutorials found!")
        return False

    # Build markdown content
    header = ATTRIBUTION_HEADER.format(title="IBM Quantum Tutorials")

    intro = f"""These tutorials are from the official [IBM Quantum Learning](https://learning.quantum.ibm.com/) platform.

**{len(tutorials)} tutorials available** covering quantum algorithms, optimization, error mitigation, and more.

To run a tutorial, click on the link below or use the file browser on the left.

"""

    # Group tutorials alphabetically
    tutorial_list = "## Available Tutorials\n\n"
    for title, path in tutorials:
        # Create relative link to notebook
        rel_path = path.relative_to(base_path / "docs" / "tutorials")
        tutorial_list += f"- [{title}](docs/tutorials/{rel_path})\n"

    # Create notebook
    cells = [
        create_markdown_cell(header + intro + tutorial_list)
    ]

    notebook = create_notebook(cells)
    output_path = base_path / "WELCOME-tutorials.ipynb"

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)

    print(f"Created {output_path} with {len(tutorials)} tutorials")
    return True


# ============================================================================
# COURSES GENERATION
# ============================================================================

def find_courses(base_path: Path) -> List[Tuple[str, Path, List[Tuple[str, Path]]]]:
    """Find all courses and their notebooks."""
    courses_dir = base_path / "learning" / "courses"

    if not courses_dir.exists():
        print(f"Error: Courses directory not found: {courses_dir}")
        return []

    courses = []
    for course_dir in sorted(courses_dir.iterdir()):
        if not course_dir.is_dir():
            continue

        course_title = slugify_to_title(course_dir.name)

        # Find all notebooks in the course (including subdirectories)
        notebooks = []
        for notebook_path in sorted(course_dir.rglob("*.ipynb")):
            title = extract_notebook_title(notebook_path)
            notebooks.append((title, notebook_path))

        if notebooks:  # Only include courses with notebooks
            courses.append((course_title, course_dir, notebooks))

    return courses


def generate_courses_welcome(base_path: Path) -> bool:
    """Generate WELCOME-courses.ipynb with links to all courses."""
    courses = find_courses(base_path)

    if not courses:
        print("No courses found!")
        return False

    # Count total notebooks
    total_notebooks = sum(len(notebooks) for _, _, notebooks in courses)

    # Build markdown content
    header = ATTRIBUTION_HEADER.format(title="IBM Quantum Courses")

    intro = f"""These courses are from the official [IBM Quantum Learning](https://learning.quantum.ibm.com/) platform.

**{len(courses)} courses available** with **{total_notebooks} notebooks** covering quantum information, algorithms, machine learning, and more.

Each course contains multiple lessons organized in a structured learning path.

"""

    # Build course list with their notebooks
    course_content = "## Available Courses\n\n"

    for course_title, course_dir, notebooks in courses:
        rel_course_path = course_dir.relative_to(base_path / "learning" / "courses")
        course_content += f"### {course_title}\n\n"
        course_content += f"*{len(notebooks)} notebooks*\n\n"

        for title, notebook_path in notebooks:
            rel_path = notebook_path.relative_to(base_path / "learning" / "courses")
            course_content += f"- [{title}](learning/courses/{rel_path})\n"

        course_content += "\n"

    # Create notebook
    cells = [
        create_markdown_cell(header + intro + course_content)
    ]

    notebook = create_notebook(cells)
    output_path = base_path / "WELCOME-courses.ipynb"

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)

    print(f"Created {output_path} with {len(courses)} courses ({total_notebooks} notebooks)")
    return True


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate WELCOME notebooks for IBM Quantum Tutorials and Courses"
    )
    parser.add_argument(
        "--path",
        type=str,
        required=True,
        help="Path to the cloned ibm-quantum-learning directory"
    )
    parser.add_argument(
        "--tutorials",
        action="store_true",
        help="Generate WELCOME-tutorials.ipynb"
    )
    parser.add_argument(
        "--courses",
        action="store_true",
        help="Generate WELCOME-courses.ipynb"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate both WELCOME notebooks"
    )

    args = parser.parse_args()

    base_path = Path(args.path).resolve()

    if not base_path.exists():
        print(f"Error: Path does not exist: {base_path}")
        sys.exit(1)

    # Default to --all if neither --tutorials nor --courses specified
    if not args.tutorials and not args.courses:
        args.all = True

    success = True

    if args.tutorials or args.all:
        if not generate_tutorials_welcome(base_path):
            success = False

    if args.courses or args.all:
        if not generate_courses_welcome(base_path):
            success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
