#!/usr/bin/env python3
"""RasQberry "Union" - IBM modular cryogenic cell, parametric model.

A desk-top, 3D-printable miniature of one cell of IBM's Modular Quantum
Cryogenic Architecture (announced 2026-08-19; photo-asset name "Union").
Cells are self-contained print sets that couple side-by-side with disc
magnets - print as many as you like.

The model is authored in REAL-WORLD METRES (numbers decoded from IBM's
interactive "cryo-fridge-explorer" on the announcement blog, cross-checked
against the MoQCA public information sheet and the press photos) and scaled
down by a preset:

    desk       body height 93.3 mm (= every existing RasQberry body),  ~1:23.6
    showpiece  1:15, with fine detail (toggle clamps, pull handle, hinges, label)

Parts per cell (separate prints, one closed body each):
    body        posts + top plate + 3 fixed pocketed panels (silver)
    plinth      base slab + casters, registration lip, LED pocket/channel (black)
    door        removable front door, held by magnets (silver)
    chandelier  6-stage dilution-fridge "chandelier" (gold + copper details)

Outputs (./output):
    Union_<preset>_<part>.stl / .step / .3mf       print orientation, z = 0 on bed
    Union_<preset>_assembly.3mf / .step             all parts, assembled, coloured
    Union_<preset>_manifest.json                    derived dimensions + magnet
                                                    positions (read by validate_union.py)

Usage:  python3 union_model.py [--preset desk|showpiece|all] [--no-led]
        (run inside the .venv-cad described in ../README.md)

All dimensions in the code are metres in REAL and millimetres everywhere
else. Requires build123d; shared helpers live in ../rqb_cad.py.
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build123d import (  # noqa: E402
    Align, Box, Color, Compound, Cylinder, Location, Plane, Pos, Rectangle,
    RectangleRounded, Rot, Text, Vector, extrude,
)

from rqb_cad import (  # noqa: E402
    bbox_size, check_solid, export_all, export_multicolour_3mf, magnet_pocket,
    rounded_box,
)

# ===========================================================================
# Parameters
# ===========================================================================

# --- the real thing, in metres (IBM explorer / MoQCA sheet) ------------------
REAL = dict(
    U=1.10,            # cell width (= pitch when cells are coupled)
    P=1.80,            # cell depth
    FRAME_H=1.837,     # height of the door/post zone (plinth top -> top plate)
    PLINTH_W=1.15, PLINTH_D=1.85, PLINTH_T=0.17, PLINTH_R=0.15,
    CASTER_H=0.10,     # floor -> plinth underside
    CASTER_XY=(0.45, 0.80),  # caster centres at (+-x, +-y)
    CASTER_BLOCK=(0.07, 0.06, 0.05), CASTER_WHEEL_R=0.05, CASTER_WHEEL_W=0.035,
    TOP_T=0.09,        # top plate thickness
    POST_R=0.07,       # corner post radius (explorer: 0.13 - slimmer here, see README)
    PANEL_T=0.11,      # door / panel thickness
    PANEL_BACK=0.045,  # back plate behind the pockets (pocket depth = PANEL_T - PANEL_BACK)
    DOOR_GAP=0.025,    # explorer: door 0.05 shorter than the frame zone
    POCKET=dict(margin_x=0.10, margin_y=0.075, gap=0.045, r=0.014),
    POCKET_COLS=dict(front=3, side=5, back=3), POCKET_ROWS=6,
    CLAMP_Z=(0.13, 0.377, 0.624, 0.871),    # fractions of door height
    CLAMP=dict(body=(0.05, 0.072, 0.026), lever_l=0.084, lever_d=0.018, knob_r=0.012),
    HANDLE=dict(r=0.011, length=0.22, standoff=0.052, x_frac=0.86),
    HINGE=dict(r=0.022, h=0.10, z_frac=0.34, standoff=0.012),
    CH=dict(plates=(0.72, 0.68, 0.59, 0.49, 0.40, 0.31), plate_r=0.09, plate_t=0.015,
            top_gap=0.085, pitch=0.176, column_r=0.013, rod_r=0.011,
            rod_top_frac=0.90, rod_bot_frac=0.92, mc_r=0.05, mc_h=0.10,
            can=(0.19, 0.21, 0.19), can_label="IBM", can_label_h=0.05),
)

# --- presets ----------------------------------------------------------------
TOTAL_REAL_H = REAL["CASTER_H"] + REAL["PLINTH_T"] + REAL["FRAME_H"] + REAL["TOP_T"]  # 2.197 m
PRESETS = {
    # body height 93.3 mm = the RasQberry style constant (cryostat, RTEs, door)
    "desk": dict(scale=0.0933 / TOTAL_REAL_H, detail=False),
    "showpiece": dict(scale=1 / 15, detail=True),
}

# --- printability (0.4 mm nozzle, PLA) ---------------------------------------
PRINT = dict(
    min_wall=1.0,        # thinnest wall we accept
    min_gap=1.0,         # thinnest web between pockets
    min_detail=0.6,      # smallest free-standing feature (else dropped)
    door_clearance=0.3,  # door <-> post, per side
    lip_clearance=0.15,  # plinth lip <-> body cavity, per side
    magnet=(3.0, 2.0),         # door magnets: diameter x thickness (disc)
    couple_magnet=(5.0, 2.0),  # cell <-> cell magnets in the plinth sides
    magnet_floor=0.6,          # material left under a magnet pocket
    stub=(4.0, 2.0),           # chandelier locating peg: diameter x length into the top plate
    led_pocket=(10.0, 3.0),    # LED pocket in the plinth centre: diameter x depth
    led_channel=(3.0, 3.0),    # wire channel to the rear edge: width x depth
    stl_tolerance=0.01,
)
LED = True   # --no-led turns the pocket/channel off

# --- colours (5 MMU slots) ----------------------------------------------------
COLOURS = dict(
    silver=Color(0.80, 0.80, 0.82),
    black=Color(0.10, 0.10, 0.11),
    gold=Color(0.85, 0.66, 0.15),
    copper=Color(0.85, 0.52, 0.33),
    white=Color(0.95, 0.95, 0.95),
)

OUTDIR = Path(__file__).parent / "output"


# ===========================================================================
# Derived dimensions (mm) for a preset
# ===========================================================================

class Dims:
    """Everything in mm, derived from REAL x scale plus the print rules."""

    def __init__(self, preset):
        p = PRESETS[preset]
        self.preset, self.scale, self.detail = preset, p["scale"], p["detail"]
        mm = self.mm
        R = REAL
        self.U, self.P = mm(R["U"]), mm(R["P"])
        self.caster_h = mm(R["CASTER_H"])
        self.plinth_t = mm(R["PLINTH_T"])
        self.plinth_w, self.plinth_d = mm(R["PLINTH_W"]), mm(R["PLINTH_D"])
        self.plinth_r = mm(R["PLINTH_R"])
        self.z_plinth_top = self.caster_h + self.plinth_t          # frame zone starts here
        self.frame_h = mm(R["FRAME_H"])
        self.z_ceiling = self.z_plinth_top + self.frame_h           # top plate underside
        self.top_t = mm(R["TOP_T"])
        self.z_top = self.z_ceiling + self.top_t                     # overall body height
        self.post_r = mm(R["POST_R"])
        self.post_cx, self.post_cy = self.U / 2 - self.post_r, self.P / 2 - self.post_r
        # panels / door: thickness must hold the door magnets with a wall each side
        mag_d, mag_t = PRINT["magnet"]
        self.panel_t = max(mm(R["PANEL_T"]), mag_d + 0.25 + 2 * 0.8)
        self.panel_back = max(mm(R["PANEL_BACK"]), PRINT["min_wall"])
        self.pocket_depth = self.panel_t - self.panel_back
        # The posts bulge into the door slab behind the front face. Each front
        # post gets a flat jamb (door stop) at x = +-(post_cx - jamb), so the
        # door itself is a plain flat panel between the jambs.
        r, t = self.post_r, self.panel_t
        self.jamb = math.sqrt(max(2 * r * t - t * t, 0.0)) if t < 2 * r else r
        self.door_w_real = 2 * (self.post_cx - self.jamb)         # opening between the jambs
        self.door_w = self.door_w_real - 2 * PRINT["door_clearance"]
        # the door hangs on its top/bottom magnets, so it nearly fills the frame zone
        self.door_h = self.frame_h - 0.4
        self.side_w = self.P - 2 * self.post_r
        # pockets
        pk = R["POCKET"]
        self.pocket_margin_x = mm(pk["margin_x"])
        self.pocket_margin_y = mm(pk["margin_y"])
        self.pocket_gap = max(mm(pk["gap"]), PRINT["min_gap"])
        self.pocket_r = mm(pk["r"])
        # features by size
        self.clamps = self.detail and mm(R["CLAMP"]["body"][2]) >= PRINT["min_detail"]
        self.handle = self.detail
        self.hinges = self.detail
        self.label = self.detail
        # chandelier
        ch = R["CH"]
        self.ch_plates = [mm(s) for s in ch["plates"]]
        self.ch_plate_r = mm(ch["plate_r"])
        self.ch_plate_t = max(mm(ch["plate_t"]), 0.8)
        self.ch_top_gap = mm(ch["top_gap"])
        self.ch_pitch = mm(ch["pitch"])
        self.ch_column_r = max(mm(ch["column_r"]), 1.5)
        self.ch_rod_r = max(mm(ch["rod_r"]), 0.6)
        self.ch_mc_r = max(mm(ch["mc_r"]), 1.5)
        self.ch_mc_h = min(mm(ch["mc_h"]), self.ch_pitch - self.ch_plate_t - 0.5)
        self.ch_can = tuple(mm(v) for v in ch["can"])
        # stub into the top plate: leave >= 1.2 mm of plate above the hole
        self.stub_d, stub_len = PRINT["stub"]
        self.stub_hole_depth = min(stub_len, self.top_t - 1.2)
        # coupling magnets live in the plinth side faces
        cm_d, cm_t = PRINT["couple_magnet"]
        if cm_d + 0.25 + 2 * 0.8 > self.plinth_t:
            cm_d = max(2.0, self.plinth_t - 0.25 - 1.6)   # shrink to fit thin plinths
        self.couple_magnet = (cm_d, cm_t)

    def mm(self, metres):
        return metres * 1000.0 * self.scale

    # ---- shared positions (door magnets, coupling magnets) -----------------
    def door_magnet_xy(self):
        """(x, y) of the door magnets in world coords: 25 % / 75 % of the door
        width, on the door's mid-thickness plane. Used for the door edges,
        the top-plate underside and the plinth top - one formula, no drift."""
        y = self.P / 2 - self.panel_t / 2
        return [(-0.25 * self.door_w, y), (0.25 * self.door_w, y)]

    def couple_magnet_yz(self):
        """(y, z) of the coupling magnets on the plinth's left/right faces."""
        z = self.caster_h + self.plinth_t / 2
        return [(-0.25 * self.P, z), (0.25 * self.P, z)]

    def table(self):
        rows = [
            ("scale", f"1:{1 / self.scale:.1f}"),
            ("cell W x D x H (mm)", f"{self.U:.1f} x {self.P:.1f} x {self.z_top:.1f}"),
            ("plinth W x D x T", f"{self.plinth_w:.1f} x {self.plinth_d:.1f} x {self.plinth_t:.1f}"),
            ("post radius / door jamb", f"{self.post_r:.2f} / {self.jamb:.2f}"),
            ("panel thickness / back", f"{self.panel_t:.2f} / {self.panel_back:.2f}"),
            ("pocket depth / gap", f"{self.pocket_depth:.2f} / {self.pocket_gap:.2f}"),
            ("door W x H x T", f"{self.door_w:.1f} x {self.door_h:.1f} x {self.panel_t:.2f}"),
            ("door magnets", f"{PRINT['magnet'][0]} x {PRINT['magnet'][1]} mm, 2 top + 2 bottom"),
            ("coupling magnets", f"{self.couple_magnet[0]:.1f} x {self.couple_magnet[1]} mm, 2 per plinth side"),
            ("chandelier plates", " / ".join(f"{s:.1f}" for s in self.ch_plates)
             + f"  (t {self.ch_plate_t:.2f}, pitch {self.ch_pitch:.2f})"),
            ("detail: clamps / handle / hinges / label",
             " / ".join(str(v) for v in (self.clamps, self.handle, self.hinges, self.label))),
            ("LED pocket / channel", f"{PRINT['led_pocket']} / {PRINT['led_channel']}" if LED else "off"),
        ]
        w = max(len(k) for k, _ in rows)
        return "\n".join(f"  {k:<{w}}  {v}" for k, v in rows)


