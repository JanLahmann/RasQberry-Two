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
> See [LICENSE](LICENSE) and [LICENSE-DOCS](LICENSE-DOCS) files for full license terms.

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
    """Create a markdown cell.

    Jupyter notebook format expects source as either:
    - A single string with \\n characters
    - An array of strings where each line ends with \\n (except last)
    """
    # Split into lines and add \n back to each line except the last
    lines = source.split('\n')
    source_lines = [line + '\n' for line in lines[:-1]]
    if lines[-1]:  # Add last line without trailing newline
        source_lines.append(lines[-1])

    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source_lines
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
# TOC.JSON PARSING
# ============================================================================

def parse_tutorials_toc_json(toc_path: Path) -> List[Dict]:
    """Parse the tutorials _toc.json file to extract section structure.

    Returns a list of sections, each containing:
    - title: Section title
    - subsections: List of subsections, each containing:
        - title: Subsection title
        - tutorials: List of (title, slug, source_dir) tuples
    - tutorials: List of (title, slug, source_dir) tuples (for sections without subsections)

    source_dir is 'docs/tutorials' for most, 'docs/guides' for hello-world.
    """
    if not toc_path.exists():
        print(f"Warning: _toc.json not found at {toc_path}")
        return []

    with open(toc_path, 'r', encoding='utf-8') as f:
        toc = json.load(f)

    sections = []

    # Navigate to children (top-level sections)
    for child in toc.get('children', []):
        section_title = child.get('title', '')

        # Skip "Overview" entries
        if child.get('url') == '/docs/tutorials':
            continue

        section = {
            'title': section_title,
            'subsections': [],
            'tutorials': []
        }

        # Process children of this section
        for item in child.get('children', []):
            if 'children' in item:
                # This is a subsection with tutorials
                subsection = {
                    'title': item.get('title', ''),
                    'tutorials': []
                }
                for tutorial in item.get('children', []):
                    if 'url' in tutorial:
                        title = tutorial.get('title', '')
                        url = tutorial.get('url', '')
                        # Extract slug from URL like /docs/tutorials/chsh-inequality
                        slug = url.split('/')[-1] if url else ''
                        if slug:
                            subsection['tutorials'].append((title, slug, 'docs/tutorials'))

                if subsection['tutorials']:
                    section['subsections'].append(subsection)
            elif 'url' in item:
                # Direct tutorial in section
                title = item.get('title', '')
                url = item.get('url', '')
                slug = url.split('/')[-1] if url else ''
                # Skip "Overview" entries
                if slug and slug != 'tutorials' and not item.get('useDivider'):
                    section['tutorials'].append((title, slug, 'docs/tutorials'))

        if section['subsections'] or section['tutorials']:
            sections.append(section)

    return sections


def inject_hello_world(sections: List[Dict], base_path: Path) -> List[Dict]:
    """Inject 'Hello world' tutorial into the 'Get started' section.

    The hello-world.ipynb is in docs/guides/ but should appear in tutorials
    as the first item in 'Get started', matching the IBM website.
    """
    hello_world_path = base_path / "docs" / "guides" / "hello-world.ipynb"

    if not hello_world_path.exists():
        print("Note: hello-world.ipynb not found in docs/guides/, skipping injection")
        return sections

    # Find or create "Get started" section
    get_started = None
    for section in sections:
        if section['title'] == 'Get started':
            get_started = section
            break

    if get_started is None:
        # Create "Get started" section if it doesn't exist
        get_started = {
            'title': 'Get started',
            'subsections': [],
            'tutorials': []
        }
        sections.insert(0, get_started)

    # Insert hello-world at the beginning of tutorials
    # Format: (title, slug, source_dir)
    hello_world_entry = ('Hello world', 'hello-world', 'docs/guides')

    # Check if already present
    existing_slugs = [t[1] for t in get_started['tutorials']]
    if 'hello-world' not in existing_slugs:
        get_started['tutorials'].insert(0, hello_world_entry)
        print("Injected 'Hello world' into Get started section")

    return sections


