#!/usr/bin/env python3
"""Ready-to-print PrusaSlicer projects and the colored complete model, from the new CAD parts.

The parts list is that of GitHub discussion #93 (Jan, 2025-11-12 and
2025-11-27) with his choices of 2026-11-15. The standard model has the
dovetail floor; without floor, the floor parts are left out and the wall base
and the cryostat are printed without their holes (the no-floor alternatives).

- `print/generated/complete/RasQberry-Two-{standard,no-floor}.3mf`: every
  part in its place in the assembled model, in its filament color (one
  object, one named part per printed piece), to see what goes where.
- `print/generated/plates/<printer>/`: PrusaSlicer projects with as many
  beds as needed (PrusaSlicer 2.9 multiple beds), parts turned the right way
  up and laid out, with the printer, print and filament presets (Prusament
  PLA, HF0.4 nozzle) and supports where needed:
  - one project per filament color (COLOR_FILES), one color per bed; the
    lid with the chandeliers prints on one nozzle with a filament change at
    a layer, or as two filaments on an MMU3 or INDX printer (MULTI);
  - `all-parts.3mf`: every bed except the floor (the floor is the white
    project), `no-floor-alternatives.3mf`: the two parts without holes.
- `print/generated/plates/README.md`: the print list (beds, parts, filament,
  grams and time per bed from PrusaSlicer).

PrusaSlicer (2.9) resolves its system presets and slices each bed once for
grams and time; the 3MF files are written here. Its CLI only knows printers
installed in its datadir, so a scratch datadir with these printers is made in
a temporary folder, with the vendor bundle PrusaSlicer itself uses (your
settings are only read, never changed).

Usage:  python build_plates.py [--prusaslicer PATH] [--vendor DIR]
"""
import argparse
import functools
import math
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import quoteattr

import numpy as np
import trimesh

from build_print import filament, stl_mesh
from rqb_cad import FILAMENTS, MODEL_HEAD, OUTPUT, PARTS, part_path, write_3mf, zip_3mf

ORIGINALS = OUTPUT.parent / "originals"
PRUSASLICER = "/Applications/Original Prusa Drivers/PrusaSlicer.app/Contents/MacOS/PrusaSlicer"
USER_VENDOR = Path.home() / "Library/Application Support/PrusaSlicer/vendor"
# (printer, print, filament preset) as named in PrusaSlicer's vendor bundle
MK4S = ("Original Prusa MK4S HF0.4 nozzle", "0.20mm SPEED @MK4S HF0.4", "Prusament PLA @MK4S HF0.4")
CORE_ONE = ("Prusa CORE One HF0.4 nozzle", "0.20mm SPEED @COREONE HF0.4", "Prusament PLA @COREONE HF0.4")
PRINTERS = {   # folder: single-nozzle presets, bed x, y (mm), two-filament printers
    "MK4S": (MK4S, (250, 210), {
        "mmu3": ("Original Prusa MK4S MMU3 HF0.4 nozzle", *MK4S[1:])}),
    "CoreOne": (CORE_ONE, (250, 220), {
        "mmu3": ("Prusa CORE One MMU3 HF0.4 nozzle", *CORE_ONE[1:]),
        "indx": ("Prusa CORE One INDX 4T HF0.4 nozzle", "0.20mm Balanced ★ @COREONEINDX HF0.4",
                 "Prusament PLA @COREONEINDX HF0.4")}),
}
VENDOR_MODELS = ("MK4S", "MK4SMMU3", "COREONE", "COREONEMMU3", "COREONE_INDX4T")
GAP = 6.0          # mm between parts on a bed
MARGIN = 2.0       # mm from the bed edge (the wall parts are 245.7 mm long)
WIPE_STRIP = 80.0  # mm kept free on the right of a bed for the MMU3 wipe tower
BED_STRIDE = 1.2   # beds of a project stand side by side, 1.2 bed widths apart
                   # (PrusaSlicer's legacy multi-bed layout, rearranged on load)
MAX_BEDS = 9       # PrusaSlicer 2.9

# ---------------------------------------------------------------- print setup

