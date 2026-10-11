#!/usr/bin/env node
/**
 * Builds public/3d-model/rasqberry-two.glb, the model for the 3D viewer on the
 * 3D model page, from the STL files on the 3D-model branch.
 *
 *   node scripts/build-3d-model.mjs <path to the "3D Model" folder> [out.glb]
 *   e.g. node scripts/build-3d-model.mjs ../RasQberry-Two-3D-model/"3D Model"
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
  console.error('usage: node scripts/build-3d-model.mjs <"3D Model" folder> [out.glb]');
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
const CAP = T(-73.3, -122.8, -1);         // hex cap: centre (1.3, -83.3) -> Cryostat centre, rests on the 93.3 mm top
const SOCKETS = [[9.0, -96.9], [9.0, -70.0], [-14.0, -83.2]]; // chandelier sockets under the cap
const SERVER_Y = [-183.8, -160.5];        // the two servers of the +Y arm (y min), stand-alone one at -137.2

const COLOURS = { // as printed (bill of materials): name -> [hex, metallic, roughness, alpha]
  floor: ['#dcdcd8', 0, 0.9, 1],          // White / Rock White
  wall: ['#232326', 0.05, 0.75, 1],       // (matte) Black
  silver: ['#9ea3aa', 0.6, 0.42, 1],     // Silk Silver: Cryostat, RTE servers
  clear: ['#f3f5f6', 0, 0.25, 0.62],       // Transparent: lids
  gold: ['#e3a33a', 0.75, 0.32, 1],       // Silk Gold: chandeliers
  glass: ['#1c262e', 0.1, 0.15, 0.55],    // welding glass (cut, not printed)
  hardware: ['#4a4a4f', 0.1, 0.6, 1],     // bolts, nuts, octopus (colour not specified)
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
add('wall-window', 'Window (welding glass, not printed)', 'Wall', 4, null, 'glass', WALL, [0, 10, 30],
  { box: [[19.9, -85.2, 1], [259.9, -84.2, 82]] });
add('wall-back', 'Wall back', 'Wall', 5, 'wall/R2_Wall-Back.stl', 'wall', chain(WALL, T(5.3, -100, 0)), [0, 130, 30]);
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
for (const [name, [hex, metal, rough, alpha]] of Object.entries(COLOURS)) {
  const n = parseInt(hex.slice(1), 16);
  const lin = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  const m = doc.createMaterial(name)
    .setBaseColorFactor([lin(n >> 16), lin((n >> 8) & 255), lin(n & 255), alpha])
    .setMetallicFactor(metal).setRoughnessFactor(rough).setDoubleSided(alpha < 1);
  if (alpha < 1) m.setAlphaMode('BLEND');
  materials[name] = m;
}

const meshes = new Map(); // file -> { mesh, centre }
function meshFor(p) {
  const key = p.file || p.id;
  if (meshes.has(key)) return meshes.get(key);
  let pos;
  if (p.file) pos = readStl(p.file);
  else { // a box: [[x0,y0,z0],[x1,y1,z1]]
    const [[a, b, c], [d, e, f]] = p.box;
    const v = [[a, b, c], [d, b, c], [d, e, c], [a, e, c], [a, b, f], [d, b, f], [d, e, f], [a, e, f]];
    const faces = [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]];
    pos = Float32Array.from(faces.flat().flatMap((i) => v[i]));
  }
  const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < pos.length; i++) { lo[i % 3] = Math.min(lo[i % 3], pos[i]); hi[i % 3] = Math.max(hi[i % 3], pos[i]); }
  const centre = lo.map((v, i) => (v + hi[i]) / 2);
  const out = new Float32Array(pos.length);
  for (let i = 0; i < pos.length; i += 3) out.set(toGl([pos[i] - centre[0], pos[i + 1] - centre[1], pos[i + 2] - centre[2]]), i);
  const accessor = doc.createAccessor().setType('VEC3').setArray(out).setBuffer(buffer);
  const prim = doc.createPrimitive().setAttribute('POSITION', accessor).setMaterial(materials[p.colour]);
  const mesh = doc.createMesh(p.file ? p.file.split('/').pop().replace('.stl', '') : p.id).addPrimitive(prim);
  const entry = { mesh, centre, triangles: pos.length / 9 };
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
    });
  scene.addChild(node);
}

scene.setExtras({
  model: 'RasQberry Two', units: 'm', up: '+Y', front: '+Z',
  source: { repo: 'JanLahmann/RasQberry-Two', branch: '3D-model', path: '3D Model', commit: sourceCommit() },
  generator: 'scripts/build-3d-model.mjs',
  note: 'Layout and colours follow the bill of materials and the hardware assembly guide; the window is not a printed part.',
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