def find_tutorial_notebook(base_path: Path, slug: str, source_dir: str = 'docs/tutorials') -> Optional[Path]:
    """Find the notebook file for a given tutorial slug.

    Args:
        base_path: Root path of the ibm-quantum-learning repo
        slug: Tutorial slug (e.g., 'chsh-inequality')
        source_dir: Directory containing the notebook (e.g., 'docs/tutorials' or 'docs/guides')
    """
    notebook_path = base_path / source_dir / f"{slug}.ipynb"
    if notebook_path.exists():
        return notebook_path
    return None


def parse_index_mdx_descriptions(mdx_path: Path) -> Dict[str, str]:
    """Parse index.mdx to extract section and subsection descriptions.

    Returns a dict mapping section/subsection titles to their descriptions.
    """
    if not mdx_path.exists():
        print(f"Note: index.mdx not found at {mdx_path}")
        return {}

    with open(mdx_path, 'r', encoding='utf-8') as f:
        content = f.read()

    descriptions = {}

    # Parse main sections: ## Section Title\n\nDescription text
    import re

    # Match section headers and capture text until next ## or <details> or * [
    section_pattern = r'^## ([^\n]+)\n\n((?:(?!^## |^\* |\<details\>).)+)'
    for match in re.finditer(section_pattern, content, re.MULTILINE | re.DOTALL):
        title = match.group(1).strip()
        desc = match.group(2).strip()
        # Clean up the description - remove markdown links, keep just text
        desc = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', desc)
        if desc and not desc.startswith('<') and not desc.startswith('*'):
            descriptions[title] = desc

    # Parse subsection descriptions from <details><summary>**Title**</summary>
    subsection_pattern = r'<summary>\*\*([^*]+)\*\*</summary>\n\n((?:(?!\* \[).)+)'
    for match in re.finditer(subsection_pattern, content, re.MULTILINE | re.DOTALL):
        title = match.group(1).strip()
        desc = match.group(2).strip()
        # Clean up
        desc = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', desc)
        if desc:
            descriptions[title] = desc

    return descriptions


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
    """Generate WELCOME-tutorials.ipynb with links to all tutorials.

    Uses _toc.json to preserve the official section structure from IBM Quantum.
    Injects 'Hello world' from docs/guides/ into Get started section.
    Parses index.mdx for section descriptions.
    Falls back to alphabetical listing if _toc.json is not available.
    """
    tutorials_dir = base_path / "docs" / "tutorials"
    toc_json = tutorials_dir / "_toc.json"
    index_mdx = tutorials_dir / "index.mdx"

    # Try to parse the _toc.json structure
    sections = parse_tutorials_toc_json(toc_json)

    if sections:
        # Inject hello-world from docs/guides/ (like the website does)
        sections = inject_hello_world(sections, base_path)
        # Parse section descriptions from index.mdx
        descriptions = parse_index_mdx_descriptions(index_mdx)
        return generate_tutorials_welcome_structured(base_path, sections, descriptions)
    else:
        return generate_tutorials_welcome_flat(base_path)


