#!/usr/bin/env node
/**
 * Builds public/3d-model/rasqberry-two.glb, the model for the 3D viewer on the
 * 3D model page, from the STL files on the 3D-model branch.
 *
 *   node scripts/build-3d-model.mjs <path to the "3D Model/print/originals" folder> [out.glb]
 *   e.g. node scripts/build-3d-model.mjs ../RasQberry-Two-3D-model/"3D Model/print/originals"
 *
 * Each printed part becomes a named node (extras: label, group, step, explode),
 * placed where it sits in the assembled model; repeated parts (RTE servers,
 * lids, chandeliers, bolts) share one mesh. Meshes are simplified and
 * meshopt-compressed; the commit of the STL folder goes into the scene extras.
 *
 * Coordinates below are in the STLs' frame (mm, Z up, the Wall at +Y); the
 * output is glTF (metres, Y up, the front of the model towards +Z).
 */
import { readFileSync, mkdirSync, statSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join, dirname, resolve } from 'node:path';
import { Document, NodeIO } from '@gltf-transform/core';
import { EXTMeshoptCompression, KHRMeshQuantization } from '@gltf-transform/extensions';
import { weld, simplify, meshopt, prune, dedup } from '@gltf-transform/functions';
import { MeshoptEncoder, MeshoptSimplifier } from 'meshoptimizer';

const SRC = process.argv[2];
const OUT = resolve(process.argv[3] || 'public/3d-model/rasqberry-two.glb');
if (!SRC) {
  console.error('usage: node scripts/build-3d-model.mjs <"3D Model/print/originals" folder> [out.glb]');
  process.exit(1);
}

// ---------------------------------------------------------------- STL + maths

function readStl(file) {
  const buf = readFileSync(join(SRC, file));
  const n = buf.readUInt32LE(80);
  const tris = [];
  if (84 + n * 50 === buf.length) {
    for (let i = 0; i < n; i++) {
      const o = 84 + i * 50 + 12;
      for (let k = 0; k < 9; k++) tris.push(buf.readFloatLE(o + k * 4));
    }
  } else {
    const re = /vertex\s+(\S+)\s+(\S+)\s+(\S+)/g;
    let m;
    while ((m = re.exec(buf.toString('latin1')))) tris.push(+m[1], +m[2], +m[3]);
  }
  return Float32Array.from(tris);
}