# how each part is printed: "up" as modelled, "flip" upside down (x 180),
# "flat" lying on its back (x -90); found by the overhang left over
ORIENT = {
    "R2_Floor-Tile1": "flip", "R2_Floor-Tile2": "flip", "R2_Floor-Tile3": "flip",
    "R2_Floor-Tile4": "flip", "R2_Floor-Tile5": "flip", "R2_Floor-Tile6s": "flip",
    "R2_Wall-Lid": "flip", "R2_Wall-Back+13": "flat", "R2_NarrowServerSingleLid": "flip",
}
# Jan's lid with the three chandeliers (two colors, from its generated 3MF):
# the lid prints sockets up, the chandeliers stand upside down on it, their
# top plates sunk into the 1 mm socket recesses. On one nozzle the filament
# changes (M600) at the first layer that starts above the lid. The plates of
# the chandeliers overhang their columns: automatic supports, blocked below
# the lid's top so that none are sealed into the sockets.
TWO_COLOR = "RQB2-Cryostat-jrl01"
LID_BODY = "lid"

FLOOR = [("R2_Floor-Tile1", 1), ("R2_Floor-Tile2", 1), ("R2_Floor-Tile3", 1),
         ("R2_Floor-Tile4", 1), ("R2_Floor-Tile5", 1), ("R2_Floor-Tile6s", 1),
         ("R2_Floor-CryoPlug", 1), ("R2_Floor-WallPlug", 2)]
# (project, [(part, count)]): the parts are packed onto as few beds as fit
COLOR_FILES = [
    ("matte-black", [("R2_Wall-Base-jrl01-2", 1), ("R2_Wall-Back+13", 1), ("R2_Wall-Lid", 1)]),
    ("galaxy-grey", [("RQB2-WallPanel-jrl02-2", 1)]),
    ("white-floor", FLOOR),
    ("silk-silver", [("RQB2-R2_CryoStandaloneGamma-jrl04", 1), ("R2_NewDoor", 1),
                     ("RQB2-R2_NarrowServerSingle-jrl02", 9)]),
    ("transparent+silk-gold", [(TWO_COLOR, 1), ("R2_NarrowServerSingleLid", 9)]),
]
FLOOR_FILE = "white-floor"
NO_FLOOR = {"R2_Wall-Base-jrl01-2": "R2_Wall-Base-jrl01-2-nofloor",
            "RQB2-R2_CryoStandaloneGamma-jrl04": "RQB2-R2_CryoStandaloneGamma-jrl04-nofloor"}
VARIANTS = ("standard", "no-floor")


def variant_items(variant):
    """[(project, items)] printed for `variant` (no floor: floor left out,
    wall base and cryostat swapped)."""
    if variant == "standard":
        return COLOR_FILES
    return [(name, [(NO_FLOOR.get(p, p), k) for p, k in items])
            for name, items in COLOR_FILES if name != FLOOR_FILE]

# ---------------------------------------------------------------- assembly

def T(x, y, z=0.0):
    """4x4 translation."""
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def rot(axis, deg):
    """4x4 rotation by `deg` about `axis` (through the origin)."""
    m = np.eye(4)
    m[:3, :3] = trimesh.transformations.rotation_matrix(math.radians(deg), axis)[:3, :3].round(12)
    return m


# The wall as in the website's 3D viewer (gh-pages scripts/build-3d-model.mjs),
# in the frame of the ORIGINAL STLs: measured from the floor's hex holes and
# the matching holes in the wall base.
WALL = T(-9.89, 383.26)
# the back stands on the base's 3 mm floor, its top flush with the base top
# (83.52 mm); the viewer keeps the original STL's height (z 8.04)
BACK_DROP = 3.0 - 8.04
# new parts, in the frame of the generated floor (= the original's): the
# plug flanges sit under the 3 mm floor plate (z -3); the wall plugs are
# turned 30 deg (locked)
CRYO_HOLE, WALL_HOLES, PLATE_UNDERSIDE = (130.32, 140.18), ((37.36, 322.27), (222.57, 322.27)), -3.0
FLANGE = {"R2_Floor-CryoPlug": 2.0, "R2_Floor-WallPlug": 4.0}
# The generated cryostats share one frame: body centered on the origin, door
# at -y, bottom opening centered at CRYO_OPENING (floor/plugs.py HOLES); it
# stands over the floor's cryostat hole. The door as in the viewer; the lid
# centered on the body, its rim LID_SINK into the top (the viewer centers it
# on the opening, 11 mm off). Three servers stand in a row on each arm wall
# (back and the two front walls), as in R2_NarrowYCryoConjoined
# (narrow_y_conjoined.py PARAMS): ARM_GAP off the wall and apart, turned
# alternately (the first two face each other like a server pair, the third
# stands back to back with the second).
ARM_WALLS, ARM_GAP = (90, -30, -150), 0.2
CRYO_OPENING, DOOR, LID_SINK = (0.0, 10.25), T(-19.05, -33.376), 3.0

