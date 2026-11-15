#!/usr/bin/env python3
"""Ready-to-print plates and the colored complete model, from the new CAD parts.

For each variant in PLAN (the new standard with the dovetail floor, and the
version without floor with the closed wall base and cryostat):

- `print/generated/complete/RasQberry-Two-<variant>.3mf`: every part in its
  place in the assembled model, in its filament colour (one object, one named
  part per printed piece), to see what goes where.
- `print/generated/plates/<printer>/<variant>/NN-<filament>-<name>.3mf`:
  PrusaSlicer projects, one filament per plate, parts turned the right way up
  and laid out on the bed, with the printer, print and filament presets
  (Prusament PLA, 0.20 mm SPEED, HF0.4 nozzle) and supports where needed.
- `print/generated/plates/README.md`: the print list (parts, quantities,
  filament, grams and time per plate from PrusaSlicer).

PrusaSlicer (2.9) is used to resolve its system presets and to slice each
plate once for grams and time; the 3MF files are written here. Its CLI only
knows printers that are installed in its datadir, so a scratch datadir with
the two printers is made in a temporary folder (yours is not touched).

Usage:  python build_plates.py [--prusaslicer PATH] [--no-slice]
"""
import argparse
import math
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
from rqb_cad import MODEL_HEAD, OUTPUT, PARTS, part_path, write_3mf, zip_3mf

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
    "R2_Wall-Lid": "flip", "R2_Wall-Back": "flat",
    "R2_NarrowServerSingleLid": "flip", "R2_CryoLid-Simple": "flip",
    "R2_ChandelierSingle": "flip",
}
SUPPORTS = {"R2_ChandelierSingle"}   # the plates of the chandelier overhang the column

# variant: [(plate name, [(part, count)])], one filament per plate
PLAN = {
    "standard": [
        ("wall-base-back", [("R2_Wall-Base-jrl01-2", 1), ("R2_Wall-Back", 1)]),
        ("wall-lid", [("R2_Wall-Lid", 1)]),
        ("floor-tile-1-plugs", [("R2_Floor-Tile1", 1), ("R2_Floor-CryoPlug", 1),
                                ("R2_Floor-WallPlug", 2)]),
        *[(f"floor-tile-{t[4:]}", [(f"R2_Floor-{t}", 1)])
          for t in ("Tile2", "Tile3", "Tile4", "Tile5", "Tile6s")],
        ("cryostat-door-servers", [("R2_NarrowYCryoConjoined", 1), ("R2_NewDoor", 1),
                                   ("R2_NarrowServerSingle", 3)]),
        ("lids", [("R2_CryoLid-Simple", 1), ("R2_NarrowServerSingleLid", 9)]),
        ("chandeliers", [("R2_ChandelierSingle", 3)]),
        ("optional-led-filter-screen", [("RQB2-WallPanel-jrl02-2", 1)]),
    ],
    "no-floor": [
        ("wall-base-back", [("R2_Wall-Base-jrl01-2-nofloor", 1), ("R2_Wall-Back", 1)]),
        ("wall-lid", [("R2_Wall-Lid", 1)]),
        ("cryostat-door-servers", [("RQB2-R2_CryoStandaloneGamma-jrl04-nofloor", 1),
                                   ("R2_NewDoor", 1), ("RQB2-R2_NarrowServerSingle-jrl02", 5)]),
        ("lids", [("R2_CryoLid-Simple", 1), ("R2_NarrowServerSingleLid", 5)]),
        ("chandeliers", [("R2_ChandelierSingle", 3)]),
        ("optional-led-filter-screen", [("RQB2-WallPanel-jrl02-2", 1)]),
    ],
}

# ---------------------------------------------------------------- assembly

def T(x, y, z=0.0):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def rot(axis, deg):
    m = np.eye(4)
    m[:3, :3] = trimesh.transformations.rotation_matrix(math.radians(deg), axis)[:3, :3].round(12)
    return m


def about(c, deg):
    return T(*c) @ rot([0, 0, 1], deg) @ T(-c[0], -c[1])


