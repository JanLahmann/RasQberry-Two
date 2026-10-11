/**
 * The three.js side of the 3D model viewer: loads the GLB made by
 * scripts/build-3d-model.mjs, renders on demand, and offers explode,
 * selection/isolation and the assembly animation. Loaded lazily by index.tsx,
 * so pages without the viewer never download three.js.
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

export interface PartInfo {
  key: string;      // the label: parts with the same label are selected together
  label: string;
  group: string;
  count: number;
  step: number;
  source?: string;  // STL file on the 3D-model branch
}

interface Part {
  obj: THREE.Mesh;
  key: string;
  base: THREE.Vector3;
  explode: THREE.Vector3;
  step: number;
  material: THREE.MeshStandardMaterial;
  highlight: THREE.MeshStandardMaterial;
  ghost: THREE.MeshStandardMaterial;
}

export interface ViewerEvents {
  onSelect?: (key: string | null) => void;
  onStep?: (step: PartInfo | null) => void; // assembly progress; null when done
}

const HIGHLIGHT = new THREE.Color('#4589ff');

export class ModelViewer {
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(32, 1, 0.005, 10);
  private controls: OrbitControls;
  private parts: Part[] = [];
  private home = { pos: new THREE.Vector3(), target: new THREE.Vector3() };
  private bounds = new THREE.Sphere(new THREE.Vector3(), 0.3);
  private explodeT = 0;
  private selected: string | null = null;
  private isolate = false;
  private frame = 0;
  private tweens: ((now: number) => boolean)[] = [];
  private assemblyRun = 0;
  private assembling = false;
  private ro: ResizeObserver;
  private down = { x: 0, y: 0 };
  readonly reducedMotion: boolean;
  meta: Record<string, unknown> = {};

  constructor(private host: HTMLElement, private events: ViewerEvents = {}) {
    this.reducedMotion = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.NeutralToneMapping;
    this.renderer.domElement.style.touchAction = 'none';
    host.appendChild(this.renderer.domElement);

    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
    this.scene.environmentIntensity = 0.75;
    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.position.set(0.4, 1, 0.6);
    this.scene.add(sun, new THREE.HemisphereLight(0xffffff, 0x8a8f98, 0.4));

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = !this.reducedMotion;
    this.controls.maxPolarAngle = Math.PI * 0.62;
    this.controls.addEventListener('change', () => this.invalidate());

    const el = this.renderer.domElement;
    el.addEventListener('pointerdown', (e) => { this.down = { x: e.clientX, y: e.clientY }; });
    el.addEventListener('pointerup', (e) => {
      if (Math.hypot(e.clientX - this.down.x, e.clientY - this.down.y) < 6) this.pick(e);
    });

    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(host);
    this.resize();
  }

  async load(url: string): Promise<PartInfo[]> {
    const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
    const gltf = await loader.loadAsync(url);
    this.meta = (gltf.scene.userData || {}) as Record<string, unknown>;
    const infos = new Map<string, PartInfo>();
    gltf.scene.traverse((o) => {
      const d = o.userData as { part?: string; label?: string; group?: string; step?: number; explode?: number[]; source?: string };
      if (!(o as THREE.Mesh).isMesh || !d.part) return;
      const obj = o as THREE.Mesh;
      const src = obj.material as THREE.MeshStandardMaterial;
      const material = src.clone();
      material.flatShading = true; // the GLB has no normals: facets, as printed
      const highlight = material.clone();
      highlight.emissive = material.color.clone().lerp(HIGHLIGHT, 0.25);
      highlight.emissiveIntensity = 0.3;
      const ghost = material.clone();
      ghost.transparent = true;
      ghost.opacity = 0.12;
      ghost.depthWrite = false;
      obj.material = material;
      const key = d.label || d.part;
      this.parts.push({
        obj, key, material, highlight, ghost,
        base: obj.position.clone(),
        explode: new THREE.Vector3().fromArray(d.explode || [0, 0, 0]),
        step: d.step || 0,
      });
      const info = infos.get(key);
      if (info) info.count++;
      else infos.set(key, { key, label: key, group: d.group || '', count: 1, step: d.step || 0, source: d.source?.split('/').pop() });
    });
    this.scene.add(gltf.scene);

    // Home view: from the front right, a little above, the whole model in frame
    const box = new THREE.Box3().setFromObject(gltf.scene);
    this.bounds = box.getBoundingSphere(new THREE.Sphere());
    this.home.target.copy(this.bounds.center).setY(box.min.y + (box.max.y - box.min.y) * 0.3);
    this.controls.minDistance = this.bounds.radius * 0.25;
    this.controls.maxDistance = this.bounds.radius * 12;
    this.resetView(false);
    return [...infos.values()].sort((a, b) => a.step - b.step || a.label.localeCompare(b.label, 'en', { numeric: true }));
  }

  /** 0 = assembled, 1 = fully exploded */
  setExplode(t: number) {
    this.stopAssembly();
    this.explodeT = t;
    for (const p of this.parts) p.obj.position.copy(p.base).addScaledVector(p.explode, t);
    this.applyLook();
  }

  select(key: string | null, frame = true) {
    this.stopAssembly();
    this.selected = key;
    this.applyLook();
    this.events.onSelect?.(key);
    if (frame && key && this.isolate) this.frameParts(this.parts.filter((p) => p.key === key));
  }

  setIsolate(on: boolean) {
    this.isolate = on;
    this.applyLook();
    if (on && this.selected) this.frameParts(this.parts.filter((p) => p.key === this.selected));
    if (!on) this.frameParts(this.parts);
  }

  resetView(animate = true) {
    const dir = new THREE.Vector3(0.55, 0.62, 1).normalize();
    this.home.pos.copy(this.home.target).addScaledVector(dir, this.fitDistance(this.bounds.radius) * 0.8);
    this.flyTo(this.home.pos, this.home.target, animate);
  }

  /** Parts fly in, step by step, in assembly order. */
  async playAssembly() {
    this.selected = null;
    this.isolate = false;
    this.applyLook();
    const token = ++this.assemblyRun;
    this.assembling = true;
    this.explodeT = 0;
    const steps = [...new Set(this.parts.map((p) => p.step))].sort((a, b) => a - b);
    for (const p of this.parts) p.obj.visible = false;
    this.invalidate();
    const dur = this.reducedMotion ? 0 : 650;
    for (const s of steps) {
      if (token !== this.assemblyRun) return;
      const group = this.parts.filter((p) => p.step === s);
      this.events.onStep?.({ key: group[0].key, label: group[0].key, group: '', count: group.length, step: s });
      await Promise.all(group.map((p, i) => this.flyIn(p, dur, i * (this.reducedMotion ? 0 : 90))));
      await new Promise((r) => setTimeout(r, this.reducedMotion ? 700 : 120));
    }
    if (token === this.assemblyRun) {
      this.assembling = false;
      this.events.onStep?.(null);
    }
  }

  stopAssembly() {
    if (!this.assembling) return;
    this.assembling = false;
    this.assemblyRun++;
    for (const p of this.parts) p.obj.position.copy(p.base).addScaledVector(p.explode, this.explodeT);
    this.events.onStep?.(null);
    this.applyLook();
  }

  dispose() {
    this.assemblyRun++;
    cancelAnimationFrame(this.frame);
    this.ro.disconnect();
    this.controls.dispose();
    this.scene.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) m.geometry.dispose();
    });
    for (const p of this.parts) [p.material, p.highlight, p.ghost].forEach((m) => m.dispose());
    this.scene.environment?.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }

  // ------------------------------------------------------------- internals

  private flyIn(p: Part, dur: number, delay: number) {
    const from = p.explode.lengthSq() > 0
      ? p.base.clone().addScaledVector(p.explode, 2.2)
      : p.base.clone().add(new THREE.Vector3(0, 0.18, 0));
    const run = this.assemblyRun;
    return new Promise<void>((resolve) => {
      const start = performance.now() + delay;
      this.tweens.push((now) => {
        if (run !== this.assemblyRun) { resolve(); return false; }
        if (now < start) return true;
        p.obj.visible = true;
        const k = dur ? Math.min(1, (now - start) / dur) : 1;
        p.obj.position.lerpVectors(from, p.base, 1 - Math.pow(1 - k, 3));
        if (k >= 1) resolve();
        return k < 1;
      });
      this.invalidate();
    });
  }

  private applyLook() {
    for (const p of this.parts) {
      const on = this.selected === null || p.key === this.selected;
      p.obj.material = this.selected === null ? p.material : on ? p.highlight : p.ghost;
      p.obj.visible = on || !this.isolate;
    }
    this.invalidate();
  }

  private frameParts(list: Part[]) {
    if (!list.length) return;
    const box = new THREE.Box3();
    for (const p of list) box.expandByObject(p.obj);
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const dir = this.camera.position.clone().sub(this.controls.target).normalize();
    const dist = Math.max(this.fitDistance(sphere.radius) * 1.15, this.controls.minDistance);
    this.flyTo(sphere.center.clone().addScaledVector(dir, dist), sphere.center, true);
  }

  private flyTo(pos: THREE.Vector3, target: THREE.Vector3, animate: boolean) {
    const p0 = this.camera.position.clone(), t0 = this.controls.target.clone();
    const dur = animate && !this.reducedMotion ? 450 : 0;
    const start = performance.now();
    this.tweens.push((now) => {
      const k = dur ? Math.min(1, (now - start) / dur) : 1;
      const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      this.camera.position.lerpVectors(p0, pos, e);
      this.controls.target.lerpVectors(t0, target, e);
      return k < 1;
    });
    this.invalidate();
  }

  /** Camera distance that fits a sphere of radius r, in the narrower of the two directions */
  private fitDistance(r: number) {
    const v = THREE.MathUtils.degToRad(this.camera.fov / 2);
    const h = Math.atan(Math.tan(v) * this.camera.aspect);
    return r / Math.sin(Math.min(v, h));
  }

  private pick(e: PointerEvent) {
    const r = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    const ray = new THREE.Raycaster();
    ray.setFromCamera(ndc, this.camera);
    const hits = ray.intersectObjects(this.parts.filter((p) => p.obj.visible && p.obj.material !== p.ghost).map((p) => p.obj), false);
    const hit = hits.length ? this.parts.find((p) => p.obj === hits[0].object) : undefined;
    this.select(hit ? hit.key : null, false);
  }

  private resize() {
    const w = this.host.clientWidth, h = this.host.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.invalidate();
  }

  private invalidate() {
    if (this.frame) return;
    this.frame = requestAnimationFrame((now) => {
      this.frame = 0;
      this.tweens = this.tweens.filter((t) => t(now));
      const moving = this.controls.update(); // true while damping
      this.renderer.render(this.scene, this.camera);
      if (this.tweens.length || moving) this.invalidate();
    });
  }
}
