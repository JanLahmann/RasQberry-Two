# Sources and provenance

The Union model is an **artistic interpretation** of IBM's Modular Quantum
Cryogenic Architecture for 3D printing — not an IBM drawing. Dimensions were
taken from the public material below; where IBM's own stylised explorer and
the photos disagree, the photos win (one chandelier per cell), and where the
real geometry does not print at desk scale, printability wins (see the
"deviations" list).

## IBM material (2026-08-19 announcement)

| What | Where | Used for |
|---|---|---|
| IBM Quantum blog "IBM's new modular architecture for cryogenic systems" (C. Dundon, M. Hollister, A. Lindler) | https://www.ibm.com/quantum/blog/modular-cryogenics | Text (box-shaped aluminium cells, 2.75 m³ vacuum, 0.53 m² wiring, "3x a kitchen fridge"), photos `IBM-Research_Union_04/05/07.jpg`, interactive explorer |
| Interactive "Cryogenic Enclosure — interactive model" (iframe in the blog) | `https://research-website-prod-interactive.s3.us-east.cloud-object-storage.appdomain.cloud/cryo-fridge-explorer/index.html` | **All proportions in `REAL`**: the explorer has no downloadable 3D asset; its three.js scene is generated procedurally in `assets/index-*.js` with metre dimensions (cell 1.1 × 1.8 × ~2.2 m, door 0.84 × 1.787 × 0.11 m, pocket grid margin 0.075 / gap 0.045, 4 clamps per door edge, handle, hinge barrels, 6 chandelier plates 0.72→0.31 m at 0.176 m pitch, casters, plinth). Decoded by reading the bundle; values copied into `union_model.py` |
| IBM Newsroom press release | https://newsroom.ibm.com/2026-08-19-ibm-connects-its-first-modular-cryogenic-systems-in-milestone-toward-fault-tolerant-quantum-computing | "> 8 ft tall and 8 ft wide" for the two coupled cells; two downloadable photos |
| Public information sheet *IBM's Modular Quantum Cryogenic Architecture* v2.1 (`MoQCA_v2.1.pdf`), Zenodo DOI 10.5281/zenodo.21997093, **CC-BY-4.0**, © 2026 IBM | https://zenodo.org/records/21997093 | Rectangular form factor, flat coupling faces, 2.75 m³ / 0.25 m³ (< 20 mK) per module, 3000 kg, 0.53 m² wiring; Figure 1 photo |
| Jay Gambetta, LinkedIn post + article; IBM / IBM Quantum LinkedIn, IBM News on X, IBM Instagram; YouTube "Unveiling IBM's cryogenic modules…" (`wwMI6IhvwE0`) | (social) | Same photos and copy as above; the **YouTube animation** was additionally mined frame by frame in a second pass (2026-08-24), see "What the video adds" below |
| Press coverage (Next Platform, EE Times, SiliconANGLE, Live Science, Quantum Insider, NAND Research, Futurum) | (see article titles) | EMI gasket + O-ring door seals, Mylar superinsulation, Bluefors cooling engines, cells couple through wall openings into a shielded tunnel |

Internal IBM marketing deck "ModularCryoGeoEnablement_Union" (5 photos,
brand copper `#FFD8C8`, IBM Plex) was used as a visual reference only and is
not part of this repository.

## What the explorer bundle tells us (beyond the table above)

- **Pockets are on the inside.** The door code builds the pocketed plate at
  the cell-facing side and a flat plate outside; clamps and handle sit on the
  flat outside. With the doors closed the explorer shows flat panels — as do
  the photos. Our model follows this.
- **Door kinematics:** hinge on one vertical edge, opens to 1.92 rad (110°);
  the four doors of a cell hinge "pinwheel"-wise (front: left edge, right:
  front edge, back: right edge, left: back edge). The two coupled cells in
  the photos hinge their front doors on the *outer* posts, so the right cell
  is the mirror image of the left one (`--hinge right`).
- **Coupling:** when a fridge is added, the facing side doors are removed and
  the chandelier plates extend across both cells (a shared cold space); the
  L-coupler hotspot sits between the cells at processor height. We model the
  shared space as a flanged window in the side panel (`--coupled`).