# generated part -> the original it was rebuilt from (for its frame)
ORIGINAL_OF = {
    "R2_Wall-Base-jrl01-2": "wall/R2_Wall-Base", "R2_Wall-Base-jrl01-2-nofloor": "wall/R2_Wall-Base",
    "R2_Wall-Back+13": "wall/R2_Wall-Back", "R2_Wall-Lid": "wall/R2_Wall-Lid",
}
STANDIN = {   # same frame as the generated part named here (Back+13: its
    # original STL has another origin; same footprint as the Back)
    "R2_Wall-Base-jrl01-2": "R2_Wall-Base", "R2_Wall-Base-jrl01-2-nofloor": "R2_Wall-Base",
    "R2_Wall-Back+13": "R2_Wall-Back",
}


@functools.cache
def mesh(name):
    """Generated STL of part `name` (cached; never modified in place)."""
    return trimesh.load(f"{part_path(name)}.stl", force="mesh", process=False)


@functools.cache
def to_original(name):
    """Move generated part `name` into its original's frame: the rebuilds
    keep the shape but were re-centered, so the bounding-box centers are
    matched (R2_Wall-Back is 2 mm narrower than its original, centered)."""
    gen = mesh(STANDIN.get(name, name)).bounds
    org = trimesh.load(ORIGINALS / f"{ORIGINAL_OF[name]}.stl", force="mesh").bounds
    if np.abs((gen[1] - gen[0]) - (org[1] - org[0])).max() > 2.5:
        raise ValueError(f"{name}: size differs from its original, frame unknown")
    return T(*(org.mean(0) - gen.mean(0)))


def body_bounds(part, body):
    """Bounds of one body of a part (e.g. the lid of the two-color part)."""
    v = next(v for n, _, (v, _) in bodies(part) if n == body)
    return v.min(0), v.max(0)


def layout(variant):
    """[(part, 4x4)]: every printed piece of `variant` in the assembled model."""
    o = to_original
    base, gamma = (NO_FLOOR.get(p, p) if variant == "no-floor" else p
                   for p in ("R2_Wall-Base-jrl01-2", "RQB2-R2_CryoStandaloneGamma-jrl04"))
    cryo = T(CRYO_HOLE[0] - CRYO_OPENING[0], CRYO_HOLE[1] - CRYO_OPENING[1])
    flat, height = mesh(gamma).bounds[1][1:]                 # wall face, top
    depth = mesh("RQB2-R2_NarrowServerSingle-jrl02").extents[1]
    # the two-color part is the lid turned over (about y): turn it back
    lid_top = body_bounds(TWO_COLOR, LID_BODY)[1][2]
    out = [(base, WALL @ o(base)),
           ("R2_Wall-Back+13", WALL @ T(5.3, -100, BACK_DROP) @ o("R2_Wall-Back+13")),
           ("R2_Wall-Lid", WALL @ o("R2_Wall-Lid")),
           (gamma, cryo), ("R2_NewDoor", cryo @ DOOR),
           (TWO_COLOR, cryo @ T(0, 0, height - LID_SINK + lid_top) @ rot([0, 1, 0], 180))]
    for wall in ARM_WALLS:
        for i in range(3):
            r = flat + ARM_GAP + depth / 2 + i * (depth + ARM_GAP)
            m = cryo @ rot([0, 0, 1], wall - 90) @ T(0, r) @ rot([0, 0, 1], 180 * (i != 1))
            out += [("RQB2-R2_NarrowServerSingle-jrl02", m), ("R2_NarrowServerSingleLid", m)]
    if variant == "standard":
        out += [(f"R2_Floor-{t}", np.eye(4))
                for t in ("Tile1", "Tile2", "Tile3", "Tile4", "Tile5", "Tile6s")]
        out.append(("R2_Floor-CryoPlug", T(*CRYO_HOLE, PLATE_UNDERSIDE - FLANGE["R2_Floor-CryoPlug"])))
        out += [("R2_Floor-WallPlug", T(x, y, PLATE_UNDERSIDE - FLANGE["R2_Floor-WallPlug"])
                 @ rot([0, 0, 1], 30)) for x, y in WALL_HOLES]
    return out


def counts(variant):
    """Copies of each part printed for `variant`."""
    n = Counter()
    for _, items in variant_items(variant):
        n.update(dict(items))
    return n


def part_filament(part):
    """Filament of part `part` (the rule in build_print, by its path)."""
    return filament(Path(PARTS[part] + ".stl"))


def file_name(part):
    """The part's file name in print/generated/ (what users look for)."""
    return Path(PARTS[part]).name


