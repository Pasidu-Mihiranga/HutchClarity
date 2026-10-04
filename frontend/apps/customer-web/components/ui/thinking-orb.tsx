"use client";

/**
 * ThinkingOrb: the chat's waiting state.
 *
 * Adapted from the "AI thinking orb and input" (MorphOrb) design: a dotted
 * sphere drawn on a canvas that assembles top-down, spins, and lights its dots
 * with one of four light programs, under a status label that cross-fades with
 * a shimmer. Only the waiting part of that design is used here. The original
 * also morphs the input pill into the orb and the orb into an answer card;
 * the chat keeps its own composer and its structured result cards, so those
 * phases are not carried over.
 *
 * Purely decorative: nothing here decides or displays a result. The label is
 * announced through a polite live region; the canvas is hidden from assistive
 * technology. With `prefers-reduced-motion` the orb is drawn once, still.
 */

import { useEffect, useLayoutEffect, useRef, useState } from "react";

/* ───────────────────────── math + easing ───────────────────────── */
type Ease = (t: number) => number;
const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const TAU = Math.PI * 2;

function mulberry32(a: number) {
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function cubicBezier(x1: number, y1: number, x2: number, y2: number): Ease {
  const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
  const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
  const sx = (t: number) => ((ax * t + bx) * t + cx) * t;
  const sy = (t: number) => ((ay * t + by) * t + cy) * t;
  const dx = (t: number) => (3 * ax * t + 2 * bx) * t + cx;
  const solve = (x: number) => {
    let t = x;
    for (let i = 0; i < 8; i++) {
      const e = sx(t) - x;
      if (Math.abs(e) < 1e-6) return t;
      const d = dx(t);
      if (Math.abs(d) < 1e-6) break;
      t -= e / d;
    }
    let lo = 0, hi = 1;
    t = x;
    for (let i = 0; i < 40; i++) {
      const e = sx(t);
      if (Math.abs(e - x) < 1e-6) break;
      if (x > e) lo = t; else hi = t;
      t = (hi - lo) / 2 + lo;
    }
    return t;
  };
  return (x) => (x <= 0 ? 0 : x >= 1 ? 1 : sy(solve(x)));
}

const E = {
  out: cubicBezier(0.22, 1, 0.36, 1),
  io: cubicBezier(0.65, 0, 0.35, 1),
};

/* ───────────────────────── timeline ───────────────────────── */
interface Track { ch: OrbKey; from: number; to: number; t0: number; t1: number; ease: Ease }
const T = (ch: OrbKey, from: number, to: number, t0: number, t1: number, ease: Ease = E.io): Track =>
  ({ ch, from, to, t0, t1, ease });

/* The orb's own entrance, as in the original ASSEMBLE phase. */
const ASSEMBLE: Track[] = [
  T("k", 0, 1, 0, 800, E.out),
  T("alpha", 0, 1, 0, 800, E.out),
  T("spin", 0, 0.9, 0, 800, E.out),
  T("pop", 1, 1.05, 0, 420, E.out),
  T("pop", 1.05, 1, 420, 800, E.io),
];

/* ───────────────────────── dotted sphere ───────────────────────── */
const RINGS = 16;
const DOTS = (() => {
  const rand = mulberry32(7);
  const out: { x: number; y: number; z: number; u: number; seed: number }[] = [];
  for (let k = 0; k < RINGS; k++) {
    const y = 1 - ((k + 0.5) / RINGS) * 2;
    const r = Math.sqrt(1 - y * y);
    const m = Math.max(4, Math.round(30 * r));
    for (let j = 0; j < m; j++) {
      const a = (j / m) * TAU + k * 0.35;
      out.push({ x: Math.cos(a) * r, y, z: Math.sin(a) * r, u: (1 - y) / 2, seed: rand() * TAU });
    }
  }
  return out;
})();
const N = DOTS.length;
const DX = Float32Array.from(DOTS, (d) => d.x);
const DY = Float32Array.from(DOTS, (d) => d.y);
const DZ = Float32Array.from(DOTS, (d) => d.z);
const DU = Float32Array.from(DOTS, (d) => d.u);
const DS = Float32Array.from(DOTS, (d) => d.seed);

/* Dots are drawn in the Hutch palette: the original's light grey disappears
   on the chat's white background. Resting dots are --orange (#f26226); a lit
   dot deepens towards --orange-strong (#c2410c). Precomputed per lit and
   alpha step so frames allocate no strings. */
const A_STEPS = 48, L_STEPS = 12;
const REST = [242, 98, 38], LIT = [194, 65, 12];
const COLORS: string[] = [];
for (let li = 0; li <= L_STEPS; li++) {
  const k = li / L_STEPS;
  const [r, g, b] = REST.map((c, i) => Math.round(lerp(c, LIT[i], k)));
  for (let ai = 0; ai <= A_STEPS; ai++) COLORS.push(`rgba(${r},${g},${b},${(ai / A_STEPS).toFixed(3)})`);
}

type OrbKey = "k" | "alpha" | "spin" | "pop";
type OrbParams = Record<OrbKey, number> & { rot: number; prog: number };

function createOrb(canvas: HTMLCanvasElement, size: number, isReduced: () => boolean) {
  const P: OrbParams = { k: 0, alpha: 0, spin: 0, pop: 1, rot: 0, prog: 0 };
  const ctx = canvas.getContext("2d");
  const lit = new Float32Array(N);
  const SX = new Float32Array(N), SY = new Float32Array(N), SR = new Float32Array(N), SD = new Float32Array(N);
  const SC = new Int16Array(N);
  const pw = [1, 0, 0, 0];
  const radius = size / 2;
  const box = Math.round(size * (220 / 132)); // original canvas-to-orb ratio, room for the glow
  let time = isReduced() ? 1.2 : 0, raf = 0, last = 0, dead = false;

  if (!ctx) return { P, start() {}, paint() {}, destroy() {} };

  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = Math.round(box * dpr);
  canvas.height = Math.round(box * dpr);
  canvas.style.width = `${box}px`;
  canvas.style.height = `${box}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const S = 0.6, CP = Math.cos(0.35), SP = Math.sin(0.35), C0 = box / 2;

  const draw = (dt: number) => {
    ctx.clearRect(0, 0, box, box);
    time += dt;
    P.rot += P.spin * dt;
    const cyw = Math.cos(P.rot), syw = Math.sin(P.rot);

    /* cross-fade between light programs over 0.35 s */
    const stepW = dt / 0.35;
    for (let q = 0; q < 4; q++) {
      const d = (q === P.prog ? 1 : 0) - pw[q];
      pw[q] += Math.abs(d) <= stepW ? d : d > 0 ? stepW : -stepW;
    }
    const decay = Math.exp(-dt / 0.5);
    const h0 = (time * 300) % N, h3 = (time * 480) % N;
    const a1 = time * 0.8, b1 = Math.sin(time * 0.5) * 0.9;
    const f1x = Math.cos(b1) * Math.cos(a1), f1y = Math.sin(b1), f1z = Math.cos(b1) * Math.sin(a1);
    const a2 = time * 0.55 + 2.1, b2 = Math.cos(time * 0.42) * 0.9;
    const f2x = Math.cos(b2) * Math.cos(a2), f2y = Math.sin(b2), f2z = Math.cos(b2) * Math.sin(a2);
    const lat = Math.sin(time * 2.2);

    for (let n = 0; n < N; n++) {
      const dx = DX[n], dy = DY[n], dz = DZ[n], u = DU[n];

      /* light programs: 0 chase, 1 two roaming spots, 2 scanning latitude, 3 fast chase */
      let pulse = 0;
      if (pw[0] > 0.001) {
        let dd = Math.abs(n - h0); if (dd > N - dd) dd = N - dd;
        const v = Math.max(0, 1 - dd / 16);
        pulse = Math.max(pulse, v * v * pw[0]);
      }
      if (pw[1] > 0.001) {
        const v1 = Math.max(0, (dx * f1x + dy * f1y + dz * f1z - 0.72) / 0.28);
        const v2 = Math.max(0, (dx * f2x + dy * f2y + dz * f2z - 0.72) / 0.28);
        const v = Math.max(v1, v2);
        pulse = Math.max(pulse, v * v * pw[1]);
      }
      if (pw[2] > 0.001) {
        const e = dy - lat;
        const v = Math.max(0, 1 - (e * e) / 0.02);
        pulse = Math.max(pulse, v * v * pw[2]);
      }
      if (pw[3] > 0.001) {
        let dd = Math.abs(n - h3); if (dd > N - dd) dd = N - dd;
        const v = Math.max(0, 1 - dd / 22);
        pulse = Math.max(pulse, v * v * pw[3]);
      }
      const l = Math.max(lit[n] * decay, pulse);
      lit[n] = l;

      /* top dots appear first */
      const ki = clamp01(P.k * (1 + S) - S * u);
      SC[n] = -1;
      if (ki <= 0.001) continue;
      const eo = E.out(ki), kk = eo * P.pop;

      const x1 = dx * cyw + dz * syw, z1 = -dx * syw + dz * cyw;
      const y2 = dy * CP - z1 * SP, z2 = dy * SP + z1 * CP;
      const f = 2.8 / (2.8 - z2), depth = (z2 + 1) / 2;

      let a = 0.14 + 0.035 * Math.sin(DS[n] + time * 1.6) + 0.36 * depth * depth + 0.7 * l;
      if (a > 1) a = 1;
      a *= eo * P.alpha;
      const ai = Math.round(a * A_STEPS);
      if (ai <= 0) continue;

      SX[n] = C0 + x1 * radius * kk * f;
      SY[n] = C0 - y2 * radius * kk * f;
      SR[n] = (size / 132) * (1.15 * (0.45 + 0.75 * depth) * f + 0.9 * l) * (0.4 + 0.6 * eo);
      SD[n] = depth;
      SC[n] = Math.round(clamp01(l) * L_STEPS) * (A_STEPS + 1) + ai;
    }

    /* back half first, then the front half over it */
    for (let pass = 0; pass < 2; pass++) {
      for (let n = 0; n < N; n++) {
        if (SC[n] < 0 || (SD[n] >= 0.5) !== (pass === 1)) continue;
        ctx.fillStyle = COLORS[SC[n]];
        ctx.beginPath();
        ctx.arc(SX[n], SY[n], SR[n], 0, TAU);
        ctx.fill();
      }
    }
  };

  const frame = (now: number) => {
    raf = 0;
    if (dead) return;
    const dt = isReduced() ? 0 : Math.max(0, Math.min(0.05, (now - last) / 1000));
    last = now;
    draw(dt);
    if (!isReduced()) raf = requestAnimationFrame(frame);
  };

  return {
    P,
    start() {
      if (raf || dead) return;
      last = performance.now();
      raf = requestAnimationFrame(frame);
    },
    /** One still frame, for reduced motion. */
    paint() { draw(0); },
    destroy() {
      dead = true;
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
    },
  };
}

function play(tracks: Track[], apply: (ch: OrbKey, v: number) => void, sig: AbortSignal) {
  const end = tracks.reduce((m, k) => Math.max(m, k.t1), 0);
  const t0 = performance.now();
  let raf = 0;
  const step = (now: number) => {
    if (sig.aborted) return;
    const t = now - t0;
    for (const k of tracks) {
      if (t < k.t0) continue;
      const p = Math.min(1, (t - k.t0) / Math.max(1, k.t1 - k.t0));
      apply(k.ch, k.from + (k.to - k.from) * k.ease(p));
    }
    if (t < end) raf = requestAnimationFrame(step);
  };
  raf = requestAnimationFrame(step);
  sig.addEventListener("abort", () => cancelAnimationFrame(raf), { once: true });
}

/* ───────────────────────────── component ───────────────────────────── */
const useIsoLayoutEffect = typeof window !== "undefined" ? useLayoutEffect : useEffect;

export interface ThinkingOrbProps {
  /** Labels to show. With `cycle`, they rotate every 1.15 s. */
  labels: string[];
  /** Rotate through `labels` on a timer (open-ended waiting). */
  cycle?: boolean;
  /** Index of the label to show when not cycling; also picks the light program. */
  index?: number;
  /** Orb diameter in px. The original design uses 132. */
  size?: number;
  className?: string;
}

export function ThinkingOrb({ labels, cycle = false, index = 0, size = 72, className }: ThinkingOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const orbRef = useRef<ReturnType<typeof createOrb> | null>(null);
  const [tick, setTick] = useState(0);
  const [lbl, setLbl] = useState<{ cur: number; prev: number | null; n: number }>({ cur: index, prev: null, n: 0 });

  useIsoLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const orb = createOrb(canvas, size, () => reduced);
    orbRef.current = orb;
    const life = new AbortController();
    if (reduced) {
      orb.P.k = 1; orb.P.alpha = 1;
      orb.paint();
    } else {
      play(ASSEMBLE, (ch, v) => { orb.P[ch] = v; }, life.signal);
      orb.start();
    }
    return () => { life.abort(); orb.destroy(); orbRef.current = null; };
  }, [size]);

  /* open-ended waiting: rotate the label and the light program together */
  useEffect(() => {
    if (!cycle || labels.length < 2) return;
    const id = window.setInterval(() => setTick((t) => t + 1), 1150);
    return () => window.clearInterval(id);
  }, [cycle, labels.length]);

  const want = cycle ? tick % Math.max(1, labels.length) : Math.max(0, Math.min(index, labels.length - 1));
  useEffect(() => {
    setLbl((l) => (l.cur === want ? l : { cur: want, prev: l.cur, n: l.n + 1 }));
    if (orbRef.current) orbRef.current.P.prog = want % 4;
  }, [want]);

  const current = labels[lbl.cur] ?? "";
  const label = (text: string) => (
    <>
      <span className="mo-lab-t">{text}</span>
      <span className="mo-dots" aria-hidden="true"><i /><i /><i /></span>
    </>
  );

  return (
    <div className={["mo-wait", className].filter(Boolean).join(" ")}>
      <div className="mo-wait-orb" style={{ width: size, height: size }} aria-hidden="true">
        <span className="mo-wait-glow" />
        <canvas ref={canvasRef} className="mo-wait-canvas" />
      </div>
      <div className="mo-status" aria-hidden="true">
        {lbl.prev !== null && labels[lbl.prev] !== undefined ? (
          <span key={"p" + lbl.n} className="mo-lab mo-out">{label(labels[lbl.prev])}</span>
        ) : null}
        <span key={"c" + lbl.n} className="mo-lab mo-in">{label(current)}</span>
      </div>
      <span className="sr-only" role="status" aria-live="polite">{current}</span>
    </div>
  );
}

export default ThinkingOrb;