# The layout of the website's 3D viewer (gh-pages scripts/build-3d-model.mjs),
# in the frame of the ORIGINAL STLs: measured from the floor's hex holes and
# the matching holes in the wall base and the cryostat.
WALL = T(-9.89, 383.26)
CRYO_C = (-72.0, -206.1)
CRYO = T(130.0 - CRYO_C[0], 145.4 - CRYO_C[1])
ARMS = (0, 120, 240)
CAP = T(-73.3, -122.8, -1)
SOCKETS = ((9.0, -96.9), (9.0, -70.0), (-14.0, -83.2))
SERVER_Y = (-183.8, -160.5)
# new parts, in the frame of the generated floor (= the original's): the
# plug flanges sit under the 3 mm floor plate (z -3); the wall plugs are
# turned 30 deg (locked)
CRYO_HOLE, WALL_HOLES, PLATE_UNDERSIDE = (130.32, 140.18), ((37.36, 322.27), (222.57, 322.27)), -3.0
FLANGE = {"R2_Floor-CryoPlug": 2.0, "R2_Floor-WallPlug": 4.0}
# the generated cryostats (conjoined, Gamma) share one frame: body centred on
# the origin, flats at y = +-33, door at -y; the jrl02 servers of the
# no-floor version stand 0.2 mm off the five walls, like the conjoined arms
FLAT, ARM_GAP, SERVER_HALF = 33.0, 0.2, 11.62
NO_FLOOR_WALLS = (0, 60, -60, 120, -120)   # deg from the back wall (+y)

# generated part -> the original it was rebuilt from (for its frame)
ORIGINAL_OF = {
    "R2_Wall-Base-jrl01-2": "wall/R2_Wall-Base", "R2_Wall-Base-jrl01-2-nofloor": "wall/R2_Wall-Base",
    "R2_Wall-Back": "wall/R2_Wall-Back", "R2_Wall-Lid": "wall/R2_Wall-Lid",
    "R2_NarrowYCryoConjoined": "cryostat/R2_NarrowYCryoConjoined",
    "R2_NewDoor": "cryostat/R2_NewDoor", "R2_CryoLid-Simple": "cryostat/R2_CryoLid-Simple",
    "R2_ChandelierSingle": "cryostat/R2_ChandelierSingle",
    "R2_NarrowServerSingle": "RTE/R2_NarrowServerSingle",
    "R2_NarrowServerSingleLid": "RTE/R2_NarrowServerSingleLid",
}
STANDIN = {   # same frame as the generated part named here
    "R2_Wall-Base-jrl01-2": "R2_Wall-Base", "R2_Wall-Base-jrl01-2-nofloor": "R2_Wall-Base",
}


def mesh(name):
    return trimesh.load(f"{part_path(name)}.stl", force="mesh", process=False)


def to_original(name):
    """Move generated part `name` into its original's frame: the rebuilds
    keep the shape but were re-centred, so the bounding-box centres are
    matched (R2_Wall-Back is 2 mm narrower than its original, centred)."""
    gen = mesh(STANDIN.get(name, name)).bounds
    org = trimesh.load(ORIGINALS / f"{ORIGINAL_OF[name]}.stl", force="mesh").bounds
    if np.abs((gen[1] - gen[0]) - (org[1] - org[0])).max() > 2.5:
        raise ValueError(f"{name}: size differs from its original, frame unknown")
    return T(*(org.mean(0) - gen.mean(0)))


def layout(variant):
    """[(part, 4x4)]: every printed piece of `variant` in the assembled model."""
    o = to_original
    cryo = CRYO @ o("R2_NarrowYCryoConjoined")       # the generated cryostat frame
    out = [("R2_Wall-Back", WALL @ T(5.3, -100) @ o("R2_Wall-Back")),
           ("R2_Wall-Lid", WALL @ o("R2_Wall-Lid")),
           ("R2_NewDoor", CRYO @ T(-204.05, -134.9, -7) @ o("R2_NewDoor")),
           ("R2_CryoLid-Simple", CRYO @ CAP @ o("R2_CryoLid-Simple"))]
    out += [("R2_ChandelierSingle", CRYO @ CAP @ T(x, y, 92.3) @ rot([1, 0, 0], 180)
             @ T(-64.24, 2.58, 14.7) @ o("R2_ChandelierSingle")) for x, y in SOCKETS]
    if variant == "standard":
        base = "R2_Wall-Base-jrl01-2"
        out += [(f"R2_Floor-{t}", np.eye(4))
                for t in ("Tile1", "Tile2", "Tile3", "Tile4", "Tile5", "Tile6s")]
        out.append(("R2_Floor-CryoPlug", T(*CRYO_HOLE, PLATE_UNDERSIDE - FLANGE["R2_Floor-CryoPlug"])))
        out += [("R2_Floor-WallPlug", T(x, y, PLATE_UNDERSIDE - FLANGE["R2_Floor-WallPlug"])
                 @ rot([0, 0, 1], 30)) for x, y in WALL_HOLES]
        out.append(("R2_NarrowYCryoConjoined", cryo))
        lid = o("R2_NarrowServerSingleLid")
        out += [("R2_NarrowServerSingleLid", CRYO @ about(CRYO_C, a) @ T(-91.1, y - 72.6) @ lid)
                for a in ARMS for y in SERVER_Y]
        for a in ARMS:   # one stand-alone server with its lid in front of each arm
            out.append(("R2_NarrowServerSingle", CRYO @ about(CRYO_C, a) @ T(-91.1, -251.7)
                        @ o("R2_NarrowServerSingle")))
            out.append(("R2_NarrowServerSingleLid", CRYO @ about(CRYO_C, a)
                        @ T(-91.1, -137.2 - 72.6) @ lid))
    else:
        base = "R2_Wall-Base-jrl01-2-nofloor"
        out.append(("RQB2-R2_CryoStandaloneGamma-jrl04-nofloor", cryo))
        for a in NO_FLOOR_WALLS:
            m = cryo @ rot([0, 0, 1], a) @ T(0, FLAT + ARM_GAP + SERVER_HALF)
            out += [("RQB2-R2_NarrowServerSingle-jrl02", m), ("R2_NarrowServerSingleLid", m)]
    out.insert(0, (base, WALL @ o(base)))
    return out


