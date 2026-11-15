#!/usr/bin/env python3
"""Ready-to-print plates and the colored complete model, from the new CAD parts.

The standard model has the dovetail floor; the version without floor leaves
out the floor plates and prints the wall base and the cryostat without their
holes (two swap plates, PLATES).

- `print/generated/complete/RasQberry-Two-{standard,no-floor}.3mf`: every
  part in its place in the assembled model, in its filament color (one
  object, one named part per printed piece), to see what goes where.
- `print/generated/plates/<printer>/NN-<filament>-<name>[-no-floor].3mf`:
  PrusaSlicer projects, parts turned the right way up and laid out on the
  bed, with the printer, print and filament presets (Prusament PLA, 0.20 mm
  SPEED, HF0.4 nozzle) and supports where needed. One filament per plate,
  except the cryostat lid with its chandeliers (filament change at a layer).
- `print/generated/plates/README.md`: the print list (parts, quantities,
  filament, grams and time per plate from PrusaSlicer).

PrusaSlicer (2.9) is used to resolve its system presets and to slice each
plate once for grams and time; the 3MF files are written here. Its CLI only
knows printers that are installed in its datadir, so a scratch datadir with
the two printers is made in a temporary folder (yours is not touched).

Usage:  python build_plates.py [--prusaslicer PATH]
"""
import argparse
import functools
import json
import math
import sys
from collections import Counter
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

import numpy as np
import trimesh

from build_print import filament, stl_mesh
from rqb_cad import FILAMENTS, MODEL_HEAD, OUTPUT, PARTS, part_path, write_3mf, zip_3mf

sys.path.insert(0, str(Path(__file__).resolve().parent / "cryostat"))
import cryostat_model  # noqa: E402

ORIGINALS = OUTPUT.parent / "originals"
PRUSASLICER = "/Applications/Original Prusa Drivers/PrusaSlicer.app/Contents/MacOS/PrusaSlicer"
PRINTERS = {   # folder: (printer, print, filament preset; bed x, y in mm)
    "MK4S": ("Original Prusa MK4S HF0.4 nozzle", "0.20mm SPEED @MK4S HF0.4",
             "Prusament PLA @MK4S HF0.4", (250, 210)),
    "CoreOne": ("Prusa CORE One HF0.4 nozzle", "0.20mm SPEED @COREONE HF0.4",
                "Prusament PLA @COREONE HF0.4", (250, 220)),
}
GAP = 6.0       # mm between parts on a plate
MARGIN = 2.0    # mm from the bed edge (the wall parts are 245.7 mm long)

# ---------------------------------------------------------------- print setup

# how each part is printed: "up" as modelled, "flip" upside down (x 180),
# "flat" lying on its back (x -90); found by the overhang left over
ORIENT = {
    "R2_Floor-Tile1": "flip", "R2_Floor-Tile2": "flip", "R2_Floor-Tile3": "flip",
    "R2_Floor-Tile4": "flip", "R2_Floor-Tile5": "flip", "R2_Floor-Tile6s": "flip",
    "R2_Wall-Lid": "flip", "R2_Wall-Back+13": "flat", "R2_NarrowServerSingleLid": "flip",
}
# the plates of the chandeliers overhang their columns (supports also on the lid)
SUPPORTS = {"RQB2-Cryostat-jrl01"}
# Jan's lid with the three chandeliers: lid transparent, chandeliers silk
# gold. One print on one nozzle: the filament changes (M600) at the first
# layer top above the 20.7 mm lid; the chandelier stems below it sit in the
# lid's sockets.
TWO_COLOR = {"RQB2-Cryostat-jrl01": 21.0}

FLOOR = [("floor-tile-1-plugs", [("R2_Floor-Tile1", 1), ("R2_Floor-CryoPlug", 1),
                                 ("R2_Floor-WallPlug", 2)])]
FLOOR += [(f"floor-tile-{t[4:]}", [(f"R2_Floor-{t}", 1)])
          for t in ("Tile2", "Tile3", "Tile4", "Tile5", "Tile6s")]