# ===========================================================================
# Geometry helpers
# ===========================================================================

def pocket_grid(d, w, h, cols, rows):
    """Pocket rectangles (cx, cy, pw, ph) on a w x h face (origin bottom-left),
    cols x rows, using the real margins/gap. Counts stay real; if the scaled
    gap fell below the printable minimum, pockets shrink to keep the webs."""
    mx, my, g = d.pocket_margin_x, d.pocket_margin_y, d.pocket_gap
    px = (w - 2 * mx - (cols - 1) * g) / cols
    py = (h - 2 * my - (rows - 1) * g) / rows
    if px <= 0 or py <= 0:
        return []
    out = []
    for i in range(cols):
        for j in range(rows):
            out.append((mx + i * (px + g) + px / 2, my + j * (py + g) + py / 2, px, py))
    return out


def pocketed_panel(d, w, h, cols, rows):
    """Panel w (x) by h (y) by panel_t (z), pockets cut into the z = 0 face.
    Local frame: x = horizontal along the face, y = up, z = into the panel."""
    panel = Box(w, h, d.panel_t, align=(Align.MIN, Align.MIN, Align.MIN))
    cutters = []
    for cx, cy, pw, ph in pocket_grid(d, w, h, cols, rows):
        r = min(d.pocket_r, pw / 2 - 0.01, ph / 2 - 0.01)
        face = RectangleRounded(pw, ph, r) if r >= 0.3 else Rectangle(pw, ph)
        cutters.append(extrude(Plane.XY.offset(-0.01) * Pos(cx, cy) * face,
                               d.pocket_depth + 0.01))
    return (panel - cutters).clean() if cutters else panel