def counts(plates):
    n = {}
    for _, items in plates:
        for part, k in items:
            n[part] = n.get(part, 0) + k
    return n


def write_complete(variant):
    pieces = layout(variant)
    printed = {k: v for k, v in counts(PLAN[variant]).items() if "WallPanel" not in k}
    placed = {}
    for part, _ in pieces:
        placed[part] = placed.get(part, 0) + 1
    if placed != printed:
        raise ValueError(f"{variant}: layout {placed} != plan {printed}")
    bodies = []
    for part, m in pieces:
        v, t = stl_mesh(f"{part_path(part)}.stl")
        v = trimesh.transform_points(np.asarray(v), m)
        bodies.append((part, filament(Path(PARTS[part] + ".stl")), (v.tolist(), t)))
    path = OUTPUT / "complete" / f"RasQberry-Two-{variant}.3mf"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_3mf(path, bodies)
    return path

# ---------------------------------------------------------------- plates

def oriented(part):
    """(vertices, triangles) of `part` turned for printing, centred in x/y,
    standing on z = 0."""
    v, t = stl_mesh(f"{part_path(part)}.stl")
    v = np.asarray(v)
    turn = {"up": np.eye(4), "flip": rot([1, 0, 0], 180), "flat": rot([1, 0, 0], -90)}
    v = trimesh.transform_points(v, turn[ORIENT.get(part, "up")])
    lo, hi = v.min(0), v.max(0)
    return v - [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]], t, hi - lo


def arrange(sizes, bed):
    """Rows, largest first: [(x, y)] centres for parts of `sizes` (x, y) on
    a bed (x, y), the whole block centred."""
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
    """Slic3r_PE.config: the resolved presets, with the filament colour and,
    where needed, automatic supports from the bed only."""
    from rqb_cad import FILAMENTS
    over = {"filament_colour": FILAMENTS[fil], "extruder_colour": FILAMENTS[fil]}
    if supports:
        over |= {"support_material": "1", "support_material_auto": "1",
                 "support_material_buildplate_only": "1"}
    lines = []
    for line in base_ini.splitlines():
        key = line.split(" = ", 1)[0]
        if line and not line.startswith("#"):
            lines.append(f"; {key} = {over.pop(key)}" if key in over else f"; {line}")
    return "; generated by PrusaSlicer 2.9 presets (build_plates.py)\n\n" + "\n".join(lines) + "\n"


def plate_filament(items):
    """The one filament of a plate's parts."""
    (fil,) = {filament(Path(PARTS[p] + ".stl")) for p, _ in items}
    return fil


def write_plate(path, items, bed, config):
    """PrusaSlicer project: one object per part, one instance per copy."""
    objs = [(part, *oriented(part)) for part, _ in items]
    copies = [(i, k) for i, (_, k) in enumerate(items) for _ in range(k)]
    centres = arrange([tuple(objs[i][3][:2]) for i, _ in copies], bed)
    model = MODEL_HEAD + ["<resources>"]
    cfg = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    for n, (part, v, t, _) in enumerate(objs, start=1):
        model.append(f'<object id="{n}" type="model" name={quoteattr(part)}><mesh><vertices>')
        model += [f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in v]
        model.append("</vertices><triangles>")
        model += [f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in t]
        model.append("</triangles></mesh></object>")
        cfg += [f'<object id="{n}" instances_count="{items[n - 1][1]}">',
                f'<metadata type="object" key="name" value={quoteattr(part)}/>',
                f'<volume firstid="0" lastid="{len(t) - 1}">',
                f'<metadata type="volume" key="name" value={quoteattr(part)}/>',
                "</volume>", "</object>"]
    model += ["</resources>", "<build>"]
    model += [f'<item objectid="{i + 1}" transform="1 0 0 0 1 0 0 0 1 {x:.3f} {y:.3f} 0" '
              f'printable="1"/>' for (i, _), (x, y) in zip(copies, centres)]
    model += ["</build>", "</model>"]
    cfg.append("</config>")
    path.parent.mkdir(parents=True, exist_ok=True)
    zip_3mf(path, model, {"Metadata/Slic3r_PE_model.config": "\n".join(cfg),
                          "Metadata/Slic3r_PE.config": config})