# (plate, [(part, count)], without floor: None = the same plate, [] = not
# printed, else the plate printed instead), from the parts list in GitHub
# discussion #93 (Jan, 2025-11-12 and 2025-11-27) and his choices of 2026-11-15
PLATES = [
    ("wall-base-back", [("R2_Wall-Base-jrl01-2", 1), ("R2_Wall-Back+13", 1)],
     [("R2_Wall-Base-jrl01-2-nofloor", 1), ("R2_Wall-Back+13", 1)]),
    ("wall-lid", [("R2_Wall-Lid", 1)], None),
    ("led-filter-screen", [("RQB2-WallPanel-jrl02-2", 1)], None),
    *[(name, items, []) for name, items in FLOOR],
    ("cryostat-door", [("RQB2-R2_CryoStandaloneGamma-jrl04", 1), ("R2_NewDoor", 1)],
     [("RQB2-R2_CryoStandaloneGamma-jrl04-nofloor", 1), ("R2_NewDoor", 1)]),
    ("servers", [("RQB2-R2_NarrowServerSingle-jrl02", 9)], None),
    ("server-lids", [("R2_NarrowServerSingleLid", 9)], None),
    ("cryostat-lid-chandeliers", [("RQB2-Cryostat-jrl01", 1)], None),
]
VARIANTS = ("standard", "no-floor")


def plates(variant):
    """[(number, plate name, items, swapped)] printed for `variant`; plates
    keep the standard numbers, `swapped` marks a no-floor swap plate."""
    out = []
    for n, (name, items, no_floor) in enumerate(PLATES, start=1):
        if variant == "standard" or no_floor is None:
            out.append((n, name, items, False))
        elif no_floor:
            out.append((n, name, no_floor, True))
    return out

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


# The layout of the website's 3D viewer (gh-pages scripts/build-3d-model.mjs),
# in the frame of the ORIGINAL STLs: measured from the floor's hex holes and
# the matching holes in the wall base and the cryostat.
WALL = T(-9.89, 383.26)
# new parts, in the frame of the generated floor (= the original's): the
# plug flanges sit under the 3 mm floor plate (z -3); the wall plugs are
# turned 30 deg (locked)
CRYO_HOLE, WALL_HOLES, PLATE_UNDERSIDE = (130.32, 140.18), ((37.36, 322.27), (222.57, 322.27)), -3.0
FLANGE = {"R2_Floor-CryoPlug": 2.0, "R2_Floor-WallPlug": 4.0}
# The generated cryostats share one frame: body centered on the origin, door
# at -y, bottom opening centred at CRYO_OPENING (floor/plugs.py); it stands
# over the floor's cryostat hole. The door and the lid (sockets 3 mm into the
# top) as in the viewer, the lid centred on the body (the viewer centres it
# on the opening, 11 mm off). Three servers stand in a row on each arm wall
# (back and the two front walls), as in R2_NarrowYCryoConjoined: 0.2 mm off
# the wall, then 0.2 mm apart, turned alternately (the first two face each
# other like a server pair, the third stands back to back with the second).
ARM_WALLS = (90, -30, -150)        # outward normals (deg)
FLAT, ARM_GAP, SERVER_DEPTH = 33.0, 0.2, 23.24
CRYO_OPENING, DOOR, LID_Z = (0.0, 10.25), T(-19.05, -33.376), 90.3

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


def layout(variant):
    """[(part, 4x4)]: every printed piece of `variant` in the assembled model."""
    o = to_original
    cryo = T(CRYO_HOLE[0] - CRYO_OPENING[0], CRYO_HOLE[1] - CRYO_OPENING[1])
    # jrl01 is the generated lid turned over (about y) and raised by its height
    lid_h = mesh("R2_CryoLid-Simple").bounds[1][2]
    out = [("R2_Wall-Back+13", WALL @ T(5.3, -100) @ o("R2_Wall-Back+13")),
           ("R2_Wall-Lid", WALL @ o("R2_Wall-Lid")),
           ("R2_NewDoor", cryo @ DOOR),
           ("RQB2-Cryostat-jrl01", cryo @ T(0, 0, LID_Z) @ rot([0, 1, 0], 180) @ T(0, 0, -lid_h))]
    for wall in ARM_WALLS:
        for i in range(3):
            r = FLAT + ARM_GAP + SERVER_DEPTH / 2 + i * (SERVER_DEPTH + ARM_GAP)
            m = cryo @ rot([0, 0, 1], wall - 90) @ T(0, r) @ rot([0, 0, 1], 180 * (i != 1))
            out += [("RQB2-R2_NarrowServerSingle-jrl02", m), ("R2_NarrowServerSingleLid", m)]
    if variant == "standard":
        base, gamma = "R2_Wall-Base-jrl01-2", "RQB2-R2_CryoStandaloneGamma-jrl04"
        out += [(f"R2_Floor-{t}", np.eye(4))
                for t in ("Tile1", "Tile2", "Tile3", "Tile4", "Tile5", "Tile6s")]
        out.append(("R2_Floor-CryoPlug", T(*CRYO_HOLE, PLATE_UNDERSIDE - FLANGE["R2_Floor-CryoPlug"])))
        out += [("R2_Floor-WallPlug", T(x, y, PLATE_UNDERSIDE - FLANGE["R2_Floor-WallPlug"])
                 @ rot([0, 0, 1], 30)) for x, y in WALL_HOLES]
    else:
        base, gamma = "R2_Wall-Base-jrl01-2-nofloor", "RQB2-R2_CryoStandaloneGamma-jrl04-nofloor"
    out += [(base, WALL @ o(base)), (gamma, cryo)]
    return out


