#!/usr/bin/env python3
"""Shared helpers for the RasQberry parametric (build123d) models.

Used by the part scripts in wall/, RTE/ and cryostat/. Keep this module
free of model-specific parameters: everything here takes its numbers as
arguments. The one exception is PARTS: where each rebuilt part is written.

All dimensions in mm.  Requires: build123d (pip install build123d)
"""
from pathlib import Path

import rqb_params

from build123d import (
    Box, Color, Compound, Cylinder, Location, Mesher, Plane, Polygon, Pos,
    RectangleRounded, Rot, Shape, Solid, export_step, export_stl, extrude,
)

# ---------------------------------------------------------------------------
# Output layout
# ---------------------------------------------------------------------------

# Generated files go to ../print/ (`3D Model/print/`), in the same part
# folders as the originals in ../originals/ and under the same file names.
# Jan's modifications sit next to the part they modify; the no-floor
# versions carry a "-no-floor" suffix.
OUTPUT = Path(__file__).resolve().parent.parent / "print"
PARTS = {
    "R2_Wall-Base": "wall/R2_Wall-Base",
    "R2_Wall-Back": "wall/R2_Wall-Back",
    "R2_Wall-Back+13": "wall/R2_Wall-Back+13",
    "R2_Wall-Lid": "wall/R2_Wall-Lid",
    "R2_NarrowServerSingleLid": "RTE/R2_NarrowServerSingleLid",
    "R2_ChandelierSingle": "cryostat/R2_ChandelierSingle",
    "R2_CryoLid-Simple": "cryostat/R2_CryoLid-Simple",
    "R2_NewDoor": "cryostat/R2_NewDoor",
    "R2_CryoStandaloneGamma": "cryostat/Standalone Version/R2_CryoStandaloneGamma",
    # Jan's modifications (originals: 3D Model - modifications - Jan/October 2025[ - no-floor])
    "R2_Wall-Base-jrl01-2": "wall/R2_Wall-Base-jrl01-2",
    "R2_Wall-Base-jrl01-2-nofloor": "wall/R2_Wall-Base-jrl01-2-no-floor",
    "RQB2-WallPanel-jrl02-2": "wall/RQB2-WallPanel-jrl02-2",
    "RQB2-R2_NarrowServerSingle-jrl02": "RTE/RQB2-R2_NarrowServerSingle-jrl02",
    "RQB2-Cryostat-jrl01": "cryostat/RQB2-Cryostat-jrl01",
    "RQB2-R2_CryoStandaloneGamma-jrl04":
        "cryostat/Standalone Version/RQB2-R2_CryoStandaloneGamma-jrl04",
    "RQB2-R2_CryoStandaloneGamma-jrl04-nofloor":
        "cryostat/Standalone Version/RQB2-R2_CryoStandaloneGamma-jrl04-no-floor",
}


def part_path(name, suffix="", root=None):
    """Path of part `name` under print/ (or `root`), without extension."""
    rel = Path(PARTS[name])
    return Path(root or OUTPUT) / rel.parent / (rel.name + suffix)


def export_part(solid, name, suffix="", root=None, **kw):
    """Export part `name` (a key of PARTS) to its place under print/
    (or under `root`). `suffix` is added to the file name, e.g. ".split-A"."""
    rel = Path(PARTS[name])
    export_all(solid, rel.name + suffix, Path(root or OUTPUT) / rel.parent, **kw)


# ---------------------------------------------------------------------------
# 2D / primitive helpers
# ---------------------------------------------------------------------------

def ccw_polygon(points):
    """Polygon face from 2D points, forced counter-clockwise.

    extrude() follows the face normal, so a clockwise polygon would extrude
    downwards. Forcing CCW makes the normal +Z and extrude() go up.
    """
    points = list(points)
    area2 = sum(x0 * y1 - x1 * y0
                for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]))
    if area2 < 0:
        points.reverse()
    return Polygon(*points, align=None)