def read_3mf_bodies(path):
    """[(name, filament, (vertices, triangles))] of a 3MF written by
    rqb_cad.write_3mf (one object, one named volume per body)."""
    z = zipfile.ZipFile(path)
    model, cfg = z.read("3D/3dmodel.model").decode(), z.read("Metadata/Slic3r_PE_model.config").decode()
    mats = re.findall(r'<base name="([^"]+)"', model)
    v = np.array(re.findall(r'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"', model), float)
    t = np.array(re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)" pid="1" p1="(\d+)"', model), int)
    out = []
    for first, last, name in re.findall(r'<volume firstid="(\d+)" lastid="(\d+)">\s*'
                                        r'<metadata type="volume" key="name" value="([^"]+)"', cfg):
        tri = t[int(first):int(last) + 1]
        used, inverse = np.unique(tri[:, :3], return_inverse=True)
        out.append((name, mats[tri[0, 3]], (v[used], inverse.reshape(-1, 3).tolist())))
    return out


@functools.cache
def bodies(part):
    """[(name, filament, (vertices as array, triangles))] of a part: its STL,
    or for the two-color part the bodies of its generated 3MF (cached)."""
    if part == TWO_COLOR:
        return read_3mf_bodies(part_path(part).with_suffix(".3mf"))
    v, t = stl_mesh(f"{part_path(part)}.stl")
    return [(file_name(part), part_filament(part), (np.asarray(v), t))]


def filaments(parts):
    """The filaments of `parts`, in printing order."""
    return list(dict.fromkeys(f for p in parts for _, f, _ in bodies(p)))


def write_complete(variant):
    """The assembled model of `variant` as one colored 3MF; checks that it
    holds as many of each part as the projects print."""
    pieces = layout(variant)
    # the LED filter screen has no place in the viewer's layout
    printed = Counter({k: v for k, v in counts(variant).items() if "WallPanel" not in k})
    placed = Counter(part for part, _ in pieces)
    if placed != printed:
        raise ValueError(f"{variant}: layout {placed} != printed {printed}")
    out = []
    for part, m in pieces:
        for name, fil, (v, t) in bodies(part):
            name = file_name(part) + (f" {name}" if part == TWO_COLOR else "")
            out.append((name, fil, (trimesh.transform_points(v, m).tolist(), t)))
    path = OUTPUT / "complete" / f"RasQberry-Two-{variant}.3mf"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_3mf(path, out)
    return path

# ---------------------------------------------------------------- beds

@functools.cache
def oriented(part):
    """([(body name, vertices, triangles)], size) of `part` turned for
    printing, centered in x/y, standing on z = 0."""
    turn = {"up": np.eye(4), "flip": rot([1, 0, 0], 180), "flat": rot([1, 0, 0], -90)}
    m = turn[ORIENT.get(part, "up")]
    vols = [(name, trimesh.transform_points(v, m), t) for name, _, (v, t) in bodies(part)]
    allv = np.vstack([v for _, v, _ in vols])
    lo, hi = allv.min(0), allv.max(0)
    shift = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]]
    return [(name, v - shift, t) for name, v, t in vols], hi - lo


def arrange(parts, bed):
    """Rows, largest first: [(x, y)] centers for `parts` on a bed (x, y),
    the whole block centered; ValueError if they do not fit."""
    sizes = [oriented(p)[1][:2] for p in parts]
    order = sorted(range(len(sizes)), key=lambda i: (-sizes[i][1], -sizes[i][0]))
    pos, rows, x, y, row_h = {}, [], 0.0, 0.0, 0.0
    for i in order:
        w, d = sizes[i]
        if x and x + w > bed[0] - 2 * MARGIN:
            rows.append(x - GAP)
            x, y, row_h = 0.0, y + row_h + GAP, 0.0
        pos[i] = (x + w / 2, y + d / 2)
        x, row_h = x + w + GAP, max(row_h, d)
    rows.append(x - GAP)
    width, depth = max(rows), y + row_h
    if width > bed[0] - 2 * MARGIN or depth > bed[1] - 2 * MARGIN:
        raise ValueError(f"does not fit: {width:.0f} x {depth:.0f} mm")
    ox, oy = (bed[0] - width) / 2, (bed[1] - depth) / 2
    return [(pos[i][0] + ox, pos[i][1] + oy) for i in range(len(sizes))]


def fits(parts, bed):
    """True if `parts` fit on one bed."""
    try:
        arrange(parts, bed)
        return True
    except ValueError:
        return False


