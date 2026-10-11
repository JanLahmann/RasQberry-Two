'use client';
/**
 * Interactive 3D view of the RasQberry Two model (content: <ModelViewer /> in
 * a Markdown page). three.js and the model (public/3d-model/, made by
 * scripts/build-3d-model.mjs) load only when the viewer scrolls into view.
 */
import { useEffect, useRef, useState } from 'react';
import type { ModelViewer as Viewer, PartInfo } from './viewer';
import styles from './model-viewer.module.scss';
import { UMAMI, umamiTrack } from '@/lib/umami';

const MODEL_URL = '/3d-model/rasqberry-two.glb';

export function ModelViewer() {
  const box = useRef<HTMLDivElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const viewer = useRef<Viewer | null>(null);
  const [state, setState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [parts, setParts] = useState<PartInfo[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [isolate, setIsolate] = useState(false);
  const [explode, setExplode] = useState(0);
  const [step, setStep] = useState<PartInfo | null>(null);
  const [assembling, setAssembling] = useState(false);
  const opened = useRef(false);
  // one Umami event per page view, on the first interaction with the viewer
  const used = (via: string) => {
    if (opened.current) return;
    opened.current = true;
    umamiTrack(UMAMI.modelViewerOpen, { via });
  };

  useEffect(() => {
    const el = stage.current;
    if (!el) return;
    let disposed = false;
    const start = async () => {
      setState('loading');
      try {
        const { ModelViewer: V } = await import('./viewer');
        if (disposed) return;
        const v = new V(el, {
          onSelect: setSelected,
          onStep: (s) => { setStep(s); if (!s) setAssembling(false); },
        });
        viewer.current = v;
        setParts(await v.load(MODEL_URL));
        if (!disposed) setState('ready');
      } catch (e) {
        console.error('3D viewer:', e);
        if (!disposed) setState('error');
      }
    };
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { io.disconnect(); start(); }
    }, { rootMargin: '300px' });
    io.observe(el);
    return () => { disposed = true; io.disconnect(); viewer.current?.dispose(); viewer.current = null; };
  }, []);

  const pick = (key: string | null) => { used('parts'); viewer.current?.select(key); };
  const toggleIsolate = (on: boolean) => { setIsolate(on); viewer.current?.setIsolate(on); };
  const reset = () => {
    used('reset');
    const v = viewer.current;
    if (!v) return;
    v.stopAssembly(); setIsolate(false); v.setIsolate(false); v.select(null); setExplode(0); v.setExplode(0); v.resetView();
  };
  const assemble = () => {
    used('assemble');
    const v = viewer.current;
    if (!v) return;
    if (assembling) { v.stopAssembly(); setAssembling(false); return; }
    setIsolate(false); setExplode(0); setAssembling(true);
    v.playAssembly();
  };
  const fullscreen = () => {
    used('fullscreen');
    if (document.fullscreenElement) document.exitFullscreen();
    else box.current?.requestFullscreen?.();
  };

  const info = parts.find((p) => p.key === selected);
  const groups = [...new Set(parts.map((p) => p.group))];
  const ready = state === 'ready';

  return (
    <div className={styles.viewer} ref={box}>
      <div className={styles.stage} ref={stage} role="img" onPointerDown={() => ready && used('model')} onWheel={() => ready && used('model')}
           aria-label="Interactive 3D model of the RasQberry Two: drag to rotate, pinch or scroll to zoom">
        {state !== 'ready' && (
          <p className={styles.status}>
            {state === 'error' ? 'The 3D view needs WebGL, which this browser does not offer.' : 'Loading the 3D model…'}
          </p>
        )}
        {info && (
          <div className={styles.info} aria-live="polite">
            <strong>{info.label}{info.count > 1 ? ` (${info.count}×)` : ''}</strong>
            {info.source && <span>{info.source}</span>}
            <label><input type="checkbox" checked={isolate} onChange={(e) => toggleIsolate(e.target.checked)} /> Show only this</label>
            <button type="button" onClick={() => { toggleIsolate(false); pick(null); }}>Show all</button>
          </div>
        )}
        {step && <div className={styles.step} aria-live="polite">{step.label}</div>}
      </div>

      <div className={styles.toolbar}>
        <button type="button" onClick={reset} disabled={!ready}>Reset view</button>
        <label className={styles.slider}>
          Exploded
          <input type="range" min={0} max={1} step={0.01} value={explode} disabled={!ready}
                 onChange={(e) => { used('explode'); const t = +e.target.value; setExplode(t); setAssembling(false); viewer.current?.setExplode(t); }} />
        </label>
        <button type="button" onClick={assemble} disabled={!ready} aria-pressed={assembling}>
          {assembling ? 'Stop' : 'Assemble'}
        </button>
        <button type="button" onClick={fullscreen} disabled={!ready} className={styles.fs}>Full screen</button>
      </div>

      {ready && (
        <details className={styles.parts} open>
          <summary>Parts ({parts.reduce((n, p) => n + p.count, 0)})</summary>
          {groups.map((g) => (
            <div key={g}>
              <h4>{g}</h4>
              <ul>
                {parts.filter((p) => p.group === g).map((p) => (
                  <li key={p.key}>
                    <button type="button" aria-pressed={selected === p.key}
                            onClick={() => pick(selected === p.key ? null : p.key)}>
                      {p.label}{p.count > 1 ? ` ×${p.count}` : ''}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </details>
      )}
    </div>
  );
}