def rounded_box(w, d, h, r, z0=0.0, centre=(0.0, 0.0)):
    """Box w x d x h with vertical edges rounded by r, centred on (x, y) =
    centre, standing on z = z0. r is clamped to the largest possible value."""
    r = max(0.0, min(r, w / 2 - 1e-3, d / 2 - 1e-3))
    if r <= 0:
        return Location((centre[0] - w / 2, centre[1] - d / 2, z0)) * Box(w, d, h, align=None)
    face = Pos(*centre) * RectangleRounded(w, d, r)
    return extrude(Plane.XY.offset(z0) * face, h)


def magnet_pocket(diameter, depth, clearance_d=0.25, clearance_h=-0.1):
    """Cylinder to subtract for a disc magnet (diameter x depth), with the
    usual FDM clearance: a bit wider, a touch shallower than nominal so the
    magnet sits flush or 0.1 mm proud for glue. Centred at the origin, axis
    +Z, spanning z = 0..depth."""
    d = diameter + clearance_d
    h = depth + clearance_h
    return Pos(0, 0, h / 2) * Cylinder(d / 2, h)


# ---------------------------------------------------------------------------
# Split + dovetail keys (generalised from the wall model)
# ---------------------------------------------------------------------------

def trapezoid_prism(cut_x, spec, grow=0.0, *, key_depth=9.0, key_neck=7.0,
                    key_end=12.0, anchor=2.0):
    """Dovetail key: trapezoid flaring from the cut plane into the right (+x)
    segment, extruded across the plate/panel thickness.

    spec: {"kind": "plate", "at": y, "z0": .., "z1": ..} or
          {"kind": "panel", "at": z, "y0": .., "y1": ..}; optional "neck"/"end"
          override the defaults. grow > 0 expands the key into the pocket
          shape (clearance offset).
    """
    neck = spec.get("neck", key_neck) + 2 * grow
    end = spec.get("end", key_end) + 2 * grow
    depth = key_depth + grow
    c, at = cut_x, spec["at"]
    pts = [
        (c - anchor, at - neck / 2), (c, at - neck / 2),
        (c + depth, at - end / 2), (c + depth, at + end / 2),
        (c, at + neck / 2), (c - anchor, at + neck / 2),
    ]
    if spec["kind"] == "plate":
        face = ccw_polygon(pts)
        return extrude(Plane.XY.offset(spec["z0"]) * face, spec["z1"] - spec["z0"])
    # "panel": same profile standing in the XZ plane, extruded along y.
    face = ccw_polygon([(x, -z) for x, z in pts])
    solid = extrude(Plane.XY.offset(spec["y0"]) * face, spec["y1"] - spec["y0"])
    return Rot(X=-90) * solid


def split_part(part, size, cuts, keys, carve=(), clearance=0.15, **key_dims):
    """Cut `part` (bbox `size` = (xmax, ymax, zmax), origin at 0) at the x
    positions `cuts`, add dovetail tails/pockets from `keys`, and optionally
    re-assign boxed regions wholly to one side (`carve`: list of
    {"cut": i, "to": "left"|"right", "box": (x0, y0, z0, x1, y1, z1)}).
    Returns the list of segment solids, left to right."""
    xmax, ymax, zmax = size
    big = 2 * max(size)
    segments = []
    bounds = [0.0] + list(cuts) + [xmax]
    for x0, x1 in zip(bounds[:-1], bounds[1:]):
        region = Location((x0, -big / 2, -big / 2)) * Box(
            x1 - x0, big + ymax, big + zmax, align=None)
        segments.append((part & region).clean())
    for spec in carve:
        x0, y0, z0, x1, y1, z1 = spec["box"]
        box = Location((x0, y0, z0)) * Box(x1 - x0, y1 - y0, z1 - z0, align=None)
        i = spec["cut"]
        keep, lose = (i, i + 1) if spec["to"] == "left" else (i + 1, i)
        segments[keep] = (segments[keep] + (part & box)).clean()
        segments[lose] = (segments[lose] - box).clean()
    for i, cut in enumerate(cuts):
        for spec in keys:
            tail = trapezoid_prism(cut, spec, **key_dims)
            pocket = trapezoid_prism(cut, spec, grow=clearance, **key_dims)
            segments[i] = (segments[i] + tail).clean()
            segments[i + 1] = (segments[i + 1] - pocket).clean()
    return segments