def place_face(panel, d, side, z0):
    """Move a panel built by pocketed_panel() (pocketed face at local z = 0,
    local x along the face, local y up) onto a cell face. Its pocketed face
    ends up flush with the post tangent plane, its bottom edge at z0."""
    # local z -> world -y, local y -> world z ; then face ends at y = 0 facing +y
    oriented = Rot(X=90) * panel
    w = panel.bounding_box().max.X - panel.bounding_box().min.X
    oriented = Pos(-w / 2, 0, z0) * oriented
    yaw = {"front": 0, "left": 90, "back": 180, "right": -90}[side]
    offs = {"front": (0, d.P / 2), "back": (0, -d.P / 2),
            "left": (-d.U / 2, 0), "right": (d.U / 2, 0)}[side]
    return Pos(offs[0], offs[1], 0) * Rot(Z=yaw) * oriented


def cyl_between(p0, p1, r):
    """Cylinder of radius r from point p0 to p1."""
    v = Vector(*p1) - Vector(*p0)
    plane = Plane(origin=Vector(*p0), z_dir=v.normalized())
    return plane * Cylinder(r, v.length, align=(Align.CENTER, Align.CENTER, Align.MIN))


def z_cyl(r, z0, z1, x=0.0, y=0.0):
    return Pos(x, y, z0) * Cylinder(r, z1 - z0, align=(Align.CENTER, Align.CENTER, Align.MIN))


