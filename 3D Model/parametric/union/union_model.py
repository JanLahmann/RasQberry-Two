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
    CLAMP_Z=(0.13, 0.377, 0.624, 0.871),    # fractions of door height, both door edges
    CLAMP=dict(body=(0.05, 0.072, 0.026), lever_l=0.084, lever_d=0.018, knob_r=0.012),
    HANDLE=dict(r=0.011, length=0.22, standoff=0.052, x_frac=0.86),  # x_frac from the hinge edge
    HINGE=dict(r=0.022, h=0.10, z_frac=0.34, standoff=0.012),
    DOOR_OPEN_DEG=110,  # explorer opens doors to 1.92 rad (informational)
    # aluminium-extrusion gantry around the cell (press photos; not in the explorer)
    GANTRY=dict(profile=0.08, clearance=0.04, above=0.50,
                tubes=dict(n=2, r=0.06, dx=0.30)),        # pulse-tube lines hanging from the top beam
    # coupling window in a side panel (cells share a cold tunnel through wall openings)
    COUPLE_WINDOW=dict(w=0.60, h=0.90, z_frac=0.42, flange=0.05, flange_out=0.025),
    # feedthrough ports on the top plate (photos); separate pins glued into blind holes
    PORTS=dict(r=0.05, h=0.12, at=((0.0, 0.50), (0.0, -0.50))),
    CH=dict(plates=(0.72, 0.68, 0.59, 0.49, 0.40, 0.31), plate_r=0.09, plate_t=0.015,
            top_gap=0.085, pitch=0.176, column_r=0.013, rod_r=0.011,
            rod_top_frac=0.90, rod_bot_frac=0.92, mc_r=0.05, mc_h=0.10,
            flange=(0.30, 0.022), pulse_tube=(0.075, 0.028),       # on top of plate 1
            feedthroughs=dict(n=7, circle_r=0.115, r=0.016, h=0.045),
            side_blocks=(0.05, 0.042, 0.14, 0.05),                # w, h, d, +-x offset
            can=(0.19, 0.21, 0.19), can_label="IBM", can_label_h=0.05,
            # "photo" style (press photos): round plates + tiers of copper blocks
            photo_block=(0.12, 0.10, 0.10), photo_blocks_per_tier=5, photo_tiers=(3, 4, 5)),
)