def pack(items, bed):
    """First fit: [[part per copy]] per bed for `items` [(part, count)]."""
    beds = []
    for part, k in items:
        for _ in range(k):
            for b in beds:
                if fits(b + [part], bed):
                    b.append(part)
                    break
            else:
                arrange([part], bed)          # raises if the part alone is too big
                beds.append([part])
    for b in beds:
        check_bed(b)
    return beds


def check_bed(parts):
    """One filament per bed; the two-color part only with parts of its first
    filament that end below its filament change."""
    fils = filaments(parts)
    if len(fils) == 1:
        return
    if TWO_COLOR not in parts or fils != filaments([TWO_COLOR]):
        raise ValueError(f"bed mixes filaments {fils}: {sorted(set(parts))}")
    lid_top = body_bounds(TWO_COLOR, LID_BODY)[1][2]
    tall = {p for p in parts if p != TWO_COLOR and oriented(p)[1][2] > lid_top}
    if tall:
        raise ValueError(f"{sorted(tall)} reach above the filament change")


def change_z(ini):
    """Top of the first layer that starts above the lid (PrusaSlicer's
    print_z for the filament change)."""
    lid_top = body_bounds(TWO_COLOR, LID_BODY)[1][2]
    first = float(re.search(r"^first_layer_height = ([\d.]+)", ini, re.M).group(1))
    layer = float(re.search(r"^layer_height = ([\d.]+)", ini, re.M).group(1))
    n = math.ceil(round((lid_top - first) / layer, 6))
    return round(first + (n + 1) * layer, 3)


def ini_value(ini, key):
    """One value of a resolved PrusaSlicer config."""
    return re.search(rf"^{key} = (.*)$", ini, re.M).group(1)


def project_config(ini, fils):
    """Slic3r_PE.config: the resolved presets with the filament colors (one
    per extruder; extra extruders keep theirs)."""
    n = len(ini_value(ini, "extruder_colour").split(";"))
    colors = [FILAMENTS[f] for f in fils][:n]
    if n > 1:
        keep = ini_value(ini, "extruder_colour").split(";")
        colors += keep[len(colors):]
    over = {"filament_colour": ";".join(colors), "extruder_colour": ";".join(colors)}
    lines = []
    for line in ini.splitlines():
        key = line.split(" = ", 1)[0]
        if line and not line.startswith("#"):
            lines.append(f"; {key} = {over.pop(key)}" if key in over else f"; {line}")
    if over:
        raise ValueError(f"not in the PrusaSlicer presets: {sorted(over)}")
    return "; generated by PrusaSlicer 2.9 presets (build_plates.py)\n\n" + "\n".join(lines) + "\n"


def blocker(part):
    """(vertices, triangles) of a box over the lid of the two-color part,
    in its printed orientation: no supports below the lid's top."""
    vols, size = oriented(part)
    lid = next(v for n, v, _ in vols if n == LID_BODY)
    lo, hi = lid.min(0) - [1, 1, 0], lid.max(0) + [1, 1, 0]
    box = trimesh.creation.box(bounds=[lo, hi])
    return box.vertices, box.faces.tolist()


