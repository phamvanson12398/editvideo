import {noise2D} from '@remotion/noise';

export const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const easeOut = (t: number) => 1 - Math.pow(1 - clamp(t), 3);
export const easeIn = (t: number) => Math.pow(clamp(t), 3);
export const easeInOut = (t: number) => {
  const x = clamp(t);
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
};
export const backOut = (t: number) => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  const x = clamp(t);
  return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
};

/** 0..1 progress of t through [start, end]. */
export const progress = (t: number, start: number, end: number) =>
  end <= start ? 1 : clamp((t - start) / (end - start));

/** Attack/sustain/release envelope over [start, end] (seconds). */
export const envelope = (t: number, start: number, end: number, attack = 0.12, release = 0.18) => {
  if (t < start || t > end) return 0;
  const a = attack > 0 ? clamp((t - start) / attack) : 1;
  const r = release > 0 ? clamp((end - t) / release) : 1;
  return Math.min(easeOut(a), easeOut(r));
};

/** Triangle peaking at the middle of [start, end]. */
export const peak = (t: number, start: number, end: number) => {
  if (t < start || t > end) return 0;
  const p = (t - start) / (end - start);
  return 1 - Math.abs(p * 2 - 1);
};

export const noise = (seed: string, x: number, y = 0) => noise2D(seed, x, y);

/** Deterministic pseudo random in [0,1) from a number. */
export const rand = (n: number) => {
  const x = Math.sin(n * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
};

export const hexToRgba = (hex: string, a: number) => {
  const h = hex.replace('#', '');
  const v = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
  const r = parseInt(v.slice(0, 2), 16) || 0;
  const g = parseInt(v.slice(2, 4), 16) || 0;
  const b = parseInt(v.slice(4, 6), 16) || 0;
  return `rgba(${r},${g},${b},${a})`;
};