def counts(variant):
    """Copies of each part over all plates of `variant`."""
    n = Counter()
    for _, _, items, _ in plates(variant):
        n.update(dict(items))
    return n


def part_filament(part):
    """Filament of part `part` (the rule in build_print, by its path)."""
    return filament(Path(PARTS[part] + ".stl"))


def file_name(part):
    """The part's file name in print/generated/ (what users look for)."""
    return Path(PARTS[part]).name


@functools.cache
def bodies(part):
    """[(name, filament, (vertices as array, triangles))] of a part: its STL,
    or for the two-color part its bodies from the generator (cached)."""
    if part in TWO_COLOR:
        prof = json.loads(cryostat_model.PROFILES.read_text())
        return [(n, f, (np.asarray(v), t)) for n, f, (v, t) in cryostat_model.jrl01_bodies(prof)]
    v, t = stl_mesh(f"{part_path(part)}.stl")
    return [(file_name(part), part_filament(part), (np.asarray(v), t))]


def filaments(items):
    """The filaments of a plate's parts, in printing order."""
    return list(dict.fromkeys(f for p, _ in items for _, f, _ in bodies(p)))


def write_complete(variant):
    """The assembled model of `variant` as one colored 3MF; checks that it
    holds as many of each part as the plates print."""
    pieces = layout(variant)
    # the LED filter screen has no place in the viewer's layout
    printed = Counter({k: v for k, v in counts(variant).items() if "WallPanel" not in k})
    placed = Counter(part for part, _ in pieces)
    if placed != printed:
        raise ValueError(f"{variant}: layout {placed} != plates {printed}")
    out = []
    for part, m in pieces:
        for name, fil, (v, t) in bodies(part):
            name = file_name(part) + (f" {name}" if part in TWO_COLOR else "")
            out.append((name, fil, (trimesh.transform_points(v, m).tolist(), t)))
    path = OUTPUT / "complete" / f"RasQberry-Two-{variant}.3mf"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_3mf(path, out)
    return path

# ---------------------------------------------------------------- plates

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


def arrange(sizes, bed):
    """Rows, largest first: [(x, y)] centres for parts of `sizes` (x, y) on
    a bed (x, y), the whole block centered."""
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
        raise ValueError(f"plate does not fit: {width:.0f} x {depth:.0f} mm")
    ox, oy = (bed[0] - width) / 2, (bed[1] - depth) / 2
    return [(pos[i][0] + ox, pos[i][1] + oy) for i in range(len(sizes))]


def project_config(base_ini, fil, supports):
    """Slic3r_PE.config: the resolved presets, with the (first) filament
    color and, where needed, automatic supports."""
    over = {"filament_colour": FILAMENTS[fil], "extruder_colour": FILAMENTS[fil]}
    if supports:
        over |= {"support_material": "1", "support_material_auto": "1",
                 "support_material_buildplate_only": "0"}
    lines = []
    for line in base_ini.splitlines():
        key = line.split(" = ", 1)[0]
        if line and not line.startswith("#"):
            lines.append(f"; {key} = {over.pop(key)}" if key in over else f"; {line}")
    if over:
        raise ValueError(f"not in the PrusaSlicer presets: {sorted(over)}")
    return "; generated by PrusaSlicer 2.9 presets (build_plates.py)\n\n" + "\n".join(lines) + "\n"


def color_change(items):
    """PrusaSlicer's per-layer G-code file for a two-color part on the
    plate (a filament change to its second filament), or None."""
    two = [p for p, _ in items if p in TWO_COLOR]
    if not two:
        return None
    (part,) = two
    second = filaments([(part, 1)])[1]
    return "\n".join([
        '<?xml version="1.0" encoding="utf-8"?>', "<custom_gcodes_per_print_z>",
        f'<code print_z="{TWO_COLOR[part]}" type="0" extruder="1" '
        f'color="{FILAMENTS[second]}" extra="" gcode="M600"/>',
        '<mode value="SingleExtruder"/>', "</custom_gcodes_per_print_z>"])