def write_project(path, beds, bed, ini, multi):
    """PrusaSlicer project with one bed per entry of `beds`: one object per
    part (one volume per body), one instance per copy. On one nozzle the
    two-color part's bed gets a filament change; on a two-filament printer
    its bodies get their own extruders (`multi`)."""
    wipe = multi and ini_value(ini, "wipe_tower") == "1"
    parts = list(dict.fromkeys(p for b in beds for p in b))
    fils = filaments(parts) if multi else filaments(parts)[:1]
    if len(fils) > len(ini_value(ini, "extruder_colour").split(";")):
        raise ValueError(f"{path.name}: {len(fils)} filaments, more than the printer has")
    if len(beds) > MAX_BEDS:
        raise ValueError(f"{path.name}: {len(beds)} beds, PrusaSlicer takes {MAX_BEDS}")
    items = []        # (object index, x, y)
    changes = []      # bed index with the two-color part (one nozzle)
    for k, b in enumerate(beds):
        dx = k * BED_STRIDE * bed[0]
        items += [(parts.index(p), x + dx, y) for p, (x, y) in zip(b, arrange(b, usable(b, bed, multi)))]
        if TWO_COLOR in b and not multi:
            changes.append(k)
    model = MODEL_HEAD + ["<resources>"]
    cfg = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    for n, part in enumerate(parts, start=1):
        vols = [(name, v, t, f) for (name, v, t), (_, f, _) in zip(oriented(part)[0], bodies(part))]
        extra = []
        if part == TWO_COLOR:
            bv, bt = blocker(part)
            extra = [("support blocker", bv, bt, None)]
        name = file_name(part)
        model.append(f'<object id="{n}" type="model" name={quoteattr(name)}><mesh><vertices>')
        for _, v, _, _ in vols + extra:
            model += [f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in v]
        model.append("</vertices><triangles>")
        cfg += [f'<object id="{n}" instances_count="{sum(i == n - 1 for i, _, _ in items)}">',
                f'<metadata type="object" key="name" value={quoteattr(name)}/>']
        if part == TWO_COLOR:
            cfg += [f'<metadata type="object" key="{k}" value="{v}"/>' for k, v in
                    (("support_material", "1"), ("support_material_auto", "1"),
                     ("support_material_buildplate_only", "0"))]
        base = first = 0
        for vname, v, t, fil in vols + extra:
            model += [f'<triangle v1="{a + base}" v2="{b + base}" v3="{c + base}"/>'
                      for a, b, c in t]
            cfg += [f'<volume firstid="{first}" lastid="{first + len(t) - 1}">',
                    f'<metadata type="volume" key="name" value={quoteattr(vname)}/>']
            if fil is None:
                cfg += ['<metadata type="volume" key="modifier" value="1"/>',
                        '<metadata type="volume" key="volume_type" value="SupportBlocker"/>']
            elif multi:
                cfg.append(f'<metadata type="volume" key="extruder" value="{fils.index(fil) + 1}"/>')
            cfg.append("</volume>")
            base, first = base + len(v), first + len(t)
        model.append("</triangles></mesh></object>")
        cfg.append("</object>")
    model += ["</resources>", "<build>"]
    model += [f'<item objectid="{i + 1}" transform="1 0 0 0 1 0 0 0 1 {x:.3f} {y:.3f} 0" '
              f'printable="1"/>' for i, x, y in items]
    model += ["</build>", "</model>"]
    cfg.append("</config>")
    meta = {"Metadata/Slic3r_PE_model.config": "\n".join(cfg),
            "Metadata/Slic3r_PE.config": project_config(ini, fils)}
    if changes:
        gold = filaments([TWO_COLOR])[1]
        blocks = [f'<custom_gcodes_per_print_z bed_idx="{k}">\n'
                  + (f'<code print_z="{change_z(ini)}" type="0" extruder="1" color="{FILAMENTS[gold]}" '
                     'extra="" gcode="M600"/>\n' if k in changes else "")
                  + '<mode value="SingleExtruder"/>\n</custom_gcodes_per_print_z>'
                  for k in sorted({0, *changes})]
        meta["Metadata/Prusa_Slicer_custom_gcode_per_print_z.xml"] = (
            '<?xml version="1.0" encoding="utf-8"?>\n' + "\n".join(blocks))
    if wipe:
        meta["Metadata/Prusa_Slicer_wipe_tower_information.xml"] = (
            '<?xml version="1.0" encoding="utf-8"?>\n' + "\n".join(
                f'<wipe_tower_information bed_idx="{k}" position_x="{bed[0] - WIPE_STRIP + 10}" '
                f'position_y="{MARGIN + 30}" rotation_deg="0"/>' for k in range(len(beds))))
    path.parent.mkdir(parents=True, exist_ok=True)
    zip_3mf(path, model, meta)

# ---------------------------------------------------------------- PrusaSlicer

def vendor_bundle(exe, vendor):
    """The PrusaResearch vendor bundle: `vendor`, else the one PrusaSlicer
    has installed (it has the newest printers, e.g. INDX), else the one that
    ships with `exe` (macOS app layout)."""
    for d in (vendor, USER_VENDOR, Path(exe).resolve().parents[1] / "Resources" / "profiles"):
        if d and (Path(d) / "PrusaResearch.ini").exists():
            return Path(d)
    raise FileNotFoundError("no PrusaResearch vendor bundle")


def scratch_datadir(bundle, tmp):
    """A PrusaSlicer datadir with the vendor bundle and the printers installed."""
    dd = Path(tmp) / "datadir"
    (dd / "vendor").mkdir(parents=True)
    for f in ("PrusaResearch.ini", "PrusaResearch.idx"):
        shutil.copy(bundle / f, dd / "vendor" / f)
    (dd / "PrusaSlicer.ini").write_text(
        "[vendor:PrusaResearch]\n" + "".join(f"model:{m} = HF0.4\n" for m in VENDOR_MODELS))
    return dd