# ---------------------------------------------------------------------------
# Checks + export
# ---------------------------------------------------------------------------

def bbox_size(shape):
    bb = shape.bounding_box()
    return (bb.max.X - bb.min.X, bb.max.Y - bb.min.Y, bb.max.Z - bb.min.Z)


def check_solid(shape, name="part"):
    """Assert that `shape` is exactly one valid solid with positive volume
    (the CI STL analyzer wants one closed body per STL). Returns the volume."""
    solids = shape.solids()
    if len(solids) != 1:
        raise ValueError(f"{name}: expected 1 solid, got {len(solids)}")
    valid = shape.is_valid
    if callable(valid):
        valid = valid()
    if not valid:
        raise ValueError(f"{name}: invalid B-rep")
    if shape.volume <= 0:
        raise ValueError(f"{name}: non-positive volume")
    return shape.volume


def _bare(shape):
    """build123d's Mesher iterates a Part/Compound into its children, which
    drop .color/.label - hand it the single Solid instead when there is one."""
    solids = shape.solids()
    return solids[0] if len(solids) == 1 else shape


def export_all(solid, stem, outdir, formats=("stl", "step"), color=None,
               stl_tolerance=None, stl_angular_tolerance=None, quiet=False):
    """Write <outdir>/<stem>.stl / .step (/ .3mf when asked; the coloured
    3MFs in print/ are written by build_print.py). `color` (build123d Color)
    is stored in the 3MF when given. Tolerances default to
    rqb_params.EXPORT; rqb_params.SCALE is applied to the solid."""
    if stl_tolerance is None:
        stl_tolerance = rqb_params.EXPORT["stl_tolerance"]
    if stl_angular_tolerance is None:
        stl_angular_tolerance = rqb_params.EXPORT["stl_angular_tolerance"]
    if rqb_params.SCALE != 1.0:
        solid = solid.scale(rqb_params.SCALE)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    if color is not None:
        solid.color = color
    if "stl" in formats:
        export_stl(solid, str(outdir / f"{stem}.stl"),
                   tolerance=stl_tolerance, angular_tolerance=stl_angular_tolerance)
    if "step" in formats:
        export_step(solid, str(outdir / f"{stem}.step"))
    if "3mf" in formats:
        m = Mesher()
        bare = _bare(solid)
        if color is not None:
            bare.color = color
        bare.label = stem
        m.add_shape(bare, linear_deflection=stl_tolerance,
                    angular_deflection=stl_angular_tolerance, part_number=stem)
        m.write(str(outdir / f"{stem}.3mf"))
    if not quiet:
        print(f"  wrote {stem}." + "/.".join(formats))


def export_multicolour_3mf(parts, path, tolerance=0.01, angular_tolerance=0.1):
    """One 3MF with several coloured bodies in a shared coordinate frame.
    parts: {name: (shape, Color)}. Slicers with multi-material support
    (PrusaSlicer/Bambu/Orca) import this as a multi-part object."""
    m = Mesher()
    for name, (shape, color) in parts.items():
        # one 3MF object per solid so every body keeps its name and colour
        for solid in shape.solids():
            solid.color = color
            solid.label = name
            m.add_shape(solid, linear_deflection=tolerance,
                        angular_deflection=angular_tolerance, part_number=name)
    m.write(str(path))
    print(f"  wrote {Path(path).name} ({len(parts)} coloured bodies)")


# ---------------------------------------------------------------------------
# Coloured 3MF
# ---------------------------------------------------------------------------