def write_plate(path, items, bed, config):
    """PrusaSlicer project: one object per part (one volume per body), one
    instance per copy."""
    objs = [(part, *oriented(part)) for part, _ in items]
    copies = [(i, k) for i, (_, k) in enumerate(items) for _ in range(k)]
    centres = arrange([tuple(objs[i][2][:2]) for i, _ in copies], bed)
    model = MODEL_HEAD + ["<resources>"]
    cfg = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    for n, (part, vols, _) in enumerate(objs, start=1):
        name = file_name(part)
        model.append(f'<object id="{n}" type="model" name={quoteattr(name)}><mesh><vertices>')
        for _, v, _ in vols:
            model += [f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in v]
        model.append("</vertices><triangles>")
        cfg += [f'<object id="{n}" instances_count="{items[n - 1][1]}">',
                f'<metadata type="object" key="name" value={quoteattr(name)}/>']
        base = first = 0
        for vname, v, t in vols:
            model += [f'<triangle v1="{a + base}" v2="{b + base}" v3="{c + base}"/>'
                      for a, b, c in t]
            cfg += [f'<volume firstid="{first}" lastid="{first + len(t) - 1}">',
                    f'<metadata type="volume" key="name" value={quoteattr(vname)}/>',
                    "</volume>"]
            base, first = base + len(v), first + len(t)
        model.append("</triangles></mesh></object>")
        cfg.append("</object>")
    model += ["</resources>", "<build>"]
    model += [f'<item objectid="{i + 1}" transform="1 0 0 0 1 0 0 0 1 {x:.3f} {y:.3f} 0" '
              f'printable="1"/>' for (i, _), (x, y) in zip(copies, centres)]
    model += ["</build>", "</model>"]
    cfg.append("</config>")
    meta = {"Metadata/Slic3r_PE_model.config": "\n".join(cfg), "Metadata/Slic3r_PE.config": config}
    if (change := color_change(items)):
        meta["Metadata/Prusa_Slicer_custom_gcode_per_print_z.xml"] = change
    path.parent.mkdir(parents=True, exist_ok=True)
    zip_3mf(path, model, meta)


# ---------------------------------------------------------------- PrusaSlicer

def scratch_datadir(exe, tmp):
    """A PrusaSlicer datadir with the vendor bundle that ships with `exe`
    (macOS app layout) and both printers installed."""
    bundle = Path(exe).resolve().parents[1] / "Resources" / "profiles"
    dd = Path(tmp) / "datadir"
    (dd / "vendor").mkdir(parents=True)
    for f in ("PrusaResearch.ini", "PrusaResearch.idx"):
        shutil.copy(bundle / f, dd / "vendor" / f)
    (dd / "PrusaSlicer.ini").write_text("[vendor:PrusaResearch]\nmodel:MK4S = HF0.4\n"
                                        "model:COREONE = HF0.4\n")
    return dd


def resolved(exe, dd, printer, print_, fil, tmp):
    """The full config of the three presets, as PrusaSlicer resolves them."""
    out = Path(tmp) / f"{printer}.ini"
    subprocess.run([exe, "--datadir", dd, "--printer-profile", printer, "--print-profile",
                    print_, "--material-profile", fil, "--save", out],
                   check=True, capture_output=True)
    ini = out.read_text()
    if f"printer_settings_id = {printer}" not in ini:
        raise RuntimeError(f"PrusaSlicer did not load {printer}")
    return ini


def slice_stats(exe, dd, plate, tmp):
    """(grams, time) from slicing `plate` with its own project config."""
    gcode = Path(tmp) / (plate.stem + ".gcode")
    r = subprocess.run([exe, "--datadir", dd, "--no-binary-gcode", "--export-gcode",
                        "-o", gcode, plate], capture_output=True, text=True)
    if r.returncode or not gcode.exists():
        raise RuntimeError(f"{plate.name}: slicing failed\n{r.stdout}{r.stderr}")
    text = gcode.read_text(errors="ignore")[-60000:]
    grams = float(re.search(r"; filament used \[g\] = ([\d.]+)", text).group(1))
    time = re.search(r"; estimated printing time \(normal mode\) = (.+)", text).group(1).strip()
    gcode.unlink()
    return grams, time

# ---------------------------------------------------------------- main

def plate_path(folder, n, name, items, swapped):
    """plates/<printer>/NN-<filaments>-<name>[-no-floor].3mf"""
    fil = "+".join(f.replace(" ", "-") for f in filaments(items))
    return OUTPUT / "plates" / folder / f"{n:02d}-{fil}-{name}{'-no-floor' if swapped else ''}.3mf"