# ===========================================================================
# Parts
# ===========================================================================

def build_body(d):
    """Posts + top plate + back/left/right pocketed panels, open front and
    bottom. Magnet pockets for the door in the top-plate underside, locating
    hole for the chandelier stub, hinge barrels beside the door (showpiece)."""
    z0, z1 = d.z_plinth_top, d.z_ceiling
    body = rounded_box(d.U, d.P, d.top_t, d.post_r, z0=z1)
    for sx in (-1, 1):
        for sy in (-1, 1):
            body += z_cyl(d.post_r, z0, z1, sx * d.post_cx, sy * d.post_cy)
    cols = REAL["POCKET_COLS"]
    rows = REAL["POCKET_ROWS"]
    body += place_face(pocketed_panel(d, d.door_w_real, d.frame_h, cols["back"], rows), d, "back", z0)
    for side in ("left", "right"):
        body += place_face(pocketed_panel(d, d.side_w, d.frame_h, cols["side"], rows), d, side, z0)
    # flat door jambs on the front posts (fill between post surface and door edge)
    for sx in (-1, 1):
        body += Pos(sx * (d.post_cx - d.jamb / 2), d.P / 2 - d.panel_t / 2, z0) * Box(
            d.jamb, d.panel_t, d.frame_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    body = body.clean()
    # door magnets: pockets in the top-plate underside (axis +z, open downwards)
    mag_d, mag_t = PRINT["magnet"]
    for x, y in d.door_magnet_xy():
        body -= Pos(x, y, z1) * magnet_pocket(mag_d, mag_t)
    # chandelier stub hole in the ceiling centre
    body -= Pos(0, 0, z1) * magnet_pocket(d.stub_d, d.stub_hole_depth, clearance_d=0.3, clearance_h=0.0)
    # hinge barrels on the front face beside the door (left post side), showpiece only
    if d.hinges:
        hr, hh = d.mm(REAL["HINGE"]["r"]), d.mm(REAL["HINGE"]["h"])
        zf = REAL["HINGE"]["z_frac"]
        zc = z0 + d.frame_h / 2
        x = -(d.post_cx - d.post_r * 0.15)   # just inboard of the post's front tangent
        y = d.P / 2 + d.mm(REAL["HINGE"]["standoff"])
        for s in (-1, 1):
            body += z_cyl(hr, zc + s * zf * d.frame_h - hh / 2, zc + s * zf * d.frame_h + hh / 2, x, y)
    return body.clean()


def build_plinth(d):
    """Base slab with rounded corners, 4 casters, a registration lip the body
    sits over, door-magnet pockets in the top face, coupling-magnet pockets in
    the left/right faces, LED pocket + wire channel (optional)."""
    zb, zt = d.caster_h, d.z_plinth_top
    plinth = rounded_box(d.plinth_w, d.plinth_d, d.plinth_t, d.plinth_r, z0=zb)
    # casters
    bw, bd, bh = (d.mm(v) for v in REAL["CASTER_BLOCK"])
    wr, ww = d.mm(REAL["CASTER_WHEEL_R"]), d.mm(REAL["CASTER_WHEEL_W"])
    cx, cy = (d.mm(v) for v in REAL["CASTER_XY"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * cx, sy * cy
            plinth += Pos(x, y, zb - bh / 2) * Box(bw, bd, bh)
            # wheel: horizontal cylinder (axis x), bottom at z = 0
            plinth += Pos(x, y, wr) * Rot(Y=90) * Cylinder(wr, ww)
    # registration lip: the body's inner cavity outline minus clearance
    lip_h = 1.0
    c = PRINT["lip_clearance"]
    lip_w, lip_d = d.U - 2 * d.panel_t - 2 * c, d.P - 2 * d.panel_t - 2 * c
    lip = Pos(0, 0, zt) * Box(lip_w, lip_d, lip_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for sx in (-1, 1):
        for sy in (-1, 1):
            lip -= z_cyl(d.post_r + c, zt - 1, zt + lip_h + 1, sx * d.post_cx, sy * d.post_cy)
    # the lip must stay behind the door (the door stands in front of it)
    lip -= Pos(0, d.P / 2 - d.panel_t - c, zt - 1) * Box(d.U, d.panel_t * 2, lip_h + 2,
                                                        align=(Align.CENTER, Align.MIN, Align.MIN))
    plinth = (plinth + lip).clean()
    # door magnets in the top face (open upwards)
    mag_d, mag_t = PRINT["magnet"]
    for x, y in d.door_magnet_xy():
        plinth -= Pos(x, y, zt) * Rot(X=180) * magnet_pocket(mag_d, mag_t)
    # coupling magnets in the left/right faces (axis x)
    cm_d, cm_t = d.couple_magnet
    for y, z in d.couple_magnet_yz():
        plinth -= Pos(-d.plinth_w / 2, y, z) * Rot(Y=90) * magnet_pocket(cm_d, cm_t)
        plinth -= Pos(d.plinth_w / 2, y, z) * Rot(Y=-90) * magnet_pocket(cm_d, cm_t)
    # LED pocket in the centre of the top face + wire channel to the rear edge
    if LED:
        ld, ldep = PRINT["led_pocket"]
        cw, cdep = PRINT["led_channel"]
        ldep = min(ldep, d.plinth_t - 1.2)
        cdep = min(cdep, ldep)
        plinth -= Pos(0, 0, zt + lip_h + 0.01) * Rot(X=180) * magnet_pocket(ld, ldep + lip_h, 0.0, 0.0)
        plinth -= Pos(0, -d.plinth_d / 4 - 1, zt + lip_h - cdep - lip_h) * Box(
            cw, d.plinth_d / 2 + 2, cdep + lip_h + 1, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return plinth.clean()


def build_door(d):
    """Removable front door: flat pocketed panel between the post jambs,
    magnet pockets in the top and bottom edges. Showpiece: toggle clamps +
    pull handle."""
    cols, rows = REAL["POCKET_COLS"]["front"], REAL["POCKET_ROWS"]
    z0 = d.z_plinth_top + 0.2
    door = place_face(pocketed_panel(d, d.door_w, d.door_h, cols, rows), d, "front", z0)
    # magnets in the top and bottom edges
    mag_d, mag_t = PRINT["magnet"]
    for x, y in d.door_magnet_xy():
        door -= Pos(x, y, z0 + d.door_h) * Rot(X=180) * magnet_pocket(mag_d, mag_t)
        door -= Pos(x, y, z0) * magnet_pocket(mag_d, mag_t)
    door = door.clean()
    yf = d.P / 2   # door face plane
    if d.clamps:
        bw, bh, bt = (d.mm(v) for v in REAL["CLAMP"]["body"])
        ll, ld_, kr = (d.mm(REAL["CLAMP"][k]) for k in ("lever_l", "lever_d", "knob_r"))
        for sx in (-1, 1):
            x = sx * (d.door_w / 2 - d.pocket_margin_x / 2)
            for zf in REAL["CLAMP_Z"]:
                z = z0 + zf * d.door_h
                door += Pos(x, yf + bt / 2, z) * Box(bw, bt, bh)
                # lever lying on the clamp body, pointing to the door centre
                door += Pos(x - sx * (ll / 2 - bw / 4), yf + bt + ld_ / 2, z) * Box(ll, ld_, ld_)
                # knob: short cylinder, not a sphere (sphere poles tessellate into
                # zero-area triangles that the CI analyzer rejects)
                door += Pos(x - sx * (ll - bw / 4), yf + bt + ld_ / 2, z) * Rot(Y=90) * Cylinder(kr, 1.5 * kr)
    if d.handle:
        h = REAL["HANDLE"]
        hr = max(d.mm(h["r"]), 0.8)
        hl, so = d.mm(h["length"]), d.mm(h["standoff"])
        x = -d.door_w / 2 + h["x_frac"] * d.door_w
        zc = z0 + d.door_h / 2
        door += z_cyl(hr, zc - hl / 2, zc + hl / 2, x, yf + so)
        # stand-offs reach down to the pocket floor (the handle sits over a pocket column)
        for s in (-1, 1):
            door += cyl_between((x, yf - d.pocket_depth - 0.5, zc + s * hl / 2),
                                (x, yf + so, zc + s * hl / 2), hr * 1.1)
    return door.clean()


def build_chandelier(d):
    """Six shrinking square plates on a central column with four slanted
    corner rods, locating stub on top; mixing-chamber cylinder under plate 5
    and one processor can under the bottom plate (copper). Returns
    (gold_solid, copper_solid, label_solid_or_None)."""
    z_ceiling = d.z_ceiling
    tops = [z_ceiling - d.ch_top_gap - i * d.ch_pitch for i in range(len(d.ch_plates))]
    gold = None
    for s, zt in zip(d.ch_plates, tops):
        plate = rounded_box(s, s, d.ch_plate_t, d.ch_plate_r, z0=zt - d.ch_plate_t)
        gold = plate if gold is None else gold + plate
    z_top, z_bot = tops[0], tops[-1] - d.ch_plate_t
    gold += z_cyl(d.ch_column_r, z_bot, z_top)
    # stub into the ceiling hole
    gold += z_cyl(d.stub_d / 2, z_top - 0.01, z_ceiling + d.stub_hole_depth - 0.2)
    # slanted corner rods
    ch = REAL["CH"]
    a0 = d.ch_plates[0] / 2 * ch["rod_top_frac"]
    a1 = d.ch_plates[-1] / 2 * ch["rod_bot_frac"]
    for sx in (-1, 1):
        for sy in (-1, 1):
            gold += cyl_between((sx * a0, sy * a0, z_top - d.ch_plate_t / 2),
                                (sx * a1, sy * a1, z_bot + d.ch_plate_t / 2), d.ch_rod_r)
    gold = gold.clean()
    # copper: mixing chamber under plate 5, processor can under plate 6
    z5 = tops[4] - d.ch_plate_t
    copper = z_cyl(d.ch_mc_r, z5 - d.ch_mc_h, z5 + 0.01)
    cw, ch_, cd = d.ch_can
    copper += Pos(0, 0, z_bot + 0.01) * Box(cw, cd, ch_, align=(Align.CENTER, Align.CENTER, Align.MAX))
    copper = copper.clean()
    label = None
    if d.label:
        try:
            txt = Text(ch["can_label"], font_size=d.mm(ch["can_label_h"]), font="Arial")
            depth = 0.4
            # on the can's front face (+y), recessed and filled white
            stamp = Pos(0, cd / 2 + 0.01, z_bot - ch_ / 2) * Rot(X=90) * extrude(txt, depth + 0.01)
            # extrude goes +z in the text frame -> after Rot(X=90) it points -y (into the can)
            label = (copper & stamp).clean()
            if label.volume > 0:
                copper = (copper - stamp).clean()
            else:
                label = None
        except Exception as exc:  # font problems etc. - label is decoration only
            print(f"  (label skipped: {exc})")
            label = None
    return gold, copper, label


# ===========================================================================
# Print orientation + main
# ===========================================================================

def on_bed(shape):
    """Translate so the bounding box rests on z = 0 and is centred in x/y."""
    bb = shape.bounding_box()
    return Pos(-(bb.min.X + bb.max.X) / 2, -(bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * shape


def print_orientation(name, shape):
    if name in ("body", "plinth", "chandelier"):
        shape = Rot(X=180) * shape          # upside down: flat top / plinth top / biggest plate on the bed
    elif name == "door":
        shape = Rot(X=90) * shape           # lying flat, pocketed face up
    return on_bed(shape)


def build_cell(preset):
    d = Dims(preset)
    print(f"=== preset {preset} ===")
    print(d.table())
    gold, copper, label = build_chandelier(d)
    chandelier = (gold + copper).clean() if label is None else (gold + copper + label).clean()
    parts = {
        "body": (build_body(d), [("silver", None)]),
        "plinth": (build_plinth(d), [("black", None)]),
        "door": (build_door(d), [("silver", None)]),
        "chandelier": (chandelier, [("gold", gold), ("copper", copper)] + ([("white", label)] if label is not None else [])),
    }
    return d, parts


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--preset", default="all", choices=["all", *PRESETS])
    ap.add_argument("--no-led", action="store_true", help="omit LED pocket and wire channel")
    ap.add_argument("--no-step", action="store_true", help="skip STEP export (faster)")
    args = ap.parse_args()
    global LED
    LED = not args.no_led
    formats = ("stl", "3mf") if args.no_step else ("stl", "step", "3mf")
    OUTDIR.mkdir(exist_ok=True)
    for preset in (PRESETS if args.preset == "all" else [args.preset]):
        d, parts = build_cell(preset)
        manifest = dict(preset=preset, scale=d.scale, led=LED, parts={},
                        door_magnet_xy=d.door_magnet_xy(), couple_magnet_yz=d.couple_magnet_yz(),
                        magnet=PRINT["magnet"], couple_magnet=d.couple_magnet,
                        z_plinth_top=d.z_plinth_top, z_ceiling=d.z_ceiling, z_top=d.z_top,
                        cell=(d.U, d.P, d.z_top), door=(d.door_w, d.door_h, d.panel_t))
        coloured = {}
        for name, (solid, colour_bodies) in parts.items():
            vol = check_solid(solid, name)
            size = bbox_size(solid)
            print(f"  {name:<10} {size[0]:6.1f} x {size[1]:6.1f} x {size[2]:6.1f} mm  "
                  f"{vol / 1000:6.2f} cm3")
            manifest["parts"][name] = dict(size_assembled=size, volume_cm3=vol / 1000,
                                           colours=[c for c, _ in colour_bodies])
            stem = f"Union_{preset}_{name}"
            export_all(print_orientation(name, solid), stem, OUTDIR, formats=formats,
                       color=COLOURS[colour_bodies[0][0]], stl_tolerance=PRINT["stl_tolerance"])
            for colour, sub in colour_bodies:
                coloured[f"{name}.{colour}"] = (solid if sub is None else sub, COLOURS[colour])
        export_multicolour_3mf(coloured, OUTDIR / f"Union_{preset}_assembly.3mf",
                               tolerance=PRINT["stl_tolerance"])
        if not args.no_step:
            from build123d import export_step
            asm = Compound(children=[s for s, _ in coloured.values()])
            export_step(asm, str(OUTDIR / f"Union_{preset}_assembly.step"))
            print(f"  wrote Union_{preset}_assembly.step")
        (OUTDIR / f"Union_{preset}_manifest.json").write_text(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