def generate_tutorials_welcome_structured(base_path: Path, sections: List[Dict],
                                          descriptions: Optional[Dict[str, str]] = None) -> bool:
    """Generate WELCOME notebook using the structured sections from _toc.json.

    Args:
        base_path: Root path of the ibm-quantum-learning repo
        sections: Parsed section structure from _toc.json
        descriptions: Section/subsection descriptions from index.mdx
    """
    if descriptions is None:
        descriptions = {}

    # Count total tutorials and verify they exist
    total_tutorials = 0
    missing_tutorials = []

    for section in sections:
        for title, slug, source_dir in section.get('tutorials', []):
            if find_tutorial_notebook(base_path, slug, source_dir):
                total_tutorials += 1
            else:
                missing_tutorials.append(slug)
        for subsection in section.get('subsections', []):
            for title, slug, source_dir in subsection.get('tutorials', []):
                if find_tutorial_notebook(base_path, slug, source_dir):
                    total_tutorials += 1
                else:
                    missing_tutorials.append(slug)

    if total_tutorials == 0:
        print("No tutorials found!")
        return False

    if missing_tutorials:
        print(f"Warning: {len(missing_tutorials)} tutorials referenced in _toc.json not found: {missing_tutorials[:5]}...")

    # Build markdown content
    header = ATTRIBUTION_HEADER.format(title="IBM Quantum Tutorials")

    intro = f"""These tutorials are from the official [IBM Quantum Learning](https://learning.quantum.ibm.com/) platform.

**{total_tutorials} tutorials available** organized by topic.

To run a tutorial, click on the link below or use the file browser on the left.

"""

    # Build structured content
    content = ""

    for section in sections:
        content += f"## {section['title']}\n\n"

        # Add section description if available
        if section['title'] in descriptions:
            content += f"{descriptions[section['title']]}\n\n"

        # Direct tutorials in section (no subsections)
        if section.get('tutorials'):
            for title, slug, source_dir in section['tutorials']:
                notebook = find_tutorial_notebook(base_path, slug, source_dir)
                if notebook:
                    content += f"- [{title}]({source_dir}/{slug}.ipynb)\n"
            content += "\n"

        # Subsections (collapsible)
        for subsection in section.get('subsections', []):
            content += f"<details>\n<summary><strong>{subsection['title']}</strong></summary>\n\n"

            # Add subsection description if available
            if subsection['title'] in descriptions:
                content += f"{descriptions[subsection['title']]}\n\n"

            for title, slug, source_dir in subsection['tutorials']:
                notebook = find_tutorial_notebook(base_path, slug, source_dir)
                if notebook:
                    content += f"- [{title}]({source_dir}/{slug}.ipynb)\n"

            content += "\n</details>\n\n"

    # Create notebook
    cells = [
        create_markdown_cell(header + intro + content)
    ]

    notebook = create_notebook(cells)
    output_path = base_path / "WELCOME-tutorials.ipynb"

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)

    print(f"Created {output_path} with {total_tutorials} tutorials in {len(sections)} sections")
    return True


def generate_tutorials_welcome_flat(base_path: Path) -> bool:
    """Generate WELCOME notebook with flat alphabetical listing (fallback)."""
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

IBM_COURSES_URL = "https://quantum.cloud.ibm.com/learning/en/courses"


def fetch_courses_structure_from_website() -> List[Dict]:
    """Fetch course categories and ordering from the IBM Quantum Learning website.

    Returns list of categories, each with:
    - title: Category name
    - courses: List of course slugs in order
    """
    import urllib.request
    import urllib.error
    import re

    try:
        req = urllib.request.Request(
            IBM_COURSES_URL,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; RasQberry/1.0)'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"Warning: Could not fetch course structure from website: {e}")
        return []

    categories = []

    # Parse categories and courses from the HTML
    # Look for category headers and course links
    # Categories are typically in sections with headers like "Foundations of quantum computing"
    category_pattern = r'<h[23][^>]*>([^<]+)</h[23]>'
    course_link_pattern = r'/learning/courses/([a-z0-9-]+)'

    # Split by category headers and extract courses
    parts = re.split(category_pattern, html, flags=re.IGNORECASE)

    current_category = None
    for i, part in enumerate(parts):
        # Check if this looks like a category title
        if i % 2 == 1:  # Odd indices are captured groups (category names)
            title = part.strip()
            # Accept category titles that look like section headers
            if title and len(title) < 100 and not title.startswith('IBM'):
                current_category = {'title': title, 'courses': []}
                categories.append(current_category)
        elif current_category is not None:
            # Extract course slugs from this section
            course_slugs = re.findall(course_link_pattern, part)
            # Remove duplicates while preserving order
            seen = set()
            for slug in course_slugs:
                if slug not in seen:
                    seen.add(slug)
                    current_category['courses'].append(slug)

    # Filter out categories with no courses
    categories = [c for c in categories if c['courses']]

    if categories:
        print(f"Fetched {len(categories)} categories with {sum(len(c['courses']) for c in categories)} courses from website")

    return categories