def resolved(exe, dd, presets, tmp):
    """The full config of the three presets, as PrusaSlicer resolves them."""
    printer, print_, fil = presets
    out = Path(tmp) / "resolved.ini"
    r = subprocess.run([exe, "--datadir", dd, "--printer-profile", printer, "--print-profile",
                        print_, "--material-profile", fil, "--save", out],
                       capture_output=True, text=True)
    ini = out.read_text() if out.exists() else ""
    if r.returncode or f"printer_settings_id = {printer}" not in ini:
        raise RuntimeError(f"PrusaSlicer did not load {presets}\n{r.stdout}{r.stderr}")
    out.unlink()
    return ini


def slice_stats(exe, dd, project, tmp):
    """([grams per extruder used], time) from slicing a one-bed `project`."""
    gcode = Path(tmp) / "bed.gcode"
    r = subprocess.run([exe, "--datadir", dd, "--no-binary-gcode", "--export-gcode",
                        "-o", gcode, project], capture_output=True, text=True)
    if r.returncode or not gcode.exists():
        raise RuntimeError(f"{project.name}: slicing failed\n{r.stdout}{r.stderr}")
    text = gcode.read_text(errors="ignore")[-80000:]
    grams = [float(g) for g in re.search(r"; filament used \[g\] = (.+)", text).group(1).split(",")]
    time = re.search(r"; estimated printing time \(normal mode\) = (.+)", text).group(1).strip()
    gcode.unlink()
    return [g for g in grams if g > 0], time


class Slicer:
    """Slices one bed at a time (cached by printer and bed content)."""

    def __init__(self, exe, dd, tmp):
        self.exe, self.dd, self.tmp, self.cache = exe, dd, tmp, {}

    def stats(self, key, parts, bed, ini, multi):
        """([grams], time) of one bed of `parts`. PrusaSlicer 2.9.7's CLI
        crashes on two filaments with a wipe tower (even on two cubes), so
        such a bed is sliced without it (NO_TOWER)."""
        k = (key, tuple(sorted(parts)))
        if k not in self.cache:
            p = Path(self.tmp) / "bed.3mf"
            if multi and ini_value(ini, "wipe_tower") == "1":
                ini = re.sub(r"^wipe_tower = 1$", "wipe_tower = 0", ini, flags=re.M)
            write_project(p, [parts], bed, ini, multi)
            self.cache[k] = slice_stats(self.exe, self.dd, p, self.tmp)
        return self.cache[k]

# ---------------------------------------------------------------- main

def usable(parts, bed, multi):
    """The bed area for `parts`: on an MMU3 a bed with two filaments keeps a
    strip free for the wipe tower (one filament needs no tower)."""
    if multi == "mmu3" and len(filaments(parts)) > 1:
        return (bed[0] - WIPE_STRIP, bed[1])
    return bed


def projects(folder, bed):
    """[(file name, beds, multi)] of a printer folder. The projects with
    several colors (all-parts, no-floor-alternatives) are for the MMU3, so
    PrusaSlicer shows each part in its color; each bed has one filament but
    the lid bed."""
    def beds(items, multi=None):
        return pack(items, usable([p for p, _ in items], bed, multi))
    out = [(f"{n}-{name}.3mf", beds(items), None) for n, (name, items)
           in enumerate(COLOR_FILES, start=1)]
    out.append(("all-parts.3mf", [b for name, items in COLOR_FILES if name != FLOOR_FILE
                                   for b in beds(items, "mmu3")], "mmu3"))
    out.append(("no-floor-alternatives.3mf",
                [b for p in NO_FLOOR.values() for b in beds([(p, 1)], "mmu3")], "mmu3"))
    # the two-color project for each two-filament printer
    fname, items = next((f"{n}-{name}", items) for n, (name, items) in enumerate(COLOR_FILES, start=1)
                        if any(p == TWO_COLOR for p, _ in items))
    out += [(f"{fname}-{multi}.3mf", beds(items, multi), multi) for multi in PRINTERS[folder][2]]
    return out


