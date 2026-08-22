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
| Jay Gambetta, LinkedIn post + article; IBM / IBM Quantum LinkedIn, IBM News on X, IBM Instagram; YouTube "Unveiling IBM's cryogenic modules…" (`wwMI6IhvwE0`) | (social) | Same photos and copy as above; no additional geometry |
| Press coverage (Next Platform, EE Times, SiliconANGLE, Live Science, Quantum Insider, NAND Research, Futurum) | (see article titles) | EMI gasket + O-ring door seals, Mylar superinsulation, Bluefors cooling engines, cells couple through wall openings into a shielded tunnel |

Internal IBM marketing deck "ModularCryoGeoEnablement_Union" (5 photos,
brand copper `#FFD8C8`, IBM Plex) was used as a visual reference only and is
not part of this repository.

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
- Door held by magnets, no hinges/clamps at desk scale (too small to print);
  the showpiece preset models clamps, pull handle and hinge barrels.