def parse_course_toc_json(toc_path: Path) -> List[Dict]:
    """Parse a course's _toc.json to get section and lesson ordering.

    Returns list of sections with proper ordering from the TOC.
    """
    if not toc_path.exists():
        return []

    with open(toc_path, 'r', encoding='utf-8') as f:
        toc = json.load(f)

    sections = []

    # Navigate to "Lessons" children (skip Overview)
    for child in toc.get('children', []):
        if child.get('title') == 'Lessons':
            for section in child.get('children', []):
                if 'children' in section:
                    # Section with lessons
                    section_data = {
                        'title': section.get('title', ''),
                        'lessons': []
                    }
                    for lesson in section.get('children', []):
                        if 'url' in lesson:
                            title = lesson.get('title', '')
                            url_parts = lesson.get('url', '').split('/')
                            if len(url_parts) >= 2:
                                lesson_slug = url_parts[-1]
                                section_slug = url_parts[-2]
                                section_data['lessons'].append({
                                    'title': title,
                                    'section_slug': section_slug,
                                    'lesson_slug': lesson_slug
                                })
                    if section_data['lessons']:
                        sections.append(section_data)

    return sections


def parse_course_description(index_mdx_path: Path) -> str:
    """Extract course description from index.mdx file.

    Extracts the main overview content until "Recommended background" or "Exam" sections.
    """
    if not index_mdx_path.exists():
        return ""

    with open(index_mdx_path, 'r', encoding='utf-8') as f:
        content = f.read()

    import re

    # Find content after # Overview, skip image line, get content until ## Recommended or ## Exam
    match = re.search(
        r'^# Overview\n\n(?:!\[.*?\]\(.*?\)\n\n)?(.*?)(?=\n## Recommended|\n## Exam|\Z)',
        content, re.MULTILINE | re.DOTALL
    )
    if match:
        desc = match.group(1).strip()
        # Clean up markdown formatting
        desc = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', desc)  # Remove links but keep text
        desc = re.sub(r'\*([^*]+)\*', r'\1', desc)  # Remove italics
        desc = re.sub(r'\n- ', '\n• ', desc)  # Convert markdown lists to bullet points
        # Truncate if too long (but allow more content now)
        if len(desc) > 1500:
            desc = desc[:1497] + "..."
        return desc

    return ""


def find_courses(base_path: Path) -> List[Tuple[str, Path, Dict[str, List[Tuple[str, Path]]]]]:
    """Find all courses and their notebooks, preserving section structure.

    Returns list of (course_title, course_dir, sections_dict) where sections_dict
    maps section names to lists of (notebook_title, notebook_path) tuples.
    For courses without sections, notebooks are grouped under "Lessons".
    """
    courses_dir = base_path / "learning" / "courses"

    if not courses_dir.exists():
        print(f"Error: Courses directory not found: {courses_dir}")
        return []

    courses = []
    for course_dir in sorted(courses_dir.iterdir()):
        if not course_dir.is_dir():
            continue

        course_title = slugify_to_title(course_dir.name)

        # Find all sections (subdirectories) in the course
        sections = {}

        # First, check for notebooks directly in the course directory (no sections)
        direct_notebooks = []
        for notebook_path in sorted(course_dir.glob("*.ipynb")):
            if '.ipynb_checkpoints' in str(notebook_path):
                continue
            title = extract_notebook_title(notebook_path)
            direct_notebooks.append((title, notebook_path))

        if direct_notebooks:
            # Course has notebooks directly in folder (no section structure)
            sections["Lessons"] = direct_notebooks
        else:
            # Course has section subdirectories
            for section_dir in sorted(course_dir.iterdir()):
                if not section_dir.is_dir():
                    continue
                # Skip checkpoint directories
                if section_dir.name.startswith('.'):
                    continue

                section_title = slugify_to_title(section_dir.name)
                notebooks = []

                for notebook_path in sorted(section_dir.glob("*.ipynb")):
                    # Skip checkpoint files
                    if '.ipynb_checkpoints' in str(notebook_path):
                        continue
                    title = extract_notebook_title(notebook_path)
                    notebooks.append((title, notebook_path))

                if notebooks:
                    sections[section_title] = notebooks

        if sections:  # Only include courses with content
            courses.append((course_title, course_dir, sections))

    return courses