# Filaments from the bill of materials (rasqberry.org), with the colours the
# website's 3D viewer uses.
FILAMENTS = {
    "matte black": "#232326",
    "white": "#DCDCD8",          # White / Rock White (floor)
    "silk silver": "#9EA3AA",
    "silk gold": "#E3A33A",
    "transparent": "#F3F5F6",
}


def shape_mesh(shape, tolerance=None, angular_tolerance=None):
    """(vertices, triangles) of a build123d shape, as for the STL."""
    tol = tolerance or rqb_params.EXPORT["stl_tolerance"]
    ang = angular_tolerance or rqb_params.EXPORT["stl_angular_tolerance"]
    verts, tris = shape.tessellate(tol, ang)
    # tessellate() repeats the vertices on shared face edges; merge them so
    # the mesh is closed (slicers check for a manifold mesh)
    index, out, remap = {}, [], []
    for v in verts:
        key = (round(v.X, 5), round(v.Y, 5), round(v.Z, 5))
        if key not in index:
            index[key] = len(out)
            out.append((v.X, v.Y, v.Z))
        remap.append(index[key])
    faces = [tuple(remap[i] for i in t) for t in tris]
    return out, [f for f in faces if len(set(f)) == 3]


def write_3mf(path, bodies):
    """3MF with ONE object; bodies: [(name, filament, (vertices, triangles))].

    Several bodies become the parts of that object, each with its filament
    as material (name + display colour, on its triangles) and, for
    PrusaSlicer / Bambu Studio / OrcaSlicer, as a named part with its own
    extruder (Metadata/Slic3r_PE_model.config; filaments numbered in order
    of first use). Plain 3MF readers see one multi-colour mesh."""
    import zipfile
    from xml.sax.saxutils import quoteattr
    names = list(dict.fromkeys(f for _, f, _ in bodies))
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<model unit="millimeter" xml:lang="en-US" '
           'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
           'xmlns:slic3rpe="http://schemas.slic3r.org/3mf/2017/06">',
           '<metadata name="slic3rpe:Version3mf">1</metadata>',
           '<resources>', '<basematerials id="1">']
    out += [f'<base name={quoteattr(n)} displaycolor="{FILAMENTS[n]}FF"/>' for n in names]
    out.append('</basematerials>')
    stem = Path(path).stem
    out.append(f'<object id="2" type="model" name={quoteattr(stem)} pid="1" '
               f'pindex="{names.index(bodies[0][1])}"><mesh><vertices>')
    base = 0
    for _, _, (verts, _) in bodies:
        out += [f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in verts]
    out.append('</vertices><triangles>')
    config = ['<?xml version="1.0" encoding="UTF-8"?>', '<config>',
              '<object id="2" instances_count="1">',
              f'<metadata type="object" key="name" value={quoteattr(stem)}/>']
    first = 0
    for name, filament, (verts, tris) in bodies:
        k = names.index(filament)
        out += [f'<triangle v1="{a + base}" v2="{b + base}" v3="{c + base}" pid="1" p1="{k}"/>'
                for a, b, c in tris]
        config += [f'<volume firstid="{first}" lastid="{first + len(tris) - 1}">',
                   f'<metadata type="volume" key="name" value={quoteattr(name)}/>',
                   f'<metadata type="volume" key="extruder" value="{k + 1}"/>',
                   '</volume>']
        base += len(verts)
        first += len(tris)
    config += ['</object>', '</config>']
    out += ['</triangles></mesh></object>', '</resources>',
            '<build><item objectid="2"/></build>', '</model>']
    types = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/'
             'package/2006/content-types"><Default Extension="rels" ContentType="application/'
             'vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" '
             'ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
             '<Default Extension="config" ContentType="text/xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.'
            'openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/'
            '3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/'
            '2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", "\n".join(out))
        z.writestr("Metadata/Slic3r_PE_model.config", "\n".join(config))