- **Chandelier details:** 6 plates (0.72 … 0.31 m, corner r 0.09, t 0.015,
  pitch 0.176, top one 0.085 below the ceiling); the upper four are brass
  (`#c8a24a`), the lower two gold (`#e9c86c`); a 0.30 m top flange on the
  ceiling; on plate 1 a pulse tube (r 0.075–0.09), seven copper feedthroughs
  (r 0.016 on a 0.115 m circle) and two copper side blocks (0.05 × 0.042 × 0.14);
  a central column (r 0.013), four slanted corner rods (r 0.011), four mid
  rods (r 0.009), 12 dark braided cables and flex ribbons (0.05 wide) down the
  stages; mixing chamber (gold, r 0.05, h 0.10) under plate 5; an aluminium
  stage frame (0.72 × 0.12 × 0.42) and two silver sample cans (0.19 × 0.21
  × 0.19) with an "IBM" label 0.265 m below the bottom plate. We keep plates,
  column, rods, flange, pulse tube, feedthroughs, side blocks, MC and one can;
  cables/ribbons/frame are omitted (too fine).
- **Materials palette:** panels `#c4c8cd` / `#d2d6da`, frame/posts `#9aa0a6`,
  chrome handle `#dfe2e6`, aluminium `#bcc0c4`, casters/black `#131416`,
  copper `#b5723c`, ribbon `#c79248`, braided cable `#33302b`, floor
  `#141517`. Used for the MMU colour slots.
- **Frame:** posts r 0.13 full height, plinth 1.15 × 1.85 × 0.17 (r 0.15) on
  casters (wheel r 0.05, block 0.07 × 0.06 × 0.05 at ±0.45/±0.80), top plate
  1.1 × 1.8 × 0.09 (r 0.13); up to 12 fridges in a row at pitch 1.1 m.
- **Hotspot copy** (the explorer's captions): "Airtight doors with
  weight-saving square pockets", "Toggle clamps … without the need for
  tools", "Pull handle", "Casters … rolled across fixed casters",
  "Temperature stages", "Signal wiring … flexible ribbon cables", "Mixing
  chamber", "Quantum processor … about a hundredth of a degree above
  absolute zero", "L-coupler".
- Not in the explorer but in every photo: the aluminium-extrusion gantry
  around/above the cells with pumps and hoses → our optional `gantry` part.

## What the video adds (frame-by-frame pass, 2026-08-24)

From the 40 s announcement animation (YouTube `wwMI6IhvwE0`; the "IE
Explains" reel re-uses the same IBM Research footage):

- **0:12** — door openings have large-radius rounded corners with a dark
  gasket/O-ring seam; toggle clamps are over-centre latches with black
  levers on silver base plates, with matching catch plates on the body;
  hex-head standoff pins near the top-plate corners. → gasket groove
  engraved on every door face (both scales), two-colour latches + jamb
  catch plates (showpiece), hex pins in the `ports` part.
- **0:27** — the top plate carries two clusters of ~7 round connector
  feedthroughs and a bolt-hole grid. → cluster discs in the `ports` part
  (both scales), bolt-hole grid (showpiece).
- **0:33 (tunnel shot)** — the cavity floor is a waffle grid of square
  recesses, the ceiling has round vent recesses. → engraved at both scales.
- **0:05–0:08 + close-up stills** — chandelier carried by black wavy
  topology-optimised blades (not straight rods); below the bottom plate a
  machined stage with a pillar bank and blocks with circular openings; two
  "IBM" cans with rounded vertical edges, hanging brackets and wire bail
  loops under the bottom corners; a helical coax line between two plates.
  → all modelled at the showpiece (desk keeps straight rods and a single
  plain can). U-shaped braided thermal straps and corrugated heat-exchanger
  banks remain omitted (too fine even at 1:15).
- **0:17 / poster frame** — the future payload: a grid of modules (gold
  shelf + silver electronics box + finned flex-cable stack). → optional
  `--interior payload` part (suffix `_pl`).
- **0:37** — parallel cooling lines run along the overhead gantry frames.
  → four pipes nested at beam level in the `gantry` part.

## Deviations from the explorer (deliberate)

- **Post radius 0.07 m instead of 0.13 m**, plus a flat door jamb on the front
  posts: the explorer's fat round posts intersect its own doors; a printable
  flat door between slimmer posts matches the photos better (door ≈ 0.83 m).
- **Pocket side margin 0.10 m** (explorer 0.075 everywhere) so pockets never
  break into the posts behind the face.
- **One chandelier per cell** (photos) instead of plates spanning all coupled
  cells (explorer). Chandelier rods/plates/column are thickened to printable
  minimums; one centred processor can instead of two.
- **Cells are self-contained prints** coupled by magnets in the plinth sides;
  the real cells share a cold tunnel through wall openings.
- All four doors are removable (held by magnets) instead of hinged; hinge
  barrels, clamps and handle are modelled at both scales with their sections
  clamped to printable minimums. `--doors front` keeps three faces fixed.
- One chandelier per cell (photos); optional `--chandelier photo` style with
  round plates and copper block tiers as seen in the right-hand cell photo.