def main():
    """Complete models, then the projects for each printer, then the print list."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prusaslicer", default=os.environ.get("PRUSASLICER", PRUSASLICER))
    ap.add_argument("--vendor", help="folder with PrusaResearch.ini/.idx (default: PrusaSlicer's own)")
    a = ap.parse_args()
    for folder in ("complete", "plates"):   # all generated here: nothing stale
        shutil.rmtree(OUTPUT / folder, ignore_errors=True)
    for variant in VARIANTS:
        print("wrote", write_complete(variant).relative_to(OUTPUT))
    bundle = vendor_bundle(a.prusaslicer, a.vendor)
    version = re.search(r"^config_version = (.+)$", (bundle / "PrusaResearch.ini").read_text(), re.M).group(1)
    report = {}
    with tempfile.TemporaryDirectory() as tmp:
        dd = scratch_datadir(bundle, tmp)
        slicer = Slicer(a.prusaslicer, dd, tmp)
        for folder, (presets, bed, multis) in PRINTERS.items():
            inis = {None: resolved(a.prusaslicer, dd, presets, tmp)}
            inis |= {m: resolved(a.prusaslicer, dd, p, tmp) for m, p in multis.items()}
            rows = []
            for fname, beds, multi in projects(folder, bed):
                path = OUTPUT / "plates" / folder / fname
                write_project(path, beds, bed, inis[multi], multi)
                for k, b in enumerate(beds, start=1):
                    st = slicer.stats((folder, multi), b, bed, inis[multi], multi)
                    rows.append((fname, k, b, st))
                    print("wrote", path.relative_to(OUTPUT), f"bed {k}", st)
            totals = {}
            for variant in VARIANTS:
                per = Counter()
                for _, items in variant_items(variant):
                    for b in pack(items, bed):
                        # the two-color bed split as a two-filament printer slices it
                        multi = next(iter(multis)) if len(filaments(b)) > 1 else None
                        grams = slicer.stats((folder, multi), b, bed, inis[multi], multi)[0]
                        per.update(dict(zip(filaments(b), grams)))
                totals[variant] = per
            report[folder] = (rows, totals, change_z(inis[None]))
    write_readme(report, version)


def write_readme(report, version):
    """The print list: per printer a table of the projects and their beds
    (grams and time from PrusaSlicer), then the filament per color."""
    lines = ["# Print plates", "",
             "Generated by `cad/build_plates.py` from the new CAD parts (experimental,",
             "not fully tested yet). PrusaSlicer projects for PrusaSlicer 2.9 or later,",
             "with as many beds as needed: open, check each bed, slice and print. Grams",
             "and times are PrusaSlicer's estimates (Prusament PLA, HF0.4 nozzle, vendor",
             f"profiles {version}).", "",
             "- One project per filament color, one color per bed. The floor is",
             "  `3-white-floor.3mf`; `all-parts.3mf` has every other bed, each part in",
             "  its color: it is set up for an MMU3 (5 filaments). Every bed has one",
             "  filament except the lid bed, so with a single nozzle choose your printer",
             "  in PrusaSlicer and change the filament between beds (for the lid bed",
             "  use `5-transparent+silk-gold.3mf`).",
             "- **Without floor:** skip the white project and print the two parts of",
             "  `no-floor-alternatives.3mf` instead of the wall base and the cryostat",
             "  (the same parts without the holes for the floor plugs).",
             "- **Lid with chandeliers** (lid transparent, chandeliers silk gold): on one",
             "  nozzle PrusaSlicer pauses for the filament change at the height given",
             "  below; `-mmu3` / `-indx` print it with two filaments on an MMU3 or INDX.",
             "  MMU3 grams and times leave out the wipe tower (PrusaSlicer's command",
             "  line crashes with it; the projects have it).",
             "  Supports only above the lid (a support blocker keeps them out of the",
             "  sockets); they print in silk gold.", "",
             "`../complete/` has both versions assembled, in color, to see what goes",
             "where (without the LED filter screen, which goes in front of the LEDs).", ""]
    for folder, (rows, totals, cz) in report.items():
        lines += [f"## {folder}", "", f"Filament change on the lid bed at {cz} mm.", "",
                  "| Project | Bed | Parts | Filament | Grams | Time |", "|---|---|---|---|---|---|"]
        for fname, k, parts, (grams, time) in rows:
            n = Counter(parts)
            desc = ", ".join(f"{c} x {file_name(p)}" for p, c in n.items())
            g = " + ".join(f"{x:.0f}" for x in grams)
            lines.append(f"| {fname} | {k} | {desc} | {' + '.join(filaments(parts))} | {g} g | {time} |")
        lines.append("")
        for variant in VARIANTS:
            grams = {f: round(g) for f, g in totals[variant].items()}
            title = "standard" if variant == "standard" else "without floor"
            lines.append(f"Filament, {title} (the lid bed split as on {next(iter(PRINTERS[folder][2])).upper()}): "
                         + ", ".join(f"{f} {g} g" for f, g in grams.items())
                         + f"; {sum(grams.values())} g in total.")
            lines.append("")
    (OUTPUT / "plates" / "README.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