def _generate_course_content(base_path: Path, course_dir: Path) -> Tuple[str, int]:
    """Generate markdown content for a single course.

    Uses _toc.json for proper section/lesson ordering.
    Falls back to directory scanning if _toc.json not available.

    Returns (markdown_content, notebook_count).
    """
    course_slug = course_dir.name
    toc_path = course_dir / "_toc.json"
    index_mdx = course_dir / "index.mdx"

    # Get course title from _toc.json or generate from slug
    course_title = slugify_to_title(course_slug)
    if toc_path.exists():
        with open(toc_path, 'r', encoding='utf-8') as f:
            toc = json.load(f)
            course_title = toc.get('title', course_title)

    # Get description
    course_desc = parse_course_description(index_mdx)

    # Get sections from _toc.json
    toc_sections = parse_course_toc_json(toc_path)

    content = ""
    notebook_count = 0

    # URL to online course
    online_url = f"https://learning.quantum.ibm.com/course/{course_slug}"

    if toc_sections:
        # Use _toc.json ordering
        content += f"<details>\n<summary><strong>{course_title}</strong> — <em>{len(toc_sections)} sections</em></summary>\n\n"

        if course_desc:
            content += f"{course_desc}\n\n"

        content += f"[View full course online]({online_url})\n\n"

        for section in toc_sections:
            section_title = section['title']
            lessons = section['lessons']

            if len(toc_sections) > 1:
                content += f"<details>\n<summary><strong>{section_title}</strong></summary>\n\n"

            for lesson in lessons:
                # Find the notebook file
                notebook_path = course_dir / lesson['section_slug'] / f"{lesson['lesson_slug']}.ipynb"
                if notebook_path.exists():
                    rel_path = notebook_path.relative_to(base_path / "learning" / "courses")
                    content += f"- [{lesson['title']}](learning/courses/{rel_path})\n"
                    notebook_count += 1

            if len(toc_sections) > 1:
                content += "\n</details>\n\n"
            else:
                content += "\n"

        content += "</details>\n\n---\n\n"
    else:
        # Fallback: scan directory
        sections = {}

        # Check for direct notebooks
        direct_notebooks = list(course_dir.glob("*.ipynb"))
        direct_notebooks = [p for p in direct_notebooks if '.ipynb_checkpoints' not in str(p)]

        if direct_notebooks:
            sections["Lessons"] = sorted(direct_notebooks)
        else:
            # Scan subdirectories
            for section_dir in sorted(course_dir.iterdir()):
                if section_dir.is_dir() and not section_dir.name.startswith('.'):
                    notebooks = list(section_dir.glob("*.ipynb"))
                    notebooks = [p for p in notebooks if '.ipynb_checkpoints' not in str(p)]
                    if notebooks:
                        sections[slugify_to_title(section_dir.name)] = sorted(notebooks)

        if sections:
            section_count = len(sections)
            nb_count = sum(len(nbs) for nbs in sections.values())

            content += f"<details>\n<summary><strong>{course_title}</strong> — <em>{section_count} sections, {nb_count} notebooks</em></summary>\n\n"

            if course_desc:
                content += f"{course_desc}\n\n"

            content += f"[View full course online]({online_url})\n\n"

            for section_title, notebooks in sections.items():
                if len(sections) > 1:
                    content += f"<details>\n<summary><strong>{section_title}</strong></summary>\n\n"

                for notebook_path in notebooks:
                    title = extract_notebook_title(notebook_path)
                    rel_path = notebook_path.relative_to(base_path / "learning" / "courses")
                    content += f"- [{title}](learning/courses/{rel_path})\n"
                    notebook_count += 1

                if len(sections) > 1:
                    content += "\n</details>\n\n"
                else:
                    content += "\n"

            content += "</details>\n\n---\n\n"
        else:
            # MDX-only course (no notebooks) - show with link to online version
            mdx_files = list(course_dir.glob("*.mdx"))
            mdx_files = [f for f in mdx_files if f.name not in ('index.mdx', 'exam.mdx', '_toc.json')]

            if mdx_files or index_mdx.exists():
                content += f"<details>\n<summary><strong>{course_title}</strong> — <em>online reading</em></summary>\n\n"

                if course_desc:
                    content += f"{course_desc}\n\n"

                content += f"*This is a text-based course. View it online:*\n"
                content += f"- [{course_title}]({online_url})\n"
                content += "\n</details>\n\n---\n\n"
                # Don't count notebooks, but return non-empty content

    return content, notebook_count


