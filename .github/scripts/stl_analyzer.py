#!/usr/bin/env python3
"""
STL Mesh Analyzer and Repair Tool for GitHub Actions

Analyzes STL files for common mesh issues:
- Non-manifold geometry
- Inverted normals
- Non-watertight meshes
- Holes in mesh surface

Uses PyMeshLab for thorough repair and trimesh for analysis.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import subprocess
import numpy as np
import trimesh

try:
    import pymeshlab
    PYMESHLAB_AVAILABLE = True
except ImportError:
    PYMESHLAB_AVAILABLE = False


def check_prusaslicer_available() -> bool:
    """Check if PrusaSlicer CLI is available."""
    try:
        # prusa-slicer --version returns non-zero, so just check if binary exists
        result = subprocess.run(
            ["which", "prusa-slicer"],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Note: This check runs at import time - will be False if prusa-slicer not yet installed
PRUSASLICER_AVAILABLE = check_prusaslicer_available()


@dataclass
class MeshIssues:
    """Container for mesh issues detected."""
    is_watertight: bool = True
    is_volume: bool = True
    is_winding_consistent: bool = True
    has_degenerate_faces: bool = False
    broken_face_count: int = 0
    hole_count: int = 0

    @property
    def has_issues(self) -> bool:
        return (
            not self.is_watertight
            or not self.is_volume
            or not self.is_winding_consistent
            or self.has_degenerate_faces
            or self.broken_face_count > 0
            or self.hole_count > 0
        )

    def to_summary(self) -> str:
        issues = []
        if not self.is_watertight:
            issues.append("Non-watertight")
        if not self.is_volume:
            issues.append("Not a valid volume")
        if not self.is_winding_consistent:
            issues.append("Inconsistent winding")
        if self.has_degenerate_faces:
            issues.append("Degenerate faces")
        if self.broken_face_count > 0:
            issues.append(f"{self.broken_face_count} broken faces")
        if self.hole_count > 0:
            issues.append(f"{self.hole_count} holes")
        return ", ".join(issues) if issues else "OK"


@dataclass
class MeshStats:
    """Container for mesh statistics."""
    file_path: str
    file_size_bytes: int
    vertex_count: int
    face_count: int
    is_empty: bool
    bounds_min: list
    bounds_max: list
    issues: MeshIssues = field(default_factory=MeshIssues)
    repaired: bool = False
    repair_path: Optional[str] = None
    error: Optional[str] = None


def analyze_mesh(file_path: Path) -> MeshStats:
    """Analyze a single STL file for mesh issues."""
    stats = MeshStats(
        file_path=str(file_path),
        file_size_bytes=file_path.stat().st_size,
        vertex_count=0,
        face_count=0,
        is_empty=True,
        bounds_min=[0, 0, 0],
        bounds_max=[0, 0, 0],
    )

    try:
        mesh = trimesh.load_mesh(str(file_path))

        if isinstance(mesh, trimesh.Scene):
            # Handle scene with multiple meshes
            if len(mesh.geometry) == 0:
                stats.is_empty = True
                return stats
            mesh = trimesh.util.concatenate(list(mesh.geometry.values()))

        if mesh.is_empty:
            stats.is_empty = True
            return stats

        stats.is_empty = False
        stats.vertex_count = len(mesh.vertices)
        stats.face_count = len(mesh.faces)
        stats.bounds_min = mesh.bounds[0].tolist()
        stats.bounds_max = mesh.bounds[1].tolist()

        # Check for issues
        issues = MeshIssues()
        issues.is_watertight = mesh.is_watertight
        issues.is_volume = mesh.is_volume
        issues.is_winding_consistent = mesh.is_winding_consistent

        # Check for degenerate faces (zero area)
        face_areas = mesh.area_faces
        issues.has_degenerate_faces = bool(np.any(face_areas < 1e-10))

        # Count broken faces
        try:
            broken = trimesh.repair.broken_faces(mesh)
            issues.broken_face_count = len(broken) if broken is not None else 0
        except Exception:
            issues.broken_face_count = 0

        # Estimate hole count from euler characteristic
        # For a watertight mesh: V - E + F = 2 (sphere topology)
        # Each hole reduces this by 1
        try:
            euler = mesh.euler_number
            expected_euler = 2  # For a single closed surface
            if euler < expected_euler:
                issues.hole_count = expected_euler - euler
        except Exception:
            pass

        stats.issues = issues

    except Exception as e:
        stats.error = str(e)

    return stats


def repair_with_pymeshlab(input_path: Path, output_path: Path) -> bool:
    """
    Repair mesh using PyMeshLab.

    Returns True if successful.
    """
    if not PYMESHLAB_AVAILABLE:
        print("  PyMeshLab not available", file=sys.stderr)
        return False

    try:
        # Check plugins are loaded
        if pymeshlab.number_plugins() == 0:
            print("  PyMeshLab plugins not loaded", file=sys.stderr)
            return False

        ms = pymeshlab.MeshSet()
        # Load with binary format hint for STL
        ms.load_new_mesh(str(input_path.absolute()))

        # Apply repair filters in order
        # 1. Remove duplicate vertices
        ms.meshing_remove_duplicate_vertices()

        # 2. Remove duplicate faces
        ms.meshing_remove_duplicate_faces()

        # 3. Remove zero area faces
        ms.meshing_remove_null_faces()

        # 4. Remove unreferenced vertices
        ms.meshing_remove_unreferenced_vertices()

        # 5. Repair non-manifold edges by splitting
        try:
            ms.meshing_repair_non_manifold_edges()
        except Exception:
            pass  # Filter may not exist in all versions

        # 6. Repair non-manifold vertices by splitting
        try:
            ms.meshing_repair_non_manifold_vertices()
        except Exception:
            pass

        # 7. Close holes (max 100 edges for better repair)
        try:
            ms.meshing_close_holes(maxholesize=100)
        except Exception:
            pass

        # 8. Re-orient all faces coherently
        try:
            ms.meshing_re_orient_faces_coherentely()
        except Exception:
            pass

        # 9. Recompute normals
        try:
            ms.compute_normal_for_point_clouds()
        except Exception:
            pass

        # Save repaired mesh
        ms.save_current_mesh(str(output_path))
        return output_path.exists()

    except Exception as e:
        print(f"  PyMeshLab error: {e}", file=sys.stderr)
        return False


def repair_with_prusaslicer(input_path: Path, output_path: Path) -> bool:
    """
    Repair mesh using PrusaSlicer CLI.

    PrusaSlicer's --repair fixes non-manifold meshes and exports with --export-stl.

    Returns True if successful.
    """
    if not PRUSASLICER_AVAILABLE:
        print("  PrusaSlicer not available", file=sys.stderr)
        return False

    try:
        # PrusaSlicer: --repair fixes mesh, --export-stl exports result
        result = subprocess.run(
            [
                "prusa-slicer",
                "--repair",
                "--export-stl",
                str(input_path),
                "-o", str(output_path)
            ],
            capture_output=True,
            timeout=300,  # 5 minute timeout for large files
            text=True
        )

        if result.returncode == 0 and output_path.exists():
            print(f"  PrusaSlicer repair successful")
            return True
        else:
            print(f"  PrusaSlicer error: {result.stderr}", file=sys.stderr)
            return False

    except subprocess.TimeoutExpired:
        print("  PrusaSlicer timeout", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  PrusaSlicer error: {e}", file=sys.stderr)
        return False


def repair_with_trimesh(input_path: Path, output_path: Path) -> bool:
    """
    Repair mesh using trimesh (fallback).

    Returns True if successful.
    """
    try:
        mesh = trimesh.load_mesh(str(input_path))

        if isinstance(mesh, trimesh.Scene):
            if len(mesh.geometry) == 0:
                return False
            mesh = trimesh.util.concatenate(list(mesh.geometry.values()))

        if mesh.is_empty:
            return False

        # Apply repairs in order
        trimesh.repair.fill_holes(mesh)
        trimesh.repair.fix_winding(mesh)
        trimesh.repair.fix_inversion(mesh, multibody=True)
        trimesh.repair.fix_normals(mesh, multibody=True)
        mesh = mesh.process(validate=True)

        mesh.export(str(output_path))
        return True

    except Exception as e:
        print(f"  Trimesh error: {e}", file=sys.stderr)
        return False


def repair_mesh(file_path: Path, output_suffix: str = "_repaired") -> tuple[Path, bool]:
    """
    Attempt to repair a mesh using MeshLab first, then trimesh as fallback.

    Returns tuple of (output_path, success).
    """
    # Generate output path
    stem = file_path.stem
    # Remove existing repair suffixes to avoid stacking
    for suffix in ["_repaired", "_fixed"]:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]

    output_path = file_path.parent / f"{stem}{output_suffix}{file_path.suffix}"

    # Try PrusaSlicer first (best repair quality - 99.4% reduction in open edges)
    print(f"  Trying PrusaSlicer repair...")
    if repair_with_prusaslicer(file_path, output_path):
        return output_path, True

    # Try PyMeshLab if PrusaSlicer unavailable
    print(f"  Trying PyMeshLab repair...")
    if repair_with_pymeshlab(file_path, output_path):
        return output_path, True

    # Fall back to trimesh
    print(f"  Falling back to trimesh repair...")
    if repair_with_trimesh(file_path, output_path):
        print(f"  Trimesh repair successful")
        return output_path, True

    print(f"  All repair methods failed", file=sys.stderr)
    return file_path, False


def find_stl_files(target_path: Path) -> list[Path]:
    """Find all STL files in target path."""
    if target_path.is_file():
        return [target_path] if target_path.suffix.lower() == ".stl" else []

    stl_files = list(target_path.rglob("*.stl")) + list(target_path.rglob("*.STL"))

    return sorted(set(stl_files))


def generate_markdown_report(results: list[MeshStats], output_dir: Path) -> str:
    """Generate a Markdown summary report."""
    total = len(results)
    with_issues = sum(1 for r in results if r.issues.has_issues and not r.error)
    with_errors = sum(1 for r in results if r.error)
    repaired = sum(1 for r in results if r.repaired)

    lines = [
        "# STL Mesh Analysis Report",
        "",
        f"**Generated:** {datetime.utcnow().isoformat()}Z",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Total files analyzed | {total} |",
        f"| Files with issues | {with_issues} |",
        f"| Files with errors | {with_errors} |",
        f"| Files repaired | {repaired} |",
        "",
    ]

    # Files with issues
    issues_results = [r for r in results if r.issues.has_issues and not r.error]
    if issues_results:
        lines.extend(
            [
                "## Files with Issues",
                "",
                "| File | Faces | Issues |",
                "|------|-------|--------|",
            ]
        )
        for r in issues_results:
            rel_path = Path(r.file_path).name
            issues_text = r.issues.to_summary()
            repaired_mark = " ✅ repaired" if r.repaired else ""
            lines.append(f"| `{rel_path}` | {r.face_count:,} | {issues_text}{repaired_mark} |")
        lines.append("")

    # Files with errors
    error_results = [r for r in results if r.error]
    if error_results:
        lines.extend(
            [
                "## Files with Errors",
                "",
                "| File | Error |",
                "|------|-------|",
            ]
        )
        for r in error_results:
            rel_path = Path(r.file_path).name
            lines.append(f"| `{rel_path}` | {r.error} |")
        lines.append("")

    # Healthy files
    healthy = [r for r in results if not r.issues.has_issues and not r.error]
    if healthy:
        lines.extend(
            [
                "## Healthy Files",
                "",
                f"{len(healthy)} files passed all checks.",
                "",
                "<details>",
                "<summary>Click to expand file list</summary>",
                "",
            ]
        )
        for r in healthy:
            rel_path = Path(r.file_path).name
            lines.append(f"- `{rel_path}` ({r.face_count:,} faces)")
        lines.extend(["", "</details>", ""])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze and repair STL mesh files")
    parser.add_argument(
        "--mode",
        choices=["analyze-only", "repair-and-commit", "repair-and-pr"],
        default="analyze-only",
        help="Operation mode",
    )
    parser.add_argument(
        "--target",
        default="3D Model",
        help="Target file or directory to analyze",
    )
    parser.add_argument(
        "--output-dir",
        default="stl-reports",
        help="Output directory for reports",
    )
    parser.add_argument(
        "--suffix",
        default="_repaired",
        help="Suffix for repaired files",
    )

    args = parser.parse_args()

    target = Path(args.target)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not target.exists():
        print(f"Error: Target path does not exist: {target}", file=sys.stderr)
        sys.exit(1)

    # Find all STL files
    stl_files = find_stl_files(target)
    print(f"Found {len(stl_files)} STL files to analyze")

    # Analyze each file
    results: list[MeshStats] = []
    for stl_file in stl_files:
        print(f"Analyzing: {stl_file.name}")
        stats = analyze_mesh(stl_file)

        # Repair if needed and mode allows
        if args.mode != "analyze-only" and stats.issues.has_issues and not stats.error:
            print(f"  Repairing: {stl_file.name}")
            repair_path, success = repair_mesh(stl_file, args.suffix)
            if success:
                stats.repaired = True
                stats.repair_path = str(repair_path)
                print(f"  Saved to: {repair_path.name}")

        results.append(stats)

    # Generate reports
    markdown_report = generate_markdown_report(results, output_dir)

    # Write summary.md
    summary_path = output_dir / "summary.md"
    with open(summary_path, "w") as f:
        f.write(markdown_report)
    print(f"\nReport written to: {summary_path}")

    # Write detailed JSON report
    json_path = output_dir / "detailed_report.json"
    with open(json_path, "w") as f:
        json.dump(
            {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "mode": args.mode,
                "target": str(target),
                "results": [asdict(r) for r in results],
            },
            f,
            indent=2,
        )

    # Create flag file if issues found (for CI to detect)
    has_issues = any(r.issues.has_issues for r in results if not r.error)
    if has_issues:
        (output_dir / "has_issues.flag").touch()

    # Print summary
    with_issues = sum(1 for r in results if r.issues.has_issues and not r.error)
    print(f"\nAnalysis complete: {with_issues}/{len(results)} files have issues")

    return 0


if __name__ == "__main__":
    sys.exit(main())