const mul = (A, B) => A.map((_, i) => {
  const r = Math.floor(i / 4), c = i % 4;
  return A[r * 4] * B[c] + A[r * 4 + 1] * B[4 + c] + A[r * 4 + 2] * B[8 + c] + A[r * 4 + 3] * B[12 + c];
});
const chain = (...ms) => ms.reduce((a, b) => mul(a, b));
const T = (x, y, z = 0) => [1, 0, 0, x, 0, 1, 0, y, 0, 0, 1, z, 0, 0, 0, 1];
const rot = (axis, deg) => {
  const a = (deg * Math.PI) / 180, c = Math.round(Math.cos(a) * 1e12) / 1e12, s = Math.round(Math.sin(a) * 1e12) / 1e12;
  if (axis === 'x') return [1, 0, 0, 0, 0, c, -s, 0, 0, s, c, 0, 0, 0, 0, 1];
  if (axis === 'y') return [c, 0, s, 0, 0, 1, 0, 0, -s, 0, c, 0, 0, 0, 0, 1];
  return [c, -s, 0, 0, s, c, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
};
const about = ([x, y], deg) => chain(T(x, y), rot('z', deg), T(-x, -y));
const apply = (M, [x, y, z]) => [0, 1, 2].map((r) => M[r * 4] * x + M[r * 4 + 1] * y + M[r * 4 + 2] * z + M[r * 4 + 3]);

// STL (mm, Z up) -> glTF (m, Y up): (x, y, z) -> (x, z, -y) / 1000
const S = 0.001;
const Q = [1, 0, 0, 0, 0, 1, 0, -1, 0]; // 3x3, row-major
const toGl = ([x, y, z]) => [x * S, z * S, -y * S];

function quatFromRows(m) { // 3x3 row-major rotation -> [x, y, z, w]
  const [a, b, c, d, e, f, g, h, i] = m;
  const tr = a + e + i;
  let q;
  if (tr > 0) { const s = Math.sqrt(tr + 1) * 2; q = [(h - f) / s, (c - g) / s, (d - b) / s, s / 4]; }
  else if (a > e && a > i) { const s = Math.sqrt(1 + a - e - i) * 2; q = [s / 4, (b + d) / s, (c + g) / s, (h - f) / s]; }
  else if (e > i) { const s = Math.sqrt(1 + e - a - i) * 2; q = [(b + d) / s, s / 4, (f + h) / s, (c - g) / s]; }
  else { const s = Math.sqrt(1 + i - a - e) * 2; q = [(c + g) / s, (f + h) / s, s / 4, (d - b) / s]; }
  const n = Math.hypot(...q);
  return q.map((v) => Math.round((v / n) * 1e9) / 1e9);
}
const m3 = (A, B) => A.map((_, k) => {
  const r = Math.floor(k / 3), c = k % 3;
  return A[r * 3] * B[c] + A[r * 3 + 1] * B[3 + c] + A[r * 3 + 2] * B[6 + c];
});
const tr3 = (A) => [A[0], A[3], A[6], A[1], A[4], A[7], A[2], A[5], A[8]];

// ---------------------------------------------------------------- the layout

// Positions measured from the STLs: the floor's hex holes for the Wall bolts
// and the Cryostat's octopus, the matching holes in the Wall base and the
// Cryostat, and the Cryostat's arms (38.1 mm wide, two 23.3 mm servers each).
const WALL = T(-9.89, 383.26);            // Wall base bolt holes -> floor hex holes (37.3/222.6, 322.3)
const WALL_BOLTS = [[47.2, -61.0], [232.5, -61.0]];
const CRYO_C = [-72.0, -206.1];           // Cryostat centre (its octopus hex hole)
const CRYO = T(130.0 - CRYO_C[0], 145.4 - CRYO_C[1]); // -> floor hex hole (130, 145.4)
const ARMS = [0, 120, 240];               // the arm along +Y (to the Wall), then the two front arms
// hex cap: centred on the Cryostat body (10.96 mm in front of its octopus hole), rim 3 mm in the 93.3 mm top
const CAP = T(-73.3, -122.8 - 10.96, -1);
const SOCKETS = [[9.0, -96.9], [9.0, -70.0], [-14.0, -83.2]]; // chandelier sockets under the cap
const SERVER_Y = [-183.8, -160.5];        // the two servers of the +Y arm (y min), stand-alone one at -137.2

const COLOURS = { // as printed (bill of materials): name -> [hex, metallic, roughness, alpha]
  floor: ['#dcdcd8', 0, 0.9, 1],          // White / Rock White
  wall: ['#232326', 0.05, 0.75, 1],       // (matte) Black
  silver: ['#d0d4da', 0.85, 0.26, 1],    // Silk Silver: Cryostat, RTE servers (bright, glossy)
  clear: ['#f3f5f6', 0, 0.25, 0.62],       // Transparent: lids
  gold: ['#e3a33a', 0.75, 0.32, 1],       // Silk Gold: chandeliers
  screen: ['#2b2c2f', 0.2, 0.35, 1],     // Galaxy Black LED filter screen: opaque, dark (lit LEDs shine through)
  hardware: ['#4a4a4f', 0.1, 0.6, 1],     // bolts, nuts, octopus (colour not specified)
  vertex: ['#ffffff', 0.3, 0.45, 1],      // parts made of boxes: colour per vertex (BOX_COLOURS)
};
const BOX_COLOURS = {                     // vertex colours of the parts made of boxes
  pcb: '#16181b',                         // LED panel boards (black)
  led: '#f2f2ee',                         // WS2812 LEDs (5 x 5 mm, off)
  pi: '#1d6b3f',                          // Raspberry Pi 5 board
  metal: '#c7cbd0',                       // USB / Ethernet sockets
  cooler: '#3a3c40',                      // GPIO header, Active Cooler
};

const parts = [];
const add = (id, label, group, step, file, colour, M, explode, extra = {}) =>
  parts.push({ id, label, group, step, file, colour, M, explode, ...extra });

// Floor: six tiles, already laid out in their STLs
const FLOOR_C = [130, 195];
for (let i = 1; i <= 6; i++) {
  const f = `floor/R2_Floor-Tile${i}${i === 6 ? 's' : ''}.stl`;
  add(`floor-${i}`, `Floor tile ${i}`, 'Floor', 1, f, 'floor', T(0, 0), null);
}

// Wall
add('wall-base', 'Wall base', 'Wall', 2, 'wall/R2_Wall-Base.stl', 'wall', WALL, [0, 60, 30]);
WALL_BOLTS.forEach(([x, y], i) =>
  add(`wall-bolt-${i + 1}`, 'Wall bolt', 'Wall', 3, 'wall/R2_Screw.stl', 'hardware',
    chain(WALL, T(x, y, 5), rot('x', 180), T(0.2, -34.7, 0)), [0, 60, 130]));
// LED array: four WS2812 panels of 4 x 12 LEDs (192), behind the filter screen as one 24 x 8 grid,
// 10 mm pitch (the 240 x 81 mm screen opening); LEDs face the screen.
const LED = { x0: 139.9 - 115, z0: 41.5 - 35, pitch: 10, front: -84.1 };   // centre of LED (0, 0), wall frame
const ledAt = (c, r) => [LED.x0 + c * LED.pitch, LED.front, LED.z0 + r * LED.pitch];   // r = 0 at the bottom
[[0, 4], [12, 4], [0, 0], [12, 0]].forEach(([c0, r0], i) => {
  const [x0, , z0] = ledAt(c0, r0);
  const boxes = [[[x0 - 5, LED.front + 1.6, z0 - 5], [x0 + 115, LED.front + 2.6, z0 + 35], 'pcb']];
  for (let c = 0; c < 12; c++) for (let r = 0; r < 4; r++) {
    const [x, y, z] = ledAt(c0 + c, r0 + r);
    boxes.push([[x - 2.5, y, z - 2.5], [x + 2.5, y + 1.6, z + 2.5], 'led']);
  }
  add(`led-panel-${i + 1}`, 'LED panel (WS2812, 4 x 12)', 'Wall', 4, null, 'vertex', WALL, [0, 30, 45], { boxes });
});

// "LEDs on": a still of the IBM LED demo (RQB2-bin/rq_led_ibm_logo.py, rainbow), top row first
const IBM_LOGO = [
  '######..#####...#.....#.',
  '######..##..##..##...##.',
  '..##....##..##..###.###.',
  '..##....#####...##.#.##.',
  '..##....#####...##...##.',
  '..##....##..##..##...##.',
  '######..##..##..##...##.',
  '######..#####...##...##.',
];
const RAINBOW = ['#fb80bf', '#fa0100', '#f9831f', '#f8df08', '#02a204', '#00c4ad', '#0041b7', '#83209e'];
const SCREEN = [[19.9, -85.2, 1], [259.9, -84.2, 82]];

add('wall-window', 'LED filter screen (galaxy black; replaces the welding glass)', 'Wall', 4, null, 'screen', WALL, [0, 10, 30],
  { box: SCREEN, leds: { demo: 'IBM LED demo (rainbow)', pitch: LED.pitch, front: SCREEN[0][1] - 0.5,
    pixels: IBM_LOGO.flatMap((row, k) => [...row].flatMap((ch, c) => ch === '#' ? [[...ledAt(c, 7 - k), RAINBOW[k]]] : [])) } });
// The back with the Raspberry Pi mount 13 mm higher (the standard in the parts list). It stands on
// the base's 3 mm floor, its top flush with the base top; its STL lies 12.13 / 380.12 / 18.08 mm
// off the plain back's, whose STL sits at z 8.04.
const BACK = chain(WALL, T(5.3, -100, 3 - 8.04), T(-12.13, -380.12, -18.08));
add('wall-back', 'Wall back', 'Wall', 5, 'wall/R2_Wall-Back+13.stl', 'wall', BACK, [0, 130, 30]);

// Raspberry Pi 5 (simplified), screwed to the four bosses on the inside of the back (holes at
// x 150.9 / 208.9, z 46.1 / 95.1 in Back+13's STL, Pi 5 pattern 58 x 49 mm); USB and Ethernet
// towards +x, the Active Cooler under the right grille.
const PI_Y = 442.26;                       // boss tops (inside face of the back)
const piBox = (x0, x1, z0, z1, h, colour, y = PI_Y - 1.6) => [[x0, y - h, z0], [x1, y, z1], colour];
add('raspberry-pi', 'Raspberry Pi 5 (simplified)', 'Wall', 5, null, 'vertex', BACK, [0, 90, 60], {
  boxes: [
    piBox(147.4, 232.4, 42.6, 98.6, 1.6, 'pi', PI_Y),             // board, 85 x 56 x 1.6
    piBox(154.4, 205.4, 92.6, 97.6, 8.5, 'cooler'),               // GPIO header 2 x 20
    piBox(156.4, 196.4, 50.6, 88.6, 9, 'cooler'),                 // Active Cooler heatsink
    piBox(212.4, 234.4, 44.1, 60.1, 13.5, 'metal'),               // Ethernet
    piBox(215.4, 234.4, 62.6, 77.6, 16, 'metal'),                 // USB 3 (2x)
    piBox(215.4, 234.4, 80.1, 95.1, 16, 'metal'),                 // USB 2 (2x)
  ],
});
add('wall-lid', 'Wall lid', 'Wall', 6, 'wall/R2_Wall-Lid.stl', 'wall', WALL, [0, 60, 120]);
WALL_BOLTS.forEach(([x, y], i) =>
  add(`wall-nut-${i + 1}`, 'Hex nut', 'Wall', 7, 'wall/R2_Hex_Nut.stl', 'hardware',
    chain(WALL, T(x + 0.25, y + 0.45, -6)), [0, 60, -70]));

// Cryostat
add('cryostat', 'Cryostat with six RTE servers', 'Cryostat', 8, 'cryostat/R2_NarrowYCryoConjoined.stl', 'silver', CRYO, [0, -40, 30]);
add('octopus', 'Octopus (alignment bolt)', 'Cryostat', 9, 'cryostat/R2_ScrewOctopusAlignment2.stl', 'hardware',
  chain(CRYO, T(...CRYO_C, 6), rot('y', 180), T(39.96, 6.31, 0)), [0, -40, -40]);
add('octopus-nut', 'Hex nut', 'Cryostat', 10, 'wall/R2_Hex_Nut.stl', 'hardware',
  chain(CRYO, T(CRYO_C[0] + 0.25, CRYO_C[1] + 0.45, -6)), [0, -40, -90]);
add('door', 'Door', 'Cryostat', 11, 'cryostat/R2_NewDoor.stl', 'silver', chain(CRYO, T(-204.05, -134.9, -7)), [0, -110, 30]);
ARMS.forEach((a, k) => SERVER_Y.forEach((y, j) =>
  add(`rte-lid-${k * 2 + j + 1}`, 'RTE server lid', 'Cryostat', 12, 'RTE/R2_NarrowServerSingleLid.stl', 'clear',
    chain(CRYO, about(CRYO_C, a), T(-91.1, y - 72.6, 0)), [0, -40, 70])));
SOCKETS.forEach(([x, y], i) =>
  add(`chandelier-${i + 1}`, 'Chandelier', 'Cryostat', 13, 'cryostat/R2_ChandelierSingle.stl', 'gold',
    chain(CRYO, CAP, T(x, y, 92.3), rot('x', 180), T(-64.24, 2.58, 14.7)), [0, -40, 110]));
add('cap', 'Cryostat cap', 'Cryostat', 14, 'cryostat/R2_CryoLid-Simple.stl', 'clear', chain(CRYO, CAP), [0, -40, 200]);
ARMS.forEach((a, k) => {
  const out = apply(rot('z', a), [0, 1, 0]).map((v) => v * 55);
  add(`rte-${k + 1}`, 'RTE server (stand-alone)', 'RTE servers', 15, 'RTE/R2_NarrowServerSingle.stl', 'silver',
    chain(CRYO, about(CRYO_C, a), T(-91.1, -251.7, 0)), [out[0], out[1] - 40, 30]);
  add(`rte-${k + 1}-lid`, 'RTE server lid', 'RTE servers', 16, 'RTE/R2_NarrowServerSingleLid.stl', 'clear',
    chain(CRYO, about(CRYO_C, a), T(-91.1, -137.2 - 72.6, 0)), [out[0], out[1] - 40, 100]);
});

// Floor tiles move apart and down
for (const p of parts.filter((p) => p.group === 'Floor')) {
  const pos = readStl(p.file);
  let cx = 0, cy = 0;
  for (let i = 0; i < pos.length; i += 3) { cx += pos[i]; cy += pos[i + 1]; }
  cx /= pos.length / 3; cy /= pos.length / 3;
  p.explode = [(cx - FLOOR_C[0]) * 0.45, (cy - FLOOR_C[1]) * 0.45, -60];
}

// ---------------------------------------------------------------- the glTF

function sourceCommit() {
  try {
    const dir = statSync(SRC).isDirectory() ? SRC : dirname(SRC);
    const commit = execFileSync('git', ['-C', dir, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
    const dirty = execFileSync('git', ['-C', dir, 'status', '--porcelain', '--', '.'], { encoding: 'utf8' }).trim() !== '';
    return dirty ? `${commit}+local-changes` : commit;
  } catch { return 'unknown'; }
}

const doc = new Document();
const buffer = doc.createBuffer();
const scene = doc.createScene('RasQberry Two');
const materials = {};
const linear = (hex) => { // '#rrggbb' as linear RGB
  const n = parseInt(hex.slice(1), 16);
  const lin = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  return [lin(n >> 16), lin((n >> 8) & 255), lin(n & 255)];
};
for (const [name, [hex, metal, rough, alpha]] of Object.entries(COLOURS)) {
  const m = doc.createMaterial(name)
    .setBaseColorFactor([...linear(hex), alpha])
    .setMetallicFactor(metal).setRoughnessFactor(rough).setDoubleSided(alpha < 1);
  if (alpha < 1) m.setAlphaMode('BLEND');
  materials[name] = m;
}

const boxTris = ([[a, b, c], [d, e, f]]) => { // a box [[x0,y0,z0],[x1,y1,z1]] as triangles
  const v = [[a, b, c], [d, b, c], [d, e, c], [a, e, c], [a, b, f], [d, b, f], [d, e, f], [a, e, f]];
  const faces = [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]];
  return faces.flat().flatMap((i) => v[i]);
};

const meshes = new Map(); // file -> { mesh, centre }
function meshFor(p) {
  const key = p.file || p.id;
  if (meshes.has(key)) return meshes.get(key);
  // positions per colour: an STL, one box, or boxes in several colours
  const byColour = new Map();
  if (p.file) byColour.set(p.colour, readStl(p.file));
  else if (p.box) byColour.set(p.colour, Float32Array.from(boxTris(p.box)));
  else { // boxes in several colours: one primitive with vertex colours, so the part stays one mesh
    const pos = [], col = [];
    for (const [lo, hi, colour] of p.boxes) {
      const t = boxTris([lo, hi]);
      pos.push(...t);
      const [r, g, b] = linear(BOX_COLOURS[colour]);
      for (let i = 0; i < t.length / 3; i++) col.push(r, g, b);
    }
    byColour.set('vertex', Float32Array.from(pos));
    p.vertexColours = Float32Array.from(col);
  }
  const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
  for (const pos of byColour.values())
    for (let i = 0; i < pos.length; i++) { lo[i % 3] = Math.min(lo[i % 3], pos[i]); hi[i % 3] = Math.max(hi[i % 3], pos[i]); }
  const centre = lo.map((v, i) => (v + hi[i]) / 2);
  const mesh = doc.createMesh(p.file ? p.file.split('/').pop().replace('.stl', '') : p.id);
  let triangles = 0;
  for (const [colour, pos] of byColour) {
    const out = new Float32Array(pos.length);
    for (let i = 0; i < pos.length; i += 3) out.set(toGl([pos[i] - centre[0], pos[i + 1] - centre[1], pos[i + 2] - centre[2]]), i);
    const accessor = doc.createAccessor().setType('VEC3').setArray(out).setBuffer(buffer);
    const prim = doc.createPrimitive().setAttribute('POSITION', accessor).setMaterial(materials[colour]);
    if (colour === 'vertex') prim.setAttribute('COLOR_0', doc.createAccessor().setType('VEC3').setArray(p.vertexColours).setBuffer(buffer));
    mesh.addPrimitive(prim);
    triangles += pos.length / 9;
  }
  const entry = { mesh, centre, triangles };
  meshes.set(key, entry);
  return entry;
}

for (const p of parts) {
  const { mesh, centre } = meshFor(p);
  const R = [p.M[0], p.M[1], p.M[2], p.M[4], p.M[5], p.M[6], p.M[8], p.M[9], p.M[10]];
  const world = apply(p.M, centre); // R c + t
  const node = doc.createNode(p.id).setMesh(mesh)
    .setRotation(quatFromRows(m3(m3(Q, R), tr3(Q))))
    .setTranslation(toGl(world))
    .setExtras({
      part: p.id, label: p.label, group: p.group, step: p.step, colour: p.colour,
      source: p.file, explode: p.explode ? toGl(p.explode) : [0, 0, 0],
      // LED pixels for "LEDs on", in the model's frame (glTF, m): [x, y, z, colour]
      ...(p.leds && { leds: { demo: p.leds.demo, size: p.leds.pitch * S,
        normal: toGl([0, 1, 2].map((r) => -p.M[r * 4 + 1])).map((v) => v / S),   // the screen's front (-y), turned with it
        pixels: p.leds.pixels.map(([x, , z, colour]) => [...toGl(apply(p.M, [x, p.leds.front, z])), colour]) } }),
    });
  scene.addChild(node);
}

scene.setExtras({
  model: 'RasQberry Two', units: 'm', up: '+Y', front: '+Z',
  source: { repo: 'JanLahmann/RasQberry-Two', branch: '3D-model', path: '3D Model/print/originals', commit: sourceCommit() },
  generator: 'scripts/build-3d-model.mjs',
  note: 'Layout and colours follow the bill of materials and the hardware assembly guide; the LED filter screen is drawn as a plain box.',
});

const before = [...meshes.values()].reduce((s, m) => s + m.triangles, 0);
await MeshoptEncoder.ready;
await MeshoptSimplifier.ready;
doc.createExtension(EXTMeshoptCompression).setRequired(true).setEncoderOptions({ method: EXTMeshoptCompression.EncoderMethod.QUANTIZE });
doc.createExtension(KHRMeshQuantization).setRequired(true);
await doc.transform(
  weld(),
  simplify({ simplifier: MeshoptSimplifier, ratio: 0, error: Number(process.env.SIMPLIFY_ERROR || 0.0008) }),
  dedup(), prune(),
  meshopt({ encoder: MeshoptEncoder, level: 'medium', quantizePosition: 14 }),
);
let after = 0;
for (const m of doc.getRoot().listMeshes()) for (const pr of m.listPrimitives()) after += pr.getIndices() ? pr.getIndices().getCount() / 3 : pr.getAttribute('POSITION').getCount() / 3;

mkdirSync(dirname(OUT), { recursive: true });
const io = new NodeIO().registerExtensions([EXTMeshoptCompression, KHRMeshQuantization]).registerDependencies({ 'meshopt.encoder': MeshoptEncoder });
await io.write(OUT, doc);
console.log(`${parts.length} parts, ${meshes.size} meshes, ${before} -> ${after} triangles, ${(statSync(OUT).size / 1e6).toFixed(2)} MB -> ${OUT}`);