# ---------------------------------------------------------------- PrusaSlicer

def scratch_datadir(exe, tmp):
    """A PrusaSlicer datadir with the vendor bundle and both printers installed."""
    home = Path.home() / "Library/Application Support/PrusaSlicer/vendor"
    dd = Path(tmp) / "datadir"
    (dd / "vendor").mkdir(parents=True)
    for f in ("PrusaResearch.ini", "PrusaResearch.idx"):
        shutil.copy(home / f, dd / "vendor" / f)
    (dd / "PrusaSlicer.ini").write_text("[vendor:PrusaResearch]\nmodel:MK4S = HF0.4\n"
                                        "model:COREONE = HF0.4\n")
    return dd


def resolved(exe, dd, printer, print_, fil, tmp):
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

TITLE = {"standard": "Standard (dovetail floor, plugs)",
         "no-floor": "Without floor (closed wall base and cryostat)"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prusaslicer", default=os.environ.get("PRUSASLICER", PRUSASLICER))
    ap.add_argument("--no-slice", action="store_true", help="skip grams/time (README unchanged)")
    a = ap.parse_args()
    for variant in PLAN:
        print("wrote", write_complete(variant).relative_to(OUTPUT))
    stats = {}
    with tempfile.TemporaryDirectory() as tmp:
        dd = scratch_datadir(a.prusaslicer, tmp)
        for folder, (printer, print_, fil_preset, bed) in PRINTERS.items():
            ini = resolved(a.prusaslicer, dd, printer, print_, fil_preset, tmp)
            for variant, plates in PLAN.items():
                for n, (name, items) in enumerate(plates, start=1):
                    fil = plate_filament(items)
                    path = (OUTPUT / "plates" / folder / variant
                            / f"{n:02d}-{fil.replace(' ', '-')}-{name}.3mf")
                    supports = any(p in SUPPORTS for p, _ in items)
                    write_plate(path, items, bed, project_config(ini, fil, supports))
                    if not a.no_slice:
                        stats[folder, variant, n] = slice_stats(a.prusaslicer, dd, path, tmp)
                    print("wrote", path.relative_to(OUTPUT), stats.get((folder, variant, n), ""))
    if not a.no_slice:
        write_readme(stats)


def write_readme(stats):
    """The print list: per variant a table of the plates (MK4S and Core One
    grams and time), then the filament per colour (MK4S)."""
    lines = ["# Print plates", "",
             "Generated by `cad/build_plates.py` from the new CAD parts (experimental,",
             "not fully tested yet). One filament per plate: open a plate in",
             "PrusaSlicer 2.9 or later, check, slice and print. Grams and times are",
             "PrusaSlicer's estimates (Prusament PLA, 0.20 mm SPEED, HF0.4 nozzle).",
             "`optional` plates are not needed for the model.", "",
             "`../complete/` has each variant assembled, in colour, to see what goes",
             "where.", ""]
    for variant, plates in PLAN.items():
        lines += [f"## {TITLE[variant]}", "",
                  "| # | Plate | Parts | Filament | MK4S | Core One |", "|---|---|---|---|---|---|"]
        per_filament = {}
        for n, (name, items) in enumerate(plates, start=1):
            fil = plate_filament(items)
            parts = ", ".join(f"{k} x {p}" for p, k in items)
            cells = " | ".join(f"{stats[f, variant, n][0]:.0f} g, {stats[f, variant, n][1]}"
                               for f in PRINTERS)
            lines.append(f"| {n:02d} | {name} | {parts} | {fil} | {cells} |")
            if not name.startswith("optional"):
                per_filament[fil] = per_filament.get(fil, 0) + stats["MK4S", variant, n][0]
        lines += ["", "Filament (MK4S, without optional plates): "
                  + ", ".join(f"{f} {g:.0f} g" for f, g in per_filament.items())
                  + f"; {sum(per_filament.values()):.0f} g in total.", ""]
    (OUTPUT / "plates" / "README.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