def main():
    """Complete models, then the plates for each printer, then the print list."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prusaslicer", default=os.environ.get("PRUSASLICER", PRUSASLICER))
    a = ap.parse_args()
    for folder in ("complete", "plates"):   # all generated here: no stale plates
        shutil.rmtree(OUTPUT / folder, ignore_errors=True)
    for variant in VARIANTS:
        print("wrote", write_complete(variant).relative_to(OUTPUT))
    stats = {}
    with tempfile.TemporaryDirectory() as tmp:
        dd = scratch_datadir(a.prusaslicer, tmp)
        for folder, (printer, print_, fil_preset, bed) in PRINTERS.items():
            ini = resolved(a.prusaslicer, dd, printer, print_, fil_preset, tmp)
            done = set()
            for variant in VARIANTS:
                for n, name, items, swapped in plates(variant):
                    path = plate_path(folder, n, name, items, swapped)
                    if path in done:
                        continue
                    done.add(path)
                    supports = any(p in SUPPORTS for p, _ in items)
                    write_plate(path, items, bed, project_config(ini, filaments(items)[0], supports))
                    stats[folder, path.name] = slice_stats(a.prusaslicer, dd, path, tmp)
                    print("wrote", path.relative_to(OUTPUT), stats[folder, path.name])
    write_readme(stats)


def grams_by_filament(items, grams):
    """The plate's grams per filament; a two-color part is split by the
    volume of its bodies."""
    vol = Counter()
    for part, k in items:
        for _, fil, (v, t) in bodies(part):
            vol[fil] += k * abs(trimesh.Trimesh(v, t, process=False).volume)
    total = sum(vol.values())
    return {f: grams * x / total for f, x in vol.items()}


def write_readme(stats):
    """The print list: a table of all plates (MK4S and Core One grams and
    time), then the filament per color for both versions (MK4S)."""
    lines = ["# Print plates", "",
             "Generated by `cad/build_plates.py` from the new CAD parts (experimental,",
             "not fully tested yet). Open a plate in PrusaSlicer 2.9 or later, check,",
             "slice and print. Grams and times are PrusaSlicer's estimates (Prusament",
             "PLA, 0.20 mm SPEED, HF0.4 nozzle).", "",
             "**Without floor:** skip the floor plates and print the two `-no-floor`",
             "plates instead of their standard ones (wall base and cryostat without",
             "the holes for the floor plugs).", "",
             "**Two colors:** the cryostat lid with its chandeliers prints in one go;",
             f"PrusaSlicer pauses at {TWO_COLOR['RQB2-Cryostat-jrl01']} mm for the filament change "
             "(transparent to silk gold). Its grams per color are split by volume;",
             "the chandeliers' supports print in silk gold too.", "",
             "`../complete/` has both versions assembled, in color, to see what goes",
             "where (without the LED filter screen, which goes in front of the LEDs).", "",
             "| # | Plate | Parts | Filament | Without floor | MK4S | Core One |",
             "|---|---|---|---|---|---|---|"]
    rows = []
    for n, (name, items, no_floor) in enumerate(PLATES, start=1):
        rows.append((n, name, items, False,
                     "same" if no_floor is None else "skip" if not no_floor else "use the next row"))
        if no_floor:
            rows.append((n, name, no_floor, True, "instead of the row above"))
    for n, name, items, swapped, nf in rows:
        path = plate_path("MK4S", n, name, items, swapped)
        parts = ", ".join(f"{k} x {file_name(p)}" for p, k in items)
        cells = " | ".join(f"{stats[f, path.name][0]:.0f} g, {stats[f, path.name][1]}" for f in PRINTERS)
        lines.append(f"| {n:02d} | {name}{'-no-floor' if swapped else ''} | {parts} | {' + '.join(filaments(items))} "
                     f"| {nf} | {cells} |")
    lines.append("")
    for variant in VARIANTS:
        per = Counter()
        for n, name, items, swapped in plates(variant):
            g = stats["MK4S", plate_path("MK4S", n, name, items, swapped).name][0]
            per.update(grams_by_filament(items, g))
        title = "Standard" if variant == "standard" else "Without floor"
        grams = {f: round(g) for f, g in per.items()}
        lines.append(f"Filament, {title.lower()} (MK4S): "
                     + ", ".join(f"{f} {g} g" for f, g in grams.items())
                     + f"; {sum(grams.values())} g in total.")
        lines.append("")
    (OUTPUT / "plates" / "README.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