def generate_courses_welcome(base_path: Path) -> bool:
    """Generate WELCOME-courses.ipynb with links to all courses.

    Fetches category structure from IBM website for proper ordering.
    Uses each course's _toc.json for section/lesson ordering.
    Falls back to alphabetical listing if fetch fails.
    """
    courses_dir = base_path / "learning" / "courses"

    if not courses_dir.exists():
        print(f"Error: Courses directory not found: {courses_dir}")
        return False

    # Get available courses on disk
    available_courses = {d.name: d for d in courses_dir.iterdir() if d.is_dir()}
    if not available_courses:
        print("No courses found!")
        return False

    # Fetch category structure from website
    categories = fetch_courses_structure_from_website()

    # Build markdown content
    header = ATTRIBUTION_HEADER.format(title="IBM Quantum Courses")

    total_courses = 0
    total_notebooks = 0
    course_content = ""

    if categories:
        # Use fetched structure
        for category in categories:
            category_courses = []
            for course_slug in category['courses']:
                if course_slug in available_courses:
                    category_courses.append(course_slug)

            if not category_courses:
                continue

            course_content += f"## {category['title']}\n\n"

            for course_slug in category_courses:
                course_dir = available_courses[course_slug]
                content, notebook_count = _generate_course_content(base_path, course_dir)
                if content:
                    course_content += content
                    total_courses += 1
                    total_notebooks += notebook_count
                # Remove from available so we track uncategorized
                del available_courses[course_slug]

        # Add any uncategorized courses
        if available_courses:
            course_content += "## Other Courses\n\n"
            for course_slug in sorted(available_courses.keys()):
                course_dir = available_courses[course_slug]
                content, notebook_count = _generate_course_content(base_path, course_dir)
                if content:
                    course_content += content
                    total_courses += 1
                    total_notebooks += notebook_count
    else:
        # Fallback: alphabetical listing
        print("Using alphabetical course listing (could not fetch from website)")
        course_content += "## Available Courses\n\n"
        for course_slug in sorted(available_courses.keys()):
            course_dir = available_courses[course_slug]
            content, notebook_count = _generate_course_content(base_path, course_dir)
            if content:
                course_content += content
                total_courses += 1
                total_notebooks += notebook_count

    intro = f"""These courses are from the official [IBM Quantum Learning](https://learning.quantum.ibm.com/) platform.

**{total_courses} courses available** with **{total_notebooks} notebooks** covering quantum information, algorithms, machine learning, and more.

Each course contains multiple lessons organized in a structured learning path.

"""

    # Create notebook
    cells = [
        create_markdown_cell(header + intro + course_content)
    ]

    notebook = create_notebook(cells)
    output_path = base_path / "WELCOME-courses.ipynb"

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)

    print(f"Created {output_path} with {total_courses} courses ({total_notebooks} notebooks)")
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