# Pockets are on the INSIDE of every door/panel (photos + explorer: flat
# brushed exteriors, weight-saving pockets facing the vacuum space). Set to
# True for the decorative variant with pockets on the outside.
POCKETS_OUTSIDE = False
HINGE_SIDE = "left"          # "left" or "right": which post carries the hinge barrels
CH_STYLE = "explorer"        # "explorer" (square brass/gold plates) or "photo" (round plates + copper tiers)
COUPLED = "none"             # "none" | "left" | "right" | "both": side panels with a coupling window
DOORS = "all"                # "all": four removable doors (explorer/photos) | "front": only the front door
# hinge edge per face, pinwheel like the explorer (front: left edge, right: front edge, ...)
HINGE_EDGES = {"front": "left", "right": "front", "back": "right", "left": "back"}
PORTS = True                 # top-plate feedthrough ports (blind holes + "ports" pin part)

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
# the explorer's material palette: panels #c4c8cd/#d2d6da, frame #9aa0a6,
# brass #c8a24a, gold #e9c86c, copper #b5723c, black #131416, chrome #dfe2e6
COLOURS = dict(
    silver=Color(0xC4 / 255, 0xC8 / 255, 0xCD / 255),
    black=Color(0x13 / 255, 0x14 / 255, 0x16 / 255),
    gold=Color(0xE9 / 255, 0xC8 / 255, 0x6C / 255),
    copper=Color(0xB5 / 255, 0x72 / 255, 0x3C / 255),
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
        # features by size (clamps/handle/hinges survive at both scales once
        # their sections are clamped to the printable minimum; the label does not)
        self.clamps = mm(R["CLAMP"]["body"][2]) >= PRINT["min_detail"]
        self.handle = True
        self.hinges = True
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

    # ---- faces ---------------------------------------------------------------
    def door_faces(self):
        """Which faces carry a removable door."""
        faces = ["front"] if DOORS == "front" else ["front", "right", "back", "left"]
        coupled = {"none": (), "left": ("left",), "right": ("right",), "both": ("left", "right")}[COUPLED]
        return [f for f in faces if f not in coupled]

    def face_w_real(self, side):
        """Opening between the jambs of a face."""
        return 2 * ((self.post_cx if side in ("front", "back") else self.post_cy) - self.jamb)

    def face_door_w(self, side):
        return self.face_w_real(side) - 2 * PRINT["door_clearance"]

    def face_xy(self, side, u, v):
        """Face-local (u along the face from its centre, v = depth from the
        outer face inwards) -> world (x, y)."""
        return {"front": (u, self.P / 2 - v), "back": (-u, -self.P / 2 + v),
                "left": (-self.U / 2 + v, -u), "right": (self.U / 2 - v, u)}[side]

    # ---- shared positions (door magnets, coupling magnets) -----------------
    def door_magnet_xy(self, side="front"):
        """(x, y) of a door's magnets in world coords: 25 % / 75 % of the door
        width, on the door's mid-thickness plane. Used for the door edges,
        the top-plate underside and the plinth top - one formula, no drift."""
        w = self.face_door_w(side)
        return [self.face_xy(side, u, self.panel_t / 2) for u in (-0.25 * w, 0.25 * w)]

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
            ("clamps / handle / hinges / label",
             " / ".join(str(v) for v in (self.clamps, self.handle, self.hinges, self.label))),
            ("doors", ", ".join(self.door_faces())),
            ("pockets / hinge / chandelier / coupled / ports",
             f"{'outside' if POCKETS_OUTSIDE else 'inside'} / {HINGE_SIDE} / {CH_STYLE} / {COUPLED} / {PORTS}"),
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
    """Panel w (x) by h (y) by panel_t (z). Local frame: x = horizontal along
    the face, y = up, z = into the panel; z = 0 is the OUTER face. Pockets are
    cut into the inner face (z = panel_t) unless POCKETS_OUTSIDE."""
    panel = Box(w, h, d.panel_t, align=(Align.MIN, Align.MIN, Align.MIN))
    z0 = -0.01 if POCKETS_OUTSIDE else d.panel_t - d.pocket_depth
    cutters = []
    for cx, cy, pw, ph in pocket_grid(d, w, h, cols, rows):
        r = min(d.pocket_r, pw / 2 - 0.01, ph / 2 - 0.01)
        face = RectangleRounded(pw, ph, r) if r >= 0.3 else Rectangle(pw, ph)
        cutters.append(extrude(Plane.XY.offset(z0) * Pos(cx, cy) * face,
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
    doors = d.door_faces()
    for side in ("front", "right", "back", "left"):
        if side in doors:
            continue
        ncols = cols["side"] if side in ("left", "right") else cols["back"]
        body += place_face(pocketed_panel(d, d.door_w_real if side in ("front", "back") else d.side_w,
                                          d.frame_h, ncols, rows), d, side, z0)
    # flat door jambs on the posts of every door face (fill between post surface and door edge)
    for side in doors:
        half = d.post_cx if side in ("front", "back") else d.post_cy
        for sgn in (-1, 1):
            x, y = d.face_xy(side, sgn * (half - d.jamb / 2), d.panel_t / 2)
            sz = (d.jamb, d.panel_t) if side in ("front", "back") else (d.panel_t, d.jamb)
            body += Pos(x, y, z0) * Box(sz[0], sz[1], d.frame_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    body = body.clean()
    # coupling windows: opening through the side panel with a shallow flange frame
    cw = REAL["COUPLE_WINDOW"]
    for side, sx in (("left", -1), ("right", 1)):
        if COUPLED not in (side, "both"):
            continue
        ww, wh = d.mm(cw["w"]), d.mm(cw["h"])
        fw, fo = max(d.mm(cw["flange"]), 1.2), max(d.mm(cw["flange_out"]), 0.8)
        zc = z0 + cw["z_frac"] * d.frame_h
        x_face = sx * d.U / 2
        frame = Pos(x_face, 0, zc) * Box(2 * fo, ww + 2 * fw, wh + 2 * fw)
        body += frame
        body -= Pos(x_face, 0, zc) * Box(2 * d.panel_t + 2 * fo + 2, ww, wh)
    # door magnets: pockets in the top-plate underside (axis +z, open downwards)
    mag_d, mag_t = PRINT["magnet"]
    for side in doors:
        for x, y in d.door_magnet_xy(side):
            body -= Pos(x, y, z1) * magnet_pocket(mag_d, mag_t)
    # blind holes for the feedthrough-port pins in the top face
    if PORTS:
        pr = max(d.mm(REAL["PORTS"]["r"]), 1.5)
        for x, y in REAL["PORTS"]["at"]:
            body -= Pos(d.mm(x), d.mm(y), d.z_top - 1.5) * z_cyl(pr * 0.8 + 0.15, 0, 1.6)
    # chandelier stub hole in the ceiling centre
    body -= Pos(0, 0, z1) * magnet_pocket(d.stub_d, d.stub_hole_depth, clearance_d=0.3, clearance_h=0.0)
    # hinge barrels on the hinge-side post of every door face
    if d.hinges:
        hr = max(d.mm(REAL["HINGE"]["r"]), 0.8)
        hh = d.mm(REAL["HINGE"]["h"])
        zf = REAL["HINGE"]["z_frac"]
        zc = z0 + d.frame_h / 2
        for side in doors:
            half = d.post_cx if side in ("front", "back") else d.post_cy
            u = hinge_u(d, side, half - d.post_r * 0.15)   # just inboard of the post's tangent
            x, y = d.face_xy(side, u, -hr * 0.6)          # half sunk into the post face: prints upright
            for s in (-1, 1):
                body += z_cyl(hr, zc + s * zf * d.frame_h - hh / 2, zc + s * zf * d.frame_h + hh / 2, x, y)
    return body.clean()


def hinge_u(d, side, half):
    """Face-local u of the hinge edge (+-half): explorer pinwheel, mirrored
    for HINGE_SIDE == "right" (the right-hand cell of a pair)."""
    edge = HINGE_EDGES[side]
    # face-local +u runs: front -> +x (right), back -> -x, left -> -y (back), right -> +y (front)
    plus_u = {"front": "right", "back": "left", "left": "back", "right": "front"}[side]
    sign = 1 if edge == plus_u else -1
    if HINGE_SIDE == "right":
        sign = -sign
    return sign * half


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
    # door magnets in the top face (open upwards), one set per door
    mag_d, mag_t = PRINT["magnet"]
    for side in d.door_faces():
        for x, y in d.door_magnet_xy(side):
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


def build_door(d, side="front"):
    """Removable door for one face: flat pocketed panel between the post
    jambs, magnet pockets in the top and bottom edges, toggle clamps on both
    edges, pull handle at the free edge. Built in place (world coords)."""
    cols = REAL["POCKET_COLS"]["side" if side in ("left", "right") else "front"]
    rows = REAL["POCKET_ROWS"]
    z0 = d.z_plinth_top + 0.2
    w = d.face_door_w(side)
    door = place_face(pocketed_panel(d, w, d.door_h, cols, rows), d, side, z0)
    mag_d, mag_t = PRINT["magnet"]
    for x, y in d.door_magnet_xy(side):
        door -= Pos(x, y, z0 + d.door_h) * Rot(X=180) * magnet_pocket(mag_d, mag_t)
        door -= Pos(x, y, z0) * magnet_pocket(mag_d, mag_t)
    door = door.clean()

    def at(u, v, z):          # face-local (u, v = outward stand-off) -> world Pos
        x, y = d.face_xy(side, u, -v)
        return Pos(x, y, z)

    along = (1, 0) if side in ("front", "back") else (0, 1)   # world axis of face-local u
    outward = (0, 1) if side in ("front", "back") else (1, 0)  # world axis of face-local v

    def box(lu, lv, lz):      # box with lu along the face, lv outward, lz up
        return Box(lu * along[0] + lv * outward[0], lu * along[1] + lv * outward[1], lz)

    if d.clamps:
        bw, bh, bt = (max(d.mm(v), 0.8) for v in REAL["CLAMP"]["body"])
        ll = d.mm(REAL["CLAMP"]["lever_l"])
        ld_ = max(d.mm(REAL["CLAMP"]["lever_d"]), 0.8)
        kr = max(d.mm(REAL["CLAMP"]["knob_r"]), 0.6)
        for su in (-1, 1):
            u = su * (w / 2 - d.pocket_margin_x / 2)
            for zf in REAL["CLAMP_Z"]:
                z = z0 + zf * d.door_h
                door += at(u, bt / 2, z) * box(bw, bt, bh)
                # lever lying on the clamp body, pointing to the door centre
                door += at(u - su * (ll / 2 - bw / 4), bt + ld_ / 2, z) * box(ll, ld_, ld_)
                # knob: short cylinder, not a sphere (sphere poles tessellate into
                # zero-area triangles that the CI analyzer rejects)
                knob = Cylinder(kr, 1.5 * kr)
                knob = (Rot(Y=90) if along[0] else Rot(X=90)) * knob
                door += at(u - su * (ll - bw / 4), bt + ld_ / 2, z) * knob
    if d.handle:
        h = REAL["HANDLE"]
        hr = max(d.mm(h["r"]), 0.8)
        hl, so = d.mm(h["length"]), d.mm(h["standoff"])
        # x_frac is measured from the hinge edge, so the handle sits near the free edge
        u = hinge_u(d, side, w / 2) * (1 - 2 * h["x_frac"])
        zc = z0 + d.door_h / 2
        x, y = d.face_xy(side, u, -so)
        door += z_cyl(hr, zc - hl / 2, zc + hl / 2, x, y)
        reach = (0.5 if not POCKETS_OUTSIDE else d.pocket_depth + 0.5)
        xi, yi = d.face_xy(side, u, reach)
        for sgn in (-1, 1):
            door += cyl_between((xi, yi, zc + sgn * hl / 2), (x, y, zc + sgn * hl / 2), hr * 1.1)
    return door.clean()


def build_chandelier(d):
    """Dilution-fridge "chandelier" hanging from the ceiling. Returns a dict of
    colour bodies {colour: solid}.

    CH_STYLE "explorer": six shrinking square plates (upper brass, lower
    gold - printed in one gold), central column, four slanted corner rods,
    top flange on the ceiling, pulse tube + 7 feedthroughs + two side blocks
    (copper) on plate 1, mixing chamber (gold) under plate 5, processor can
    (silver, recessed "IBM" on the showpiece) under the bottom plate.
    CH_STYLE "photo": as in the press photos - round plates, and three tiers
    of copper blocks under the lower plates instead of the can."""
    ch = REAL["CH"]
    z_ceiling = d.z_ceiling
    n = len(d.ch_plates)
    tops = [z_ceiling - d.ch_top_gap - i * d.ch_pitch for i in range(n)]
    round_plates = CH_STYLE == "photo"

    def plate(size, zt):
        if round_plates:
            return z_cyl(size / 2, zt - d.ch_plate_t, zt)
        return rounded_box(size, size, d.ch_plate_t, d.ch_plate_r, z0=zt - d.ch_plate_t)

    gold = None
    for sz, zt in zip(d.ch_plates, tops):
        pl = plate(sz, zt)
        gold = pl if gold is None else gold + pl
    z_top, z_bot = tops[0], tops[-1] - d.ch_plate_t
    gold += z_cyl(d.ch_column_r, z_bot, z_top)
    # top flange sitting on the ceiling + locating stub into the ceiling hole
    fl_w, fl_t = d.mm(ch["flange"][0]), max(d.mm(ch["flange"][1]), 0.8)
    gold += rounded_box(fl_w, fl_w, fl_t, d.mm(0.03), z0=z_ceiling - fl_t)
    gold += z_cyl(d.stub_d / 2, z_ceiling - fl_t - 0.01, z_ceiling + d.stub_hole_depth - 0.2)
    # column continues up to the flange
    gold += z_cyl(d.ch_column_r, z_top - 0.01, z_ceiling - fl_t + 0.01)
    # slanted corner rods
    a0 = d.ch_plates[0] / 2 * ch["rod_top_frac"]
    a1 = d.ch_plates[-1] / 2 * ch["rod_bot_frac"]
    if round_plates:      # keep the rods inside the round plates
        a0, a1 = a0 / math.sqrt(2), a1 / math.sqrt(2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            gold += cyl_between((sx * a0, sy * a0, z_top - d.ch_plate_t / 2),
                                (sx * a1, sy * a1, z_bot + d.ch_plate_t / 2), d.ch_rod_r)
    # mixing chamber (gold) under plate 5
    z5 = tops[4] - d.ch_plate_t
    gold += z_cyl(d.ch_mc_r, z5 - d.ch_mc_h, z5 + 0.01)
    gold = gold.clean()

    # copper: pulse tube + feedthroughs + side blocks on top of plate 1
    pt_r, pt_h = max(d.mm(ch["pulse_tube"][0]), 1.0), max(d.mm(ch["pulse_tube"][1]), 0.8)
    copper = z_cyl(pt_r, z_top - 0.01, z_top + pt_h)
    ft = ch["feedthroughs"]
    ft_r = max(d.mm(ft["r"]), 0.5)
    for i in range(ft["n"]):
        a = 2 * math.pi * i / ft["n"]
        x, y = d.mm(ft["circle_r"]) * math.cos(a), d.mm(ft["circle_r"]) * math.sin(a)
        copper += z_cyl(ft_r, z_top - 0.01, z_top + max(d.mm(ft["h"]) * (0.6 + 0.2 * (i % 3)), 0.8), x, y)
    bw, bh, bd, bx = (d.mm(v) for v in ch["side_blocks"])
    for sx in (-1, 1):
        copper += Pos(sx * bx, 0, z_top - 0.01) * Box(bw, bd, bh, align=(Align.CENTER, Align.CENTER, Align.MIN))
    bodies = {"gold": gold}
    label = None
    if round_plates:
        # tiers of copper blocks hanging under the lower plates
        pw_, ph_, pd_ = (d.mm(v) for v in ch["photo_block"])
        per = ch["photo_blocks_per_tier"]
        for ti in ch["photo_tiers"]:
            zt = tops[ti] - d.ch_plate_t
            span = d.ch_plates[ti] * 0.8
            for k in range(per):
                x = -span / 2 + span * (k + 0.5) / per
                w = min(pw_, span / per - 0.3)
                copper += Pos(x, 0, zt + 0.01) * Box(w, pd_, ph_, align=(Align.CENTER, Align.CENTER, Align.MAX))
        bodies["copper"] = copper.clean()
    else:
        bodies["copper"] = copper.clean()
        # processor can (silver) under the bottom plate
        cw, ch_, cd = d.ch_can
        can = Pos(0, 0, z_bot + 0.01) * Box(cw, cd, ch_, align=(Align.CENTER, Align.CENTER, Align.MAX))
        if d.label:
            try:
                txt = Text(ch["can_label"], font_size=d.mm(ch["can_label_h"]), font="Arial")
                depth = 0.4
                stamp = Pos(0, cd / 2 + 0.01, z_bot - ch_ / 2) * Rot(X=90) * extrude(txt, depth + 0.01)
                label = (can & stamp).clean()
                if label.volume > 0:
                    can = (can - stamp).clean()
                else:
                    label = None
            except Exception as exc:  # font problems etc. - label is decoration only
                print(f"  (label skipped: {exc})")
                label = None
        bodies["silver"] = can.clean()
    if label is not None:
        bodies["white"] = label
    return bodies


def build_gantry(d):
    """Aluminium-extrusion frame around the cell as in the press photos: four
    square posts outside the plinth, a top rectangle of beams 0.5 m above the
    cell, one cross beam carrying two pulse-tube lines that hang down to the
    top plate. Prints upside down (top frame on the bed)."""
    g = REAL["GANTRY"]
    prof = max(d.mm(g["profile"]), 3.5)
    gap = d.mm(g["clearance"])
    hx = d.plinth_w / 2 + gap + prof / 2
    hy = d.plinth_d / 2 + gap + prof / 2
    z_top = d.z_top + d.mm(g["above"])
    gantry = None
    for sx in (-1, 1):
        for sy in (-1, 1):
            post = Pos(sx * hx, sy * hy, 0) * Box(prof, prof, z_top, align=(Align.CENTER, Align.CENTER, Align.MIN))
            gantry = post if gantry is None else gantry + post
    for sy in (-1, 1):   # beams along x
        gantry += Pos(0, sy * hy, z_top - prof / 2) * Box(2 * hx + prof, prof, prof)
    for sx in (-1, 1):   # beams along y
        gantry += Pos(sx * hx, 0, z_top - prof / 2) * Box(prof, 2 * hy + prof, prof)
    gantry += Pos(0, 0, z_top - prof / 2) * Box(2 * hx, prof, prof)   # cross beam
    tr = max(d.mm(g["tubes"]["r"]), 1.2)
    for i in range(g["tubes"]["n"]):
        x = (i - (g["tubes"]["n"] - 1) / 2) * 2 * d.mm(g["tubes"]["dx"])
        gantry += z_cyl(tr, d.z_top + 0.6, z_top - prof + 0.01, x, 0)
    return gantry.clean()


def build_ports(d):
    """Feedthrough-port pins for the top plate (glued into the blind holes)."""
    pr = max(d.mm(REAL["PORTS"]["r"]), 1.5)
    ph = max(d.mm(REAL["PORTS"]["h"]), 2.0)
    ports = None
    for x, y in REAL["PORTS"]["at"]:
        pin = z_cyl(pr * 0.8, d.z_top - 1.4, d.z_top + 0.01, d.mm(x), d.mm(y)) + \
            z_cyl(pr, d.z_top, d.z_top + ph, d.mm(x), d.mm(y))
        ports = pin if ports is None else ports + pin
    return ports.clean()


# ===========================================================================
# Print orientation + main
# ===========================================================================

def on_bed(shape):
    """Translate so the bounding box rests on z = 0 and is centred in x/y."""
    bb = shape.bounding_box()
    return Pos(-(bb.min.X + bb.max.X) / 2, -(bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * shape


def print_orientation(name, shape):
    if name in ("body", "plinth", "chandelier", "gantry"):
        shape = Rot(X=180) * shape          # upside down: flat top / plinth top / biggest plate / top frame on the bed
    elif name == "ports":
        pass                                # pins standing on their pegs
    elif name.startswith("door"):
        side = name.split("_")[1] if "_" in name else "front"
        # bring the face's outward normal to +z: lying flat, outer face (clamps, handle) up
        shape = {"front": Rot(X=90), "back": Rot(X=-90), "left": Rot(Y=90), "right": Rot(Y=-90)}[side] * shape
    return on_bed(shape)


def build_cell(preset):
    d = Dims(preset)
    print(f"=== preset {preset} ===")
    print(d.table())
    ch_bodies = build_chandelier(d)
    chandelier = None
    for b in ch_bodies.values():
        chandelier = b if chandelier is None else chandelier + b
    chandelier = chandelier.clean()
    parts = {
        "body": (build_body(d), [("silver", None)]),
        "plinth": (build_plinth(d), [("black", None)]),
    }
    for side in d.door_faces():
        parts[f"door_{side}"] = (build_door(d, side), [("silver", None)])
    parts.update({
        "chandelier": (chandelier, list(ch_bodies.items())),
        "gantry": (build_gantry(d), [("silver", None)]),
    })
    if PORTS:
        parts["ports"] = (build_ports(d), [("silver", None)])
    return d, parts


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--preset", default="all", choices=["all", *PRESETS])
    ap.add_argument("--no-led", action="store_true", help="omit LED pocket and wire channel")
    ap.add_argument("--hinge", default="left", choices=["left", "right"],
                    help="hinge side (IBM's left cell hinges left, the right one right); "
                         "'right' adds the suffix _R to the output files")
    ap.add_argument("--chandelier", default="explorer", choices=["explorer", "photo"],
                    help="chandelier style; 'photo' adds the suffix _photo")
    ap.add_argument("--pockets-outside", action="store_true",
                    help="decorative variant: pocket grid on the outside (suffix _out)")
    ap.add_argument("--coupled", default="none", choices=["none", "left", "right", "both"],
                    help="coupling window in the given side panel(s) (suffix _cL/_cR/_cLR)")
    ap.add_argument("--no-ports", action="store_true", help="omit top-plate port holes and the ports part")
    ap.add_argument("--doors", default="all", choices=["all", "front"],
                    help="four removable doors (default, as the real cell) or only the front door (suffix _1d)")
    ap.add_argument("--no-step", action="store_true", help="skip STEP export (faster)")
    args = ap.parse_args()
    global LED, HINGE_SIDE, CH_STYLE, POCKETS_OUTSIDE, COUPLED, PORTS, DOORS
    LED = not args.no_led
    HINGE_SIDE, CH_STYLE, POCKETS_OUTSIDE = args.hinge, args.chandelier, args.pockets_outside
    COUPLED, PORTS, DOORS = args.coupled, not args.no_ports, args.doors
    suffix = ("_R" if HINGE_SIDE == "right" else "") + ("_photo" if CH_STYLE == "photo" else "") \
        + ("_out" if POCKETS_OUTSIDE else "") \
        + {"none": "", "left": "_cL", "right": "_cR", "both": "_cLR"}[COUPLED] \
        + ("_1d" if DOORS == "front" else "")
    formats = ("stl", "3mf") if args.no_step else ("stl", "step", "3mf")
    OUTDIR.mkdir(exist_ok=True)
    for preset in (PRESETS if args.preset == "all" else [args.preset]):
        d, parts = build_cell(preset)
        manifest = dict(preset=preset, scale=d.scale, led=LED, parts={},
                        doors={side: d.door_magnet_xy(side) for side in d.door_faces()},
                        couple_magnet_yz=d.couple_magnet_yz(),
                        magnet=PRINT["magnet"], couple_magnet=d.couple_magnet,
                        z_plinth_top=d.z_plinth_top, z_ceiling=d.z_ceiling, z_top=d.z_top,
                        cell=(d.U, d.P, d.z_top), door=(d.door_w, d.door_h, d.panel_t),
                        doors_mode=DOORS)
        coloured = {}
        for name, (solid, colour_bodies) in parts.items():
            if name == "ports":     # several loose pins in one file, by design
                vol = sum(check_solid(sub, f"{name}[{i}]") for i, sub in enumerate(solid.solids()))
            else:
                vol = check_solid(solid, name)
            size = bbox_size(solid)
            print(f"  {name:<10} {size[0]:6.1f} x {size[1]:6.1f} x {size[2]:6.1f} mm  "
                  f"{vol / 1000:6.2f} cm3")
            manifest["parts"][name] = dict(size_assembled=size, volume_cm3=vol / 1000,
                                           colours=[c for c, _ in colour_bodies])
            stem = f"Union_{preset}{suffix}_{name}"
            export_all(print_orientation(name, solid), stem, OUTDIR, formats=formats,
                       color=COLOURS[colour_bodies[0][0]], stl_tolerance=PRINT["stl_tolerance"])
            for colour, sub in colour_bodies:
                coloured[f"{name}.{colour}"] = (solid if sub is None else sub, COLOURS[colour])
        export_multicolour_3mf(coloured, OUTDIR / f"Union_{preset}{suffix}_assembly.3mf",
                               tolerance=PRINT["stl_tolerance"])
        if not args.no_step:
            from build123d import export_step
            asm = Compound(children=[s for s, _ in coloured.values()])
            export_step(asm, str(OUTDIR / f"Union_{preset}{suffix}_assembly.step"))
            print(f"  wrote Union_{preset}{suffix}_assembly.step")
        manifest.update(hinge=HINGE_SIDE, chandelier=CH_STYLE, pockets_outside=POCKETS_OUTSIDE,
                        coupled=COUPLED, ports=PORTS)
        (OUTDIR / f"Union_{preset}{suffix}_manifest.json").write_text(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
